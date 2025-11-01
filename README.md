# LoA Worker

An intelligent agent system for automating the processing of Letters of Authority (LoA) responses from financial providers. This single README consolidates all design, implementation, and usage documentation.

## Overview

LoA Worker processes inbound communications (emails, Teams messages, transcripts, documents) to:

- Classify messages by relevance and category
- Extract structured client and provider information
- Track case state and field completion
- Trigger automated actions (follow-ups, case updates, completions)
- Maintain a full audit trail of all operations

The system follows a modular, testable pipeline with clean separations between channels, LLMs, state, actions, and storage.

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
│    Storage Layer (Firestore/Mock)       │
├─────────────────────────────────────────┤
│          Core Models & Types            │
└─────────────────────────────────────────┘
```

### Core Architecture Details

#### 1) Message Ingestion Layer

- Purpose: Abstract different sources (email, Teams, transcripts, documents) behind a unified interface.
- Components:
  - `BaseChannel` (ABC)
  - `DummyChannel` (JSON dataset for testing)
  - Future: `EmailChannel`, `TeamsChannel`, `TranscriptChannel`, `DocumentChannel`
- Pattern: Strategy pattern for pluggable sources

#### 2) Processing Pipeline

- Purpose: Transform raw messages into actionable insights using LLM-powered analysis.
- Flow: Raw Message → Normalize → Classify → Extract Entities → Route Action → Execute
- Components:
  - `MessageNormalizer`
  - `MessageClassifier` [LLM]
  - `EntityExtractor` [LLM]
  - `IntentDetector` [LLM]
  - `PipelineOrchestrator`
- Pattern: Pipeline with dependency injection for LLM services

#### 3) LLM Integration Layer

- Purpose: Provide clean abstraction for LLM calls with mockability for testing.
- Components:
  - `LLMService` (ABC)
  - Prompt templates (Jinja2)
  - Response parsing (structured JSON → Pydantic)
  - `MockLLMService` (for testing)
- Key methods:
  - `classify_message(message) -> Classification`
  - `extract_entities(message) -> ExtractedEntities`
  - `determine_action(message, context) -> Action`
- Design principle: All LLM calls return structured data (Pydantic), never raw strings

#### 4) State Management

- Purpose: Track case progress, field completion, and state transitions.
- Components:
  - `CaseRepository` (Firestore CRUD)
  - `CaseStateMachine` (OPEN → IN_PROGRESS → AWAITING_INFO ⟷ IN_PROGRESS → COMPLETE; ↘ CANCELLED)
  - `FieldTracker` (required vs received fields for LoA cases)
  - `AuditRepository` (immutable log of changes)
- Firestore collections: `cases/`, `case_fields/` (sub-collection), `audit_logs/`, `messages/`

#### 5) Action Engine

- Purpose: Execute actions based on pipeline decisions.
- Components:
  - `ActionHandler` (ABC)
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

### Non-Functional Design Decisions

- Reliability:
  - Idempotent actions
  - Firestore transactions for atomic updates
  - Error handling tiers (retryable, parsing, critical)
- Auditability:
  - Immutable audit log
  - Message traceability
  - LLM decision logging; microsecond timestamps
- Scalability:
  - Pre-filtering, async I/O, batch processing
  - Caching (context, provider templates)
  - Stateless horizontal scaling
- Maintainability:
  - Plugin architecture, strict typing, DI
  - Config-driven (no hardcoded values)
  - Unit/integration/E2E tests; docstrings
- Cost Awareness:
  - Smart pre-filtering and prompt optimization
  - Model selection and response caching
  - Monitoring of token usage

## Project Structure

```
loa_worker/
├── src/
│   ├── core/           # Data models, enums, exceptions
│   ├── channels/       # Message ingestion channels
│   ├── pipeline/       # Processing pipeline
│   ├── llm/            # LLM service abstraction
│   ├── storage/        # Firestore repositories
│   ├── actions/        # Action handlers
│   ├── state/          # State machine and field tracking
│   └── cli/            # Command-line interface
├── tests/              # Test suite
├── scenario_full_workflows.json  # Sample dataset
└── README.md
```

## Implementation Summary (Phase 1 Complete)

### Core Data Layer (`src/core/`)

- 11 Pydantic models (Message, Case, Task, FieldValue, Classification, ExtractedEntities, Action, AuditLog, ProcessingResult, BatchProcessingResult)
- 6 enums (SourceType, MessageCategory, ActionType, CaseType, CaseStatus, ProcessingStatus)
- Custom exception hierarchy
- Full type hints and validation; useful model helpers

### Channel Abstraction (`src/channels/`)

- `BaseChannel` (ABC) with async context manager support
- `DummyChannel` reads JSON dataset

### LLM Integration (`src/llm/`)

- `LLMService` (ABC) with 5 core methods: classify, extract, determine action, generate follow-up email, health check
- `MockLLMService` that uses expected metadata for end-to-end testing (no API calls)

### Storage Layer (`src/storage/`)

- Firestore async client wrapper
- `CaseRepository` with rich case/task CRUD (transactions supported)
- `AuditRepository` for immutable logs
- Mock repositories (in-memory) with identical interface

### State Management (`src/state/`)

- `CaseStateMachine` enforces valid transitions, auto-transition logic, terminal detection
- `FieldTracker` tracks completion and progress, surfaces low-confidence fields

### Action Handlers (`src/actions/`)

- 8 action types across case, task, and follow-up; router dispatches; full audit logging with rollback

### Pipeline (`src/pipeline/`)

- PreFilter (keyword heuristics, domain lists)
- PipelineOrchestrator (7-step flow, async, batch, validation, error recovery)

### CLI (`src/cli/`)

- Commands: `process`, `cases`, `classify`, `stats`
- Rich output with tables/progress; validation mode; flexible filtering

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

### Smart Message Routing (Pre-Filter)

```python
def should_process_message(message: Message) -> bool:
    if is_blacklisted_sender(message.sender):
        return False
    if is_whitelisted_sender(message.sender):
        return True
    loa_keywords = ['loa', 'letter of authority', 'policy', 'plan number']
    text = get_message_text(message).lower()
    return any(kw in text for kw in loa_keywords)
