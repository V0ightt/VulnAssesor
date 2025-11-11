# Pre-Deployment Verification Checklist
## VulnAssesor v1.1.0 - November 11, 2025

Use this checklist to verify all enhancements are working correctly before deploying to production.

---

## ✅ PRE-DEPLOYMENT SETUP

### 1. Database Migrations
```bash
# Apply all migrations
python manage.py migrate Dashboard

# Verify migrations applied
python manage.py showmigrations Dashboard

# Expected output should show:
# [X] 0001_initial
# [X] 0002_nucleitemplate_scanjob_scanresult
# [X] 0003_nucleiconfig
# [X] 0004_add_scan_cancellation
# [X] 0005_add_performance_indexes
```
- [ ] All migrations applied successfully
- [ ] No migration errors in logs

### 2. Static Files
```bash
python manage.py collectstatic --noinput
```
- [ ] CSS files collected
- [ ] main.css includes new styles (.status-cancelled, .btn-danger)

### 3. Celery Worker
```bash
# Check worker is running
celery -A VulnAssesor inspect active

# Or in Docker
docker-compose ps
```
- [ ] Celery worker is running
- [ ] Redis is accessible
- [ ] Worker can process tasks

---

## ✅ FEATURE TESTING

### Feature 1: Scan Cancellation

