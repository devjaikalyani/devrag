"""
main.py — DevRAG unified FastAPI backend.

Two surfaces, one index:
  - Chat/RAG routes (ported from CodeRAG unchanged, so the frontend works as-is):
    /health, /index/stats, /repo/switch, /ingest/*, /query, /query/stream,
    /history, /index
  - Agent routes (new):
    POST /solve                  start an autonomous run (issue URL or local task)
    GET  /solve/{run_id}/events  SSE stream of run progress
    GET  /runs                   run history
    GET  /runs/{run_id}          single run detail
    GET  /usage                  LLM token/cost totals for this process
  - Billing routes (Razorpay, domestic INR + international USD):
    GET  /billing/plans          pricing catalog
    GET  /billing/status         current tier, expiry, remaining free quota
    POST /billing/order          create a Razorpay order for checkout
    POST /billing/verify         verify checkout signature, activate Pro
    POST /billing/webhook        Razorpay server-to-server confirmation

Free-tier limits return HTTP 402 with an upgrade hint.
"""

import json
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from devrag.config import get_available_providers, settings
from devrag.rag.service import get_pipeline
from devrag.llm.client import usage as llm_usage
from devrag.agent import runner
from devrag.billing import entitlements, plans as billing_plans, razorpay_client
from devrag.billing.entitlements import EntitlementError
from devrag.billing.razorpay_client import RazorpayNotConfigured

app = FastAPI(title="DevRAG API", version="1.0.0")

