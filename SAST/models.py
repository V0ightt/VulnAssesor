from django.db import models
from django.contrib.auth.models import User
from django.db.models import Max

class Project(models.Model):
    name = models.CharField(max_length=255)
    repository_url = models.URLField(blank=True, null=True)
    source_zip = models.FileField(upload_to='projects/zips/', blank=True, null=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_scan = models.DateTimeField(blank=True, null=True)
    root_directory = models.CharField(max_length=512, blank=True, null=True)
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('CLONING', 'Cloning'),
        ('READY', 'Ready'),
        ('CANCELLED', 'Cancelled'),
        ('FAILED', 'Failed'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    ingestion_task_id = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return self.name

class SASTScanJob(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('CLONING', 'Cloning'),
        ('SCANNING', 'Scanning'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    SCAN_TYPE_CHOICES = [
        ('FULL', 'Full Scan'),
        ('INCREMENTAL', 'Incremental Scan'),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='scans')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    commit_hash = models.CharField(max_length=40, blank=True, null=True)
    scan_type = models.CharField(max_length=20, choices=SCAN_TYPE_CHOICES, default='FULL')
    agent_run_metadata = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.project.name} - {self.get_scan_type_display()} ({self.status})"

class SASTFinding(models.Model):
    SEVERITY_CHOICES = [
        ('CRITICAL', 'Critical'),
        ('HIGH', 'High'),
        ('MEDIUM', 'Medium'),
        ('LOW', 'Low'),
        ('INFO', 'Info'),
    ]

    scan_job = models.ForeignKey(SASTScanJob, on_delete=models.CASCADE, related_name='findings')
    file_path = models.CharField(max_length=512)
    line_number = models.IntegerField()
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES)
    title = models.CharField(max_length=255)
    description = models.TextField()
    code_snippet = models.TextField()
    ai_explanation = models.TextField(blank=True, null=True)
    ai_fix_code = models.TextField(blank=True, null=True)
    is_fixed = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.title} - {self.file_path}:{self.line_number}"

class SASTFix(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('ACCEPTED', 'Accepted'),
        ('REJECTED', 'Rejected'),
    ]

    SCOPE_CHOICES = [
        ('SNIPPET', 'Snippet'),
        ('FILE', 'File'),
    ]

    finding = models.OneToOneField(SASTFinding, on_delete=models.CASCADE, related_name='fix')
    proposed_code = models.TextField()
    explanation = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    scope = models.CharField(max_length=20, choices=SCOPE_CHOICES, default='SNIPPET')
    start_line = models.IntegerField(default=1)
    end_line = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Fix for {self.finding.title}"


class ProjectProgressEvent(models.Model):
    """
    Bounded, safe progress stream for ingestion and SAST scan activity.
    """
    MAX_EVENTS_PER_PROJECT = 120
    MAX_EVENTS_PER_SCAN = 120

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='progress_events')
    scan_job = models.ForeignKey(
        SASTScanJob,
        on_delete=models.CASCADE,
        related_name='progress_events',
        blank=True,
        null=True,
    )
    sequence = models.PositiveIntegerField(default=1)
    phase = models.CharField(max_length=80)
    event_type = models.CharField(max_length=40)
    title = models.CharField(max_length=160)
    detail = models.TextField(blank=True)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['sequence', 'created_at']
        indexes = [
            models.Index(fields=['project', 'sequence']),
            models.Index(fields=['project', '-created_at']),
            models.Index(fields=['scan_job', 'sequence']),
            models.Index(fields=['event_type', '-created_at']),
        ]

    def __str__(self):
        target = f"scan #{self.scan_job_id}" if self.scan_job_id else f"project #{self.project_id}"
        return f"{target} [{self.sequence}] {self.title}"

    @classmethod
    def record(cls, project, phase, event_type, title, detail='', payload=None, scan_job=None):
        queryset = cls.objects.filter(project=project)
        if scan_job:
            queryset = queryset.filter(scan_job=scan_job)
        else:
            queryset = queryset.filter(scan_job__isnull=True)

        current = queryset.aggregate(max_sequence=Max('sequence'))
        event = cls.objects.create(
            project=project,
            scan_job=scan_job,
            sequence=(current['max_sequence'] or 0) + 1,
            phase=phase,
            event_type=event_type,
            title=title,
            detail=detail or '',
            payload=payload or {},
        )
        cls.prune(project, scan_job=scan_job)
        return event

    @classmethod
    def prune(cls, project, scan_job=None, keep=None):
        limit = keep or (cls.MAX_EVENTS_PER_SCAN if scan_job else cls.MAX_EVENTS_PER_PROJECT)
        queryset = cls.objects.filter(project=project)
        queryset = queryset.filter(scan_job=scan_job) if scan_job else queryset.filter(scan_job__isnull=True)
        stale_ids = list(
            queryset.order_by('-sequence')
            .values_list('id', flat=True)[limit:]
        )
        if stale_ids:
            cls.objects.filter(id__in=stale_ids).delete()
