from django.db import models
from django.contrib.auth.models import User

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
        ('FAILED', 'Failed'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')

    def __str__(self):
        return self.name

class SASTScanJob(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('CLONING', 'Cloning'),
        ('SCANNING', 'Scanning'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
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

    finding = models.OneToOneField(SASTFinding, on_delete=models.CASCADE, related_name='fix')
    proposed_code = models.TextField()
    explanation = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Fix for {self.finding.title}"
