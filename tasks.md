# Auto-Analyst — Backend Task Breakdown

## Phase 1: Project Scaffolding

*Goal: A running FastAPI app with Postgres, logging, and test harness.*

- [x] **1.1** Initialise FastAPI project structure under `backend/`  

- [x] **1.2** Add core dependencies to `pyproject.toml`  

- [x] **1.3** Set up `docker-compose.yml` with Postgres service  

- [x] **1.4** Add `config.py` with Pydantic Settings  
  DB URL, LLM API keys, cost budget default, file storage path, environment.

- [x] **1.5** Add pre-commit hooks (ruff, mypy) if not already present.

---

## Phase 2: Data Layer

*Goal: ORM models, migrations, and file storage for datasets.*

- [x] **2.1** Define SQLModel / SQLAlchemy model  
  Fields: `id`, `filename`, `status` (uploaded/profiled/error), `domain`, `data_type`, `profile_json`, `file_path`, `created_at`.

- [x] **2.2** Set up Alembic for migrations  
  Initialise, generate first migration, add to `docker-compose` startup or document run command.

- [x] **2.3** Implement async DB session dependency (`get_db`) using SQLAlchemy async session.

- [ ] **2.4** Implement CSV file storage utility  
  Save to `./data/datasets/{dataset_id}/input.csv`; validate file type and size; reject malformed CSV early.

- [ ] **2.5** Write unit tests for models and storage utility.

---

## Phase 3: LangGraph Nodes (MVP Runtime)

*Goal: The core analysis graph, node by node.*

- [ ] **3.1** Define the `State` TypedDict for the graph  
  `dataset_id`, `session_id`, `profile`, `skills_loaded`, `hypotheses`, `evidence`, `dashboard_html`, `critic_score`, `critic_feedback`, `iteration_count`, `error`.

- [ ] **3.2** Implement `profiler` node  
  Read CSV head + summary stats via Pandas; infer `domain` and `data_type`; update dataset record.

- [ ] **3.3** Implement `skill_loader` node  
  Match dataset profile against skill triggers; load relevant `.md` files into state.

- [ ] **3.4** Implement `hypothesis_generator` node  
  LLM call to produce 3–5 testable hypotheses given profile + skills. Log tokens/cost.

- [ ] **3.5** Implement `analyzer` node  
  For each hypothesis, LLM generates Python code; execute in sandboxed subprocess (or local restricted env for MVP). Capture dataframes / Plotly figures. Retry on code error (max 2). Skip on persistent failure and note in dashboard.

- [ ] **3.6** Implement `dashboard_builder` node  
  Compile narrative + figures into Jinja2 HTML template. Save to `./data/sessions/{session_id}/dashboard.html`.

- [ ] **3.7** Implement `critic` node  
  LLM reviews dashboard quality; returns `score` (0–1) and `feedback`. If score < threshold, loop back to builder with feedback. Max 3 iterations; abort if score delta stalls.

- [ ] **3.8** Wire nodes into LangGraph with conditional edges (profiler → skill_loader → hypothesis_generator → analyzer → dashboard_builder → critic → [builder|deliver]).

- [ ] **3.9** Add error handling and retry logic per design spec  
  LLM exponential backoff (max 3 retries); graph panic → session `error` + log traceback.

- [ ] **3.10** Implement checkpointing with postgres in key nodes

- [ ] **3.11** Write unit tests for each node in isolation (mocked LLM / filesystem).

---

## Phase 4: API Endpoints

*Goal: Expose the graph via REST API.*

- [ ] **4.1** `POST /datasets` — Upload CSV  
  Save file, create dataset record (`status=uploaded`), trigger profiler graph node asynchronously (background task or graph invoke), return `dataset_id`.

- [ ] **4.2** `GET /datasets` — List user's datasets  
  Return list with profile metadata; filter by current user (auth placeholder if no auth yet).

- [ ] **4.3** `POST /datasets/{id}/sessions` — Create session  
  Validate dataset is `profiled`; create session (`status=processing`); kick off full analysis graph asynchronously; return `session_id`.

- [ ] **4.4** `GET /sessions/{id}` — Get session status  
  Return status + `dashboard_html` content if `status=ready`.

- [ ] **4.5** `POST /sessions/{id}/chat` — Follow-up question  
  Append user message to `Turn` table; re-run relevant graph nodes (e.g., analyzer + builder) with conversation context; return updated dashboard.

- [ ] **4.6** Add global exception handlers (malformed CSV → 400, graph panic → 500 with reference ID).

- [ ] **4.7** Write integration tests for all endpoints with mocked LLM.

---

## Phase 5: Observability & Cost Controls

*Goal: Know what's happening and don't overspend.*

