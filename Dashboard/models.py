import os

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
    max_host_errors = models.IntegerField(
        default=30,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        help_text="Maximum errors before stopping scan on a host (1-100)"
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
            templates_path: Path to the templates directory (None to use default templates)

        Returns:
            list: Command arguments for subprocess
        """
        command = ['nuclei']

        # Target
        command.extend(['-target', target_url])

        # Templates - only specify if custom templates provided
        if templates_path is not None:
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

        # Max host errors - prevent infinite scanning on problematic hosts
        command.extend(['-max-host-error', str(self.max_host_errors)])

        # Timeout (in seconds)
        command.extend(['-timeout', str(self.timeout)])

        # Custom arguments
        if self.custom_args:
            # Split by spaces, but respect quoted strings
            import shlex
            custom_args_list = shlex.split(self.custom_args)
            command.extend(custom_args_list)

        return command


class AIConfig(models.Model):
    """
    Stores site-wide AI provider settings for SAST scans.
    API key values stay in environment variables; this model stores only
    provider selection, model names, base URLs, and env var names.
    """
    PROVIDER_OPENAI = 'openai'
    PROVIDER_ANTHROPIC = 'anthropic'
    PROVIDER_DEEPSEEK = 'deepseek'

    PROVIDER_CHOICES = [
        (PROVIDER_OPENAI, 'OpenAI'),
        (PROVIDER_ANTHROPIC, 'Claude'),
        (PROVIDER_DEEPSEEK, 'DeepSeek'),
    ]

    provider = models.CharField(
        max_length=20,
        choices=PROVIDER_CHOICES,
        default=PROVIDER_OPENAI,
        help_text="AI provider used for SAST scans, fix generation, and verification."
    )
    openai_scan_model = models.CharField(max_length=120, default='gpt-5-nano')
    openai_fix_model = models.CharField(max_length=120, default='gpt-5-nano')
    openai_verify_model = models.CharField(max_length=120, default='gpt-5-nano')
    anthropic_scan_model = models.CharField(max_length=120, default='claude-sonnet-4-5')
    anthropic_fix_model = models.CharField(max_length=120, default='claude-sonnet-4-5')
    anthropic_verify_model = models.CharField(max_length=120, default='claude-sonnet-4-5')
    deepseek_scan_model = models.CharField(max_length=120, default='deepseek-v4-flash')
    deepseek_fix_model = models.CharField(max_length=120, default='deepseek-v4-flash')
    deepseek_verify_model = models.CharField(max_length=120, default='deepseek-v4-flash')

    openai_api_key_env_var = models.CharField(max_length=120, default='OPENAI_API_KEY')
    anthropic_api_key_env_var = models.CharField(max_length=120, default='ANTHROPIC_API_KEY')
    deepseek_api_key_env_var = models.CharField(max_length=120, default='DEEPSEEK_API_KEY')

    openai_base_url = models.URLField(blank=True, default='')
    anthropic_base_url = models.URLField(blank=True, default='')
    deepseek_base_url = models.URLField(default='https://api.deepseek.com')

    max_output_tokens = models.IntegerField(
        default=4096,
        validators=[MinValueValidator(512), MaxValueValidator(200000)],
        help_text="Maximum tokens returned by AI providers where supported."
    )
    request_timeout = models.IntegerField(
        default=120,
        validators=[MinValueValidator(10), MaxValueValidator(600)],
        help_text="Provider request timeout in seconds."
    )

    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ai_config_updates'
    )

    class Meta:
        verbose_name = "AI Configuration"
        verbose_name_plural = "AI Configuration"

    def __str__(self):
        return f"AI Configuration ({self.get_provider_display()})"

    def save(self, *args, **kwargs):
        if not self.pk and AIConfig.objects.exists():
            existing = AIConfig.objects.first()
            self.pk = existing.pk
        self._apply_provider_model_defaults()
        super().save(*args, **kwargs)

    @classmethod
    def get_config(cls):
        config, created = cls.objects.get_or_create(pk=1)
        return config

    @classmethod
    def provider_defaults(cls):
        return {
            cls.PROVIDER_OPENAI: {
                'scan_model': 'gpt-5-nano',
                'fix_model': 'gpt-5-nano',
                'verify_model': 'gpt-5-nano',
            },
            cls.PROVIDER_ANTHROPIC: {
                'scan_model': 'claude-sonnet-4-5',
                'fix_model': 'claude-sonnet-4-5',
                'verify_model': 'claude-sonnet-4-5',
            },
            cls.PROVIDER_DEEPSEEK: {
                'scan_model': 'deepseek-v4-flash',
                'fix_model': 'deepseek-v4-flash',
                'verify_model': 'deepseek-v4-flash',
            },
        }

    def _apply_provider_model_defaults(self):
        for provider, defaults in self.provider_defaults().items():
            prefix = self._provider_field_prefix(provider)
            scan_field = f'{prefix}_scan_model'
            fix_field = f'{prefix}_fix_model'
            verify_field = f'{prefix}_verify_model'
            if not getattr(self, scan_field):
                setattr(self, scan_field, defaults['scan_model'])
            if not getattr(self, fix_field):
                setattr(self, fix_field, defaults['fix_model'])
            if not getattr(self, verify_field):
                setattr(self, verify_field, defaults['verify_model'])

    @classmethod
    def _provider_field_prefix(cls, provider):
        return {
            cls.PROVIDER_OPENAI: 'openai',
            cls.PROVIDER_ANTHROPIC: 'anthropic',
            cls.PROVIDER_DEEPSEEK: 'deepseek',
        }[provider]

    def models_for_provider(self, provider=None):
        selected_provider = provider or self.provider
        prefix = self._provider_field_prefix(selected_provider)
        defaults = self.provider_defaults()[selected_provider]
        return {
            'scan_model': getattr(self, f'{prefix}_scan_model') or defaults['scan_model'],
            'fix_model': getattr(self, f'{prefix}_fix_model') or defaults['fix_model'],
            'verify_model': getattr(self, f'{prefix}_verify_model') or defaults['verify_model'],
        }

    @property
    def scan_model(self):
        return self.models_for_provider()['scan_model']

    @scan_model.setter
    def scan_model(self, value):
        setattr(self, f'{self._provider_field_prefix(self.provider)}_scan_model', value)

    @property
    def fix_model(self):
        return self.models_for_provider()['fix_model']

    @fix_model.setter
    def fix_model(self, value):
        setattr(self, f'{self._provider_field_prefix(self.provider)}_fix_model', value)

    @property
    def verify_model(self):
        return self.models_for_provider()['verify_model']

    @verify_model.setter
    def verify_model(self, value):
        setattr(self, f'{self._provider_field_prefix(self.provider)}_verify_model', value)

    def selected_api_key_env_var(self):
        return {
            self.PROVIDER_OPENAI: self.openai_api_key_env_var,
            self.PROVIDER_ANTHROPIC: self.anthropic_api_key_env_var,
            self.PROVIDER_DEEPSEEK: self.deepseek_api_key_env_var,
        }[self.provider]

    def selected_base_url(self):
        return {
            self.PROVIDER_OPENAI: self.openai_base_url,
            self.PROVIDER_ANTHROPIC: self.anthropic_base_url,
            self.PROVIDER_DEEPSEEK: self.deepseek_base_url,
        }[self.provider]

    def get_api_key(self):
        env_var = self.selected_api_key_env_var()
        return os.environ.get(env_var, '')

    def require_api_key(self):
        env_var = self.selected_api_key_env_var()
        api_key = os.environ.get(env_var)
        if not api_key:
            raise ValueError(f"{env_var} environment variable is not set.")
        return api_key

    def key_statuses(self):
        return {
            self.PROVIDER_OPENAI: {
                'label': 'OpenAI',
                'env_var': self.openai_api_key_env_var,
                'configured': bool(os.environ.get(self.openai_api_key_env_var)),
            },
            self.PROVIDER_ANTHROPIC: {
                'label': 'Claude',
                'env_var': self.anthropic_api_key_env_var,
                'configured': bool(os.environ.get(self.anthropic_api_key_env_var)),
            },
            self.PROVIDER_DEEPSEEK: {
                'label': 'DeepSeek',
                'env_var': self.deepseek_api_key_env_var,
                'configured': bool(os.environ.get(self.deepseek_api_key_env_var)),
            },
        }

    def selected_provider_settings(self):
        selected_models = self.models_for_provider()
        return {
            'provider': self.provider,
            'provider_label': self.get_provider_display(),
            'api_key_env_var': self.selected_api_key_env_var(),
            'base_url': self.selected_base_url(),
            'scan_model': selected_models['scan_model'],
            'fix_model': selected_models['fix_model'],
            'verify_model': selected_models['verify_model'],
            'max_output_tokens': self.max_output_tokens,
            'request_timeout': self.request_timeout,
        }


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
        ('CANCELLED', 'Cancelled'),
    ]

    website = models.ForeignKey(Website, on_delete=models.CASCADE, related_name='scan_jobs')
    celery_task_id = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    error_message = models.TextField(blank=True, null=True, help_text="Error details if scan failed")
    cancelled_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='cancelled_scans')

    def __str__(self):
        return f"Scan #{self.id} - {self.website.name} ({self.status})"

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Scan Job"
        verbose_name_plural = "Scan Jobs"
        indexes = [
            models.Index(fields=['-created_at', 'status']),
            models.Index(fields=['status']),
            models.Index(fields=['celery_task_id']),
        ]


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
        indexes = [
            models.Index(fields=['job', 'severity']),
            models.Index(fields=['severity', '-created_at']),
        ]

