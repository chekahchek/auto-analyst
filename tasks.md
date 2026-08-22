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
  Fields: `id`, `user_id`, `original_filename`, `storage_path`, `domain`, `data_type`, `created_at`.

- [x] **2.2** Set up Alembic for migrations  
  Initialise, generate first migration, add to `docker-compose` startup or document run command.

- [x] **2.3** Implement async DB session dependency (`get_db`) using SQLAlchemy async session.

- [x] **2.4** Implement CSV file storage utility  
  Save to `./data/datasets/{dataset_id}/input.csv`; validate file type and size; reject malformed CSV early.

- [x] **2.5** Write unit tests for models and storage utility.

- [x] **2.6** Define `Session` model  
  Fields: `id`, `dataset_id` (FK), `created_at`, `updated_at`.

- [x] **2.7** Define `Message` model (append-only conversation history)  
  Fields: `id`, `session_id` (FK, indexed), `sequence`, `role` (user/assistant/system/tool), `content`, `created_at`.

- [ ] **2.8** Index `Message` for ordered history retrieval  
  Replace the standalone `Message.sequence` index with a composite `(session_id, sequence)` index. Generate Alembic migration.

- [x] **2.9** Define `Artifact` model (per-iteration analysis outputs)  
  Fields: `id`, `session_id` (FK, indexed), `iteration`, `hypotheses_evidence_json`, `narrative_json`, `dashboard_path`, `created_at`. One row per analysis-producing turn; columns are nullable since an iteration may not produce all three. Follow-ups hydrate the full set of iterations into a system message.

---


## Phase 3: Skill Authoring

*Goal: Write the skills the main loop consumes. They live in `skills/` and are discoverable by the existing `list_available_skills` / `read_skill_instructions` tools.*

- [x] **3.1** Author analytical skills per data type  
  `analytical/time-series/SKILL.md`, `analytical/tabular-eda/SKILL.md`, `analytical/free-text/SKILL.md`, plus `panel`, `event-log`, `cohort` if needed.

- [x] **3.2** Author `core/storytelling-dashboard/SKILL.md`  
  Narrative restructuring conventions: how to order hypotheses and evidence into a coherent story.

- [x] **3.3** Author `core/frontend-design/SKILL.md`  
  HTML/Plotly layout conventions, theming, responsive rules, accessibility defaults.

- [x] **3.4** Author `core/profile-data/SKILL.md`  
  CSV profiling conventions: infer domain, data type, and column semantics.

- [ ] **3.5** Author `core/critic-rubric/SKILL.md`  
  Scoring criteria (0–1), feedback format, and what constitutes a revision vs. an approval.

- [x] **3.6** Create system prompt for core 

- [x] **3.7** Tests: skill files parse correctly, frontmatter is valid YAML, no broken links.

---

## Phase 4: State Schema

*Goal: Shared state design before any loop node is built. Checkpointing strategy is decided later (5.9), once the nodes exist.*

- [ ] **4.1** Define the `AnalystState` TypedDict for the main analysis graph  
  `session_id`, `dataset_id`, `dataset_path`, `messages` (with `add_messages` reducer), `profile` (domain + data_type), `hypotheses_evidence`, `narrative`, `dashboard_path`, `dashboard_html`, `critic_score`, `critic_feedback`, `iteration_count`.

---

## Phase 5: Main Agentic Loop

*Goal: The core analysis graph wired end-to-end. The agent self-loads skills per node via the existing tools (profiler pattern).*

- [x] **5.1** Implement `profiler` node  
  Self-loads `core/profile-data` skill; infers `domain` + `data_type`; result persisted on the Dataset row. Lives under `app/agents/profiler/`; invoked as a background task from `POST /datasets`.

