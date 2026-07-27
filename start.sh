#!/bin/bash
# DevRAG — start all services
# Usage: ./start.sh   (no venv activation needed)

# Resolve project root from the script's own location
ROOT="$(cd "$(dirname "$0")" && pwd)"

# Direct paths into the venv — never touch the parent shell
UVICORN="$ROOT/.venv/bin/uvicorn"
MLFLOW="$ROOT/.venv/bin/mlflow"

# ── Sanity checks ────────────────────────────────────────────────────────────

if [ ! -f "$ROOT/.venv/bin/python" ]; then
    echo "ERROR: venv not found at .venv/"
    echo "    Run: python3.11 -m venv .venv && .venv/bin/pip install -r requirements.txt"
    exit 1
fi

if [ ! -f "$ROOT/.env" ]; then
    echo "ERROR: no .env file found."
    echo "    Run: cp .env.example .env  then add your ANTHROPIC_API_KEY"
    exit 1
fi

# ── Environment ───────────────────────────────────────────────────────────────

# Load .env into this process without polluting the parent shell
while IFS= read -r line || [ -n "$line" ]; do
    [[ "$line" =~ ^#.*$ || -z "$line" ]] && continue
    export "$line"
done < "$ROOT/.env"

export PYTHONPATH="$ROOT:${PYTHONPATH:-}"
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export KMP_DUPLICATE_LIB_OK=TRUE
export TOKENIZERS_PARALLELISM=false
export OPENBLAS_NUM_THREADS=1

# ── Clear ports ───────────────────────────────────────────────────────────────

echo "Clearing ports 8001 and 3000..."
lsof -ti:8001 2>/dev/null | xargs kill -9 2>/dev/null || true
lsof -ti:3000 2>/dev/null | xargs kill -9 2>/dev/null || true
sleep 1

# ── Cleanup handler ───────────────────────────────────────────────────────────

API_PID="" MLFLOW_PID="" FRONTEND_PID=""

cleanup() {
    echo ""
    echo "Stopping DevRAG..."
    [ -n "$API_PID" ]      && kill "$API_PID"      2>/dev/null || true
    [ -n "$MLFLOW_PID" ]   && kill "$MLFLOW_PID"   2>/dev/null || true
    [ -n "$FRONTEND_PID" ] && kill "$FRONTEND_PID" 2>/dev/null || true
    exit 0
}
trap cleanup SIGINT SIGTERM

# ── 1. MLflow (optional) ─────────────────────────────────────────────────────

if [ -f "$MLFLOW" ]; then
    lsof -ti:5000 2>/dev/null | xargs kill -9 2>/dev/null || true
    sleep 0.5
    echo "Starting MLflow on http://localhost:5000 ..."
    mkdir -p "$ROOT/data/mlflow-artifacts"
    "$MLFLOW" server \
        --host 127.0.0.1 \
        --port 5000 \
        --backend-store-uri "sqlite:///$ROOT/data/mlflow.db" \
        --default-artifact-root "$ROOT/data/mlflow-artifacts" \
        >> "$ROOT/data/mlflow.log" 2>&1 &
    MLFLOW_PID=$!
else
    echo "MLflow not in venv — skipping (pip install mlflow to enable)"
fi

# ── 2. FastAPI ────────────────────────────────────────────────────────────────

echo "Starting API on http://localhost:8001 ..."
"$UVICORN" devrag.api.main:app \
    --port 8001 \
    --workers 1 \
    --reload \
    --reload-dir "$ROOT/devrag" \
    --log-level warning &
API_PID=$!

# Wait up to 120s for the API to be healthy: a cold start on Intel Mac
# spends 30-60s just importing torch/langgraph before uvicorn can bind.
echo "    Waiting for API (cold start can take a minute)..."
for i in $(seq 1 120); do
    if curl -s http://localhost:8001/health > /dev/null 2>&1; then
        echo "    API ready"
        break
    fi
    if [ "$i" -eq 120 ]; then
        echo ""
        echo "    ERROR: API did not start in 120s. Check the error above."
        echo "    Quick debug: $UVICORN devrag.api.main:app --port 8001"
        cleanup
    fi
    sleep 1
done

# ── 3. Next.js frontend ───────────────────────────────────────────────────────

echo "Starting frontend on http://localhost:3000 ..."
cd "$ROOT/frontend" && npm run dev > /dev/null 2>&1 &
FRONTEND_PID=$!
cd "$ROOT"

# ── Done ─────────────────────────────────────────────────────────────────────

echo ""
echo "==========================================="
echo "  DevRAG is running"
echo ""
echo "  UI     ->  http://localhost:3000"
echo "  Agent  ->  http://localhost:3000/agent"
echo "  API    ->  http://localhost:8001"
echo "  MLflow ->  http://localhost:5000"
echo ""
echo "  Ctrl+C to stop everything"
echo "==========================================="
echo ""

wait $API_PID $FRONTEND_PID
