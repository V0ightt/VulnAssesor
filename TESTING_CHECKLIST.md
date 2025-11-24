# Phase 4 Testing Checklist (DAST + SAST with AI)

## Pre-Testing Setup

### General Setup
- [ ] Migrations have been applied (Dashboard + SAST apps)
- [ ] Docker containers are running (if using Docker)
- [ ] Celery worker is running
- [ ] Redis is accessible
- [ ] At least one user account exists

### DAST Setup
- [ ] Nuclei is installed (check with `nuclei -version` in container)
- [ ] At least one website has been added
- [ ] At least one Nuclei template exists

### SAST Setup (NEW - Phase 4)
- [ ] OpenAI API key is set as environment variable (`OPENAI_API_KEY`)
- [ ] Media directory is writable (`media/projects/`)
- [ ] Git is available in the environment (for Git cloning)
- [ ] Test project/repository is available

---

## DAST (Dynamic Scanning) Tests

## Template Management Tests

### Template List View
- [ ] Navigate to `/templates/`
- [ ] Page loads without errors
- [ ] Empty state shows if no templates exist
- [ ] "Create Template" button is visible
- [ ] Templates are displayed in grid layout (if any exist)
- [ ] Each template card shows name, description, and date
- [ ] Edit and Delete buttons are present on each card

### Template Creation
- [ ] Click "Create Template" button
- [ ] Form loads with all fields (name, description, template_content)
- [ ] "Insert Sample Template" button works
- [ ] Can paste custom YAML content
- [ ] Form validation works (try submitting empty form)
- [ ] Success message appears after creation
- [ ] Redirected to template list after save
- [ ] New template appears in the list

### Template Editing
- [ ] Click Edit button on a template
- [ ] Form loads with existing data pre-filled
- [ ] Can modify name, description, and content
- [ ] Changes are saved successfully
- [ ] Success message appears
- [ ] Redirected to template list
- [ ] Changes are reflected in the list

### Template Deletion
- [ ] Click Delete button on a template
- [ ] Alpine.js modal appears with confirmation
- [ ] Modal shows template name
- [ ] "Cancel" button closes modal without deleting
- [ ] "Delete" button removes the template
- [ ] Template disappears from list immediately (HTMX)
- [ ] No page reload occurs

## Scan Management Tests

### Scan Creation - No Templates
- [ ] Remove all templates (or test with new user)
- [ ] Click scan button (⚡) on a website
- [ ] Warning message appears: "No templates available"
- [ ] Link to create template is shown
- [ ] Cannot start scan without templates

### Scan Creation - With Templates
- [ ] Ensure at least 2 templates exist
- [ ] Click scan button (⚡) on a website
- [ ] Scan creation page loads
- [ ] Website name and URL are displayed
- [ ] All templates are listed with checkboxes
- [ ] No templates are selected initially
- [ ] "Select All" button selects all templates
- [ ] "Deselect All" button clears all selections
- [ ] Selection count updates correctly
- [ ] "Start Scan" button is enabled when templates selected
- [ ] "Start Scan" button is disabled when no templates selected

### Scan Execution
- [ ] Select at least one template
- [ ] Click "Start Scan"
- [ ] Success message appears
- [ ] Redirected to dashboard
- [ ] New scan appears in "Recent Scans" table
- [ ] Scan shows PENDING status with spinner
- [ ] Scan ID, website name, and URL are visible

### Real-time Status Updates (HTMX Polling)
- [ ] Watch the scan in Recent Scans section
- [ ] Status changes from PENDING to RUNNING (check Celery logs)
- [ ] Spinner icon is visible during PENDING/RUNNING
- [ ] Status badge color changes appropriately
- [ ] After scan completes, status changes to COMPLETED
- [ ] Green checkmark appears for COMPLETED status
- [ ] Polling stops after completion (check Network tab)
- [ ] "View Results" button appears when COMPLETED
- [ ] Finding count is displayed (e.g., "3 findings")

### Scan Results - No Findings
- [ ] Create a scan that won't find anything (use non-matching template)
- [ ] Wait for completion
- [ ] Click "View Results"
- [ ] Empty state shows: "No Vulnerabilities Found"
- [ ] Positive message is displayed
- [ ] Summary shows 0 findings

