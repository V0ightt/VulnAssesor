# VulnAssesor Project Specification

- **Last Updated:** May 4, 2026
- **Current State:** Working Django 5.2 application with Nuclei DAST and configurable AI-backed multi-agent SAST
- **Operational Mode:** Development-oriented stack with background workers and live HTMX updates

---

## 1. Purpose

VulnAssesor is a Django-based security workspace for two related workflows:

- **DAST** for live website scanning with Nuclei.
- **SAST** for repository analysis using a configurable AI-backed orchestrator and sequential specialist agents that explore code with tool calls.

The application is server-rendered, user-scoped, and intentionally simple to operate: users sign in, register websites or projects, launch scans, and review results in the browser. HTMX and Alpine.js provide the live interactions, while Celery and Redis handle background work.

This document is the implementation reference for the current repository. It should track the code as it exists now, not the older phase-by-phase narrative.

---

## 2. Stack and Runtime

### Core stack
- Django 5.2.8
- Python 3.14
- Celery
- Redis
- PostgreSQL in Docker, SQLite for local development
- OpenAI, Claude, and DeepSeek API integration for SAST
- GitPython
- Pygments
- PyYAML
- Nuclei 3.4.10

### Frontend stack
- Django templates
- HTMX 1.9.10
- Alpine.js 3.13.3
- Custom dark theme in `static/css/main.css`

### Runtime defaults
- `DEBUG=True` in `VulnAssesor/settings.py`
- Hard-coded development `SECRET_KEY` in settings
- `STATIC_URL=/static/` to keep asset URLs absolute
- Docker Compose starts Django with `runserver`, not gunicorn
- The app is therefore best treated as a development or internal deployment until the settings are hardened