- [ ] **5.2** Implement `analyst` node  
  - Agent with tools: `list_available_skills`, `read_skill_instructions(skill_path)`, `execute_python_script(code)`, `read_dashboard_html()` (loads the current dashboard on demand from `dashboard_path`). It discovers and loads the relevant analytical skill, decides whether to run Python, or answers conversationally from existing `messages`.
  - Agent outputs structured JSON: `{"message": "....", "hypotheses_evidence": [...]}` where hypotheses_evidence is generated for first-time message or subsequent follow-up analysis.
  - If `hypotheses_evidence` is set, route to `storyteller`
  - Retry code errors (max 2 per script). Skip persistent failures and note in dashboard.
  - On `max_llm_calls` exhaustion, route to a node that appends a graceful "budget reached" message. Every run must end with a clean, content-only assistant message (see design_spec.md § Conversation State).

- [ ] **5.3** Implement `storyteller` node  
  Loads `core/storytelling-dashboard` skill; restructures `hypotheses_evidence` into a `narrative` stored in state.

- [ ] **5.4** Implement `frontend_designer` node  
  Loads `core/frontend-design` skill; renders `narrative` + figures into Jinja2 HTML. Stores `dashboard_html` in state. Save to `./data/sessions/{session_id}/dashboard.html`.

- [ ] **5.5** Implement `critic` node  
  Loads `core/critic-rubric` skill; reviews `dashboard_html`; returns `score` (0–1) and `feedback`.

- [ ] **5.6** Wire iterative builder subgraph  
  `storyteller → frontend_designer → critic`. Conditional edges:  
  - `score < threshold` → loop back to `storyteller` (or `frontend_designer` if feedback is purely visual).  
  - Max 3 iterations; abort if score delta stalls (< 0.05 between iterations).

- [ ] **5.7** Wire full graph  
  `analyst` → conditional on `hypotheses_evidence` present → either `[storyteller → frontend_designer → critic loop] → response → persist` or `persist` → END. `response` composes the chat-facing assistant message (summary of findings); `persist` writes the turn's two message rows (user + final assistant, content only) plus updated artifacts.

- [ ] **5.8** Add error handling and retry logic  
  LLM exponential backoff (max 3 retries per node); graph panic → log traceback and return 500 with reference ID.

- [ ] **5.9** Define Postgres checkpointing strategy
  Use LangGraph's built-in `PostgresSaver`. Use a fresh `thread_id` per chat message (e.g., `f"{session_id}:{message_id}"`). The checkpointer stores the internal graph state during a single run (ReAct tool-call loops, critic iterations). The application DB (`message` table + `session` columns) remains the source of truth across messages. Do not use the checkpointer as a user-facing conversation store.

- [ ] **5.10** Implement checkpointing in key nodes  
  Configure the analyst ReAct agent and the main graph to use `PostgresSaver`. Checkpoint after `analyst` node completion and after each critic iteration.

- [ ] **5.11** Write unit tests for each node in isolation (mocked LLM / filesystem).

---

## Phase 6: API Endpoints

*Goal: Expose the graph via REST API.*

- [ ] **6.1** `POST /datasets` — Upload CSV  
  Save file, create dataset record, create a session for the dataset, trigger profiler graph node asynchronously, return `dataset_id` and `session_id`.

- [ ] **6.2** `GET /datasets` — List user's datasets  
  Return list with profile metadata; filter by current user (auth placeholder if no auth yet).

- [ ] **6.3** `POST /datasets/{id}/sessions` — Create session *(manual fallback)*  
  Create a session only if the dataset does not have one already. The analysis graph is invoked by the first chat message (6.5), not here.

- [ ] **6.4** `GET /sessions/{id}` — Get session  
  Return session metadata + `dashboard_html` content if the latest artifact has a `dashboard_path` set.

- [ ] **6.5** `POST /sessions/{id}/chat` — Send message (first or follow-up)  
  Append user message to `message` table; hydrate graph state with ordered history, dataset path, profile, and all artifact iterations (system block); invoke analysis graph; persist a new message pair and any new artifact row; return response and dashboard if generated.

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
  Accumulate LLM call costs in graph state (in-memory per session). Hard-stop if configurable max budget exceeded (default $1.00). No DB column; cumulative cost is derived from logs/OTel.

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
- [ ] Long chat sessions: truncate or summarise `conversation_history` before LLM calls? For MVP: pass full history.
