# VulnAssesor

VulnAssesor is a Django 5.2 security assessment workspace for websites and source repositories. It combines Nuclei-powered DAST with an OpenAI-backed SAST agent, all rendered through Django templates with HTMX and Alpine.js.

## What You Can Do
- Register and authenticate users.
- Add websites and run live DAST scans with Nuclei.
- Create, edit, and delete your own Nuclei templates.
- Load bundled templates from `nuclei-templates/`.
- Configure Nuclei behavior from the web UI.
- Create SAST projects from Git URLs or ZIP uploads.
- Watch real-time scan progress and review findings.
- Read AI explanations and proposed fixes for SAST findings.
- Browse imported repositories with a read-only file explorer and code viewer.

## Stack
- Django 5.2.8
- Python 3.14
- HTMX 1.9.10
- Alpine.js 3.13.3
- Celery
- Redis
- PostgreSQL or SQLite
- Nuclei 3.4.10
- OpenAI, GitPython, Pygments, and PyYAML
- Docker and Docker Compose

## Quick Start
### Docker
1. Set `OPENAI_API_KEY` in your shell or `.env` file.
2. Run `docker compose up --build` or `docker-compose up --build`.
3. Open `http://localhost:8000`.

The compose stack starts Postgres, Redis, the Django web container, and a Celery worker. The web container runs migrations, loads bundled templates, collects static files, and starts Django's development server.
Static assets are served from `/static/` and collected into `staticfiles/` during the Docker startup sequence.

### Local Development
1. Create and activate a Python 3.14 virtual environment.
2. Install dependencies with `pip install -r requirements.txt`.
3. Choose a database backend:
   - `USE_SQLITE=True` uses `db.sqlite3`.
   - Otherwise configure `POSTGRES_*` for PostgreSQL.
4. Export `OPENAI_API_KEY`.
5. Run:
   ```bash
   python manage.py migrate
   python manage.py load_templates
   python manage.py runserver
   celery -A VulnAssesor worker -l info
   ```
6. Open `http://localhost:8000`.

## Environment Variables
- `OPENAI_API_KEY` - required for SAST scans.
- `USE_SQLITE=True` - switch to SQLite.
- `DJANGO_ALLOWED_HOSTS` - comma-separated host list.
- `POSTGRES_NAME`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT` - PostgreSQL settings.
- `SAST_SCAN_MAX_TOOL_CALLS`, `SAST_SCAN_MAX_SEARCH_RESULTS`, `SAST_SCAN_MAX_READ_LINES`, `SAST_SCAN_MAX_DIRECTORY_ENTRIES`, `SAST_SCAN_MAX_TOOL_RESULT_BYTES`, `SAST_SCAN_SOFT_CONTEXT_TOKENS`, `SAST_SCAN_HARD_CONTEXT_TOKENS` - SAST agent limits.

## How DAST Works
1. Add a website from the dashboard.
2. Create one or more templates, or use the bundled YAML files.
3. Start a scan and optionally select templates.
4. If no templates are selected, the worker uses Nuclei's default templates.
5. The Celery task writes any selected templates to a temporary directory, runs Nuclei, and parses JSONL findings.
6. The dashboard updates the scan row with HTMX polling until the job finishes.
7. Open the results page to filter by severity, search findings, copy raw JSON, or export the scan as JSON.

## How SAST Works
1. Create a project from a Git URL or a ZIP upload.
2. The ingestion task clones or extracts the workspace into `media/projects/<project_id>/`.
3. Project status moves through `PENDING`, `CLONING`, `READY`, `FAILED`, or `CANCELLED`.
4. Start a scan from the project page.
5. Any pending or running scan for that project is cancelled before a new one is queued.
6. The agent explores the repository through tool calls instead of loading the whole tree into memory.
7. Findings store file path, line number, severity, description, code snippet, AI explanation, and a proposed fix.
8. The project page shows scan status, scan history, and read-only workspace browsing endpoints.

## Useful Commands
- `python manage.py load_templates` - import YAML templates from `nuclei-templates/`.
- `python manage.py load_templates --dry-run` - preview imports.
- `python manage.py load_templates --overwrite` - refresh existing template records.
- `python manage.py test` - run the test suite.
- `nuclei -ut` - update Nuclei's upstream templates.
- `python manage.py createsuperuser` - create an admin account for Django admin access.

## Project Layout
- `Dashboard/` - auth, websites, templates, DAST scans, Nuclei config, and the Celery DAST task.
- `SAST/` - project ingestion, repository exploration, SAST scans, fix generation, and workspace services.
- `templates/` - Django templates and HTMX partials.
- `static/` - CSS and JavaScript assets.
- `nuclei-templates/` - bundled default Nuclei templates.
- `media/projects/` - per-project SAST workspaces.
- `VulnAssesor/` - project settings, URLs, and Celery bootstrap.

## Testing
Most of the automated behavior coverage lives in `SAST/tests.py`, which exercises the repository tooling, memory manager, agent loop, cancellation handling, and fix persistence. `Dashboard/tests.py` is still a placeholder, so changes to the dashboard should be checked carefully.

## Current Limits
- The app is configured for development use by default.
- SAST fix application, branch creation, and pull request automation are not wired into the UI yet.
- DAST AI enrichment is not implemented yet.
- The Nuclei configuration view is currently accessible to authenticated users in code, even though it is intended to be restricted later.
- ZIP ingestion uses straightforward extraction and should be hardened if you expect untrusted archives.

## Roadmap
- Apply accepted SAST fixes directly to repositories.
- Create branches and pull requests from accepted fixes.
- Add AI enrichment to DAST findings.
- Add monitoring, alerting, and PDF reporting.

For deeper implementation notes, see [agents.md](agents.md).