### Scan Results - With Findings
- [ ] Create a scan that will find vulnerabilities
- [ ] Wait for completion
- [ ] Click "View Results"
- [ ] Results page loads successfully
- [ ] Summary section shows:
  - [ ] Target URL
  - [ ] Total findings count
  - [ ] Start time
  - [ ] Completion time
- [ ] Severity breakdown shows counts for each level
- [ ] Severity stats have appropriate colors (critical=red, high=orange, etc.)
- [ ] Results are listed below, grouped or sorted by severity
- [ ] Each result shows:
  - [ ] Severity badge
  - [ ] Vulnerability name
  - [ ] Expand/collapse arrow

### Result Details Expansion
- [ ] Click on a result to expand it
- [ ] Alpine.js smoothly expands the details
- [ ] Expanded view shows:
  - [ ] Template name
  - [ ] Target URL (clickable link)
  - [ ] Detection timestamp
  - [ ] Raw JSON data
- [ ] Click "Copy" button on raw JSON
- [ ] JSON is copied to clipboard
- [ ] Click result again to collapse
- [ ] Details hide smoothly

## Dashboard Integration Tests

### Recent Scans Section
- [ ] Recent scans section is visible on dashboard
- [ ] Shows up to 10 most recent scans
- [ ] Each scan row includes all necessary information
- [ ] Multiple scans can poll simultaneously
- [ ] No performance issues with multiple active scans

### Website Actions
- [ ] Scan button (⚡) is visible on each website row
- [ ] Button has tooltip: "Start Scan"
- [ ] Button is styled correctly (blue, lightning icon)
- [ ] Clicking opens scan creation page
- [ ] Edit and Delete buttons still work as before

### Navigation
- [ ] "Templates" link is visible in navbar
- [ ] Clicking navigates to template list
- [ ] "Dashboard" link returns to main dashboard
- [ ] All navigation is smooth without errors

## Error Handling Tests

### Template Errors
- [ ] Try creating template with only name (no content)
- [ ] Error message appears
- [ ] Try creating template with invalid YAML
- [ ] Scan may fail with appropriate error message

### Scan Errors
- [ ] Try starting scan with no templates selected
- [ ] Error message appears: "Please select at least one template"
- [ ] Delete all templates while scan is pending
- [ ] Scan continues or handles gracefully

### Network Errors
- [ ] Simulate Celery being down
- [ ] Scan stays in PENDING indefinitely
- [ ] Status can still be viewed
- [ ] No JavaScript errors in console

### Permission Tests
- [ ] Create second user account
- [ ] User A cannot see User B's templates
- [ ] User A cannot edit User B's templates
- [ ] User A cannot see User B's scan results
- [ ] User A cannot access User B's scans via URL manipulation

## Performance Tests

### Load Testing
- [ ] Create 10+ templates
- [ ] Template list loads quickly
- [ ] Grid layout is responsive
- [ ] Create 10+ scans
- [ ] Dashboard loads without delay
- [ ] HTMX polling doesn't cause lag

### Long Running Scans
- [ ] Start a scan that takes 2+ minutes
- [ ] HTMX continues polling
- [ ] Page remains responsive
- [ ] Can navigate away and return
- [ ] Status is still updating when returning

## Mobile Responsiveness

- [ ] Open site on mobile device or resize browser to mobile width
- [ ] Navigation menu is accessible
- [ ] Template grid adapts to single column
- [ ] Scan creation form is usable
- [ ] Results page is readable
- [ ] Tables scroll horizontally if needed
- [ ] Buttons are tap-friendly

## Browser Compatibility

### Chrome
- [ ] All features work
- [ ] HTMX polling works
- [ ] Alpine.js modals work
- [ ] No console errors

### Firefox
- [ ] All features work
- [ ] HTMX polling works
- [ ] Alpine.js modals work
- [ ] No console errors

### Edge
- [ ] All features work
- [ ] HTMX polling works
- [ ] Alpine.js modals work
- [ ] No console errors

### Safari (if available)
- [ ] All features work
- [ ] HTMX polling works
- [ ] Alpine.js modals work
- [ ] No console errors

## Accessibility Tests

- [ ] Tab navigation works through all forms
- [ ] All buttons are keyboard accessible
- [ ] Form fields have proper labels
- [ ] Error messages are announced
- [ ] Color contrast is sufficient (dark theme)
- [ ] Alt text on icons (where applicable)

## Security Tests

