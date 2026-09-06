# Auto-Analyst – Design Specification

A self-improving agentic system for data analysis. The user uploads a CSV, an agent profiles it, loads the right analytical and domain skills, forms hypotheses, gathers evidence, and produces a storytelling dashboard. A critic agent gates the output. Domain knowledge accumulates via memories and is periodically promoted into versioned skills.


## Objectives

* **End-to-end analysis:** CSV → hypotheses → evidence → storytelling dashboard.
* **Self-improving:** domain knowledge from past sessions loads into future ones.
* **Reviewable:** promoted knowledge is auditable, versioned, rollback-able.


## API Contract

| Endpoint | Method | Description |
|---|---|---|
| `/datasets` | `POST` | Upload CSV. Creates dataset and a session, runs profiler. Returns `dataset_id` and `session_id`. |
| `/datasets` | `GET` | List user's datasets with profile metadata. |
| `/datasets/{id}/sessions` | `POST` | Create a session manually if one does not exist. |
| `/sessions/{id}` | `GET` | Get session metadata + latest dashboard HTML if available. |
| `/sessions/{id}/chat` | `POST` | Send a message (first or follow-up). Hydrates state, invokes analysis graph, returns response and dashboard if generated. |


## Runtime Flow

```mermaid
sequenceDiagram
    actor U as User
    participant A as AnalystAgent
    participant P as Profiler

    U->>A: Upload CSV
    A->>P: Profile dataset
    Note over P: Infer data type
    P->>P: Self-load core/profile-data skill

    A->>A: analyst
    Note over A: Discover/load analytical skill via tools, generate hypotheses, execute Python (sandbox) to test each, collect evidence. Agent decides whether to answer conversationally or run analysis.

    loop builder iteration (max 3)
        A->>A: storyteller (Pre-loaded storytelling skill)
        A->>A: frontend_designer (Pre-loaded frontend-design skill)
        A->>A: critic (Pre-loaded critic-rubric skill)
        alt score < threshold
            A->>A: Revise narrative or design
        end
    end

    A-->>U: Deliver dashboard
```

## Conversation State

**Within a run**, `messages` holds the full working context: every tool call and tool result. This scratchpad is discarded when the run ends.

**Across runs**, only the clean transcript is kept: the user message and the final assistant message of each turn. Two rows per turn, content only — no tool calls. Tool-call traces live in logs, not the `message` table.

**Every run ends with a clean assistant message:**
- Conversational path: the analyst's direct reply.
- Analysis path: a response node composes a summary after the build loop.
- Budget exhaustion: a node appends a "budget reached" message instead of stopping mid-tool-call.

**Artifacts are separate rows, not messages.** Each analysis-producing turn writes one `artifact` row keyed by `session_id + iteration`, holding `hypotheses_evidence_json`, `narrative_json` (do not include the full plotly graphs, only the pointer referencing it), and `dashboard_path`. On follow-up hydration:
- The transcript (`message` rows) is injected as `user`/`assistant` messages.
  - All artifact iterations are injected as a single system block (light metadata only — no `figure`), so the LLM can reference any prior iteration.
- The latest dashboard HTML is read on demand via a tool from its `dashboard_path`.

**The dashboard is latest-only.** A single `dashboard.html` per session, overwritten on render or edit; `dashboard_path` always points at the current render and is not versioned by `iteration` (which versions the analysis only).

### Plotly Figures
One hard rule: **large data (Plotly `figure` JSON) never goes into an LLM prompt.** An LLM cannot copy a big blob back out verbatim — it emits placeholders like `{"fig_placeholder": true}` instead. So figures live on disk as files, moved by code; the LLM only ever handles words and small references.

| Tier | What it holds 
|---|---
| `figures/<i>.json` (session-scoped) | one Plotly figure per chart, stable identity by index 
| state (in-memory) | `hypotheses_evidence`, `narrative` — holds the pointer to each figure, not the JSON 
| DB `artifact` | `hypotheses_evidence_json`, `narrative_json`, `dashboard_path` — pointer only, no figure JSON 
| LLM prompt | insight text + chart titles/descriptions + `dashboard_path` 


