# Chapter Three
# Proposed System Design and Implementation

## 3.1 Introduction

This chapter presents the design and implementation of the proposed Dynamic Website Vulnerability Monitoring and Reporting Web Service, named VulnAssesor. The system was developed as a web-based security assessment workspace that combines Dynamic Application Security Testing (DAST) for live websites with Static Application Security Testing (SAST) for source-code repositories. The main purpose of the implementation is to provide a practical environment where a user can register a target website or software project, start a scan, monitor the scan progress, and review the generated security findings from one browser-based interface.

The design of the system follows a modular and asynchronous architecture. This choice was necessary because vulnerability scanning is a time-consuming operation and should not block the normal web interface. Therefore, the application separates user interaction, data storage, background scanning, and external security analysis into clear components. Django is used for the web application and database interaction, Celery is used for background job execution, Redis is used as the message broker, Nuclei is used for dynamic vulnerability scanning, and configurable AI providers are used to support the SAST analysis workflow.

This chapter describes the system architecture, the database model, the implementation of the DAST and SAST modules, the user interface, and the main security considerations applied during development.

## 3.2 System Design Goals

The proposed system was designed according to several practical goals. First, the system should be easy to use by students, developers, or administrators who need to run vulnerability scans without using command-line tools directly. Second, scan execution should run in the background so that the web application remains responsive while long-running jobs are active. Third, all data should be scoped to the authenticated user, so each user can only manage their own websites, projects, templates, scans, and findings. Fourth, the system should support both website-level scanning and source-code-level scanning because these two approaches detect different types of weaknesses.

The system was also designed to provide live operational feedback. Instead of forcing the user to wait until a scan finishes, the interface shows scan states such as pending, running, completed, failed, or cancelled. For SAST scans, the interface also displays safe progress information about repository exploration and specialist analysis. These updates are implemented without full page reloads by using HTMX partial rendering.

Another important design goal was configurability. Nuclei options such as timeout, rate limit, concurrency, retry behavior, and custom arguments are stored in a configuration model. Similarly, SAST AI provider settings are stored in a separate configuration model that allows the system to select between OpenAI, Claude, and DeepSeek. API keys are not saved in the database; only the names of environment variables are stored.

## 3.3 Overall System Architecture

The architecture of VulnAssesor consists of five main layers: the presentation layer, the Django application layer, the background processing layer, the data storage layer, and the external analysis layer. Figure 3.1 shows the high-level architecture of the proposed system.

**Figure 3.1: High-Level Architecture of VulnAssesor**

The presentation layer is implemented using Django templates, HTMX, Alpine.js, and a custom CSS theme. It provides the dashboard, website management pages, template management pages, SAST project pages, file explorer, scan status panels, and result views. The user interacts with the system only through this layer.

The Django application layer receives HTTP requests, validates user access, reads and writes database records, and dispatches long-running tasks to Celery. It contains two main Django applications. The `Dashboard` application manages authentication, websites, Nuclei templates, DAST scans, Nuclei configuration, and AI provider configuration. The `SAST` application manages project ingestion, repository browsing, SAST scan jobs, AI-assisted findings, and proposed fixes.

The background processing layer is implemented with Celery workers. It is responsible for operations that may take a long time, such as cloning a repository, extracting an uploaded ZIP file, running Nuclei, and executing the SAST agent workflow. Redis is used as the broker between Django and Celery. When a user starts a scan from the browser, Django creates a database job record and sends a task message to Redis. A Celery worker then receives the task and performs the actual scanning work.

The data storage layer is based on PostgreSQL in the Docker environment, while SQLite can be used for local development by enabling the `USE_SQLITE` environment variable. The database stores users, websites, custom Nuclei templates, scan jobs, scan results, SAST projects, SAST findings, proposed fixes, and bounded progress events.

The external analysis layer contains the actual scanning and AI services. Nuclei is used to perform DAST by sending requests to the target website and matching responses against YAML templates. For SAST, the system uses configurable AI provider adapters. The AI provider does not scan files directly from the filesystem; instead, the system exposes bounded repository tools such as listing directories, searching code, and reading limited line ranges.

## 3.4 Implementation Environment and Technology Stack

