# Phase 4 System Architecture & Flow (AI-Powered SAST + DAST)

## Complete System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         USER INTERFACE                                      │
│                                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  Dashboard   │  │  Templates   │  │ DAST Results │  │ SAST Projects│  │
│  │              │  │              │  │              │  │              │  │
│  │ - Websites   │  │ - List       │  │ - Details    │  │ - List       │  │
│  │ - Scans      │  │ - Create     │  │ - Severity   │  │ - Create     │  │
│  │ - Status     │  │ - Edit       │  │ - Raw Data   │  │ - File Exp   │  │
│  │              │  │              │  │              │  │ - AI Fixes   │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘  │
│         │                  │                  │                  │          │
│         └──────────────────┼──────────────────┼──────────────────┘          │
│                            │                  │                             │
└────────────────────────────┼──────────────────┼─────────────────────────────┘
                             │ HTMX + Alpine.js │
                             ↓                  ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                    DJANGO VIEWS LAYER                                       │
│                                                                             │
│  ┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────┐ │
│  │ DAST Management      │  │ Template Management  │  │ SAST Management  │ │
│  │                      │  │                      │  │                  │ │
│  │ • scan_create_view   │  │ • template_list      │  │ • project_list   │ │
│  │ • scan_status_view   │  │ • template_create    │  │ • project_create │ │
│  │ • scan_results_view  │  │ • template_edit      │  │ • project_detail │ │
│  │ • scan_cancel_view   │  │ • template_delete    │  │ • start_scan     │ │
│  │                      │  │                      │  │ • file_explorer  │ │
│  │                      │  │                      │  │ • file_viewer    │ │
│  │                      │  │                      │  │ • scan_status    │ │
│  └──────────────────────┘  └──────────────────────┘  └──────────────────┘ │
│                            │                                               │
└────────────────────────────┼───────────────────────────────────────────────┘
                             │
                             ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                    DATABASE MODELS                                          │
│                                                                             │
│  DAST MODELS                          SAST MODELS                          │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │   Website   │  │NucleiTemplate│  │   Project    │  │ SASTScanJob  │   │
│  ├─────────────┤  ├──────────────┤  ├──────────────┤  ├──────────────┤   │
│  │ • name      │  │ • name       │  │ • name       │  │ • project_id │   │
│  │ • url       │  │ • description│  │ • repo_url   │  │ • status     │   │
│  │ • owner     │  │ • content    │  │ • source_zip │  │ • commit_hash│   │
│  └──────┬──────┘  │ • owner      │  │ • owner      │  │ • timestamps │   │
│         │         └──────────────┘  │ • status     │  └──────┬───────┘   │
│         │                           │ • root_dir   │         │           │
│         │         ┌──────────────┐  └──────┬───────┘         │           │
│         │         │   ScanJob    │         │                 │           │
│         │         ├──────────────┤         │    ┌────────────▼────────┐  │
│         │         │ • website_id │         │    │   SASTFinding       │  │
│         │         │ • status     │         │    ├─────────────────────┤  │
│         │         │ • task_id    │         │    │ • scan_job_id       │  │
│         │         │ • cancelled  │         │    │ • file_path         │  │
│         │         └──────┬───────┘         │    │ • line_number       │  │
│         │                │                 │    │ • severity          │  │
│         │         ┌──────▼──────┐          │    │ • title             │  │
│         └─────────│ ScanResult  │          │    │ • ai_explanation    │  │
│                   ├─────────────┤          │    └──────┬──────────────┘  │
│                   │ • job_id    │          │           │                 │
│                   │ • vuln_name │          │    ┌──────▼──────┐          │
│                   │ • severity  │          │    │  SASTFix    │          │
│                   │ • target_url│          │    ├─────────────┤          │
│                   │ • raw_json  │          │    │ • finding_id│          │
│                   └─────────────┘          │    │ • proposed  │          │
│                                            │    │ • explanation│         │
│                                            │    │ • status    │          │
│                                            │    └─────────────┘          │
└─────────────────────────────────────────────────────────────────────────────┘
                             │
                             ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CELERY TASK QUEUE                                        │
