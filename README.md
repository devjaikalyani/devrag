# DevRAG

Chat with any codebase, then let the agent fix it.

DevRAG is an agentic AI developer platform that merges two systems into one product:

- A production-grade code understanding engine (from CodeRAG): CodeBERT embeddings + FAISS + BM25 with reciprocal rank fusion, cross-encoder reranking, and NLI faithfulness scoring, with fully isolated per-repo indexes.
- An autonomous coding agent (from DevAgent): a LangGraph pipeline that turns a GitHub issue into a tested pull request — plan, explore, code, test, debug, self-review, PR.

The merge is the point: the hybrid retriever that powers chat is the same index the agent uses to explore a repository. One ingestion serves both surfaces, so the agent reasons over semantically retrieved code instead of grep guesses.

Default LLM is Claude Sonnet 5 (`claude-sonnet-5`) with Claude Haiku 4.5 for cheap steps, adaptive thinking, prompt caching, and structured JSON plans. Groq, Mistral, and Ollama work as drop-in fallbacks — the app runs even without an Anthropic key.

## Architecture

```
                     devrag/ (Python package)
  +------------------------------------------------------+
  |  rag/          shared retrieval engine                |
  |   chunker, loaders, embedder (FAISS+BM25+RRF),        |
  |   reranker, retriever, faithfulness, pipeline         |
  |        ^                          ^                   |
  |        | /query (chat)            | retrieve(query)   |
  |  api/main.py  <------------  agent/ (LangGraph)       |
  |   FastAPI: ingest, query,    plan, explore (RAG),     |
  |   solve, runs, SSE events    code, test, debug,       |
  |        ^                     review, PR               |
  |        |                                              |
  |  frontend/ (Next.js chat UI + Agent Runs page)        |
  |                                                       |
  |  llm/  unified client: Claude Sonnet 5 default,       |
  |        Haiku 4.5 fast path, Groq/Mistral/Ollama       |
  |        fallback; complexity router; cost metering     |
  +------------------------------------------------------+
```

## Quick start

Requirements: Python 3.11, Node 18+, an Anthropic API key (recommended) or a Groq/Mistral key.

```bash
cd DevRAG
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
cd frontend && npm install && cd ..

cp .env.example .env    # add ANTHROPIC_API_KEY (and GITHUB_TOKEN for issue mode)
./start.sh
```

- UI: http://localhost:3000 (chat) and http://localhost:3000/agent (agent runs)
- API: http://localhost:8001 (docs at /docs)
- MLflow: http://localhost:5000

## Usage

### Chat with a codebase

Ingest a repo in the UI (Cmd+K), or via CLI:

```bash
.venv/bin/python cli.py ingest https://github.com/owner/repo
.venv/bin/python cli.py ask "How does authentication work in this project?"
```

Answers cite source files with line ranges and carry a faithfulness score — an NLI model checks the answer is actually entailed by the retrieved code.

### Let the agent fix an issue

```bash
# Full pipeline: fork, clone, index, plan, fix, test, self-review, open PR
.venv/bin/python cli.py solve https://github.com/owner/repo/issues/42

# Plan only, change nothing
.venv/bin/python cli.py solve https://github.com/owner/repo/issues/42 --dry-run

# Fix and test locally but do not open a PR
.venv/bin/python cli.py solve https://github.com/owner/repo/issues/42 --no-pr

# Free-text task against a local repo (never opens a PR)
.venv/bin/python cli.py solve --repo /path/to/repo --task "Fix the divide-by-zero bug in calculator.py"
```

Or from the UI: open the Agent page, paste an issue URL or describe a task, and watch the run live — plan steps, retrieved context, file edits, test output, PR link, and cost per run.

### API

All CodeRAG chat routes are preserved, plus the agent surface:

| Route | Purpose |
|---|---|
| `POST /ingest/github` `/ingest/directory` `/ingest/text` `/ingest/file` | Index a repo or document |
| `POST /query`, `GET /query/stream` | Ask about the active repo (cited, faithfulness-scored) |
| `GET /index/stats`, `POST /repo/switch`, `DELETE /repo/{key}` | Manage per-repo indexes |
| `POST /solve` | Start an agent run (`issue_url` or `repo_path` + `task`, with `dry_run` / `no_pr`) |
| `GET /solve/{run_id}/events` | SSE stream of run progress |
| `GET /runs`, `GET /runs/{id}` | Run history |
| `GET /usage` | Token and cost totals |