The full figure JSON never lives in state — state only holds a pointer (the file path) to each figure. This is how the plotly figures are processed:

1. Analyst node generates the plotly figures and saves them to disk as `figures/<i>.json` in `sessions/<id>/` directory
2. Analyst submits `hypotheses_evidence` where each chart's `figure` is a pointer (file path) to the figure, not the JSON

3. In the storyteller node, the pointer is removed prior to the LLM call, since the storyteller only needs the title/description to organise the story. The code in the storyteller node then builds the `narrative` with the pointer kept alongside each chart
4. In the frontend designer node, the pointer is stripped away before the LLM call. The LLM writes HTML with `__PLOTLY_FIGURE_<i>__` as a placement placeholder. The code in the frontend designer node replaces each placeholder with a declarative reference to the saved figure filename; it does not load or inline the figure JSON.
5. `dashboard_html` is stored to disk holding lightweight references to the figures. Before returning a dashboard to the browser, the backend materializes those references into inline Plotly data; that delivery representation is not persisted as a second dashboard copy.


For follow-up conversation:

1. `read_dashboard` and `read_figure(index)` are provided to the analyst node so that it can read the artifacts that are stored in disk at `sessions/<id>/` path
2. If user wants to edit the dashboard/figures, `execute_python_script` tool is used to update the figure and `update_dashboard_html` is used to update the HTML and store them to disk. These tools are directly accessible in the analyst node without needing to generate the hypotheses again.
### First-time Conversation Flow

1. User uploads CSV.
2. Backend creates a dataset and a session, then triggers the profiler in the background.
3. Backend returns `dataset_id` and `session_id` to the user.
4. User sends the first message (set to be a default message in the frontend), e.g. `"Generate insights"`.
5. Backend queries the DB and enriches the graph state before execution:
    - `messages`: `["Generate insights"]`
    - `profile`: `{data_type}`
    - `dataset_path`
    - `figures_dir`
    - no artifact rows yet (first iteration)
6. Backend hydrates the complete `AnalystState` and invokes LangGraph
7. Analyst node:
   - Discovers and loads the relevant analytical skill via `read_skill_instructions`.
   - Calls `execute_python_script` to run Python on the dataset.
   - Produces `hypotheses_evidence`.
   - Conditional edge to continue to Storyteller Node
8. Storyteller Node:
   - Storyteller loads the storytelling skill and condenses `hypotheses_evidence` into `narrative`.
   - Conditional edge to continue to Frontend Design Node
9. Frontend Design Node:
   - Frontend designer loads the frontend skill and generates `dashboard_html`
   - Conditional edge to continue to Critic node with the full context
10. Critic Node: scores the dashboard; if below threshold, the loop revises narrative or design (max 3 iterations).
11. Response node composes the chat-facing assistant message (summary of findings) and appends it to `messages`.
12. After graph processing completes successfully, the backend persists to the DB in one transaction:
    - The initial message
    - One `artifact` row: `iteration=1`, `hypotheses_evidence_json`, `narrative_json`, `dashboard_path`
13. Backend materializes the reference-based dashboard and returns the response with inline Plotly data to the user.

### Follow-up Conversation Flow

1. User sends a follow-up message, e.g. `"Why did churn spike in Q2?"`.
2. Backend loads from the DB:
   - Clean transcript (user + final assistant messages of past turns)
   - `profile`, `dataset_path`
   - All artifact iterations (`hypotheses_evidence_json` + `narrative_json` per row) injected as a system prompt, light metadata only (insights + chart titles/descriptions — no `figure`)
3. Backend hydrates the `AnalystState` (see Conversation State) and invokes LangGraph.
4. Analyst node decides whether to answer from the existing context, edit the dashboard, or run new analysis.
5. **Conversation path** (no new analysis needed):
   - The analyst node appends the answer directly to `messages`.
   - The graph returns the final state.