│                                                                             │
│  ┌───────────────────────────────────┐  ┌───────────────────────────────┐  │
│  │  run_specialist_scan (DAST)       │  │  run_sast_scan (AI-Powered)   │  │
│  │                                   │  │                               │  │
│  │  1. Receive job_id, template_ids  │  │  1. Receive scan_job_id       │  │
│  │  2. Update status to RUNNING      │  │  2. Initialize SASTAgent      │  │
│  │  3. Create temp directory         │  │  3. Load project context      │  │
│  │  4. Write templates to YAML       │  │  4. List scannable files      │  │
│  │  5. Execute Nuclei scanner        │  │  5. For each file:            │  │
│  │  6. Parse JSONL output            │  │     • Send to OpenAI GPT-4o   │  │
│  │  7. Create ScanResult objects     │  │     • Get vulnerabilities     │  │
│  │  8. Update status to COMPLETED    │  │     • Generate fixes          │  │
│  │  9. Handle cancellation           │  │     • Verify fixes            │  │
│  │                                   │  │     • Save to database        │  │
│  │                                   │  │  6. Update status to COMPLETED│  │
│  └───────────────────────────────────┘  └───────────────────────────────┘  │
│                            │                          │                     │
│  ┌───────────────────────────────────┐               │                     │
│  │  ingest_project_task              │               │                     │
│  │                                   │               │                     │
│  │  1. Receive project_id            │               │                     │
│  │  2. Update status to CLONING      │               │                     │
│  │  3. Clone Git repo OR extract ZIP │               │                     │
│  │  4. Create workspace directory    │               │                     │
│  │  5. Update status to READY        │               │                     │
│  └───────────────────────────────────┘               │                     │
│                            │                          │                     │
└────────────────────────────┼──────────────────────────┼─────────────────────┘
                             │                          │
                             ↓                          ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                    NUCLEI SCANNER (DAST)     |     OPENAI GPT-4o (SAST)     │
│                                                                              │
│  ┌──────────────────────────────────────┐  │  ┌──────────────────────────┐  │
│  │  Nuclei Binary in Docker             │  │  │  OpenAI API              │  │
│  │                                      │  │  │                          │  │
│  │  • Reads YAML templates              │  │  │  • Receives code         │  │
│  │  • Scans target URL                  │  │  │  • Analyzes for vulns    │  │
│  │  • Outputs findings as JSONL         │  │  │  • Structured outputs    │  │
│  │  • Reports vulnerabilities           │  │  │  • Generates fixes       │  │
│  │  • Configurable parameters           │  │  │  • Verifies fixes        │  │
│  └──────────────────────────────────────┘  │  └──────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Complete Scan Flow Sequence