- [ ] CSRF tokens are present on all forms
- [ ] Cannot access other users' data via URL manipulation
- [ ] XSS attempts in template content are handled safely
- [ ] SQL injection attempts in forms are prevented
- [ ] Template content is not executed as code

## Integration Tests

### Full Workflow Test
1. [ ] Register new user
2. [ ] Add a website
3. [ ] Create 2-3 templates (use samples)
4. [ ] Start scan with all templates
5. [ ] Watch status progress
6. [ ] View results
7. [ ] Expand multiple findings
8. [ ] Copy JSON data
9. [ ] Edit a template
10. [ ] Run another scan with edited template
11. [ ] Delete old scan results (future feature)
12. [ ] Delete unused template
13. [ ] Logout and login again
14. [ ] Verify all data persists

## Celery Worker Tests

- [ ] Check Celery logs for task execution
- [ ] Verify no errors in worker logs
- [ ] Confirm tasks complete successfully
- [ ] Check that temporary directories are cleaned up
- [ ] Verify task timeouts work (if scan takes > 10 minutes)

## Database Tests

- [ ] Verify all migrations applied: `python manage.py showmigrations`
- [ ] Check database has new tables (nucleitemplate, scanjob, scanresult)
- [ ] Verify foreign key relationships are correct
- [ ] Check that CASCADE deletes work (delete website → scans deleted)
- [ ] Verify data integrity after multiple operations

## Docker-Specific Tests (if using Docker)

- [ ] `docker-compose ps` shows all services running
- [ ] Web service is accessible
- [ ] Celery service is running
- [ ] Redis service is running
- [ ] Database service is running
- [ ] Nuclei is installed in web container: `docker-compose exec web nuclei -version`
- [ ] Logs are accessible: `docker-compose logs web`, `docker-compose logs celery`

## Edge Cases

- [ ] Start scan, immediately delete website (should handle gracefully)
- [ ] Create template with very large content (>10KB YAML)
- [ ] Create 100+ scan results (pagination future feature)
- [ ] Run simultaneous scans on same website
- [ ] Scan a non-existent URL (should timeout or fail gracefully)
- [ ] Template with syntax errors (Nuclei should report)

---

## SAST (Static Analysis with AI) Tests (Phase 4 - NEW)

### Project Creation - Git Repository

- [ ] Navigate to `/sast/projects/`
- [ ] Click "New Project" button
- [ ] Form loads with Git URL and ZIP upload options
- [ ] Enter a valid Git repository URL
- [ ] Enter project name
- [ ] Click "Create Project"
- [ ] Success message appears
- [ ] Redirected to project detail page
- [ ] Project status shows "PENDING" or "CLONING"
- [ ] Status updates to "READY" when cloning completes
- [ ] Check Celery logs for ingest task execution

### Project Creation - ZIP Upload

- [ ] Create a ZIP file with source code (.py, .js, etc.)
- [ ] Navigate to `/sast/projects/new/`
- [ ] Enter project name
- [ ] Upload ZIP file
- [ ] Click "Create Project"
- [ ] Success message appears
- [ ] Project status shows "CLONING"
- [ ] Status updates to "READY" when extraction completes
- [ ] Workspace directory created in `media/projects/<id>/`

### File Explorer

- [ ] Once project is READY, file explorer loads
- [ ] Directory structure is displayed
- [ ] Folders show with folder icon
- [ ] Files show with file icon
- [ ] Click on a folder to navigate into it
- [ ] Breadcrumb navigation works
- [ ] Click on a file to view it
- [ ] File viewer loads with syntax highlighting
- [ ] Code is formatted correctly (Monokai theme)
- [ ] Line numbers are visible
- [ ] Syntax highlighting matches file type (.py=Python, .js=JavaScript, etc.)
- [ ] Can navigate back to parent directory

### SAST Scan Initiation

- [ ] Project is in READY status
- [ ] "Start SAST Scan" button is visible
- [ ] Click "Start SAST Scan"
- [ ] Any existing PENDING/SCANNING scans are cancelled
- [ ] New SASTScanJob is created with status="PENDING"
- [ ] Redirected to project detail page
- [ ] Scan appears in "Latest Scan" section
- [ ] HTMX polling starts (check Network tab)
- [ ] Status badge shows "PENDING" with spinner

### Real-Time Scan Status Updates (AI Scanning)