#### Test 1.1: Cancel PENDING Scan
1. Create a new scan (don't let it start)
2. Immediately click "Cancel Scan" button
3. Confirm the dialog

**Expected Results:**
- [ ] Status changes to "Cancelled"
- [ ] Shows "Cancelled by {username}"
- [ ] No full page reload occurs
- [ ] Scan never enters RUNNING state

#### Test 1.2: Cancel RUNNING Scan
1. Create a scan with a slow target (use example.com with many templates)
2. Wait for status to become "Running"
3. Click "Cancel Scan"
4. Confirm

**Expected Results:**
- [ ] Process stops within 2-5 seconds
- [ ] Status changes to "Cancelled"
- [ ] Celery task is terminated
- [ ] No orphan nuclei processes running

#### Test 1.3: Cannot Cancel COMPLETED Scan
1. Let a scan complete
2. Look for cancel button

**Expected Results:**
- [ ] No cancel button visible
- [ ] Shows "View Results" button instead

#### Test 1.4: Cancellation Persistence
1. Cancel a scan
2. Refresh the page

**Expected Results:**
- [ ] Status remains "Cancelled"
- [ ] Cancelled_by information persists

---

### Feature 2: Infinite Scan Prevention

#### Test 2.1: Max Host Errors Configuration
1. Go to Nuclei Configuration
2. Check max_host_errors field exists
3. Change value to 10
4. Save

**Expected Results:**
- [ ] Field is visible and editable
- [ ] Value saves correctly
- [ ] Min value is 1, max is 100

#### Test 2.2: Max Host Errors in Command
1. Set max_host_errors to 25
2. Check command preview

**Expected Results:**
- [ ] Command includes `-max-host-error 25`
- [ ] Preview updates when value changes

#### Test 2.3: Scan Stops After Max Errors
1. Create scan targeting invalid/unresponsive host
2. Monitor scan execution
3. Check logs

**Expected Results:**
- [ ] Scan stops after configured errors
- [ ] Doesn't run indefinitely
- [ ] Status becomes COMPLETED or FAILED

---

### Feature 3: HTMX Polling (No Full Reloads)

#### Test 3.1: Scan Row Updates
1. Create a new scan
2. Watch the dashboard (don't refresh manually)
3. Observe status changes

**Expected Results:**
- [ ] Status badge updates automatically every 3 seconds
- [ ] Page doesn't reload
- [ ] Only the scan row changes
- [ ] Browser network tab shows XHR requests to /scan/X/status/

#### Test 3.2: Polling Stops When Complete
1. Create a short scan
2. Let it complete
3. Watch network tab

**Expected Results:**
- [ ] Polling continues while PENDING/RUNNING
- [ ] Polling stops when COMPLETED
- [ ] No more requests after completion

#### Test 3.3: Multiple Scans Polling
1. Create 3 scans quickly
2. Watch all three update

**Expected Results:**
- [ ] All scans poll independently
- [ ] Each updates its own row
- [ ] No interference between scans

---

### Feature 4: Live Command Preview

#### Test 4.1: Timeout Changes
1. Go to Nuclei Configuration
2. Change timeout from 600 to 300
3. Watch command preview (don't save yet)

**Expected Results:**
- [ ] Preview updates immediately
- [ ] Shows `-timeout 300`
- [ ] No page reload
- [ ] Changes before saving

#### Test 4.2: Checkbox Changes
1. Toggle "Silent Mode" checkbox
2. Watch preview

**Expected Results:**
- [ ] Preview adds/removes `-silent` flag
- [ ] Updates instantly on toggle

#### Test 4.3: Rate Limit Changes
1. Change rate limit to 100
2. Watch preview

**Expected Results:**
- [ ] Shows `-rate-limit 100`
- [ ] Updates as you type

#### Test 4.4: Custom Args
1. Type `-proxy http://localhost:8080` in custom args
2. Watch preview

**Expected Results:**
- [ ] Custom args appear at end of command
- [ ] Updates while typing

#### Test 4.5: All Fields Together
1. Change timeout, rate_limit, concurrency
2. Toggle all checkboxes
3. Add custom args
4. Watch preview update for each change

**Expected Results:**
- [ ] All changes reflected immediately
- [ ] Command syntax is correct
- [ ] No JavaScript errors in console

---

### Feature 5: Database Performance

#### Test 5.1: Dashboard Query Count
1. Create 50+ scans (use script or manually)
2. Enable Django query logging:
```python
# In settings.py temporarily
LOGGING = {
    'version': 1,
    'handlers': {
        'console': {'class': 'logging.StreamHandler'},
    },
    'loggers': {
        'django.db.backends': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
    },
}
```
3. Load dashboard page
4. Count queries in terminal

**Expected Results:**
- [ ] Less than 5 queries for dashboard
- [ ] No N+1 query patterns
- [ ] Page loads in < 500ms

#### Test 5.2: Scan Results Query Count
1. Create scan with 100+ results
2. Visit results page
3. Check query count

**Expected Results:**
- [ ] Less than 10 queries
- [ ] No query per result
- [ ] Severity grouping is fast

#### Test 5.3: Index Usage
```bash
# In PostgreSQL
EXPLAIN ANALYZE SELECT * FROM "Dashboard_scanjob" 
WHERE status = 'RUNNING' 
ORDER BY created_at DESC;
```

**Expected Results:**
- [ ] Query uses index
- [ ] Execution time < 10ms
- [ ] No sequential scan

---

## ✅ UI/UX TESTING

### User Experience Checks

#### Test UX.1: No Unexpected Page Reloads
1. Complete entire workflow: add website → create scan → cancel → view results
2. Monitor browser for full page reloads

**Expected Results:**
- [ ] No full page reload during scan operations
- [ ] Smooth transitions
- [ ] URL doesn't change unnecessarily

#### Test UX.2: Loading States
1. Create scan
2. Watch for visual feedback

**Expected Results:**
- [ ] Spinner shows on pending/running
- [ ] Status badges have appropriate colors
- [ ] No "jumping" or layout shifts

#### Test UX.3: Error Messages
1. Try to save invalid nuclei config (e.g., timeout = -1)
2. Try to cancel completed scan (via URL manipulation)

**Expected Results:**
- [ ] Clear error messages
- [ ] No 500 errors
- [ ] User-friendly wording

#### Test UX.4: Mobile Responsiveness
1. Open dashboard on mobile device or resize browser
2. Test all features

**Expected Results:**
- [ ] Buttons are tappable
- [ ] Text is readable
- [ ] No horizontal scrolling
- [ ] Modals work correctly

---

## ✅ SECURITY TESTING

### Security Checks

#### Test SEC.1: Authorization - Cancel Other User's Scan
1. Login as user A
2. Create scan (note scan ID)
3. Logout, login as user B
4. Try to POST to `/scan/{scan_id_from_user_A}/cancel/`

**Expected Results:**
- [ ] Returns 404 or 403
- [ ] Scan is NOT cancelled
- [ ] No unauthorized access

#### Test SEC.2: CSRF Protection
1. Try POST to cancel endpoint without CSRF token
```bash
curl -X POST http://localhost:8000/scan/1/cancel/
```

**Expected Results:**
- [ ] Returns 403 Forbidden
- [ ] Scan not cancelled

#### Test SEC.3: SQL Injection
1. Try cancelling with malicious scan ID:
```
/scan/1' OR '1'='1/cancel/
```

**Expected Results:**
- [ ] Returns 404
- [ ] No SQL error
- [ ] Django ORM protects against injection

#### Test SEC.4: XSS in Custom Args
1. Enter in custom args: `<script>alert('xss')</script>`
2. Save and view command preview

**Expected Results:**
- [ ] Script not executed
- [ ] Text is escaped in HTML
- [ ] No alert popup

---

## ✅ PERFORMANCE TESTING

### Load Tests

#### Test PERF.1: Dashboard with Many Scans
1. Create 100 scans (use script)
2. Load dashboard
3. Measure time

**Expected Results:**
- [ ] Loads in < 1 second
- [ ] No timeout errors
- [ ] Smooth scrolling

#### Test PERF.2: Concurrent Scans
1. Start 5 scans simultaneously
2. Watch Celery worker

**Expected Results:**
- [ ] All scans process
- [ ] No deadlocks
- [ ] Worker doesn't crash

#### Test PERF.3: HTMX Polling Load
1. Have 10 active scans polling
2. Monitor server resources

**Expected Results:**
- [ ] CPU usage acceptable
- [ ] No memory leaks
- [ ] Server responds quickly

---

## ✅ ERROR HANDLING

### Edge Cases

#### Test ERR.1: Nuclei Not Installed
1. Temporarily rename nuclei binary
2. Try to start scan

**Expected Results:**
- [ ] Graceful error message
- [ ] Scan status = FAILED
- [ ] Error details stored

#### Test ERR.2: Redis Down
1. Stop Redis
2. Try to create scan

**Expected Results:**
- [ ] User-friendly error
- [ ] No 500 error page
- [ ] System remains stable

#### Test ERR.3: Database Connection Lost
1. Simulate DB disconnect during scan

**Expected Results:**
- [ ] Task retries or fails gracefully
- [ ] No data corruption
- [ ] Error logged

#### Test ERR.4: Invalid Nuclei Config
1. Set rate_limit to invalid value via Django admin
2. Try to run scan

**Expected Results:**
- [ ] Validation prevents save OR
- [ ] Scan fails with clear error

---

## ✅ INTEGRATION TESTING

### Full Workflow Tests

#### Test INT.1: Complete Scan Lifecycle
1. Register new user
2. Add website
3. Create custom template
4. Start scan with template
5. Watch it run
6. View results
7. Start second scan
8. Cancel it

**Expected Results:**
- [ ] All steps work smoothly
- [ ] No errors
- [ ] Data is correct
- [ ] User experience is good

#### Test INT.2: Configuration Persistence
1. Change all nuclei config settings
2. Save
3. Create scan
4. Check Celery logs for actual command used

**Expected Results:**
- [ ] Scan uses new settings
- [ ] Command matches preview
- [ ] Settings persist across scans

---

## ✅ BROWSER COMPATIBILITY

Test on:
- [ ] Chrome/Edge (latest)
- [ ] Firefox (latest)
- [ ] Safari (latest)
- [ ] Mobile Chrome
- [ ] Mobile Safari

Check:
- [ ] HTMX works
- [ ] Alpine.js works
- [ ] CSS renders correctly
- [ ] No console errors

---

## ✅ DOCUMENTATION

- [ ] ENHANCEMENTS_SUMMARY.md is accurate
- [ ] QUICK_REFERENCE.md is complete
- [ ] agents.md is updated
- [ ] README.md mentions new features
- [ ] Inline code comments are clear

---

## ✅ DEPLOYMENT READINESS

### Pre-Production Checklist

- [ ] All tests above pass
- [ ] No console errors in browser
- [ ] No Python exceptions in logs
- [ ] Database migrations tested
- [ ] Celery worker stable
- [ ] Redis connection stable
- [ ] Static files served correctly
- [ ] CSRF tokens working
- [ ] User authentication working
- [ ] All new features documented

### Production Deployment Steps

```bash
# 1. Backup database
pg_dump vulnassesor > backup_$(date +%Y%m%d).sql

# 2. Pull latest code
git pull origin main

# 3. Apply migrations
python manage.py migrate

# 4. Collect static files
python manage.py collectstatic --noinput

# 5. Restart services
docker-compose restart

# 6. Verify worker is running
docker-compose ps

# 7. Check logs
docker-compose logs -f --tail=50

# 8. Test one scan
# Visit dashboard, create test scan, verify it works
```

### Post-Deployment Verification

- [ ] Dashboard loads
- [ ] Can create scan
- [ ] Can cancel scan
- [ ] Live preview works
- [ ] No errors in logs
- [ ] Performance is good

---

## ✅ ROLLBACK PLAN (If Issues Found)

### Quick Rollback Steps

```bash
# 1. Revert code
git revert HEAD

# 2. Rollback migrations
python manage.py migrate Dashboard 0003_nucleiconfig

# 3. Restart services
docker-compose restart

# 4. Verify system is stable
```

### What to Monitor After Rollback
- [ ] Existing scans still work
- [ ] No new errors
- [ ] System is stable

---

## 📊 SUCCESS CRITERIA

All features are considered successfully deployed when:

1. ✅ **Cancellation Works**
   - Users can cancel scans
   - Process stops within 2 seconds
   - Status updates correctly

2. ✅ **No Infinite Scans**
   - Scans respect max_host_errors
   - Scans respect timeout
   - No hung processes

3. ✅ **No Page Reloads**
   - HTMX polling works
   - Partial updates only
   - Smooth user experience

4. ✅ **Live Preview Works**
   - Updates instantly
   - No save required
   - All fields reactive

5. ✅ **Performance Improved**
   - < 5 queries for dashboard
   - < 500ms page load
   - Indexes used

6. ✅ **No Regressions**
   - Existing features work
   - No new bugs
   - System is stable

---

## 📝 SIGN-OFF

- [ ] Developer tested all features
- [ ] QA verified functionality
- [ ] Security review completed
- [ ] Performance acceptable
- [ ] Documentation complete
- [ ] Ready for production

**Tested By:** _______________
**Date:** _______________
**Version:** 1.1.0
**Status:** ⬜ PASS / ⬜ FAIL

---

**Notes/Issues Found:**
_____________________________________
_____________________________________
_____________________________________

**Next Steps:**
_____________________________________
_____________________________________
_____________________________________

