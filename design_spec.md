# Auto-Analyst – Design Specification

A self-improving agentic system for data analysis. The user uploads a CSV, an agent profiles it, loads the right analytical and domain skills, forms hypotheses, gathers evidence, and produces a storytelling dashboard. A critic agent gates the output. Domain knowledge accumulates via memories and is periodically promoted into versioned skills.


## Objectives

* **End-to-end analysis:** CSV → hypotheses → evidence → storytelling dashboard.
* **Self-improving:** domain knowledge from past sessions loads into future ones.
* **Reviewable:** promoted knowledge is auditable, versioned, rollback-able.


## API Contract

| Endpoint | Method | Description |
|---|---|---|
| `/datasets` | `POST` | Upload CSV. Creates dataset, runs profiler. Returns `dataset_id`. |
| `/datasets` | `GET` | List user's datasets with profile metadata. |
| `/datasets/{id}/sessions` | `POST` | Create a chat session for a dataset. Returns `session_id`; analysis starts asynchronously. |
| `/sessions/{id}` | `GET` | Get session status + latest dashboard HTML if ready. |
| `/sessions/{id}/chat` | `POST` | Follow-up question. Appends to conversation, re-runs relevant graph nodes. |


### Runtime Flow

```mermaid
sequenceDiagram
    actor U as User
    participant A as AnalystAgent
    participant P as Profiler

    U->>A: Upload CSV
    A->>P: Profile dataset
    Note over P: Infer domain and data type
    P->>P: Self-load core/profile-data skill

    A->>A: analyst
    Note over A: Self-load analytical skill, generate hypotheses, execute Python (sandbox) to test each, collect evidence. Agent decides when done.

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

    users {
        uuid id PK
        string email
        timestamp created_at
    }

    datasets {
        uuid id PK
        uuid user_id FK
        string filename
        string original_filename
        string storage_path
        string domain
        string data_type
        jsonb profile_json
        timestamp created_at
        timestamp updated_at
    }

    sessions {
        uuid id PK
        uuid dataset_id FK
        string dashboard_path
        decimal cost_spent
        timestamp created_at
        timestamp updated_at
    }

    messages {
        uuid id PK
        uuid session_id FK
        enum role "user | assistant | system | tool"
        text content
        timestamp created_at
    }
```


## Observability & Cost Controls

- **Structured logging:** `structlog` JSON. Every node logs entry/exit with timing. Every LLM call logs model, tokens, cost.
- **Cost tracking:** Per-session spend accumulator. Hard-stop if max budget exceeded (configurable, default $1.00).
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
- Should intermediate artifacts (dataframes, generated code, plotly figures) be persisted to disk to enable analytical follow-ups (e.g. "show me the raw data behind chart 3")? For MVP they are treated as transient agent working memory. Revisit post-MVP.