- [ ] Watch scan status update via HTMX
- [ ] Status changes: PENDING → SCANNING
- [ ] Spinner/loading indicator is visible
- [ ] Status badge color changes (yellow for SCANNING)
- [ ] Check Celery logs for scan progress
- [ ] AI makes requests to OpenAI API (check logs)
- [ ] After completion, status changes to COMPLETED
- [ ] Green checkmark appears
- [ ] HTMX polling stops
- [ ] Completion timestamp is displayed

### Scan Cancellation

- [ ] Start a SAST scan
- [ ] While status is PENDING or SCANNING, click "Cancel Scan"
- [ ] Status updates to CANCELLED
- [ ] Scan stops processing files
- [ ] Can start a new scan after cancellation

### SAST Results - No Findings

- [ ] Scan a project with clean, secure code
- [ ] Wait for scan to complete
- [ ] Results section shows "No vulnerabilities found"
- [ ] Positive message is displayed
- [ ] Scan summary shows 0 findings

### SAST Results - With Findings

- [ ] Scan a project with known vulnerabilities
- [ ] Wait for scan to complete (may take 1-10 minutes)
- [ ] Findings section displays
- [ ] Summary shows total finding counts by severity
- [ ] Severity breakdown: CRITICAL, HIGH, MEDIUM, LOW, INFO
- [ ] Each finding card shows:
  - [ ] File path
  - [ ] Line number
  - [ ] Severity badge (color-coded)
  - [ ] Vulnerability title
  - [ ] Description
  - [ ] AI-generated explanation (plain English)
  - [ ] Code snippet showing vulnerable code
  - [ ] Proposed fix section

### AI-Generated Fixes

- [ ] Each finding has a "Proposed Fix" section
- [ ] Fixed code is displayed
- [ ] Explanation of the fix is provided
- [ ] Fix verification status is shown
- [ ] Verified fixes are marked with checkmark
- [ ] Unverified/failed fixes are marked with warning

### Fix Verification

- [ ] Check findings that passed verification
- [ ] Verification reasoning is displayed
- [ ] Check findings that failed verification
- [ ] Failure reasoning is displayed
- [ ] Both types of fixes are saved and visible

### Scan History

- [ ] Project detail page shows "Recent Scans" section
- [ ] Last 10 scans are listed
- [ ] Each scan shows:
  - [ ] Scan ID
  - [ ] Status
  - [ ] Start time
  - [ ] Finding counts
- [ ] Can click on historical scan to view results
- [ ] Newest scans appear first

### Multi-Language Support

- [ ] Test with Python files (.py) - syntax highlighting works
- [ ] Test with JavaScript files (.js) - AI detects JS vulnerabilities
- [ ] Test with TypeScript files (.ts)
- [ ] Test with Java files (.java)
- [ ] Test with C files (.c)
- [ ] Test with Go files (.go)
- [ ] Test with PHP files (.php)
- [ ] Test with HTML files (.html)
- [ ] Test with CSS files (.css)
- [ ] All supported languages are scanned and highlighted correctly

### Context-Aware Analysis

- [ ] Create a project with `agents.md` file
- [ ] Create a project with `README.md` file
- [ ] Start SAST scan
- [ ] Check Celery logs - AI reads context files
- [ ] AI recommendations reference project architecture
- [ ] Context files limited to 2000 chars (check truncation)

### OpenAI API Integration

- [ ] Verify `OPENAI_API_KEY` is set
- [ ] Scan starts successfully
- [ ] Check Celery logs for API requests
- [ ] API responses include structured data (Pydantic)
- [ ] Handle API rate limiting gracefully (if applicable)
- [ ] Handle API errors without crashing scan

### Project Deletion

- [ ] Navigate to project detail page
- [ ] Click "Delete Project" button
- [ ] Confirmation modal appears (if implemented)
- [ ] Confirm deletion
- [ ] Project is removed from database
- [ ] Workspace directory is deleted (`media/projects/<id>/`)
- [ ] Associated scans are deleted (CASCADE)
- [ ] Associated findings are deleted (CASCADE)
- [ ] Redirected to project list

### Error Handling - SAST

- [ ] Try creating project without Git URL or ZIP file
- [ ] Error message appears
- [ ] Try invalid Git URL
- [ ] Ingest task fails gracefully, status="FAILED"
- [ ] Try uploading invalid ZIP file
- [ ] Error is handled, status="FAILED"
- [ ] Start scan without OpenAI API key
- [ ] Scan fails with clear error message
- [ ] Simulate OpenAI API being down
- [ ] Error is logged, scan fails gracefully