6. **Dashboard edit path** (no new analysis, dashboard changes):
   - `read_dashboard` returns the HTML with references to the figure files; the analyst edits text/structure and submits via `update_dashboard_html`.
   - Figure edits use `read_figure(index)` + `execute_python_script` to rewrite `figures/<i>.json` in place — the HTML already references the file, so nothing is re-rendered.
7. **New analysis path**:
   - The analyst node loads the relevant skill via `read_skill_instructions`.
   - It calls `execute_python_script` to run new Python code.
   - It produces new `hypotheses_evidence`, stored as a new artifact iteration.
   - Storyteller, frontend designer, and critic loop regenerate the narrative and dashboard.
   - Response node composes the assistant message.
8. After graph processing completes successfully, the backend persists the turn's two message rows. A new artifact row (`iteration` incremented) is written only for the new-analysis path; a dashboard edit overwrites the existing reference-based render in place.
9. Backend materializes the reference-based dashboard and returns the response with inline Plotly data (if a dashboard was generated or updated) to the user.


## Skill Registry

Skills are stored in a separate repository for more flexible access control, allowing users to submit MR without affecting the core agent capabilities.

Three types of skills:

| Scope | Purpose |
| --- | --- |
| `core/*` | Core skills powering the agent to perform profiling, storytelling, frontend design, critic rubric, web search, memory capture etc. |
| `analytical/*` | Guide on analysing different types of data e.g. time series, text, tabular, etc. |
| `domain-knowledge/*` | Domain knowledge for understanding dataset, nuances in the data, etc.|

```
skills/
  core/
    profile-data/SKILL.md
    storytelling-dashboard/SKILL.md
    frontend-design/SKILL.md
    critic-rubric/SKILL.md
    web-search/SKILL.md
    capture-memories/SKILL.md
  analytical/
    time-series/SKILL.md
    tabular-eda/SKILL.md
    free-text/SKILL.md
    panel/SKILL.md
    event-log/SKILL.md
    cohort/SKILL.md
  domain-knowledge/
    finance/SKILL.md
    ops/SKILL.md
    growth/SKILL.md
    hr/SKILL.md
```

## Database Model

```mermaid
erDiagram
    users ||--o{ datasets : "owns"
    datasets ||--o{ sessions : "has"
    sessions ||--o{ messages : "contains"
    sessions ||--o{ artifacts : "produces"

    users {
        uuid id PK
        string email
        timestamp created_at
    }

    datasets {
        uuid id PK
        uuid user_id FK
        string original_filename
        string storage_path
        string data_type
        timestamp created_at
    }

    sessions {
        uuid id PK
        uuid dataset_id FK
        timestamp created_at
        timestamp updated_at
    }

    messages {
        uuid id PK
        uuid session_id FK
        int sequence
        enum role "user | assistant | system | tool"
        text content
        timestamp created_at
    }

    artifacts {
        uuid id PK
        uuid session_id FK
        int iteration
        json hypotheses_evidence_json
        json narrative_json
        string dashboard_path
        timestamp created_at
    }
```


## Observability & Cost Controls

- **Structured logging:** `structlog` JSON. Every node logs entry/exit with timing. Every LLM call logs model, tokens, cost.
- **Cost tracking:** Per-session spend accumulator in application memory (injected via graph state). Hard-stop if max budget exceeded (configurable, default $1.00). No `cost_spent` DB column — cumulative cost lives in logs/OTel.
- **Tracing:** OpenTelemetry spans across FastAPI → LangGraph → LLM calls.
- **Metrics:** Prometheus counters for sessions, deliveries, errors by type, avg tokens/cost per session.

## Testing Strategy

| Layer | Approach |
|---|---|
| **Unit** | pytest. Skill file parsing, HTML rendering, graph nodes in isolation (mocked LLM). |
| **Integration** | Full graph end-to-end with frozen CSV fixtures + cached LLM responses. Assert expected HTML sections. |
| **Eval / Regression** | `tests/eval/` with frozen CSVs and expected dashboard attributes. Run on PRs. |
| **Cost guard** | Mock LLM client by default. Real calls only in eval, gated by env var. |