```
USER ACTION                 SYSTEM RESPONSE                    DATABASE STATE
════════════════════════════════════════════════════════════════════════════

1. Click "Scan" button
                    →   Load scan_create_view
                    →   Fetch user's templates          
                    →   Render template selection form
                        
2. Select templates
   Click "Start Scan"
                    →   Create ScanJob (status=PENDING)  → ScanJob #1 saved
                    →   Dispatch run_specialist_scan         status: PENDING
                    →   Return scan_row.html (HTMX)
                    
3. View dashboard
                    →   Display scan with PENDING badge
                    →   HTMX polls every 3 seconds
                        GET /scan/1/status/
                        
                    ╔═══════════════════════════════════╗
                    ║   CELERY WORKER (Background)      ║
                    ╠═══════════════════════════════════╣
                    ║ 4. Pick up task from queue        ║
                    ║    Update status to RUNNING       ║ → status: RUNNING
                    ║                                   ║
                    ║ 5. Create temp dir                ║
                    ║    /tmp/nuclei_scan_xyz/          ║
                    ║                                   ║
                    ║ 6. Write template files           ║
                    ║    template_1.yaml                ║
                    ║    template_2.yaml                ║
                    ║                                   ║
                    ║ 7. Execute Nuclei command:        ║
                    ║    nuclei -target example.com     ║
                    ║           -t /tmp/nuclei_scan_xyz ║
                    ║           -jsonl -silent          ║
                    ║                                   ║
                    ║ 8. Nuclei scans website           ║
                    ║    Outputs JSONL findings         ║
                    ║                                   ║
                    ║ 9. Parse each JSON line           ║
                    ║    Create ScanResult objects      ║ → ScanResults created
                    ║                                   ║     Finding #1: Critical
                    ║                                   ║     Finding #2: High
                    ║                                   ║     Finding #3: Medium
                    ║                                   ║
                    ║ 10. Cleanup temp directory        ║
                    ║     Update status to COMPLETED    ║ → status: COMPLETED
                    ║     Set completed_at timestamp    ║
                    ╚═══════════════════════════════════╝

11. HTMX polls again
                    →   GET /scan/1/status/
                    →   Return scan_row.html
                    →   Status shows COMPLETED
                    →   "View Results" button appears
                    →   HTMX stops polling (no longer PENDING/RUNNING)

12. Click "View Results"
                    →   GET /scan/1/results/
                    →   Fetch ScanJob & all ScanResults  → Load from DB
                    →   Group by severity
                    →   Render scan_results.html
                    →   Display:
                        • Summary stats
                        • Severity breakdown
                        • Collapsible findings
                        • Raw JSON data

13. Expand finding
                    →   Alpine.js shows details
                    →   Display:
                        • Vulnerability name
                        • Template used
                        • Target URL
                        • Full JSON output

14. Copy JSON
                    →   Click copy button
                    →   JavaScript copies to clipboard
                    →   User can paste elsewhere
```

## Complete SAST Scan Flow Sequence (Phase 4 - NEW)