### Permission Tests - SAST

- [ ] Create second user account
- [ ] User A cannot see User B's projects
- [ ] User A cannot access User B's project detail via URL
- [ ] User A cannot delete User B's projects
- [ ] User A cannot start scans on User B's projects

### Performance Tests - SAST

- [ ] Scan a small project (5-10 files)
- [ ] Scan completes in reasonable time (< 5 minutes)
- [ ] Scan a medium project (20-50 files)
- [ ] Scan completes without errors (5-15 minutes)
- [ ] Scan a large project (100+ files)
- [ ] Monitor performance, check for timeout issues
- [ ] Multiple files scanned without memory issues

### Integration - DAST + SAST

- [ ] User has both websites and projects
- [ ] Dashboard shows both DAST and SAST scans
- [ ] Can navigate between DAST and SAST sections
- [ ] Both scan types use same HTMX polling mechanism
- [ ] No conflicts or interference between scan types

---

## Final Verification

- [ ] No errors in browser console
- [ ] No errors in Django server logs
- [ ] No errors in Celery worker logs
- [ ] All DAST pages load in < 2 seconds
- [ ] All SAST pages load in < 2 seconds (excluding AI processing)
- [ ] UI is consistent and professional
- [ ] Dark theme is applied everywhere (DAST and SAST)
- [ ] All animations are smooth
- [ ] User experience is intuitive
- [ ] OpenAI API key is secure (environment variable)
- [ ] Project workspaces are properly isolated

## Sign-Off

Date Tested: _______________

Tester: _______________

Issues Found: _______________

Phase 3 (DAST): ⬜ Pass ⬜ Fail ⬜ Partial

Phase 4 (SAST): ⬜ Pass ⬜ Fail ⬜ Partial

Overall Status: ⬜ Pass ⬜ Fail ⬜ Partial

Notes:
_________________________________
_________________________________
_________________________________

---

## Quick Test Script

For rapid testing, run these commands:

```bash
# 1. Check services
docker-compose ps

# 2. Check Nuclei (DAST)
docker-compose exec web nuclei -version

# 3. Check OpenAI API key (SAST)
docker-compose exec web python -c "import os; print('API Key:', 'SET' if os.getenv('OPENAI_API_KEY') else 'NOT SET')"

# 4. Check database tables
docker-compose exec web python manage.py dbshell
\dt  # List tables
\d Dashboard_nucleitemplate  # DAST tables
\d Dashboard_scanjob
\d Dashboard_scanresult
\d SAST_project              # SAST tables
\d SAST_sastscanjob
\d SAST_sastfinding
\d SAST_sastfix

# 5. Create test DAST data
docker-compose exec web python manage.py shell
from Dashboard.models import *
from django.contrib.auth.models import User
user = User.objects.first()
# Create test template, scan, etc.

# 6. Create test SAST data
from SAST.models import *
project = Project.objects.create(name="Test", repository_url="https://github.com/user/repo", owner=user)

# 7. Monitor DAST logs in real-time
docker-compose logs -f celery | grep specialist

# 8. Monitor SAST logs in real-time
docker-compose logs -f celery | grep sast

# 9. Check project workspaces
ls -la media/projects/
```

## Automated Test Suite (Future)

Consider implementing:
- [ ] Unit tests for Dashboard models
- [ ] Unit tests for SAST models
- [ ] Unit tests for Dashboard views
- [ ] Unit tests for SAST views
- [ ] Integration tests for DAST scan workflow
- [ ] Integration tests for SAST scan workflow with mock OpenAI
- [ ] Selenium tests for UI (both DAST and SAST)
- [ ] Load tests with Locust
- [ ] API tests with pytest
- [ ] AI response validation tests
- [ ] Fix generation tests
- [ ] Workspace isolation tests

---

**Testing Status**: 
- Phase 3 (DAST): ⬜ Not Started ⬜ In Progress ⬜ Complete
- Phase 4 (SAST): ⬜ Not Started ⬜ In Progress ⬜ Complete

**Ready for Production**: ⬜ Yes ⬜ No ⬜ With Fixes

**AI Integration Working**: ⬜ Yes ⬜ No ⬜ Partial

