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

- [x] **2.4** Implement CSV file storage utility  
  Save to `./data/datasets/{dataset_id}/input.csv`; validate file type and size; reject malformed CSV early.

- [x] **2.5** Write unit tests for models and storage utility.

---


## Phase 3: Skill Authoring

*Goal: Write the skills the main loop consumes. They live in `skills/` and are discoverable by the existing `list_available_skills` / `read_skill_instructions` tools.*

- [x] **4.1** Author analytical skills per data type  
  `analytical/time-series/SKILL.md`, `analytical/tabular-eda/SKILL.md`, `analytical/free-text/SKILL.md`, plus `panel`, `event-log`, `cohort` if needed.

- [x] **4.2** Author `core/storytelling-dashboard/SKILL.md`  
  Narrative restructuring conventions: how to order hypotheses and evidence into a coherent story.

- [x] **4.3** Author `core/frontend-design/SKILL.md`  
  HTML/Plotly layout conventions, theming, responsive rules, accessibility defaults.

- [ ] **4.4** Author `core/critic-rubric/SKILL.md`  
  Scoring criteria (0–1), feedback format, and what constitutes a revision vs. an approval.

- [x] **4.5** Create system prompt for core 

- [x] **4.6** Tests: skill files parse correctly, frontmatter is valid YAML, no broken links.

---

## Phase 4: State Schema & Graph Foundation

*Goal: Shared state design and checkpointing strategy before any loop node is built.*

- [ ] **3.1** Define the `AnalystState` TypedDict for the main analysis graph  
  `dataset_id`, `session_id`, `profile`, `skills_loaded`, `hypotheses_evidence`, `narrative`, `dashboard_html`, `critic_score`, `critic_feedback`, `iteration_count`, `error`.

- [ ] **3.2** Define Postgres checkpointing strategy  
  Which state fields get persisted at which node transitions; schema for `checkpoints` table or use of LangGraph's built-in Postgres saver.

---

## Phase 5: Main Agentic Loop

*Goal: The core analysis graph wired end-to-end. The agent self-loads skills per node via the existing tools (profiler pattern).*

- [ ] **5.1** Implement `analyst` node  
  - Create system prompt for analytical nodes to generate relevant plotly charts, plotly chart manifest, output format as a JSON object
  - Agent self-loads analytical skill, generates hypotheses, and repeatedly produces Python code (via `execute_python_script` tool) to test each hypothesis. Collects evidence (dataframes / Plotly figures) into `hypotheses_evidence`. Retry on code error (max 2 per script). Skip persistent failures and note in dashboard. Agent decides when it has enough hypotheses; no hardcoded count.
  - Create conditional transition from analyst to storyteller when hypotheses are generated

- [ ] **5.2** Implement `storyteller` node  
  Loads `core/storytelling-dashboard` skill; restructures `hypotheses_evidence` into a `narrative` stored in state.

- [ ] **5.3** Implement `frontend_designer` node  
  Loads `core/frontend-design` skill; renders `narrative` + figures into Jinja2 HTML. Stores `dashboard_html` in state. Save to `./data/sessions/{session_id}/dashboard.html`.

- [ ] **5.4** Implement `critic` node  
  Loads `core/critic-rubric` skill; reviews `dashboard_html`; returns `score` (0–1) and `feedback`.

- [ ] **5.5** Wire iterative builder subgraph  
  `storyteller → frontend_designer → critic`. Conditional edges:  
  - `score < threshold` → loop back to `storyteller` (or `frontend_designer` if feedback is purely visual).  
  - Max 3 iterations; abort if score delta stalls (< 0.05 between iterations).

- [ ] **5.6** Wire full graph  
  `analyst → [storyteller → frontend_designer → critic loop] → END`.

- [ ] **5.7** Add error handling and retry logic  
  LLM exponential backoff (max 3 retries per node); graph panic → session `error` + log traceback.

- [ ] **5.8** Implement checkpointing in key nodes  
  Persist state after `analyst` and after each critic iteration.

- [ ] **5.9** Write unit tests for each node in isolation (mocked LLM / filesystem).

---

## Phase 6: API Endpoints

*Goal: Expose the graph via REST API.*

- [ ] **6.1** `POST /datasets` — Upload CSV  
  Save file, create dataset record (`status=uploaded`), trigger profiler graph node asynchronously (background task or graph invoke), return `dataset_id`.

- [ ] **6.2** `GET /datasets` — List user's datasets  
  Return list with profile metadata; filter by current user (auth placeholder if no auth yet).

- [ ] **6.3** `POST /datasets/{id}/sessions` — Create session  
  Validate dataset is `profiled`; create session (`status=processing`); kick off full analysis graph asynchronously; return `session_id`.

