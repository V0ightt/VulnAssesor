# agents.md

## 1. Project Overview

### Technology Stack
* **Backend Framework:** Django 5.2
* **Programming Language:** Python 3.14
* **Frontend Enhancement:** HTMX for dynamic, responsive interactions
* **Database:** PostgreSQL (production), SQLite (development)
* **Message Broker:** Redis
* **Task Queue:** Celery
* **Containerization:** Docker

### UI/UX Design Specifications
* **Theme:** Modern dark theme inspired by GitHub's interface
* **Color Palette:**
  - Primary Background: `#0d1117` (deep dark)
  - Secondary Background: `#161b22` (card/panel background)
  - Tertiary Background: `#21262d` (hover states)
  - Border Color: `#30363d`
  - Text Primary: `#c9d1d9` (light gray)
  - Text Secondary: `#8b949e` (muted gray)
  - Accent Blue: `#58a6ff` (links, primary actions)
  - Success Green: `#3fb950`
  - Warning Yellow: `#d29922`
  - Danger Red: `#f85149`
* **Typography:** System font stack for optimal readability
* **Responsiveness:** Mobile-first design with HTMX-powered dynamic updates
* **Interactions:** Smooth transitions, hover effects, and real-time updates without page reloads

## Project Overview

The project is a web service designed to be a comprehensive security and monitoring hub for websites.

The primary goal is to allow a user to sign in, add their website, and then perform several key actions:
* **SAST (Static Application Security Testing):** Scan their website's source code for vulnerabilities.
* **DAST (Dynamic Application Security Testing):** Scan the live, running website to find weaknesses.
* **Monitoring:** Continuously monitor the site's uptime and security status 24/7.

The **key feature** of this service is the integration of an AI API. This AI will be used to automatically analyze any vulnerability found, explain the risk in simple, plain English, and provide a specific, code-level fix.

## 2. Core Architecture (The "Team")

The system is designed as a modular, asynchronous "team" of components, each with a specialized role.

* **The Dashboard (Django + HTMX Frontend):** This is the user interface, built directly with **Django templates**. It is made fast and interactive using **HTMX**, which allows parts of the page (like scan statuses) to update live without a full page reload.
* **The Manager (Django API Server):** This is the "brain" of the operation. It handles all user requests, manages data, and gives out jobs. In this architecture, it *also* serves the HTMX-powered frontend.
* **The To-Do List (Redis):** This is the message broker that connects the Manager and the Workshop. The Manager assigns a job by placing it on this list. This asynchronous design keeps the frontend fast and responsive.
* **The Workshop (Celery Worker Engines):** These are the background workers that pick up tasks from the Redis "To-Do List" and perform the actual, time-consuming jobs. There are three types of workers:
    * **Code Reviewer (SAST Engine):** Scans code repositories.
    * **Security Tester (DAST Engine):** Probes the live website.
    * **Night Watchman (Monitoring Engine):** Pings the site for uptime and performs other checks.
* **The Filing Cabinet (PostgreSQL Database):** This is the system's permanent memory. It stores all essential data, including user information, website details, scan results, and uptime history.
* **External Services:**
    * **AI API:** Used by the Workshop (Celery Workers) to analyze vulnerabilities and get explanations/fixes.
    * **Docker:** The entire system (Manager, Workshop, Database, etc.) is bundled with Docker, which makes it easy to deploy and scale.



[Image of the system's core architecture diagram]


## 3. How a Scan Works (The Workflow)

The entire process is designed to be asynchronous, providing the user with an immediate response while the heavy work happens in the background.

1.  **User Request:** The user clicks the "Start Scan" button on the Dashboard. This sends an **HTMX request** to the Django Manager.
2.  **Job Assignment:** The request is handled by a Django view. The Manager immediately creates a new "Scan Job" in the database and places this job onto the Redis "To-Do List".
3.  **Immediate Feedback:** The Manager's view instantly responds to the HTMX request by returning a **small HTML snippet** of the new "Pending" scan. HTMX swaps this snippet directly into the page, so the user sees the update *without* a page reload.
4.  **Heavy Lifting:** A Celery Worker in the Workshop, which is constantly monitoring the Redis list, picks up the new job.
5.  **Execution:** The Worker runs the actual scan (e.g., a DAST scan), which might take several minutes.
6.  **AI Analysis:** For each vulnerability the Worker finds, it sends the technical details to the external AI API.
7.  **Filing the Report:** The AI API returns a plain-English explanation and a code-level fix. The Worker takes this "enriched" data and saves the complete, final report in the PostgreSQL "Filing Cabinet".
8.  **Viewing Results:** The user, on the Dashboard, sees the scan status update to "Complete" (this can be done by having HTMX poll a status-check URL). They can then click to view the full report.