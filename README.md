# LoA Worker

An intelligent agent system for automating the processing of Letters of Authority (LoA) responses from financial providers. This README reflects the current, working implementation across the Python backend and the Next.js dashboard.

## Overview

LoA Worker processes inbound communications (emails, Teams messages, transcripts, documents) to:

- Classify messages by relevance and category
- Extract structured client and provider information
- Track case state and field completion
- Trigger automated actions (follow-ups, case updates, completions)
- Maintain a full audit trail of all operations

It follows a modular, testable pipeline with clean separations between channels, LLMs, state, actions, and storage. A basic dashboard (Next.js) provides read-only views of cases and audit logs from Firestore.

## Architecture

### Modular Pipeline

```
Messages → Pre-Filter → Classify (LLM) → Extract (LLM) →
Match Case → Determine Action (LLM) → Execute → Audit
```

### Clean Architecture Layers

```
┌─────────────────────────────────────────┐
│           CLI / UI Layer                │
├─────────────────────────────────────────┤
│         Pipeline Orchestration          │
├─────────────────────────────────────────┤
│  Actions │ State │ LLM │ Channels      │
├─────────────────────────────────────────┤
│      Storage Layer (Firestore)          │
├─────────────────────────────────────────┤
│          Core Models & Types            │
└─────────────────────────────────────────┘
```

### Core Architecture Details

#### 1) Message Ingestion Layer

- Purpose: Abstract different sources (email, Teams, transcripts, documents) behind a unified interface.
- Components:
  - `BaseChannel` (ABC)
  - `DummyChannel` (reads JSON dataset for testing)
  - Future: `EmailChannel`, `TeamsChannel`, `TranscriptChannel`, `DocumentChannel`
- Pattern: Strategy pattern for pluggable sources

#### 2) Processing Pipeline

- Purpose: Transform raw messages into actionable insights.
- Steps (as implemented in `PipelineOrchestrator`):
  1. Pre-filter (fast rejection of spam/marketing)
  2. Classify message (LLM)
  3. Extract entities (LLM)
  4. Match/find existing case
  5. Determine action (LLM)
  6. Execute action (case/task/follow-up)
  7. Log and audit
- Pattern: Pipeline with dependency injection for LLM services

#### 3) LLM Integration Layer

- Purpose: Provide clean abstraction for LLM calls with a mock for testing.
- Components:
  - `LLMService` with default implementations
  - `MockLLMService` (uses dataset expectations; no API calls)
  - `LLMClient` (Google `genai` client for Gemini models)
- Key methods:
  - `classify_message(message) -> Classification`
  - `extract_entities(message, classification) -> ExtractedEntities`
  - `determine_action(message, classification, entities, existing_case) -> Action`
  - `generate_followup_email(case, missing_fields) -> str`
  - `health_check() -> bool`
- Provider: Gemini 2.5 Flash via `google-genai`. To run locally without LLM credentials, set `MOCK_LLM_SERVICE=true`.

#### 4) State Management

- Purpose: Track case progress, field completion, and state transitions.
- Components:
  - `CaseRepository` (Firestore CRUD; async client)
  - `AuditRepository` (immutable audit trail)
  - `CaseStateMachine` (OPEN → IN_PROGRESS → AWAITING_INFO ⟷ IN_PROGRESS → COMPLETE; ↘ CANCELLED)
  - `FieldTracker` (required vs received fields for LoA cases)
- Firestore collections (as used today):
  - `cases/`
  - `cases/{caseId}/tasks/` (sub-collection)
  - `tasks/` (for standalone tasks)
  - `audit_logs/`

#### 5) Action Engine

- Purpose: Execute actions based on pipeline decisions.
- Components:
  - `CaseActionHandler` (CREATE/UPDATE/COMPLETE/CANCEL)
  - `TaskActionHandler` (CREATE/COMPLETE)
  - `FollowupActionHandler` (DRAFT_FOLLOWUP_EMAIL/INITIATE_LOA_CHASE)
  - `ActionRouter` (dispatch)
- Pattern: Command pattern with audit trail

#### 6) Data Models (Pydantic)

Representative models used throughout the system:

```python
class Message: ...
class Case: ...
class Classification: ...
class ExtractedEntities: ...
class Action: ...
class AuditLog: ...
```