The system was implemented using a development-oriented full-stack environment. Table 3.1 summarizes the main technologies used in the project and their roles.

**Table 3.1: Main Technologies Used in the System**

| Technology | Role in the System |
| --- | --- |
| Python 3.14 | Main programming language |
| Django 5.2 | Web framework, routing, templates, authentication, ORM |
| PostgreSQL | Main database in the Docker deployment |
| SQLite | Optional local development database |
| Redis | Message broker and Celery result backend |
| Celery | Background task execution for scans and ingestion |
| Nuclei 3.4.10 | Dynamic web vulnerability scanner |
| GitPython | Repository cloning and Git metadata access |
| HTMX | Live partial updates without full page reloads |
| Alpine.js | Lightweight client-side interface behavior |
| Pygments | Syntax highlighting for the read-only file viewer |
| Docker Compose | Local orchestration for database, Redis, web, and worker services |
| OpenAI, Claude, DeepSeek | Configurable AI providers for SAST analysis |

The Docker Compose environment starts four services: a PostgreSQL database container, a Redis container, a Django web container, and a Celery worker container. The web container runs database migrations, loads bundled Nuclei templates, collects static files, and starts Django's development server. The worker container waits for the database and then starts the Celery worker.

The current configuration is suitable for development and internal testing. The Django settings file keeps `DEBUG=True`, uses a development secret key, and runs the web container with Django's built-in development server. For production deployment, these settings would need to be hardened.

## 3.5 Database Design

The database schema is divided into DAST-related models, SAST-related models, configuration models, and progress event models. Django's ORM is used to define these models and manage relationships between them.

For the DAST module, the main entity is the `Website` model. Each website has a name, URL, owner, and timestamps. The `NucleiTemplate` model stores custom YAML templates created by users. Each template belongs to a specific owner, which prevents users from accessing templates created by other accounts. The `ScanJob` model represents one DAST scan request and stores the target website, Celery task identifier, status, completion time, error message, and cancellation information. The `ScanResult` model stores each individual finding returned by Nuclei, including the template name, vulnerability name, severity, target URL, and raw JSON finding.

For SAST, the `Project` model stores the source project information. A project may be created from a Git repository URL or an uploaded ZIP archive. It also stores the project owner, workspace root, ingestion task identifier, and status. The `SASTScanJob` model stores each source-code scan, including scan status, commit hash, scan type, timestamps, and agent execution metadata. The `SASTFinding` model stores confirmed vulnerabilities detected by the SAST workflow. Each finding includes the affected file path, line number, severity, title, description, code snippet, and AI explanation. The `SASTFix` model stores one proposed fix for a finding, including the replacement code, explanation, scope, line range, and acceptance status.

The system also includes two singleton-style configuration models. `NucleiConfig` stores scan execution options for the Nuclei command, while `AIConfig` stores the selected SAST provider, model names, base URLs, request timeout, maximum output tokens, and API key environment variable names. Storing only environment variable names reduces the risk of exposing API keys through the database.

Progress events are stored in `ScanProgressEvent` for DAST and `ProjectProgressEvent` for SAST. These models record safe, bounded operational messages such as queueing, scanning, parsing, tool usage, completion, failure, or cancellation. The progress streams are intentionally limited so that the database does not grow without control.

## 3.6 DAST Module Implementation

The DAST module allows a user to add websites, manage Nuclei templates, start scans, cancel scans, and review scan results. The workflow begins when the user selects a website and starts a scan. If custom templates are selected, the system passes their identifiers to the Celery task. If no templates are selected, the scan uses the default Nuclei templates available in the environment.

When a DAST scan is created, the Django view first verifies that the target website belongs to the authenticated user. It then creates a `ScanJob` record with a `PENDING` status and dispatches the Celery task. The scan row in the dashboard is updated through HTMX polling, so the user can see the status change as the job progresses.

The actual scanning logic is implemented in the `run_specialist_scan` Celery task. The task loads the scan job, marks it as `RUNNING`, records the Celery task identifier, and reads the current Nuclei configuration. If custom templates are used, the task writes each selected template into a temporary directory using safe filenames. It then builds the Nuclei command as a list of process arguments rather than a shell string. This reduces command construction risk and makes the command easier to control.