_origins = (
    [o.strip() for o in settings.allowed_origins.split(",")]
    if settings.allowed_origins != "*" else ["*"]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API key auth — set API_KEY in .env to enable; leave blank for local dev.
# The Razorpay webhook is called by Razorpay's servers and authenticates
# itself with its own HMAC signature, so it must bypass the API key.
_PUBLIC_PATHS = {"/health", "/docs", "/openapi.json", "/redoc", "/billing/webhook"}


@app.middleware("http")
async def api_key_middleware(request: Request, call_next):
    if settings.api_key and request.url.path not in _PUBLIC_PATHS:
        if request.headers.get("X-API-Key") != settings.api_key:
            return JSONResponse({"detail": "Invalid or missing API key"}, status_code=401)
    return await call_next(request)


# ── Models ────────────────────────────────────────────────────────────────

class IngestGitHubRequest(BaseModel):
    url: str
    branch: str = "main"

class IngestDirectoryRequest(BaseModel):
    path: str

class IngestTextRequest(BaseModel):
    text: str
    source_name: str = "inline"

class SwitchRepoRequest(BaseModel):
    key: str

class QueryRequest(BaseModel):
    question: str
    check_faithfulness: bool = True

class QueryResponse(BaseModel):
    question: str
    answer: str
    sources: List[dict]
    faithfulness_score: Optional[float]
    is_faithful: Optional[bool]
    active_repo: Optional[str]

class SolveRequest(BaseModel):
    issue_url: Optional[str] = None   # GitHub issue URL (issue mode)
    repo_path: Optional[str] = None   # local repo path (task mode)
    task: Optional[str] = None        # free-text task (task mode)
    dry_run: bool = False             # plan only, no code changes
    no_pr: bool = False               # fix and test but do not open a PR

class CreateOrderRequest(BaseModel):
    package: str                      # pro_monthly | pro_yearly
    currency: str = "INR"             # INR (domestic) | USD (international)

class VerifyPaymentRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str
    package: str
    currency: str = "INR"


# ── Chat / RAG routes (CodeRAG surface) ───────────────────────────────────

@app.get("/health")
def health():
    p = get_pipeline()
    return {
        "status": "ok",
        "service": "devrag",
        "active_key": p.active_key,
        "total_chunks": p.faiss_index.index.ntotal if p.faiss_index else 0,
        "llm_providers": get_available_providers(),
        "model_primary": settings.model_primary,
    }


@app.get("/index/stats")
def index_stats():
    p = get_pipeline()
    return {
        "total_chunks": p.faiss_index.index.ntotal if p.faiss_index else 0,
        "index_loaded": p.faiss_index is not None,
        "active_key": p.active_key,
        "ingested_sources": p.get_ingested_sources(),
    }


@app.post("/repo/switch")
def switch_repo(req: SwitchRepoRequest):
    p = get_pipeline()
    result = p.switch_repo(req.key)
    if result["status"] == "error":
        raise HTTPException(status_code=404, detail=result["reason"])
    return result


@app.delete("/repo/{key}")
def delete_repo(key: str):
    get_pipeline().delete_repo(key)
    return {"status": "ok", "message": f"Deleted repo '{key}'"}


def _enforce_repo_limit(new_key: str):
    p = get_pipeline()
    sources = p.get_ingested_sources()
    is_new = new_key not in {s.get("key") for s in sources}
    try:
        entitlements.check_repo_allowed(len(sources), is_new)
    except EntitlementError as e:
        raise HTTPException(status_code=402, detail=str(e))


@app.post("/ingest/github")
def ingest_github(req: IngestGitHubRequest):
    from devrag.rag.pipeline import _safe_key
    _enforce_repo_limit(_safe_key(f"{req.url}@{req.branch}"))
    try:
        return get_pipeline().ingest_github(req.url, branch=req.branch)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ingest/directory")
def ingest_directory(req: IngestDirectoryRequest):
    if not Path(req.path).exists():
        raise HTTPException(status_code=404, detail=f"Path not found: {req.path}")
    from devrag.rag.pipeline import _safe_key
    _enforce_repo_limit(_safe_key(f"local::{req.path}"))
    return get_pipeline().ingest_directory(req.path)


@app.post("/ingest/text")
def ingest_text(req: IngestTextRequest):
    return get_pipeline().ingest_text(req.text, source_name=req.source_name)


@app.post("/ingest/file")
async def ingest_file(file: UploadFile = File(...)):
    content = await file.read()
    text = content.decode("utf-8", errors="ignore")
    return get_pipeline().ingest_text(text, source_name=file.filename or "upload")


@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest):
    p = get_pipeline()
    if p.retriever is None:
        raise HTTPException(status_code=400, detail="No repo selected. Ingest or switch to a repo first.")
    try:
        entitlements.check_query_allowed()
    except EntitlementError as e:
        raise HTTPException(status_code=402, detail=str(e))
    response = p.query(req.question, check_faithfulness=req.check_faithfulness)
    return QueryResponse(
        question=response.query,
        answer=response.answer,
        sources=[{
            "source": r.chunk.source,
            "start_line": r.chunk.start_line,
            "end_line": r.chunk.end_line,
            "language": r.chunk.language,
            "rerank_score": round(r.rerank_score, 4),
            "text_preview": r.chunk.text[:200],
        } for r in response.sources],
        faithfulness_score=response.faithfulness.score if response.faithfulness else None,
        is_faithful=response.faithfulness.is_faithful if response.faithfulness else None,
        active_repo=p.active_key,
    )


@app.get("/query/stream")
def query_stream(question: str):
    p = get_pipeline()
    if p.retriever is None:
        raise HTTPException(status_code=400, detail="No repo selected.")
    try:
        entitlements.check_query_allowed()
    except EntitlementError as e:
        raise HTTPException(status_code=402, detail=str(e))

    def token_generator():
        try:
            for token in p.stream_query(question):
                yield f"data: {token}\n\n"
        except Exception as e:
            yield f"data: Error: {str(e)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(token_generator(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache"})


@app.delete("/history")
def clear_history():
    get_pipeline().clear_history()
    return {"status": "ok"}


@app.delete("/index")
def clear_all():
    get_pipeline().clear_all()
    return {"status": "ok", "message": "All indexes cleared"}


# ── Agent routes ──────────────────────────────────────────────────────────

