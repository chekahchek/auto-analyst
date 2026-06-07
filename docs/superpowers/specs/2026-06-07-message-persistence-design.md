# Message Persistence & Conversation Sequencing Design

## Context

Auto-Analyst uses LangGraph for multi-agent orchestration. A single user request can involve 20+ LLM calls across phases (profiling, planning, code execution, hypothesis generation, web search, critic, refinement). The database needs to store the conversation history so users can review past sessions, while LangGraph's built-in checkpointer handles crash recovery.

This design defines:
1. How messages are ordered in the database
2. When and how messages are persisted during graph execution

---

## Data Model

### Changes to `message` table

| Field | Type | Purpose |
|---|---|---|
| `sequence` | `int` | Monotonically increasing per session. Assigned at write time by the persistence layer. Query: `ORDER BY sequence`. |
| `metadata_json` | `Optional[str]` | Optional JSON blob for context like `{"phase": "profiling", "tool": "execute_python"}`. |
| `created_at` | `datetime` | Secondary sort / audit trail. |

`sequence` starts at 1 per session and increments by 1. No gaps expected under normal operation.

The existing `role` enum covers message types:
- `USER` — human input
- `ASSISTANT` — final response or status summary
- `SYSTEM` — injected prompts
- `TOOL` — tool results (only persisted if they represent a major phase outcome)

---

## Persistence Interface

### `MessageStore`

A service class that buffers messages in memory and flushes them to the database in batches.

```python
class MessageStore:
    def __init__(self, db: AsyncSession):
        self.db = db
        self._pending: list[Message] = []

    def queue(self, role: MessageRole, content: str, metadata: dict | None = None) -> None:
        """Buffer a message for later batch write."""
        ...

    async def add_message(
        self,
        session_id: UUID,
        role: MessageRole,
        content: str,
        metadata: dict | None = None,
    ) -> Message:
        """Write a single message immediately."""
        ...

    async def flush(self, session_id: UUID) -> list[Message]:
        """Write all buffered messages in one atomic transaction."""
        ...
```

**Design principles:**
- Any LangGraph node can call `queue()` or `add_message()` when it has something worth recording.
- Sequence numbering is centralized — nodes never assign `sequence` themselves.
- The service handles advisory locking, batching, and transaction boundaries internally.

---

## Sequence Numbering & Concurrency

`flush()` assigns sequences atomically:

1. Acquire a Postgres advisory lock keyed by `session_id`
2. Query `MAX(sequence)` for the session
3. Assign `sequence = max + 1, max + 2, ...` to pending messages in order
4. Insert all messages in one transaction
5. Release lock on transaction commit

**Why an advisory lock?** LangGraph graphs may run parallel branches. Without locking, two branches could read the same `MAX(sequence)` and both insert `sequence=5`.

---

## Integration with LangGraph

### Lifecycle

```
API Request arrives
    ↓
FastAPI creates AsyncSession (get_db)
    ↓
Create MessageStore(db_session)
    ↓
Pass store into LangGraph graph (via config or state)
    ↓
Graph runs → nodes call store.queue() or store.flush()
    ↓
Graph finishes → final flush() if anything left in buffer
    ↓
FastAPI commits the outer session
    ↓
Response sent
```

### Flush Points

- End of each major subgraph/phase
- Immediately for user input (already in DB from API layer)
- Immediately for the final response
- Immediately for error halt messages

### What Gets Written

| Category | Persistence | Example |
|---|---|---|
| User input | Immediate | User's question |
| Phase status | Buffered, flushed at phase end | "Profiling complete — 5 columns found" |
| Final response | Immediate | The final analysis |
| Error halt | Immediate | "Analysis stopped: [error]" |
| Internal tool calls | Not written | `execute_python`, `read_skill` results |
| LLM reasoning chains | Not written | Internal planning steps |

---

## Error Handling

| Scenario | Behavior |
|---|---|
| Node queues messages, graph errors before flush | Queued messages lost in memory. Acceptable — they were status updates for a failed run. |
| `flush()` hits a DB error | Entire batch rolls back atomically. No partial writes. |
| Graph succeeds but final flush forgotten | Messages sit in buffer. Mitigation: always call `flush()` at graph END. |

---

## Testing

| Test | Coverage |
|---|---|
| `test_sequence_monotonic` | Insert 3 messages, assert `sequence == [1, 2, 3]` |
| `test_concurrent_writes` | Two coroutines add messages to same session simultaneously, assert no duplicate sequences |
| `test_batch_flush_atomic` | Queue 3 messages, make DB fail on insert, assert none written |
| `test_store_queues_dont_write` | Call `queue()` 5 times, assert DB is empty before `flush()` |

---

## Out of Scope

- Specific LangGraph node definitions (will be designed per graph phase)
- Exact trigger mapping (nodes call `MessageStore` when they see fit)
- Frontend rendering of status messages