```

## Installation

### Prerequisites

- Python 3.10+
- Google Cloud Firestore enabled (recommended for persistence)

### Setup

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

4) Configure environment (Firestore)

```bash
cp .env.example .env
# Edit .env with your Firestore credentials
```

5) Install package in development mode

```bash
pip install -e .
```

## Configuration

Environment variables:

- `FIRESTORE_PROJECT_ID`: GCP project for Firestore
- `GOOGLE_APPLICATION_CREDENTIALS`: Path to service account key JSON
- `LOG_LEVEL`: Logging verbosity
- `ENABLE_PRE_FILTER`: Enable/disable fast pre-filtering
- `MAX_CONCURRENT_MESSAGES`: Parallel processing limit

Firestore shell setup example:

```bash
export FIRESTORE_PROJECT_ID=your-project
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json
```

## Usage (CLI)

### Process Messages

```bash
# Process the full sample dataset
loa-worker process --file scenario_full_workflows.json

# Process a specific day
loa-worker process --file scenario_full_workflows.json --day 1

# Validate outputs against expected results
loa-worker process --file scenario_full_workflows.json --validate
```

### Test Classification/Extraction

```bash
loa-worker classify "Please open an LOA case for Alice Brown. Capture DOB, NI number, Plan number."
```

### Cases and Audit

```bash
loa-worker cases           # list cases
loa-worker cases --status OPEN --type loa --limit 10
loa-worker audit --case <case_id>
```

## Sample Dataset

`scenario_full_workflows.json` contains 21 messages over 3 days:

- Day 1: Alice Brown LoA workflow (creation, missing info, responses, updates, completion)
- Days 2–3: Ben Carter annual review (tasks, completions, progress tracking)

The dataset includes expected values for validation testing.

## LLM Integration

The system uses an abstract `LLMService` to support multiple providers.

- Primary operations:
  - `classify_message()` – determine relevance and category
  - `extract_entities()` – structured data extraction
  - `determine_action()` – select next action
- Current: `MockLLMService` enables full testing without API calls
- Real provider integration: implement `LLMService`, provide prompts, and wire API keys

Example (sketch):

```python
class AnthropicLLMService(LLMService):
    async def classify_message(self, message: Message):
        response = await self.client.messages.create(...)
        return parse_classification(response)
```

## Performance Characteristics (Estimates)

- Pre-filter: <1ms/message; filters 80%+ spam
- LLM operations: ~1–2s per relevant message total
- Firestore: writes 50–200ms; reads 20–100ms
- Batch processing: sequential 1–2s/msg; parallel (10 workers) ~200–300ms/msg

## Cost Considerations (Estimates)

Assuming 100 messages/day, 80% filtered, 20 messages hit LLM, ~2k tokens/message:

- Claude Sonnet: ~$0.12/day, ~$3.60/month
- Optimizations: pre-filtering, caching, cheaper models for classification

## Security Considerations

- Data protection: Firestore encryption at rest; no PII in logs
- Access control: service account, API keys via env, row-level security
- Error handling: sensitive data not exposed; retry with backoff

## Case State Machine

```
OPEN → IN_PROGRESS → AWAITING_INFO ⟷ IN_PROGRESS → COMPLETE
                                    ↘ CANCELLED
```

LoA cases auto-transition to COMPLETE when all required fields are received.

## Known Limitations

- Batch-only (no real-time yet)
- Single-tenant
- No UI (Next.js dashboard planned)
- Limited provider knowledge (no template learning yet)
- Sequential processing (parallelization planned)

## Roadmap

### Phase 2: LLM Integration

- Implement real provider service
- Prompt templates and confidence thresholds
- Human review queue for low confidence
- Token usage tracking

### Phase 3: Production Channels

- Email (IMAP) and Teams (Graph API) channels
- Webhook receivers and real-time processing

### Phase 4: Advanced Features

- Template learning and provider knowledge base
- Next.js dashboard and advanced analytics
- Multi-tenancy and production monitoring

## How to Extend

### Add a New Channel (e.g., Email)

1) Create `src/channels/email_channel.py`
2) Inherit `BaseChannel`; implement `fetch_messages()`
3) Parse into `Message` with appropriate content type

### Add Real LLM Integration

1) Create `src/llm/<provider>_service.py`
2) Implement `LLMService` methods
3) Add templates in `src/config/prompts.yaml`
4) Configure API keys in `.env`

### Add a New Action Type

1) Add enum to `ActionType`
2) Implement handler and wire in `router.py`
3) Include audit logging

## Testing Strategy

- Unit: isolated components with mocks
- Integration: component interactions with mock repos
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

Built with: Python, Pydantic, Firestore, Click, Rich