### Non-Functional Design Notes

- Reliability:
  - Action handlers aim to be idempotent where practical
  - Typed models and validation
  - Clear error paths (processing failure recorded)
- Auditability:
  - Immutable audit log entries with before/after state
  - LLM decision context captured via structured models
- Scalability:
  - Pre-filtering to reduce LLM calls
  - Batch processing (currently sequential)
- Maintainability:
  - Plugin-style architecture, strict typing, DI
  - Separation of concerns across modules
- Cost Awareness:
  - Pre-filtering and prompt scoping
  - Optional mock LLM for development/testing

## Project Structure

```
loa_worker/
├── src/
│   ├── core/            # Data models, enums, exceptions
│   ├── channels/        # Message ingestion channels
│   ├── pipeline/        # Processing pipeline
│   ├── llm/             # LLM service abstraction and client
│   ├── storage/         # Firestore repositories and client wrapper
│   ├── actions/         # Action handlers and router
│   ├── state/           # State machine and field tracking
│   └── cli/             # Command-line interface
├── dashboard/            # Next.js dashboard (read-only UI)
├── tests/                # Test suite
├── scenario_full_workflows.json  # Sample dataset
└── README.md
```

## Implementation Summary

### Core Data Layer (`src/core/`)

- Pydantic models: Message, Case, Task, FieldValue, Classification, ExtractedEntities, Action, AuditLog, ProcessingResult, BatchProcessingResult
- Enums: SourceType, MessageCategory, ActionType, CaseType, CaseStatus, ProcessingStatus, LLMName
- Custom exception hierarchy

### Channels (`src/channels/`)

- `BaseChannel` (ABC) with async context manager support
- `DummyChannel` reads the bundled JSON dataset

### LLM Integration (`src/llm/`)

- `LLMService` with default implementations calling Gemini (via `google-genai`)
- `MockLLMService` for deterministic testing using dataset expectations
- `MOCK_LLM_SERVICE=true` forces mock behavior

### Storage (`src/storage/`)

- Firestore async client wrapper (`FirestoreClient`)
- `CaseRepository` with case/task CRUD
- `AuditRepository` for immutable logs

### State (`src/state/`)

- `CaseStateMachine` enforces valid transitions and auto-transitions for LoA
- `FieldTracker` tracks completion and surface low-confidence fields

### Actions (`src/actions/`)

- Case, Task, and Follow-up handlers; `ActionRouter` dispatches; audit logging on all

### Pipeline (`src/pipeline/`)

- `PreFilter` (keyword/domain heuristics)
- `PipelineOrchestrator` (7-step flow, async, batch, validation)

### CLI (`src/cli/`)

- Commands: `process`, `cases`, `classify`, `stats`
- Rich output using `rich`

## Key Algorithms

### Field Completion Detection

```python
def is_case_complete(case: Case) -> bool:
    if case.case_type != CaseType.LOA:
        return case.status == CaseStatus.COMPLETE
    required = set(case.required_fields)
    received = set(case.received_fields.keys())
    return required.issubset(received)
```

### Smart Message Pre-Filter (Heuristics)

```python
def should_process_message(message: Message) -> bool:
    # domain allow/deny + keyword scoring
    # default to True if uncertain (let LLM decide)
    ...
```

## Installation

### Prerequisites

- Python 3.10+
- Node.js 18+ (for dashboard)
- Google Cloud Firestore with a service account JSON

### Backend Setup (Python)

1) Clone and enter the repo

```bash
cd loa_worker
```

2) Create and activate a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
```

3) Install dependencies

```bash
pip install -r requirements.txt
```

4) Configure environment variables (required)

```bash
export FIRESTORE_PROJECT_ID=your-project-id
export GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/to/service-account.json
export MOCK_LLM_SERVICE=true  # recommended for local/dev to avoid real LLM calls
```

### Dashboard Setup (Next.js)

1) Install dependencies

```bash
cd dashboard
npm install
```

2) Configure environment variables (server-side)

```bash
export FIRESTORE_PROJECT_ID=your-project-id
export GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/to/service-account.json
```

3) Run the dev server

```bash
npm run dev
```

Open `http://localhost:3000` to view the dashboard.

## Usage (CLI)

Run the CLI via module invocation (no package install required):

