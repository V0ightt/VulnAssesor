from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator

# Create your models here.

class Website(models.Model):
    name = models.CharField(max_length=200)
    url = models.URLField()
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='websites')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['-created_at']


class NucleiConfig(models.Model):
    """
    Stores configurable Nuclei CLI settings.
    Only one instance should exist (singleton pattern).
    """
    # Basic settings
    timeout = models.IntegerField(
        default=600,
        validators=[MinValueValidator(60), MaxValueValidator(3600)],
        help_text="Scan timeout in seconds (60-3600)"
    )
    rate_limit = models.IntegerField(
        default=150,
        validators=[MinValueValidator(1), MaxValueValidator(1000)],
        help_text="Maximum requests per second (1-1000)"
    )
    concurrency = models.IntegerField(
        default=25,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        help_text="Number of concurrent templates to run (1-100)"
    )

    # Output settings
    silent_mode = models.BooleanField(
        default=True,
        help_text="Hide banner and progress bar"
    )
    no_color = models.BooleanField(
        default=True,
        help_text="Disable colored output"
    )
    jsonl_output = models.BooleanField(
        default=True,
        help_text="Output results as JSON Lines (required for parsing)"
    )

    # Network settings
    retries = models.IntegerField(
        default=1,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="Number of times to retry a failed request (0-10)"
    )
    follow_redirects = models.BooleanField(
        default=True,
        help_text="Follow HTTP redirects"
    )

    # Advanced settings
    custom_args = models.TextField(
        blank=True,
        help_text="Additional custom Nuclei arguments (e.g., '-proxy http://proxy:8080')"
    )

    # Metadata
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='nuclei_config_updates'
    )

    def __str__(self):
        return f"Nuclei Configuration (Updated: {self.updated_at.strftime('%Y-%m-%d %H:%M')})"

    class Meta:
        verbose_name = "Nuclei Configuration"
        verbose_name_plural = "Nuclei Configuration"

    def save(self, *args, **kwargs):
        # Ensure only one instance exists (singleton)
        if not self.pk and NucleiConfig.objects.exists():
            # Update existing instance instead of creating new one
            existing = NucleiConfig.objects.first()
            self.pk = existing.pk
        super().save(*args, **kwargs)

    @classmethod
    def get_config(cls):
        """Get or create the singleton configuration instance."""
        config, created = cls.objects.get_or_create(pk=1)
        return config

    def build_command(self, target_url, templates_path):
        """
        Build the Nuclei CLI command with current configuration.

        Args:
            target_url: The target website URL
            templates_path: Path to the templates directory

        Returns:
            list: Command arguments for subprocess
        """
        command = ['nuclei']

        # Target
        command.extend(['-target', target_url])

        # Templates
        command.extend(['-t', str(templates_path)])

        # Output format
        if self.jsonl_output:
            command.append('-jsonl')

        # Silent mode
        if self.silent_mode:
            command.append('-silent')

        # No color
        if self.no_color:
            command.append('-no-color')

        # Rate limit
        command.extend(['-rate-limit', str(self.rate_limit)])

        # Concurrency
        command.extend(['-c', str(self.concurrency)])

        # Retries
        if self.retries > 0:
            command.extend(['-retries', str(self.retries)])

        # Follow redirects
        if not self.follow_redirects:
            command.append('-no-follow-redirects')

        # Timeout (in seconds)
        command.extend(['-timeout', str(self.timeout)])

        # Custom arguments
        if self.custom_args:
            # Split by spaces, but respect quoted strings
            import shlex
            custom_args_list = shlex.split(self.custom_args)
            command.extend(custom_args_list)

        return command


class NucleiTemplate(models.Model):
    """
    Stores user's custom Nuclei scan templates.
    """
    name = models.CharField(max_length=200, help_text="Name of the template (e.g., 'Log4j Check')")
    description = models.TextField(help_text="Brief description of what this template scans for")
    template_content = models.TextField(help_text="Raw YAML content of the Nuclei template")
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='nuclei_templates')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Nuclei Template"
        verbose_name_plural = "Nuclei Templates"


class ScanJob(models.Model):
    """
    Tracks a single scan request from start to finish.
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('RUNNING', 'Running'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    ]

    website = models.ForeignKey(Website, on_delete=models.CASCADE, related_name='scan_jobs')
    celery_task_id = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    error_message = models.TextField(blank=True, null=True, help_text="Error details if scan failed")

    def __str__(self):
        return f"Scan #{self.id} - {self.website.name} ({self.status})"

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Scan Job"
        verbose_name_plural = "Scan Jobs"


class ScanResult(models.Model):
    """
    Stores individual findings from a scan.
    """
    SEVERITY_CHOICES = [
        ('critical', 'Critical'),
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low'),
        ('info', 'Info'),
    ]

    job = models.ForeignKey(ScanJob, on_delete=models.CASCADE, related_name='results')
    template_name = models.CharField(max_length=200, help_text="Name of the template that found this")
    vulnerability_name = models.CharField(max_length=255, help_text="Human-readable name of the vulnerability")
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='info')
    target_url = models.URLField(help_text="Specific URL where the finding was located")
    raw_finding = models.JSONField(help_text="Full JSON output from Nuclei for this finding")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.vulnerability_name} ({self.severity}) - {self.target_url}"

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Scan Result"
        verbose_name_plural = "Scan Results"