- [ ] **6.4** `GET /sessions/{id}` — Get session status  
  Return status + `dashboard_html` content if `status=ready`.

- [ ] **6.5** `POST /sessions/{id}/chat` — Follow-up question  
  Append user message to `Turn` table; re-run relevant graph nodes (e.g., analyzer + builder) with conversation context; return updated dashboard.

- [ ] **6.6** Add global exception handlers (malformed CSV → 400, graph panic → 500 with reference ID).

- [ ] **6.7** Write integration tests for all endpoints with mocked LLM.

---

## Phase 7: Observability & Cost Controls

*Goal: Know what's happening and don't overspend.*

- [ ] **7.1** Add OpenTelemetry instrumentation  
  Spans across FastAPI request → LangGraph node → LLM call.

- [ ] **7.2** Add Prometheus metrics endpoint (`/metrics`)  
  Counters: sessions started, dashboards delivered, errors by type. Histograms: tokens per session, cost per session, graph execution time.

- [ ] **7.3** Implement per-session cost accumulator  
  Sum LLM call costs into `Session.cost_spent`. Hard-stop if configurable max budget exceeded (default $1.00).

- [ ] **7.4** Add healthcheck endpoint (`/health`) and readiness probe logic.

---

## Phase 8: Testing & Quality

*Goal: Confidence in the system before iterating.*

- [ ] **8.1** Unit tests — skill file parsing, HTML rendering, each graph node mocked.

- [ ] **8.2** Integration tests — full graph end-to-end with frozen CSV fixtures + cached LLM responses. Assert expected HTML sections present.

- [ ] **8.3** Eval / regression tests under `tests/eval/`  
  Frozen CSVs + expected dashboard attributes. Run on PRs.

- [ ] **8.4** Mock LLM client by default; real calls gated by env var (`ENABLE_LIVE_LLM=1`).

- [ ] **8.5** CI workflow (GitHub Actions) — lint, test, eval.

---

## Phase 9: Memory Model *(Future)*

*Goal: Capture domain context not yet in skills.*

- [ ] **9.1** Define `Memory` SQLModel / SQLAlchemy model  
  Fields: `id`, `domain`, `content`, `created_at`, `status` (active/inactive).

- [ ] **9.2** Add memory capture node to graph  
  Runs after analysis to extract reusable insights.

- [ ] **9.3** Add memory retrieval — load active memories for matching domain into context.

- [ ] **9.4** API endpoints for memory CRUD (admin / internal use).

---

## Phase 10: Self-Improvement Loop *(Future)*

*Goal: Promote memories to versioned skills automatically.*

- [ ] **10.1** Design AutoDreamAgent script / service  
  Clusters domain memories, scores, consolidates into skill markdown.

- [ ] **10.2** Implement MR creation workflow  
  Open MR to skill registry repo with `source_memory_ids` listed.

- [ ] **10.3** Eval CI for skill MRs  
  Run frozen CSV benchmark on MR diff, post delta as comment.

- [ ] **10.4** Post-merge job  
  Archive promoted memory IDs (`status=archived`); bump skill version.

- [ ] **10.5** Rollback mechanism — git revert + restore memories.

- [ ] **10.6** Schedule trigger (local cron or EventBridge later).

---

## Phase 11: AWS Deployment *(Future)*

*Goal: Production-grade hosted infrastructure.*

- [ ] **11.1** Containerise FastAPI app with Dockerfile.

- [ ] **11.2** Terraform / CDK stack — VPC, subnets, security groups.

- [ ] **11.3** App Runner — host FastAPI container.

- [ ] **11.4** Aurora Serverless v2 (Postgres) — replace local Postgres.

- [ ] **11.5** S3 buckets  
  CSV storage (presigned POST uploads); skills storage (synced from skills repo).

- [ ] **11.6** Lambda (container image) — sandboxed code execution for `analyzer` node.

- [ ] **11.7** ECS Fargate + EventBridge — weekly cron for AutoDreamAgent.

- [ ] **11.8** SSM Parameter Store — secrets (API keys, DB creds, GitHub token).

- [ ] **11.9** CloudWatch / X-Ray — centralised logging and tracing.

- [ ] **11.10** GitHub Actions — CI/CD pipeline for skill registry sync + cache invalidation.

---

## Open Questions to Resolve

- [ ] Should intermediate artifacts (dataframes, generated code, plotly figures) be persisted to disk for analytical follow-ups? For MVP: transient. Revisit post-MVP.
- [ ] Auth strategy — API key, OAuth, or defer to AWS deployment (Phase 11)?
- [ ] Code sandbox for MVP — local subprocess with restrictions, or Docker-in-Docker?
