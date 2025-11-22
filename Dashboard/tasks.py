import time
import json
import subprocess
import tempfile
from pathlib import Path
from celery import shared_task
from django.utils import timezone
from .models import ScanJob, ScanResult, NucleiTemplate, NucleiConfig


@shared_task
def simple_test_task(task_duration_seconds):
    """
    A simple test task that sleeps for a given duration.
    """
    print(f"Task started! Will run for {task_duration_seconds} seconds.")

    for i in range(task_duration_seconds):
        time.sleep(1)
        print(f"Task running... {i + 1} seconds passed.")

    print("Task finished!")
    return f"Task complete after {task_duration_seconds} seconds."


def check_cancellation_and_wait(job, process, config, command):
    """
    Helper function to poll process and check for cancellation.
    Returns the process result or raises appropriate exceptions.
    """
    start_time = time.time()
    while process.poll() is None:
        # Check for timeout
        if time.time() - start_time > config.timeout:
            process.kill()
            raise subprocess.TimeoutExpired(command, config.timeout)

        # Refresh job status from DB and check for cancellation
        job.refresh_from_db()
        if job.status == 'CANCELLED':
            print(f"[Specialist] Job {job.id} was cancelled during execution")
            process.kill()
            process.wait(timeout=5)
            return None  # Signal cancellation

        time.sleep(2)

    # Get output
    stdout, stderr = process.communicate(timeout=5)
    return type('Result', (), {
        'returncode': process.returncode,
        'stdout': stdout,
        'stderr': stderr
    })()