### Process Messages

```bash
# Process the full sample dataset (requires Firestore env vars)
python -m src.cli.main process --file scenario_full_workflows.json

# Process a specific day
python -m src.cli.main process --file scenario_full_workflows.json --day 1

# Validate outputs against expected results
python -m src.cli.main process --file scenario_full_workflows.json --validate
```

### Test Classification

```bash
python -m src.cli.main classify "Please open an LoA case for Alice Brown. Capture DOB and plan number."
```

### List Cases / Stats

```bash
python -m src.cli.main cases --status OPEN --type loa --limit 10
python -m src.cli.main stats
```

## Sample Dataset

`scenario_full_workflows.json` contains 21 messages over 3 days:

- Day 1: Alice Brown LoA workflow (creation, missing info, responses, updates, completion)
- Days 2–3: Ben Carter annual review (tasks, completions, progress tracking)

The dataset includes expected values for validation testing used by `MockLLMService`.

## LLM Integration

- Abstract service: `LLMService`
- Default provider: Gemini 2.5 Flash via `google-genai`
- Local/dev: `MOCK_LLM_SERVICE=true` uses `MockLLMService` (no external calls)

## Performance Characteristics (Estimates)

- Pre-filter: <1ms/message; filters 80%+ spam/marketing
- LLM operations: ~1–2s per relevant message total
- Firestore: writes 50–200ms; reads 20–100ms
- Batch processing: sequential (1–2s/msg). Future work: parallel processing

## Cost Considerations (Estimates)

Assuming 100 messages/day, 80% filtered, 20 messages hit LLM, ~2k tokens/message:

- Cost depends on provider/model; pre-filtering reduces spend
- Use the mock service for development/testing to avoid costs

## Security Considerations

- Data protection: Firestore encryption at rest; avoid PII in logs
- Access control: Service account JSON via env; least-privileged accounts
- Dashboard uses Firebase Admin SDK (server-side only)

## Case State Machine

```
OPEN → IN_PROGRESS → AWAITING_INFO ⟷ IN_PROGRESS → COMPLETE
                                    ↘ CANCELLED
```

LoA cases auto-transition to COMPLETE when all required fields are received.

## Known Limitations

- Batch-only (no real-time ingestion yet)
- Sequential processing (no concurrency yet)
- Single-tenant; no auth on dashboard
- Firestore required (no in-memory repository currently)
- LLM defaults to Gemini unless `MOCK_LLM_SERVICE=true`

## Roadmap

### Phase 2: LLM Integration

- Confidence thresholds and prompt tuning
- Human review queue for low-confidence extractions
- Token usage tracking/metrics

### Phase 3: Production Channels

- Email (IMAP) and Teams (Graph API) channels
- Webhook receivers and real-time processing

### Phase 4: Advanced Features

- Template learning and provider knowledge base
- Dashboard enhancements and analytics; auth/multi-tenancy
- Production monitoring and alerting

## How to Extend

### Add a New Channel (e.g., Email)

1) Create `src/channels/email_channel.py`
2) Inherit `BaseChannel`; implement `fetch_messages()`
3) Parse into `Message` with appropriate content type

### Add a New LLM Provider

1) Extend `LLMService` in `src/llm/`
2) Implement: `classify_message`, `extract_entities`, `determine_action`, `generate_followup_email`
3) Wire provider selection in `get_llm_service()`

### Add a New Action Type

1) Add enum to `ActionType`
2) Implement handler and wire in `actions/router.py`
3) Include audit logging

## Testing Strategy

- Unit: isolated components with mocks
- Integration: component interactions with Firestore (or via mocks where added)
- E2E: full workflows via `DummyChannel`

Example tests: `tests/unit/test_case_state.py`, `tests/unit/test_models.py`

## Development

### Run Tests

```bash
pytest
```

### Code Quality

```bash
black src/ tests/
ruff check src/ tests/
mypy src/
```

## Contributing

1) Follow existing patterns and structure
2) Add tests for new functionality
3) Update documentation
4) Run quality checks before committing

## License

[Your License Here]

## Support

For issues and questions:

- Open an issue on GitHub
- Review the sample dataset for expected behavior

---

Built with: Python, Pydantic, Firestore, Click, Rich, Next.js