- [ ] **5.1** Add OpenTelemetry instrumentation  
  Spans across FastAPI request → LangGraph node → LLM call.

- [ ] **5.2** Add Prometheus metrics endpoint (`/metrics`)  
  Counters: sessions started, dashboards delivered, errors by type. Histograms: tokens per session, cost per session, graph execution time.

- [ ] **5.3** Implement per-session cost accumulator  
  Sum LLM call costs into `Session.cost_spent`. Hard-stop if configurable max budget exceeded (default $1.00).

- [ ] **5.4** Add healthcheck endpoint (`/health`) and readiness probe logic.

---

## Phase 6: Testing & Quality

*Goal: Confidence in the system before iterating.*

- [ ] **6.1** Unit tests — skill registry parsing, HTML rendering, each graph node mocked.

- [ ] **6.2** Integration tests — full graph end-to-end with frozen CSV fixtures + cached LLM responses. Assert expected HTML sections present.

- [ ] **6.3** Eval / regression tests under `tests/eval/`  
  Frozen CSVs + expected dashboard attributes. Run on PRs.

- [ ] **6.4** Mock LLM client by default; real calls gated by env var (`ENABLE_LIVE_LLM=1`).

- [ ] **6.5** CI workflow (GitHub Actions) — lint, test, eval.

---

## Phase 7: Skill Registry Integration

*Goal: Load skills dynamically into the graph.*

- [ ] **7.1** Define skill file schema (YAML frontmatter + markdown body) with `triggers` field.

- [ ] **7.2** Implement skill registry loader  
  Scan `skills/` directory; parse triggers; match against dataset profile; return relevant skill contents.

- [ ] **7.3** Add basic skill files per design spec  
  `core/profile-data.md`, `core/capture-memories.md`, `core/web-search.md`, `analytical/time-series.md`, `analytical/tabular-eda.md`, `analytical/free-text.md`, `analytical/storytelling-dashboard.md`, `domain-knowledge/finance.md`, `domain-knowledge/ops.md`, `domain-knowledge/growth.md`.

- [ ] **7.4** Tests for skill matching logic.

---

## Phase 8: Memory Model *(Future)*

*Goal: Capture domain context not yet in skills.*

- [ ] **8.1** Define `Memory` SQLModel / SQLAlchemy model  
  Fields: `id`, `domain`, `content`, `created_at`, `status` (active/inactive).

- [ ] **8.2** Add memory capture node to graph  
  Runs after analysis to extract reusable insights.

- [ ] **8.3** Add memory retrieval — load active memories for matching domain into context.

- [ ] **8.4** API endpoints for memory CRUD (admin / internal use).

---

## Phase 9: Self-Improvement Loop *(Future)*

*Goal: Promote memories to versioned skills automatically.*

- [ ] **9.1** Design AutoDreamAgent script / service  
  Clusters domain memories, scores, consolidates into skill markdown.

- [ ] **9.2** Implement MR creation workflow  
  Open MR to skill registry repo with `source_memory_ids` listed.

- [ ] **9.3** Eval CI for skill MRs  
  Run frozen CSV benchmark on MR diff, post delta as comment.

- [ ] **9.4** Post-merge job  
  Archive promoted memory IDs (`status=archived`); bump skill version.

- [ ] **9.5** Rollback mechanism — git revert + restore memories.

- [ ] **9.6** Schedule trigger (local cron or EventBridge later).

---

## Phase 10: AWS Deployment *(Future)*

*Goal: Production-grade hosted infrastructure.*

- [ ] **10.1** Containerise FastAPI app with Dockerfile.

- [ ] **10.2** Terraform / CDK stack — VPC, subnets, security groups.

- [ ] **10.3** App Runner — host FastAPI container.

- [ ] **10.4** Aurora Serverless v2 (Postgres) — replace local Postgres.

- [ ] **10.5** S3 buckets  
  CSV storage (presigned POST uploads); skills storage (synced from skills repo).

- [ ] **10.6** Lambda (container image) — sandboxed code execution for `analyzer` node.

- [ ] **10.7** ECS Fargate + EventBridge — weekly cron for AutoDreamAgent.

- [ ] **10.8** SSM Parameter Store — secrets (API keys, DB creds, GitHub token).

- [ ] **10.9** CloudWatch / X-Ray — centralised logging and tracing.

- [ ] **10.10** GitHub Actions — CI/CD pipeline for skill registry sync + cache invalidation.

---

## Open Questions to Resolve

- [ ] Should intermediate artifacts (dataframes, generated code, plotly figures) be persisted to disk for analytical follow-ups? For MVP: transient. Revisit post-MVP.
- [ ] Auth strategy — API key, OAuth, or defer to Phase 10?
- [ ] Code sandbox for MVP — local subprocess with restrictions, or Docker-in-Docker?