@shared_task(bind=True)
def run_specialist_scan(self, job_id, template_ids):
    """
    The "Specialist" worker that runs Nuclei scans.

    Args:
        job_id: ID of the ScanJob to process
        template_ids: List of NucleiTemplate IDs to use for scanning (empty list uses default templates)

    Returns:
        dict: Summary of the scan results
    """
    print(f"[Specialist] Starting scan for job {job_id} with templates {template_ids}")

    try:
        # Get the ScanJob object
        job = ScanJob.objects.get(id=job_id)

        # Check if job was cancelled before we even started
        if job.status == 'CANCELLED':
            print(f"[Specialist] Job {job_id} was cancelled before execution")
            return {'status': 'cancelled', 'message': 'Scan was cancelled'}

        # Update job status to RUNNING and save Celery task ID
        job.status = 'RUNNING'
        job.celery_task_id = self.request.id
        job.save()

        print(f"[Specialist] Job {job_id} status updated to RUNNING")

        # Get Nuclei configuration
        config = NucleiConfig.get_config()

        # Check if we should use default templates or custom templates
        use_default_templates = not template_ids or len(template_ids) == 0

        # Initialize result variable
        result = None
        is_cancelled = False
        
        # Prepare command and temp directory if needed
        command = []
        temp_dir_obj = None
        
        try:
            if use_default_templates:
                print(f"[Specialist] Using Nuclei default templates")
                command = config.build_command(job.website.url, None)
            else:
                # Create a temporary directory to store custom templates
                temp_dir_obj = tempfile.TemporaryDirectory()
                temp_path = Path(temp_dir_obj.name)

                # Fetch the NucleiTemplate objects and write them to files
                templates = NucleiTemplate.objects.filter(id__in=template_ids)

                if not templates.exists():
                    raise ValueError("No valid templates found")

                print(f"[Specialist] Writing {templates.count()} templates to {temp_dir_obj.name}")

                for template in templates:
                    # Create a safe filename from the template name
                    safe_name = "".join(c if c.isalnum() or c in ('-', '_') else '_' for c in template.name)
                    filename = f"{template.id}_{safe_name}.yaml"
                    template_file = temp_path / filename

                    # Write the template content to the file with explicit encoding
                    template_file.write_text(template.template_content, encoding='utf-8')

                # Build the Nuclei command using configuration
                command = config.build_command(job.website.url, str(temp_path))
                print(f"[Specialist] Template directory: {temp_path}")

            # Execute Nuclei with cancellation support
            print(f"[Specialist] Executing command: {' '.join(command)}")
            
            # Use mkstemp to create real files on disk for output capture
            # This avoids Windows-specific locking issues with TemporaryFile
            import os
            fd_out, stdout_path = tempfile.mkstemp()
            fd_err, stderr_path = tempfile.mkstemp()
            os.close(fd_out)
            os.close(fd_err)
            
            try:
                with open(stdout_path, 'w', encoding='utf-8') as f_out, \
                     open(stderr_path, 'w', encoding='utf-8') as f_err:
                    
                    process = subprocess.Popen(
                        command,
                        stdout=f_out,
                        stderr=f_err,
                        text=True,
                        encoding='utf-8'
                    )

                    try:
                        # Wait with timeout and periodic cancellation checks
                        start_time = time.time()
                        while process.poll() is None:
                            # Check for timeout
                            if time.time() - start_time > config.timeout:
                                process.kill()
                                raise subprocess.TimeoutExpired(command, config.timeout)

                            # Refresh job status from DB
                            job.refresh_from_db()
                            if job.status == 'CANCELLED':
                                print(f"[Specialist] Job {job_id} was cancelled during execution")
                                process.kill()
                                process.wait(timeout=5)
                                is_cancelled = True
                                break

                            time.sleep(2)
                            
                    except subprocess.TimeoutExpired:
                        process.kill()
                        raise

                # Process finished, read outputs from disk
                with open(stdout_path, 'r', encoding='utf-8') as f:
                    stdout = f.read()
                with open(stderr_path, 'r', encoding='utf-8') as f:
                    stderr = f.read()
                
                result = type('Result', (), {
                    'returncode': process.returncode if not is_cancelled else -1,
                    'stdout': stdout,
                    'stderr': stderr
                })()
                
            finally:
                # Clean up output temp files
                if os.path.exists(stdout_path):
                    os.unlink(stdout_path)
                if os.path.exists(stderr_path):
                    os.unlink(stderr_path)

        finally:
            # Clean up template temp directory if it exists
            if temp_dir_obj:
                temp_dir_obj.cleanup()

        print(f"[Specialist] Nuclei execution completed with return code: {result.returncode}")

        # Log stderr for debugging
        if result.stderr:
            print(f"[Specialist] Nuclei stderr output:")
            print(result.stderr)

        # Check if Nuclei reported an error
        if result.returncode != 0:
            error_details = result.stderr if result.stderr else "No error details available"
            print(f"[Specialist] WARNING: Nuclei exited with code {result.returncode}")
            print(f"[Specialist] Error details: {error_details}")

            # Check for common issues
            if "no templates provided" in error_details.lower():
                print(f"[Specialist] ERROR: Nuclei couldn't find templates")
                # Continue anyway to save error info

        # Process the output
        findings_count = 0

        if result.stdout:
            # Each line in stdout is a JSON object representing a finding
            for line in result.stdout.strip().split('\n'):
                if not line.strip():
                    continue

                try:
                    finding = json.loads(line)

                    # Extract relevant information from the Nuclei output
                    # Nuclei JSON structure: https://docs.projectdiscovery.io/tools/nuclei/running#json-output
                    template_id = finding.get('template-id', 'unknown')
                    template_name = finding.get('template', template_id)
                    info = finding.get('info', {})
                    vulnerability_name = info.get('name', template_id)
                    severity = info.get('severity', 'info').lower()
                    matched_at = finding.get('matched-at', job.website.url)

                    # Create a ScanResult object
                    ScanResult.objects.create(
                        job=job,
                        template_name=template_name,
                        vulnerability_name=vulnerability_name,
                        severity=severity,
                        target_url=matched_at,
                        raw_finding=finding
                    )

                    findings_count += 1
                    print(f"[Specialist] Found: {vulnerability_name} ({severity}) at {matched_at}")

                except json.JSONDecodeError as e:
                    print(f"[Specialist] Failed to parse JSON line: {line[:100]}... Error: {e}")
                    continue

        # Check for errors in stderr
        if result.stderr:
            print(f"[Specialist] Nuclei stderr: {result.stderr}")

        # Update job status to COMPLETED if not cancelled
        if not is_cancelled:
            job.status = 'COMPLETED'
        
        job.completed_at = timezone.now()
        job.save()

        summary = {
            'job_id': job_id,
            'status': 'cancelled' if is_cancelled else 'success',
            'findings_count': findings_count,
            'target': job.website.url,
        }

        print(f"[Specialist] Scan completed. Status: {summary['status']}. Found {findings_count} vulnerabilities.")
        return summary

    except ScanJob.DoesNotExist:
        error_msg = f"ScanJob with id {job_id} does not exist"
        print(f"[Specialist] ERROR: {error_msg}")
        return {'status': 'error', 'message': error_msg}

    except subprocess.TimeoutExpired:
        config = NucleiConfig.get_config()
        error_msg = f"Scan timed out after {config.timeout} seconds"
        print(f"[Specialist] ERROR: {error_msg}")

        try:
            job = ScanJob.objects.get(id=job_id)
            job.status = 'FAILED'
            job.error_message = error_msg
            job.completed_at = timezone.now()
            job.save()
        except:
            pass

        return {'status': 'error', 'message': error_msg}

    except Exception as e:
        error_msg = f"Scan failed: {str(e)}"
        print(f"[Specialist] ERROR: {error_msg}")

        try:
            job = ScanJob.objects.get(id=job_id)
            job.status = 'FAILED'
            job.error_message = error_msg
            job.completed_at = timezone.now()
            job.save()
        except:
            pass

        return {'status': 'error', 'message': error_msg}