@app.post("/solve")
def solve(req: SolveRequest):
    """Start an autonomous agent run. Returns run_id immediately;
    follow progress on /solve/{run_id}/events."""
    issue_mode_with_pr = bool(req.issue_url) and not (req.dry_run or req.no_pr)
    try:
        entitlements.check_agent_run_allowed(issue_mode_with_pr=issue_mode_with_pr)
    except EntitlementError as e:
        raise HTTPException(status_code=402, detail=str(e))

    if req.issue_url:
        run = runner.start_issue_run(req.issue_url, dry_run=req.dry_run, no_pr=req.no_pr)
    elif req.repo_path and req.task:
        if not Path(req.repo_path).exists():
            raise HTTPException(status_code=404, detail=f"Path not found: {req.repo_path}")
        run = runner.start_task_run(req.repo_path, req.task, dry_run=req.dry_run)
    else:
        raise HTTPException(
            status_code=422,
            detail="Provide either issue_url, or repo_path plus task.",
        )
    return {"run_id": run.id, "status": run.status, "mode": run.mode}


@app.get("/solve/{run_id}/events")
def solve_events(run_id: str):
    """SSE stream of run events: status, node transitions, tests, PR, cost."""
    if runner.get_run(run_id) is None:
        raise HTTPException(status_code=404, detail=f"Unknown run: {run_id}")

    def event_generator():
        for event in runner.iter_events(run_id):
            yield f"data: {json.dumps(event, default=str)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache"})


@app.get("/runs")
def runs():
    return {"runs": runner.list_runs()}


@app.get("/runs/{run_id}")
def run_detail(run_id: str):
    run = runner.get_run(run_id)
    if run is not None:
        return {**run.to_summary(), "events": run.events}
    record = runner.RUNS_DIR / f"{run_id}.json"
    if record.exists():
        return json.loads(record.read_text())
    raise HTTPException(status_code=404, detail=f"Unknown run: {run_id}")


@app.get("/usage")
def usage_stats():
    return llm_usage.stats()


# ── Billing routes (Razorpay) ─────────────────────────────────────────────

@app.get("/billing/plans")
def billing_plans_catalog():
    return billing_plans.get_plans()


@app.get("/billing/status")
def billing_status():
    return entitlements.status()


@app.post("/billing/order")
def billing_create_order(req: CreateOrderRequest):
    """Create a Razorpay order. INR for domestic, USD for international."""
    try:
        return razorpay_client.create_order(req.package, req.currency.upper())
    except RazorpayNotConfigured as e:
        raise HTTPException(status_code=503, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Razorpay order creation failed: {e}")


@app.post("/billing/verify")
def billing_verify(req: VerifyPaymentRequest):
    """Verify the checkout signature and activate Pro."""
    if req.package not in billing_plans.PACKAGES:
        raise HTTPException(status_code=422, detail=f"Unknown package: {req.package}")
    try:
        valid = razorpay_client.verify_payment_signature(
            req.razorpay_order_id, req.razorpay_payment_id, req.razorpay_signature
        )
    except RazorpayNotConfigured as e:
        raise HTTPException(status_code=503, detail=str(e))
    if not valid:
        raise HTTPException(status_code=400, detail="Payment signature verification failed.")

    record = entitlements.activate_pro(
        req.package, req.razorpay_payment_id, req.razorpay_order_id, req.currency.upper()
    )
    return {"status": "ok", "tier": record["tier"], "expires_at": record["expires_at"]}


@app.post("/billing/webhook")
async def billing_webhook(request: Request):
    """Razorpay server-to-server confirmation (source of truth when hosted).

    Configure the webhook in the Razorpay dashboard for the event
    payment.captured, pointing at https://<your-host>/billing/webhook.
    """
    raw = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")
    try:
        if not razorpay_client.verify_webhook_signature(raw, signature):
            raise HTTPException(status_code=400, detail="Invalid webhook signature.")
    except RazorpayNotConfigured as e:
        raise HTTPException(status_code=503, detail=str(e))

    payload = json.loads(raw)
    event = payload.get("event", "")
    if event == "payment.captured":
        entity = payload["payload"]["payment"]["entity"]
        order_id = entity.get("order_id", "")
        payment_id = entity.get("id", "")
        currency = entity.get("currency", "INR")
        package = (entity.get("notes") or {}).get("package") or \
            razorpay_client.fetch_order_package(order_id) or "pro_monthly"
        entitlements.activate_pro(package, payment_id, order_id, currency)
    return {"status": "ok", "event": event}