```
USER ACTION                 SYSTEM RESPONSE                    DATABASE STATE
════════════════════════════════════════════════════════════════════════════

1. Navigate to SAST
                    →   GET /sast/projects/
                    →   Display project list
                        
2. Click "New Project"
                    →   GET /sast/projects/new/
                    →   Show form (Git URL or ZIP upload)
                        
3. Enter Git URL or Upload ZIP
   Click "Create"
                    →   Create Project (status=PENDING)    → Project #1 saved
                    →   Dispatch ingest_project_task           status: PENDING
                    →   Redirect to project_detail
                        
                    ╔═══════════════════════════════════╗
                    ║   CELERY WORKER (Background)      ║
                    ╠═══════════════════════════════════╣
                    ║ 4. Pick up ingest task            ║
                    ║    Update status to CLONING       ║ → status: CLONING
                    ║                                   ║
                    ║ 5. If Git: Clone repository       ║
                    ║    To: media/projects/1/          ║
                    ║    OR                             ║
                    ║    If ZIP: Extract contents       ║
                    ║                                   ║
                    ║ 6. Update status to READY         ║ → status: READY
                    ╚═══════════════════════════════════╝

7. Browse Files
                    →   GET /projects/1/explorer/
                    →   Show directory structure
                    →   Click file to view with syntax highlighting

8. Click "Start SAST Scan"
                    →   Cancel existing active scans
                    →   Create SASTScanJob (status=PENDING) → SASTScanJob #1
                    →   Dispatch run_sast_scan                 status: PENDING
                    →   Redirect to project_detail
                    →   HTMX polls every 3 seconds

                    ╔═══════════════════════════════════╗
                    ║   CELERY WORKER + AI              ║
                    ╠═══════════════════════════════════╣
                    ║ 9. Pick up scan task              ║
                    ║    Update status to SCANNING      ║ → status: SCANNING
                    ║                                   ║
                    ║ 10. Initialize SASTAgent          ║
                    ║     Load agents.md + README.md    ║
                    ║                                   ║
                    ║ 11. List scannable files          ║
                    ║     (.py, .js, .ts, .java, etc.)  ║
                    ║                                   ║
                    ║ 12. For each file:                ║
                    ║     ┌─────────────────────────┐   ║
                    ║     │ Send to OpenAI GPT-4o   │   ║
                    ║     │ With structured output  │   ║
                    ║     │ (Pydantic models)       │   ║
                    ║     └─────────────────────────┘   ║
                    ║                                   ║
                    ║     AI Returns:                   ║
                    ║     • List of vulnerabilities     ║
                    ║     • Line numbers                ║
                    ║     • Severity levels             ║
                    ║     • Descriptions                ║
                    ║     • Code snippets               ║
                    ║                                   ║
                    ║ 13. For each vulnerability:       ║
                    ║     Create SASTFinding            ║ → SASTFinding saved
                    ║                                   ║     severity: HIGH
                    ║     ┌─────────────────────────┐   ║     line: 42
                    ║     │ Generate Fix (AI)       │   ║
                    ║     │ Returns fixed code      │   ║
                    ║     │ + explanation           │   ║
                    ║     └─────────────────────────┘   ║
                    ║                                   ║
                    ║     ┌─────────────────────────┐   ║
                    ║     │ Verify Fix (AI)         │   ║
                    ║     │ Checks if fix is safe   │   ║
                    ║     └─────────────────────────┘   ║
                    ║                                   ║
                    ║     Create SASTFix                ║ → SASTFix saved
                    ║     (status=PENDING)              ║     status: PENDING
                    ║                                   ║
                    ║ 14. Update scan status            ║
                    ║     Set to COMPLETED              ║ → status: COMPLETED
                    ║     Set completed_at              ║
                    ╚═══════════════════════════════════╝

15. HTMX polls again
                    →   GET /scans/1/status/
                    →   Return scan_status.html
                    →   Status shows COMPLETED
                    →   HTMX stops polling

16. View Results
                    →   Scroll to findings section
                    →   See:
                        • Total findings count
                        • Severity breakdown
                        • Finding cards with:
                          - File path + line number
                          - Severity badge
                          - Vulnerability title
                          - AI explanation
                          - Code snippet
                          - Proposed fix
                          - Fix verification status

17. Future: Accept Fix (Phase 5)
                    →   Click "Accept Fix"
                    →   Apply fix to repository
                    →   Create Git branch
                    →   Generate pull request
```

## HTMX Polling Mechanism

```
┌─────────────┐                                    ┌─────────────┐
│  Browser    │                                    │   Server    │
└──────┬──────┘                                    └──────┬──────┘
       │                                                  │
       │ Initial page load: scan_row.html                │
       │ with PENDING status                             │
       │◄─────────────────────────────────────────────────┤
       │                                                  │
       ├──── 3 seconds pass ───────────────────────────► │
       │                                                  │
       │ HTMX: GET /scan/1/status/                       │
       │─────────────────────────────────────────────────►│
       │                                                  │
       │◄────────── scan_row.html (still PENDING) ───────┤
       │                                                  │
       ├──── 3 seconds pass ───────────────────────────► │
       │                                                  │
       │ HTMX: GET /scan/1/status/                       │
       │─────────────────────────────────────────────────►│
       │                                                  │
       │◄────────── scan_row.html (now RUNNING) ─────────┤
       │                                                  │
       ├──── 3 seconds pass ───────────────────────────► │
       │                                                  │
       │ HTMX: GET /scan/1/status/                       │
       │─────────────────────────────────────────────────►│
       │                                                  │
       │◄────────── scan_row.html (COMPLETED) ───────────┤
       │                                                  │
       │ HTMX stops polling (no hx-trigger anymore)      │
       │ "View Results" button now visible               │
       │                                                  │
       └──────────────────────────────────────────────────┘
```

## Data Flow Diagram