Nuclei is executed as a subprocess with JSON Lines output enabled. JSON Lines output is important because each line can be parsed as a separate finding. The worker captures standard output and standard error through temporary files, which improves compatibility on Windows. During execution, the task periodically checks whether the scan has been cancelled and stops the Nuclei process if cancellation is requested.

After Nuclei finishes, the worker reads each JSON line, extracts the template identifier, vulnerability name, severity, and matched URL, and saves the result as a `ScanResult` record. The scan is then marked as `COMPLETED`, `FAILED`, or `CANCELLED` depending on the outcome. The results page groups findings by severity and allows the user to search, inspect, copy, and export the raw JSON data.

**Figure 3.2: DAST Scan Workflow**

1. User starts a scan from the dashboard.
2. Django creates a `ScanJob` record.
3. Celery receives the scan task.
4. The worker prepares custom templates if needed.
5. Nuclei scans the target website.
6. JSONL findings are parsed and stored.
7. The dashboard and result pages display the outcome.

## 3.7 SAST Module Implementation

The SAST module is designed to analyze source-code repositories and generate security findings with explanations and proposed fixes. A project can be created either by providing a Git repository URL or by uploading a ZIP archive. Project ingestion is handled asynchronously so that large repositories or archives do not block the web request.

The `ingest_project_task` Celery task prepares the workspace, clones the Git repository or extracts the ZIP file, records progress events, and marks the project as `READY` when source import is complete. Each project workspace is stored under the media directory using the project identifier. The `ProjectManager` service centralizes workspace operations such as preparing directories, resolving paths, reading files, listing directories, cloning repositories, extracting archives, and deleting workspaces.

Path safety is an important part of the SAST implementation. The `resolve_path` method normalizes user-provided paths and ensures that the final resolved path remains inside the project workspace. This prevents path traversal when the file explorer, file viewer, or SAST tools request repository files. Directory listing also hides ignored folders such as `.git`, `node_modules`, build folders, virtual environments, and cache directories.

The SAST scan itself is executed by the `run_sast_scan` Celery task. Before scanning starts, the task verifies that the project is in the `READY` state. It then creates a `SASTScanOrchestrator`, loads the current AI configuration, builds the selected provider adapter, and records provider information such as selected scan, fix, and verification models. If the required provider API key is not available in the expected environment variable, the scan fails early with a clear error message.

The SAST workflow is not a simple file-by-file scan. Instead, it uses an orchestrator-and-specialist design. The orchestrator first explores the repository through controlled tool calls and identifies potential vulnerability surfaces. A vulnerability surface is not yet a confirmed finding; it is a candidate area that may require deeper analysis. Examples include request handlers, authentication boundaries, database access, file operations, subprocess usage, template rendering, deserialization, secrets, and outbound requests.

After discovery, the orchestrator deduplicates and prioritizes the surfaces. The system then dispatches each selected surface to a specialist agent. The specialist registry maps surface types such as SQL injection, cross-site scripting, authentication bypass, path traversal, and command injection to dedicated specialist classes. If a surface type does not have a dedicated specialist, the generic security specialist is used.

Each specialist runs three phases. The first phase investigates whether the reported surface is actually exploitable. The second phase generates a proposed fix for confirmed vulnerabilities. The third phase verifies whether the proposed fix addresses the issue without introducing obvious new problems. These phases use separate model calls and bounded repository tools. The available tools are `list_directory`, `search_codebase`, and `read_file`. Tool outputs are limited by configured line, byte, and result-count limits to avoid sending unnecessary repository content to the provider.

Confirmed SAST findings are stored as `SASTFinding` records, and proposed fixes are stored as `SASTFix` records. The system currently stores fixes for review, but the full accept, apply, branch, and pull request workflow remains future work.

**Figure 3.3: SAST Multi-Agent Workflow**

1. User creates or selects a ready project.
2. Django creates a `SASTScanJob`.
3. Celery starts the SAST scan task.
4. The orchestrator maps potential vulnerability surfaces.
5. Surfaces are deduplicated and sent to specialist agents.
6. Specialists investigate, generate fixes, and verify fixes.
7. Findings and proposed fixes are stored in the database.
8. The project page displays scan status, activity, findings, and fixes.