## How the agent works

1. Plan — Claude Sonnet 5 produces a structured JSON action plan (schema-enforced output).
2. Explore — zero LLM calls: planner-flagged files are read directly, then hybrid semantic retrieval over the shared index pulls the most relevant chunks; grep is the last resort.
3. Code — a tool loop (`read_file`, `str_replace_in_file`, `search_codebase`) edits source files, never tests.
4. Test — the repo's own test suite runs; failures feed the debugger.
5. Debug — up to `MAX_RETRIES` fix attempts with full failure context.
6. Review — the agent critiques its own diff before shipping.
7. PR — a branch named `devrag/issue-N` and a pull request with a generated description (Haiku 4.5 — cheap step).

Complexity routing sends trivial fixes to Haiku 4.5 and hard ones to Sonnet 5 (or an optional architect model such as Opus 4.8 via `MODEL_ARCHITECT`).

## Configuration

Everything lives in `.env` — see `.env.example` for the full annotated list. The essentials:

| Variable | Meaning |
|---|---|
| `ANTHROPIC_API_KEY` | Primary LLM credentials |
| `MODEL_PRIMARY` / `MODEL_FAST` / `MODEL_ARCHITECT` | Model tiers (defaults: Sonnet 5 / Haiku 4.5 / unset) |
| `GITHUB_TOKEN` | Needed only for issue mode (fork, clone, PR) |
| `LLM_PROVIDER` | `auto` picks the first configured provider; or force `groq` / `mistral` / `ollama` |
| `API_KEY` / `ALLOWED_ORIGINS` | Production hardening |

## Testing

```bash
.venv/bin/pytest tests/ -v          # unit tests
.venv/bin/python scripts/test_single.py   # local end-to-end agent run on a synthetic buggy repo
```

## Roadmap

Built now: retrieval-grounded agent, Claude Sonnet 5 with adaptive thinking and prompt caching, unified chat-and-act product, faithfulness-scored answers, per-run cost metering, live SSE run timeline.

Planned, in priority order:

1. GitHub App mode — comment `@devrag fix` on any issue to trigger a run; webhook triage. This is the distribution channel that matters most.
2. MCP server — expose ingest/search/solve as MCP tools so Claude Code, Cursor, and any MCP client can use DevRAG as their code-understanding backend.
3. Incremental indexing — file-hash watch mode so indexes stay warm on every commit instead of full re-ingestion.
4. Tree-sitter chunking — true AST-aware chunk boundaries for all supported languages, replacing regex heuristics.
5. Sandboxed test execution — Docker-per-run isolation for safe execution of untrusted repos.
6. Repo memory — persist per-repo learnings (past fixes, conventions, failed approaches) and inject them into planner context.
7. SWE-bench CI gate — nightly evaluation run publishing a public scoreboard; the credibility engine.
8. VS Code extension and hosted SaaS free tier — the reach multipliers once the core is proven.

## Project layout

```
DevRAG/
  cli.py               Typer CLI: ingest | ask | solve | serve | usage
  start.sh             boots MLflow + API (8001) + frontend (3000)
  devrag/
    config.py          unified settings (env-driven)
    llm/               Claude-native client, complexity router, cost tracking
    rag/               retrieval engine: chunker, embedder, retriever, pipeline
    agent/             LangGraph nodes: planner, explorer, coder, tester,
                       debugger, reviewer, pr_opener, graph, runner
    tools/             filesystem, github, testing, rag_search
    api/main.py        unified FastAPI
  frontend/            Next.js 16 UI: chat + agent runs
  scripts/             test_single.py, evaluation scripts
  tests/               merged unit test suites
```

## Origins

DevRAG merges two standalone projects (both left intact in sibling directories):

- `coderag/` — the retrieval engine and chat UI
- `DevAgent/` — the autonomous agent pipeline

The originals remain runnable; DevRAG is where development continues.