## Memory Model *(Future — not in MVP)*

Memories are domain-specific context not yet captured in skills. They are periodically promoted to skills via the self-improvement loop.

```yaml
id: mem_01HXYZ...
domain: finance
content: "..."
created_at: timestamp
status: active | inactive
```


## Self-Improvement Loop *(Future — not in MVP)*

```mermaid
flowchart LR
    M[(Memory Store)] --> AD[AutoDreamAgent]
    AD -->|cluster + score + consolidate| MR[Open MR to skill registry]
    MR --> EV["Eval CI - frozen CSV benchmark"]
    EV --> HR(Human review)
    HR -->|merge| PM[Post-merge job]
    PM -->|status=archived| M
    PM -->|version bump| SR[[Skill Registry]]
    SR -. regression .-> REV[git revert]
```

1. **Scheduled job:** AutoDreamAgent clusters domain memories → opens MR listing `source_memory_ids`.
2. **Eval CI:** runs frozen benchmark on MR diff, posts delta.
3. **Post-merge job:** archives promoted memory IDs.

Rollback = git revert. Archived memories stay archived.


## AWS Architecture *(Future — not in MVP)*

**Main app**

```mermaid
flowchart LR
    Browser -->|presigned POST| S3_CSV[(S3 · CSV Storage)]
    Browser -->|API requests| AppRunner[App Runner]
    AppRunner -->|sessions / turns / memories| RDS[(Aurora Serverless v2\nPostgres)]
    AppRunner -->|load & cache skills| S3_Skills[(S3 · Skills)]
    AppRunner -->|invoke| Lambda[Lambda\nCode Sandbox]
    Lambda -->|read CSV\nwrite artifacts| S3_CSV
    SSM{{SSM Parameter Store}} -.->|secrets| AppRunner
```

**Self-improvement loop**

```mermaid
flowchart LR
    EventBridge([EventBridge\nweekly cron]) -->|trigger| ECS[ECS Fargate\nAutoDreamAgent]
    RDS[(Aurora Serverless v2\nPostgres)] -->|read memories| ECS
    ECS -->|archive promoted memories| RDS
    ECS -->|open MR| GitHub[GitHub\nSkills Repo]
    GitHub -->|CI passes + merge| Actions[GitHub Actions]
    Actions -->|sync skills| S3_Skills[(S3 · Skills)]
    Actions -->|invalidate cache| AppRunner[App Runner\nFastAPI]
    SSM{{SSM Parameter Store}} -.->|secrets| ECS
```

- **App Runner** — hosts the FastAPI backend as a container
- **S3** — two purposes:
  - *CSV storage:* browser uploads directly via presigned POST
  - *Skills storage:* skill markdown files synced from the skills repo via GitHub Actions on merge. Backend caches skills in memory with a short TTL; a post-merge webhook hits `/admin/invalidate-skills-cache` to force refresh. No redeployment needed on skill updates.
- **Aurora Serverless v2 (Postgres)** — Store datasets (metadata + profile), sessions, conversation turns, memories. Use to re-create prompt during follow-up questions.
- **Lambda (container image)** — sandboxed code execution
- **EventBridge Scheduler** — weekly cron that triggers the AutoDreamAgent as a one-off ECS Fargate task. Reads memories from RDS, clusters them, opens a GitHub MR to the skills repo.
- **SSM Parameter Store** — stores Anthropic API key, DB credentials, GitHub token. Free tier; no need for Secrets Manager at this scale.

## Open questions
- Plotly figures are persisted as files under a session-scoped `figures/` dir and referenced by the dashboard HTML, but stay out of the LLM — see *Plotly Figures*. Dataframes and generated code remain transient working memory; a follow-up like "show me the raw data behind chart 3" needs those persisted, which is still open for post-MVP.
