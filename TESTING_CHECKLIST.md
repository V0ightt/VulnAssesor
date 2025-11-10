# Phase 3 Testing Checklist

## Pre-Testing Setup

- [ ] Migrations have been applied
- [ ] Docker containers are running (if using Docker)
- [ ] Celery worker is running
- [ ] Redis is accessible
- [ ] Nuclei is installed (check with `nuclei -version` in container)
- [ ] At least one user account exists
- [ ] At least one website has been added

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

## Final Verification

- [ ] No errors in browser console
- [ ] No errors in Django server logs
- [ ] No errors in Celery worker logs
- [ ] All pages load in < 2 seconds
- [ ] UI is consistent and professional
- [ ] Dark theme is applied everywhere
- [ ] All animations are smooth
- [ ] User experience is intuitive

## Sign-Off

Date Tested: _______________

Tester: _______________

Issues Found: _______________

Status: ⬜ Pass ⬜ Fail ⬜ Partial

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

# 2. Check Nuclei
docker-compose exec web nuclei -version

# 3. Check database
docker-compose exec web python manage.py dbshell
\dt  # List tables
\d Dashboard_nucleitemplate  # Describe table
\d Dashboard_scanjob
\d Dashboard_scanresult

# 4. Create test data
docker-compose exec web python manage.py shell
from Dashboard.models import *
from django.contrib.auth.models import User
user = User.objects.first()
# Create test template, scan, etc.

# 5. Monitor logs in real-time
docker-compose logs -f celery
```

## Automated Test Suite (Future)

Consider implementing:
- [ ] Unit tests for models
- [ ] Unit tests for views
- [ ] Integration tests for scan workflow
- [ ] Selenium tests for UI
- [ ] Load tests with Locust
- [ ] API tests with pytest

---

**Testing Status**: ⬜ Not Started ⬜ In Progress ⬜ Complete

**Ready for Production**: ⬜ Yes ⬜ No ⬜ With Fixes