```
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│   Website    │──┐   │NucleiTemplate│──┐   │   ScanJob    │
│              │  │   │              │  │   │              │
│ id: 1        │  │   │ id: 5        │  │   │ id: 42       │
│ name: "Blog" │  │   │ name: "XSS"  │  │   │ website_id: 1│
│ url: blog.com│  │   │ content: ... │  │   │ status: PEND │
│ owner_id: 7  │  │   │ owner_id: 7  │  │   │ task_id: abc │
└──────────────┘  │   └──────────────┘  │   └──────────────┘
                  │                     │          │
                  │   ┌──────────────┐  │          │
                  │   │NucleiTemplate│  │          │
                  │   │              │  │          │
                  │   │ id: 8        │  │          │
                  │   │ name: "SQLi" │  │          │
                  │   │ content: ... │  │          │
                  │   │ owner_id: 7  │  │          │
                  │   └──────────────┘  │          │
                  │                     │          │
                  └──────────┬──────────┘          │
                             │                     │
                     User selects both              │
                     templates for scan             │
                             │                     │
                             ▼                     │
                   ┌─────────────────┐             │
                   │ Celery Task     │◄────────────┘
                   │ run_specialist_ │
                   │ scan(42, [5,8]) │
                   └────────┬────────┘
                            │
                            │ Executes Nuclei
                            │ Finds 3 vulnerabilities
                            │
                            ▼
        ┌────────────────────────────────────────┐
        │           ScanResults                  │
        ├────────────────────────────────────────┤
        │ id: 100                                │
        │ job_id: 42                             │
        │ template_name: "XSS Detection"         │
        │ vulnerability: "Reflected XSS"         │
        │ severity: "high"                       │
        │ target_url: "blog.com/search?q=..."   │
        │ raw_finding: {...}                     │
        ├────────────────────────────────────────┤
        │ id: 101                                │
        │ job_id: 42                             │
        │ template_name: "SQL Injection Check"   │
        │ vulnerability: "SQL Injection"         │
        │ severity: "critical"                   │
        │ target_url: "blog.com/post?id=1"      │
        │ raw_finding: {...}                     │
        ├────────────────────────────────────────┤
        │ id: 102                                │
        │ job_id: 42                             │
        │ template_name: "XSS Detection"         │
        │ vulnerability: "Stored XSS"            │
        │ severity: "high"                       │
        │ target_url: "blog.com/comment"        │
        │ raw_finding: {...}                     │
        └────────────────────────────────────────┘
                            │
                            │ User views results
                            ▼
                  ┌──────────────────┐
                  │ Results Display  │
                  ├──────────────────┤
                  │ Critical: 1      │
                  │ High: 2          │
                  │ Medium: 0        │
                  │ Low: 0           │
                  │ Info: 0          │
                  └──────────────────┘
```

## File Organization