## 3.8 User Interface Implementation

The user interface is server-rendered using Django templates. This approach keeps the frontend simple while still allowing dynamic behavior through HTMX and Alpine.js. The base template provides a shared layout with navigation links to the dashboard, DAST templates, configuration page, and SAST projects. Authentication pages allow users to register, log in, and log out.

The main dashboard works as a command center. It summarizes the number of websites, projects, scans, findings, active operations, and proposed fixes for the authenticated user. It also displays recent DAST and SAST activity. Live operation panels are updated with HTMX, allowing users to monitor ongoing scans and ingestion tasks without reloading the full page.

The DAST interface includes website management, template management, scan creation, live status rows, and scan result pages. The result page presents severity counts, search functionality, collapsible finding cards, raw JSON viewing, and JSON export.

The SAST interface includes project creation, project ingestion status, scan controls, scan history, live scan activity, findings, proposed fixes, and a read-only repository explorer. The file explorer lists project files and directories, while the file viewer displays source code with syntax highlighting through Pygments. This is useful because the user can inspect the source location related to a finding directly inside the application.

## 3.9 Security and Safety Considerations

Several safety measures were applied during implementation. Most application views require authentication, and database queries are scoped to the current user. This prevents one user from accessing another user's websites, templates, projects, scans, findings, or fixes.

The DAST worker constructs the Nuclei command as an argument list and uses temporary directories for selected templates. Custom Nuclei arguments are still supported through configuration, but they are parsed with shell-like argument splitting rather than executed through a shell command string. Scan cancellation is handled through the scan status stored in the database and, when possible, through the Celery task identifier.

For SAST, workspace path resolution prevents direct path traversal outside the project directory. Tool access is limited to safe operations: listing directories, searching code, and reading bounded line ranges. The progress event system records operational summaries but avoids storing private reasoning, full prompts, full source files, full tool outputs, or proposed code bodies in the live activity stream. Proposed code is stored only in the dedicated fix model where it belongs.

The AI configuration model does not store API key values. Instead, it stores the names of environment variables, and the application checks these variables at runtime. This design reduces the risk of secret leakage through database backups or administrative views.

There are also known limitations. The current settings are development-oriented because `DEBUG` is enabled and the secret key is hard-coded. The Nuclei configuration page is intended to be restricted to administrative users, but the current code allows authenticated-user access. ZIP extraction should also be hardened before accepting untrusted archives in a production environment.

## 3.10 Testing and Evaluation Approach

The system includes automated tests and manual testing support. The SAST tests cover repository tools, memory management, orchestrator behavior, specialist registry dispatch, specialist fix flow, cancellation behavior, provider routing, metadata aggregation, and safe progress event behavior. These tests are important because the SAST workflow depends on multiple interacting components.

Dashboard testing is more limited and should be expanded in future work. However, the implementation provides a manual testing checklist that can be used to verify major user flows such as account creation, website registration, template creation, DAST scan execution, SAST project ingestion, scan cancellation, and result viewing.

For practical evaluation, the system can be tested by scanning known vulnerable websites in a controlled environment and by importing small vulnerable repositories. The expected outputs are stored scan results, severity classification, visible progress events, SAST findings, and proposed fixes. Since security scanners may produce false positives or miss some vulnerabilities, the results should be reviewed by a human user before being treated as final security conclusions.

## 3.11 Summary

This chapter described the design and implementation of VulnAssesor as a web-based vulnerability assessment service. The system combines Django, Celery, Redis, PostgreSQL, Nuclei, and configurable AI providers to support both DAST and SAST workflows. The DAST module scans live websites using Nuclei templates and stores parsed JSON findings. The SAST module ingests source projects and uses an orchestrator-and-specialist agent design to identify vulnerability surfaces, confirm findings, generate proposed fixes, and verify them.

The implementation emphasizes asynchronous processing, user-scoped data access, bounded progress reporting, configurable scanning behavior, and safe repository exploration. Although the current system is functional for development and internal testing, several areas remain for future hardening, including production settings, stricter administrative access control, hardened ZIP extraction, and complete fix application with branch and pull request automation.
