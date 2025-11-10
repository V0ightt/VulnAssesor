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


@shared_task(bind=True)
def run_specialist_scan(self, job_id, template_ids):
    """
    The "Specialist" worker that runs Nuclei scans.

    Args:
        job_id: ID of the ScanJob to process
        template_ids: List of NucleiTemplate IDs to use for scanning

    Returns:
        dict: Summary of the scan results
    """
    print(f"[Specialist] Starting scan for job {job_id} with templates {template_ids}")

    try:
        # Get the ScanJob object
        job = ScanJob.objects.get(id=job_id)

        # Update job status to RUNNING and save Celery task ID
        job.status = 'RUNNING'
        job.celery_task_id = self.request.id
        job.save()

        print(f"[Specialist] Job {job_id} status updated to RUNNING")

        # Create a temporary directory to store templates
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Fetch the NucleiTemplate objects and write them to files
            templates = NucleiTemplate.objects.filter(id__in=template_ids)

            if not templates.exists():
                raise ValueError("No valid templates found")

            print(f"[Specialist] Writing {templates.count()} templates to {temp_dir}")

            for template in templates:
                # Create a safe filename from the template name
                # Remove any special characters that might cause issues
                safe_name = "".join(c if c.isalnum() or c in ('-', '_') else '_' for c in template.name)
                filename = f"{template.id}_{safe_name}.yaml"
                template_file = temp_path / filename

                # Write the template content to the file with explicit encoding
                template_file.write_text(template.template_content, encoding='utf-8')
                print(f"[Specialist] Created template file: {filename}")
                print(f"[Specialist] Template file path: {template_file}")
                print(f"[Specialist] Template file exists: {template_file.exists()}")
                print(f"[Specialist] Template file size: {template_file.stat().st_size} bytes")

            # List all files in temp directory for debugging
            files_in_temp = list(temp_path.glob('*.yaml'))
            print(f"[Specialist] Total YAML files in temp dir: {len(files_in_temp)}")
            for f in files_in_temp:
                print(f"[Specialist]   - {f.name}")

            # Get Nuclei configuration
            config = NucleiConfig.get_config()

            # Build the Nuclei command using configuration
            command = config.build_command(job.website.url, str(temp_path))

            print(f"[Specialist] Executing command: {' '.join(command)}")
            print(f"[Specialist] Template directory: {temp_path}")
            print(f"[Specialist] Template directory exists: {temp_path.exists()}")

            # Execute Nuclei with configured timeout
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=config.timeout  # Use configured timeout
            )

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
                    print(f"[Specialist] ERROR: Nuclei couldn't find templates in {temp_path}")
                    print(f"[Specialist] Files in directory: {list(temp_path.glob('*'))}")
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

            # Update job status to COMPLETED
            job.status = 'COMPLETED'
            job.completed_at = timezone.now()
            job.save()

            summary = {
                'job_id': job_id,
                'status': 'success',
                'findings_count': findings_count,
                'target': job.website.url,
            }

            print(f"[Specialist] Scan completed successfully. Found {findings_count} vulnerabilities.")
            return summary

    except ScanJob.DoesNotExist:
        error_msg = f"ScanJob with id {job_id} does not exist"
        print(f"[Specialist] ERROR: {error_msg}")
        return {'status': 'error', 'message': error_msg}

    except subprocess.TimeoutExpired:
        config = NucleiConfig.get_config()
        error_msg = f"Scan timed out after {config.timeout} seconds"
        print(f"[Specialist] ERROR: {error_msg}")
        job.status = 'FAILED'
        job.error_message = error_msg
        job.completed_at = timezone.now()
        job.save()
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