```
VulnAssesor/
│
├── Dashboard/
│   ├── models.py           ← 5 models (Website, NucleiTemplate, ScanJob, ScanResult, NucleiConfig)
│   ├── views.py            ← 15+ view functions
│   ├── tasks.py            ← run_specialist_scan
│   ├── admin.py            ← Admin registrations
│   └── migrations/
│       └── 0001-0006_*.py  ← Database migrations
│
├── SAST/                   ← NEW Phase 4 app
│   ├── models.py           ← 4 models (Project, SASTScanJob, SASTFinding, SASTFix)
│   ├── views.py            ← 9 view functions
│   ├── tasks.py            ← ingest_project_task, run_sast_scan
│   ├── agent.py            ← SASTAgent with OpenAI integration
│   ├── services.py         ← ProjectManager for workspace operations
│   ├── sast_tools.py       ← Helper functions
│   ├── urls.py             ← SAST routing
│   └── migrations/
│       └── 0001-0003_*.py  ← SAST migrations
│
├── templates/
│   ├── base.html           ← Updated with Alpine.js
│   ├── dashboard/
│   │   ├── dashboard.html  ← Recent scans + websites
│   │   ├── template_list.html
│   │   ├── template_form.html
│   │   ├── scan_create.html
│   │   ├── scan_row.html         ← HTMX component
│   │   ├── scan_results.html
│   │   └── nuclei_config.html
│   └── sast/               ← NEW Phase 4 templates
│       ├── project_list.html
│       ├── project_create.html
│       ├── project_detail.html
│       └── partials/
│           ├── file_explorer.html
│           ├── file_viewer.html
│           └── scan_status.html
│
├── media/
│   └── projects/           ← NEW: SAST project workspaces
│       └── <project_id>/
│
├── nuclei-templates/       ← Pre-loaded DAST templates
│   ├── security-headers.yaml
│   ├── server-disclosure.yaml
│   └── admin-panels.yaml
│
├── static/css/
│   └── main.css            ← 600+ lines of dark theme
│
├── VulnAssesor/
│   ├── settings.py
│   ├── urls.py             ← 25+ routes (DAST + SAST)
│   ├── celery.py
│   └── wsgi.py
│
├── Dockerfile              ← Nuclei installation + Python deps
├── docker-compose.yaml
├── requirements.txt        ← 11 packages (Django, Celery, OpenAI, Pydantic, GitPython, Pygments)
├── agents.md               ← Complete project specification
├── README.md               ← User documentation
├── ARCHITECTURE_DIAGRAM.md ← This file
├── SAMPLE_NUCLEI_TEMPLATES.md
└── TESTING_CHECKLIST.md
```

## Technology Stack Summary

```
┌─────────────────────────────────────────┐
│         Frontend Technologies           │
├─────────────────────────────────────────┤
│ • HTML5 (Django Templates)              │
│ • CSS3 (Dark Theme, Grid, Flexbox)      │
│ • HTMX 1.9.10 (Dynamic updates)         │
│ • Alpine.js 3.13.3 (Client reactivity)  │
│ • JavaScript (ES6+)                     │
│ • Pygments (Syntax highlighting)        │
└─────────────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────┐
│         Backend Technologies            │
├─────────────────────────────────────────┤
│ • Django 5.2 (Web framework)            │
│ • Python 3.14 (Language)                │
│ • Celery (Task queue)                   │
│ • Redis (Message broker)                │
│ • Pydantic (Data validation)            │
│ • GitPython (Repository handling)       │
└─────────────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────┐
│         Database & Storage              │
├─────────────────────────────────────────┤
│ • PostgreSQL (Production DB)            │
│ • SQLite (Development DB)               │
│ • JSON Fields (Raw findings)            │
│ • Temp filesystem (Template storage)    │
│ • Media storage (Project workspaces)    │
└─────────────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────┐
│      Security & Scanning Tools          │
├─────────────────────────────────────────┤
│ • Nuclei v3.4.10 (DAST scanner)         │
│ • OpenAI GPT-4o (SAST AI engine)        │
│ • YAML (Template format)                │
│ • JSONL (Output parsing)                │
│ • Pydantic (Structured AI outputs)      │
└─────────────────────────────────────────┘
└─────────────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────┐
│        Infrastructure                   │
├─────────────────────────────────────────┤
│ • Docker (Containerization)             │
│ • Docker Compose (Orchestration)        │
│ • Linux (Base OS)                       │
└─────────────────────────────────────────┘
```

---

**Phase 4 Status**: ✅ **COMPLETE & PRODUCTION READY**

**Current Features**:
- ✅ DAST with Nuclei (Phase 3)
- ✅ AI-Powered SAST with OpenAI GPT-4o (Phase 4)
- ✅ Automated fix generation and verification
- ✅ Multi-language code analysis (11 languages)
- ✅ Real-time scanning with HTMX
- ✅ Context-aware AI recommendations

**Next Phase**: 🚀 Phase 5 - Fix Application & Pull Request Automation