### Environment variables
- `OPENAI_API_KEY` - required when the configured SAST provider is OpenAI
- `ANTHROPIC_API_KEY` - required when the configured SAST provider is Claude
- `DEEPSEEK_API_KEY` - required when the configured SAST provider is DeepSeek
- `USE_SQLITE=True` - switch to SQLite
- `DJANGO_ALLOWED_HOSTS` - comma-separated host list
- `POSTGRES_NAME`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT` - PostgreSQL connection settings
- `SAST_SCAN_MAX_TOOL_CALLS` - shared fallback tool-call budget
- `SAST_SCAN_ORCHESTRATOR_MAX_TOOL_CALLS` - broad surface-discovery tool-call budget; defaults to `SAST_SCAN_MAX_TOOL_CALLS`
- `SAST_SCAN_SPECIALIST_MAX_TOOL_CALLS` - per-specialist phase tool-call budget; defaults to half of `SAST_SCAN_MAX_TOOL_CALLS`, minimum 6
- `SAST_SCAN_MAX_SPECIALISTS` - maximum deduplicated surfaces dispatched in one scan; defaults to 6
- `SAST_SCAN_MAX_SEARCH_RESULTS`
- `SAST_SCAN_MAX_READ_LINES`
- `SAST_SCAN_MAX_DIRECTORY_ENTRIES`
- `SAST_SCAN_MAX_TOOL_RESULT_BYTES`
- `SAST_SCAN_MAX_FILE_BYTES`
- `SAST_SCAN_RIPGREP_TIMEOUT`
- `SAST_SCAN_INVENTORY_MAX_FILES`
- `SAST_SCAN_MAX_SINK_CANDIDATES`
- `SAST_SCAN_SOFT_CONTEXT_TOKENS`
- `SAST_SCAN_HARD_CONTEXT_TOKENS`

---

## 3. Repository Map

### Top-level ownership
- `Dashboard/` - authentication, website CRUD, Nuclei template CRUD, DAST scan orchestration, Nuclei configuration, and helper endpoints
- `SAST/` - project ingestion, repository exploration, SAST scans, fix generation, and workspace services
- `SAST/agents/` - orchestrator, specialist agents, structured schemas, memory aggregation, and registry dispatch
- `SAST/inventory.py` - deterministic pre-scan repository inventory for large-repo routing context
- `templates/` - Django UI templates and HTMX partials
- `static/` - CSS and client assets
- `nuclei-templates/` - bundled Nuclei YAML templates that can be loaded into the database
- `media/projects/` - per-project SAST workspaces
- `VulnAssesor/` - project settings, URLs, Celery bootstrap, and WSGI/ASGI entry points

### Main support files
- `docker-compose.yaml` - local orchestration for Postgres, Redis, web, and worker containers
- `Dockerfile` - Python image with Nuclei installed and templates updated at build time
- `requirements.txt` - runtime dependencies
- `wait-for-db.sh` - startup helper used by Compose
- `manage.py` - Django management entry point

---

## 4. Authentication and UI Shell

### Access model
- Most application views use `login_required`.
- Dashboard websites, templates, scans, and SAST projects are owner-scoped.
- The admin site currently covers the Dashboard models; `SAST/admin.py` is still a stub.

### Base template behavior
- `templates/base.html` loads HTMX and Alpine from CDN.
- HTMX requests automatically receive the CSRF token through a `htmx:configRequest` hook.
- Authenticated users get a GitHub-inspired sidebar with Dashboard, Templates, Configuration, and Projects navigation.
- Project links in the sidebar are injected by `SAST.context_processors.user_projects`.
- Messages are rendered globally and the layout has a dedicated mobile sidebar.

---

## 5. Dashboard App

### 5.1 Models

#### `Website`
- `name`
- `url`
- `owner`
- `created_at`
- `updated_at`
- Ordered by newest first

#### `NucleiTemplate`
- `name`
- `description`
- `template_content`
- `owner`
- `created_at`
- `updated_at`
- Owner-scoped custom templates for DAST scans

#### `NucleiConfig`
Singleton configuration for Nuclei CLI generation.

Fields:
- `timeout`
- `rate_limit`
- `concurrency`
- `silent_mode`
- `no_color`
- `jsonl_output`
- `retries`
- `max_host_errors`
- `follow_redirects`
- `custom_args`
- `updated_at`
- `updated_by`

Behavior:
- `get_config()` returns or creates the singleton row.
- `build_command(target_url, templates_path)` constructs the Nuclei command as a list.
- `jsonl_output` should stay enabled because the parser depends on JSON Lines output.
- `custom_args` are appended at the end and are split with `shlex`.

#### `AIConfig`
Singleton configuration for the SAST AI backend.

Fields:
- `provider` - `openai`, `anthropic`, or `deepseek`
- `openai_scan_model`
- `openai_fix_model`
- `openai_verify_model`
- `anthropic_scan_model`
- `anthropic_fix_model`
- `anthropic_verify_model`
- `deepseek_scan_model`
- `deepseek_fix_model`
- `deepseek_verify_model`
- `openai_api_key_env_var`
- `anthropic_api_key_env_var`
- `deepseek_api_key_env_var`
- `openai_base_url`
- `anthropic_base_url`
- `deepseek_base_url`
- `max_output_tokens`
- `request_timeout`
- `updated_at`
- `updated_by`

Behavior:
- `get_config()` returns or creates the singleton row.
- API key values are never stored in the database; only environment variable names are stored.
- `require_api_key()` fails fast with the missing environment variable name.
- `key_statuses()` exposes configured/missing state for the configuration UI without exposing secret values.
- `selected_provider_settings()` returns the active provider's API settings and provider-specific scan, fix, and verification models.

#### `ScanJob`
- `website`
- `celery_task_id`
- `status`
- `created_at`
- `completed_at`
- `error_message`
- `cancelled_by`

Status values:
- `PENDING`
- `RUNNING`
- `COMPLETED`
- `FAILED`
- `CANCELLED`

Indexes:
- `created_at` plus `status`
- `status`
- `celery_task_id`

#### `ScanResult`
- `job`
- `template_name`
- `vulnerability_name`
- `severity`
- `target_url`
- `raw_finding`
- `created_at`

Severity values:
- `critical`
- `high`
- `medium`
- `low`
- `info`

Indexes:
- `job` plus `severity`
- `severity` plus `created_at`

#### `ScanProgressEvent`
Bounded, safe live progress events for DAST scans.

Fields:
- `scan_job`
- `sequence`
- `phase`
- `event_type`
- `title`
- `detail`
- `payload`
- `created_at`

Behavior:
- `record(...)` appends a sequenced event for the scan.
- Old events are pruned so each scan keeps only recent operational context.
- Payloads are safe summaries and should not include raw scanner output beyond bounded status metadata.

### 5.2 Routes and views

#### Authentication
- `/register/` - `register_view`
- `/login/` - `login_view`
- `/logout/` - `logout_view`

#### Dashboard and website management
- `/` - `dashboard_view`
- `/dashboard/live-operations/` - `dashboard_live_operations_view`, HTMX command-center live operations partial
- `/website/add/` - `website_add_view`
- `/website/<int:pk>/edit/` - `website_edit_view`
- `/website/<int:pk>/delete/` - `website_delete_view`

#### Template management
- `/templates/` - `template_list_view`
- `/templates/create/` - `template_create_view`
- `/templates/<int:pk>/edit/` - `template_edit_view`
- `/templates/<int:pk>/delete/` - `template_delete_view`

#### DAST scan workflow
- `/scan/create/<int:website_pk>/` - `scan_create_view`
- `/scan/<int:scan_pk>/status/` - `scan_status_view`
- `/scan/<int:scan_pk>/cancel/` - `scan_cancel_view`
- `/scan/<int:scan_pk>/delete/` - `scan_delete_view`
- `/scan/<int:scan_pk>/results/` - `scan_results_view`

#### Configuration and support
- `/nuclei/config/` - `nuclei_config_view`, combined Nuclei and AI provider configuration
- `/nuclei/update-templates/` - `nuclei_update_templates_view`
- `/test-celery/` - `test_celery_view`

### 5.3 DAST workflow

`scan_create_view` validates template ownership and creates a `ScanJob` in `PENDING` state. If the user selected templates, the job is handed to Celery with those template IDs. If no templates are selected, the worker falls back to Nuclei default templates.

`run_specialist_scan` in `Dashboard/tasks.py` does the actual scan work:

1. Fetch the job and mark it `RUNNING`.
2. Resolve the current `NucleiConfig` singleton.
3. If custom templates were selected, write them to a temporary directory using safe filenames.
4. Build the Nuclei command with the configured timeout, rate limit, concurrency, retries, redirect handling, and custom args.
5. Run Nuclei with JSONL output enabled.
6. Capture stdout and stderr using real temporary files for Windows compatibility.
7. Parse each JSON line into a `ScanResult` row.
8. Emit safe progress events for queueing, configuration, template preparation, command launch, heartbeat, parsing, findings, and terminal status.
9. Update the job to `COMPLETED`, `FAILED`, or `CANCELLED`.
10. Store `completed_at` and, on failure, `error_message`.

Additional notes:
- The helper `check_cancellation_and_wait` exists, but the task currently uses its own polling loop.
- Scan cancellation uses the Celery task ID when it is available.
- `nuclei_update_templates_view` runs `nuclei -ut` with a five minute timeout.
- `test_celery_view` is a simple 10 second smoke test for the worker.

### 5.4 DAST templates

`templates/dashboard/scan_create.html` lets the user multi-select templates or leave the list empty to use Nuclei defaults.

`templates/dashboard/scan_row.html` provides the polling row used by the dashboard. It updates every 3 seconds while the scan is pending or running.

`templates/dashboard/scan_results.html` provides:
- severity tabs and counts
- search across findings
- collapsible finding cards
- raw JSON copy
- JSON export

### 5.5 Nuclei config note

The Nuclei config view is intended as an administrative control surface, but the staff-only check is currently commented out in code. Treat the current access behavior as authenticated-user access until that is restored.

---

## 6. SAST App

### 6.1 Models

#### `Project`
- `name`
- `repository_url`
- `source_zip`
- `owner`
- `created_at`
- `updated_at`
- `last_scan`
- `root_directory`
- `status`
- `ingestion_task_id`

Project statuses:
- `PENDING`
- `CLONING`
- `READY`
- `CANCELLED`
- `FAILED`

#### `SASTScanJob`
- `project`
- `status`
- `created_at`
- `completed_at`
- `celery_task_id`
- `cancel_requested_at`
- `cancelled_by`
- `commit_hash`
- `scan_type`
- `agent_run_metadata`

Scan statuses:
- `PENDING`
- `CLONING`
- `SCANNING`
- `CANCELLING`
- `COMPLETED`
- `FAILED`
- `CANCELLED`

Scan types:
- `FULL`
- `INCREMENTAL`

Indexes:
- `project` plus `status` plus newest `created_at`
- `status` plus newest `created_at`
- `celery_task_id`

#### `SASTFinding`
- `scan_job`
- `file_path`
- `line_number`
- `severity`
- `title`
- `description`
- `code_snippet`
- `ai_explanation`
- `ai_fix_code`
- `is_fixed`
- `confidence_score`
- `created_at`

Severity values:
- `CRITICAL`
- `HIGH`
- `MEDIUM`
- `LOW`
- `INFO`

`ai_fix_code` and `is_fixed` are still legacy fields in the model.

Indexes:
- `scan_job` plus `severity`
- `scan_job` plus newest `created_at`
- `severity` plus newest `created_at`

#### `SASTFix`
- `finding` one-to-one relation
- `proposed_code`
- `explanation`
- `status`
- `scope`
- `start_line`
- `end_line`
- `verification_status`
- `verification_reason`
- `created_at`

Status values:
- `PENDING`
- `ACCEPTED`
- `REJECTED`

Scope values:
- `SNIPPET`
- `FILE`

Verification status values:
- `NOT_VERIFIED`
- `PASSED`
- `FAILED`

Indexes:
- `status` plus newest `created_at`
- `verification_status` plus newest `created_at`

#### `ProjectProgressEvent`
Bounded, safe live progress events for SAST project ingestion and SAST scans.

Fields:
- `project`
- `scan_job` - optional; null for ingestion events
- `sequence`
- `phase`
- `event_type`
- `title`
- `detail`
- `payload`
- `created_at`

Behavior:
- Scan events are scoped to a `SASTScanJob`; ingestion events are scoped to the project.
- `record(...)` appends sequenced events and prunes older entries.
- Tool-call events expose safe activity only: tool name, paths, line ranges, hit counts, samples, model/phase metadata, and outcomes.
- Events must not expose private chain-of-thought, raw prompts, full tool outputs, full source file content, or proposed code bodies.

### 6.2 Routes and views

- `/sast/projects/` - `project_list`
- `/sast/projects/new/` - `project_create`
- `/sast/projects/<int:project_id>/` - `project_detail`
- `/sast/projects/<int:project_id>/explorer/` - `file_explorer`
- `/sast/projects/<int:project_id>/viewer/` - `file_viewer`
- `/sast/projects/<int:project_id>/scan/` - `start_scan`
- `/sast/projects/<int:project_id>/ingestion-status/` - `ingestion_status`
- `/sast/projects/<int:project_id>/cancel-ingestion/` - `cancel_ingestion`
- `/sast/scans/<int:scan_id>/cancel/` - `cancel_scan`
- `/sast/scans/<int:scan_id>/status/` - `scan_status`
- `/sast/projects/<int:project_id>/delete/` - `project_delete`

### 6.3 SAST workflow

Project creation starts with either a repository URL or an uploaded ZIP file. `ingest_project_task` then:

1. Loads the `Project` row.
2. Sets the project to `CLONING`.
3. Creates the workspace with `ProjectManager`.
4. Clones the repository or extracts the ZIP archive.
5. Emits safe ingestion progress for workspace preparation, clone or extract milestones, ready, failed, and cancelled states.
6. Sets `root_directory` and marks the project `READY`.
7. Marks the project `FAILED` or `CANCELLED` on error or cancellation.

When a scan starts, `run_sast_scan`:

1. Fetches the `SASTScanJob` and its `Project`.
2. Fails fast unless the project is `READY`.
3. Sets the scan to `SCANNING`.
4. Captures the repository head commit if the project is a Git checkout.
5. Instantiates `SASTScanOrchestrator`, which loads `AIConfig` once and builds one provider.
6. Builds a deterministic repository inventory with file/language counts, top-level structure, entrypoint candidates, and vulnerability sink candidates from bounded searches.
7. Runs `OrchestratorAgent.discover_surfaces()` to gather potential vulnerability surfaces, using the inventory only as routing context.
8. Deduplicates surfaces and dispatches them sequentially through `SpecialistRegistry`.
9. Runs each specialist's investigation, fix generation, and fix verification in its own conversation and memory scope.
10. Persists each specialist result immediately after its fix and verification are ready.
11. Emits safe progress events for provider setup, inventory, orchestrator exploration, tool calls, surface dispatch, specialist phases, finding persistence, fix persistence, completion, failure, and cancellation.
12. Stores running and final aggregate orchestrator, specialist, inventory, surface, and tool metadata in `agent_run_metadata`.
13. Marks the scan `COMPLETED`, stores `completed_at`, and updates `project.last_scan`.

Cancellation behavior:
- `cancel_scan` marks an active scan as `CANCELLING`, stores `cancel_requested_at` and `cancelled_by`, and keeps polling while the worker cleans up.
- The worker marks the scan `CANCELLED` only after the active agent loop stops and already persisted findings/fixes remain visible.
- `cancel_ingestion` revokes the ingestion task and marks the project `CANCELLED`.
- `BaseToolCallingAgent._ensure_scan_active()` raises a dedicated cancellation exception when the active scan job flips to `CANCELLING` or `CANCELLED`.

### 6.4 Project manager and workspace safety

`SAST/services.py` provides `ProjectManager`, which owns all workspace operations.

Key methods:
- `prepare_workspace()` - create the workspace directory
- `resolve_path()` - convert a relative path into a workspace-safe absolute path
- `clone_repository()` - clone or pull the repository
- `extract_zip()` - extract the uploaded ZIP into the workspace
- `get_file_content()` - read file text
- `get_file_lines()` - read a bounded line range
- `get_directory_structure()` - list workspace entries
- `iter_workspace_files()` - iterate files for scans
- `push_changes()` - commit and push fixes to the remote repo
- `get_repository_head_commit()` - read the current Git head
- `delete_workspace()` - remove the workspace directory

Important guardrails:
- `resolve_path()` blocks path traversal.
- `get_directory_structure()` hides `.git` by default.
- `iter_workspace_files()` skips ignored directories and hidden implementation folders.
- `clone_repository()` and `extract_zip()` accept optional progress callbacks used by live ingestion events.
- ZIP extraction should still be reviewed carefully if this is promoted to a hardened deployment.

### 6.5 SAST helper functions

`SAST/sast_tools.py` provides the repository-safe tool surface used by the agent and task code.

Functions:
- `list_directory(project, directory='')`
- `search_codebase(project, query, directory='')`
- `read_file(project, file_path, start_line=1, end_line=None, max_lines=None, max_bytes=None)`
- `report_vulnerability(scan_job, file_path, line_number, severity, title, description, code_snippet, confidence_score=None)`
- `apply_fix(finding_id, proposed_code, explanation, scope='SNIPPET', start_line=1, end_line=1, verification_status='NOT_VERIFIED', verification_reason='')`
- `modify_code(project, file_path, new_content)`
- `push_fixes(project, commit_message='Applied SAST fixes')`
- `get_vulnerability_context(finding_id)`
- `list_project_files(project)`

Behavior notes:
- `list_directory()` stops after the configured entry limit and reports truncation.
- `search_codebase()` uses ripgrep when available, applies ignored directories and allowed extensions, enforces a timeout and result limit, and falls back to Python regex search otherwise.
- `read_file()` clamps line ranges and byte size to keep model inputs bounded, and rejects disallowed extensions or oversized files.
- The allowed file list is intentionally broad and includes common code, config, and shell files.
- `modify_code()` and `push_fixes()` exist as phase-5 scaffolding and are not yet wired into the main workflow.

### 6.6 AI agent design

`SAST/agents/` is the current SAST engine. `SAST/agent.py` remains as a compatibility layer that re-exports the legacy schemas, `ScanMemoryManager`, `ScanCancelledError`, and a deprecated `SASTAgent` facade for older imports.

Core characteristics:
- `SASTScanOrchestrator` runs inside the existing `run_sast_scan` Celery task.
- The orchestrator starts with a deterministic inventory phase before AI surface discovery.
- `OrchestratorAgent` performs broad repository exploration and returns potential `VulnerabilitySurface` objects only.
- `SpecialistRegistry` maps vulnerability types to specialist classes and falls back to `GenericSecuritySpecialistAgent`.
- Specialists run sequentially for v1; Celery fan-out is intentionally deferred.
- Agents return structured data only. `run_sast_scan` remains the persistence boundary, but each specialist result is saved immediately after fix generation and verification.
- One provider is built from `AIConfig` per scan and passed to each agent; each agent starts its own conversation.
- Provider conversations are rebased after tool turns onto the task prompt, compact summaries, and bounded recent evidence excerpts so older raw tool outputs are not repeatedly resent.
- It loads the target project's `agents.md`, `AGENTS.md`, and `README.md` into the system context when available.
- It does not assume repository contents that have not been discovered through tool calls.
- It focuses on exploitable vulnerabilities only, not style warnings.

Current tool set:
- `list_directory`
- `search_codebase`
- `read_file`

Current specialists:
- `SQLiSpecialistAgent`
- `XSSSpecialistAgent`
- `AuthBypassSpecialistAgent`
- `PathTraversalSpecialistAgent`
- `CommandInjectionSpecialistAgent`
- `GenericSecuritySpecialistAgent`

Supported vulnerability surface types:
- `SQL_INJECTION`
- `XSS`
- `AUTH_BYPASS`
- `PATH_TRAVERSAL`
- `COMMAND_INJECTION`
- `SSRF`
- `DESERIALIZATION`
- `SECRETS`
- `ACCESS_CONTROL`
- `FILE_UPLOAD`
- `TEMPLATE_INJECTION`
- `OTHER`

Current default model names:
- OpenAI: `gpt-5-nano` for scanning, fix generation, and verification
- Claude: `claude-sonnet-4-5` for scanning, fix generation, and verification
- DeepSeek: `deepseek-v4-flash` for scanning, fix generation, and verification
- Each provider has independent scan, fix, and verification model fields in Configuration > AI Providers.

Structured output models:
- `Vulnerability`
- `ScanResult`
- `FixResult`
- `VerificationResult`
- `VulnerabilitySurface`
- `OrchestratorSurfaceResult`
- `SpecialistFindingResult`
- `ScanExecutionResult`

Supporting components:
- `BaseToolCallingAgent` owns project context loading, tool definitions, tool dispatch, structured parsing, and cancellation checks.
- `BaseToolCallingAgent` emits safe progress events for tool calls without persisting raw file contents or private reasoning.
- `ScanMemoryManager` tracks explored paths, tool counts, truncation, compact summaries, and bounded recent evidence excerpts.
- `aggregate_scan_metadata()` preserves legacy top-level metadata keys and adds nested `orchestrator` and `specialists` metadata.
- `ExplorationResult` wraps the raw investigation transcript and metadata.
- `ScanCancelledError` is raised when the active scan is cancelled mid-run.
- `SAST/llm/` contains provider adapters, provider conversation rebasing hooks, and the provider registry.

Implementation note:
- This is a repository-exploration pipeline, not a simple per-file loop. The orchestrator decides which surfaces merit deeper review, and specialists convert gathered evidence into confirmed findings, proposed fixes, and verification results.

### 6.7 SAST templates and UI

Current templates and partials:
- `templates/sast/project_list.html`
- `templates/sast/project_create.html`
- `templates/sast/project_detail.html`
- `templates/sast/partials/project_detail_content.html`
- `templates/sast/partials/scan_status.html`
- `templates/sast/partials/scan_activity.html`
- `templates/sast/partials/ingestion_status.html`
- `templates/sast/partials/file_explorer.html`
- `templates/sast/partials/file_viewer.html`

Important UI behavior:
- `project_detail` auto-refreshes the outer content while ingestion is in progress.
- `scan_status` polls every 2 seconds for active and cancelling scans.
- The project detail view shows scan controls, current scan status, elapsed time, current phase, reviewed/total surfaces, tool calls, findings saved, last activity, cancellation state, safe live scan activity, ingestion activity, findings, fixes, and read-only project context.
- Findings render as soon as they are persisted; proposed fixes are collapsed by default and show explicit verification status and reason.
- The file explorer and viewer are implemented as read-only partial endpoints for repository navigation and syntax-highlighted code viewing.
- Pygments uses the Monokai theme for code highlighting.

---

## 7. Deployment and Bootstrap

### Docker Compose startup
The current Compose file starts:
- `db` - Postgres 15
- `redis` - Redis 7
- `web` - Django web container
- `worker` - Celery worker

The web container currently runs:
1. `wait-for-db.sh`
2. `makemigrations`
3. `migrate`
4. `load_templates`
5. `collectstatic --noinput`
6. `runserver 0.0.0.0:8000`

The worker container starts Celery after the database is reachable.

### Dockerfile behavior
- Starts from `python:3.14-slim`
- Installs build tools, git, libpq, wget, and unzip
- Installs Nuclei 3.4.10
- Runs `nuclei -update-templates` during image build
- Installs Python dependencies from `requirements.txt`

### Template bootstrap
`Dashboard/management/commands/load_templates.py` loads YAML templates from `nuclei-templates/` into the database.

Supported command options:
- `--user <username>`
- `--overwrite`
- `--dry-run`

Behavior notes:
- If no user is supplied, the command uses or creates a `system` user.
- The command reads `*.yaml` and `*.yml` files from `nuclei-templates/`.
- The command is run automatically by Compose startup.

---

## 8. Testing and Coverage

Current test coverage is uneven:
- `Dashboard/tests.py` covers AI configuration and live progress event basics, but DAST behavior still needs broader coverage.
- `SAST/tests.py` contains meaningful coverage for the repository tools, memory manager, inventory summaries, orchestrator, specialist registry, specialist fix flow, cancellation behavior, streaming fix persistence, and scan status UI states.
- The SAST tests also use fakes to verify bounded context rebasing, structured output, provider routing, metadata aggregation, tool-loop behavior, and safe progress events.

If you change SAST internals, the existing tests are the best safety net. Dashboard workflow behavior still needs dedicated coverage.

---

## 9. Known Gaps and Current Constraints

- The app is not production hardened yet. `DEBUG=True` and the hard-coded secret key still need attention.
- The Nuclei config view is intended to be restricted, but the staff check is currently commented out.
- DAST AI enrichment is not yet wired in.
- Fix application, branch creation, and pull request automation remain future work.
- `SASTFix` stores proposed fixes, but there is no complete accept/reject/apply UI yet.
- SAST specialists run sequentially in one Celery task; distributed fan-out is intentionally deferred.
- ZIP extraction should be reviewed if the project is used with untrusted uploads in a hardened environment.
- The current stack assumes a running Celery worker and Redis broker for scan execution.
- DAST does not currently enforce a single active scan per website in the same way SAST cancels existing project scans.
- SAST models now have live-polling indexes, but they do not yet have richer multi-attempt tracking that later phases may need.

---

## 10. Current Feature Summary

### Implemented
- User authentication
- Website management
- Nuclei template CRUD
- Nuclei configuration UI and command generation
- DAST scan orchestration with live polling
- Safe live DAST progress events and command-center operations polling
- DAST results viewing, filtering, and export
- Project ingestion from Git or ZIP
- Safe live ingestion progress events
- Repository browsing endpoints
- AI-assisted SAST scanning with orchestrator and specialist agents
- Deterministic SAST pre-scan repository inventory
- Streaming SAST finding/fix persistence during sequential specialist execution
- Safe live SAST agent activity, tool-call, and phase progress events
- Fix generation and verification
- Workspace deletion and cancellation flows
- Docker-based local environment

### Future work
- Apply accepted SAST fixes to source trees
- Branch and pull request automation
- AI enrichment for DAST findings
- Monitoring and alerting
- Reporting enhancements

---

## 11. Reference Files

- `README.md` - user-facing overview and setup guide
- `TESTING_CHECKLIST.md` - manual QA checklist
- `SAMPLE_NUCLEI_TEMPLATES.md` - sample template library
- `ARCHITECTURE_DIAGRAM.md` - system architecture reference

---

## 12. Maintenance Rule

When the code changes, update this document and `README.md` together. These files should be treated as the current contract for how the project runs, what it exposes, and what still remains unfinished.
