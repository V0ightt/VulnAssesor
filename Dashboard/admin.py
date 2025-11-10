from django.contrib import admin
from .models import Website, NucleiTemplate, ScanJob, ScanResult, NucleiConfig

# Register your models here.

@admin.register(Website)
class WebsiteAdmin(admin.ModelAdmin):
    list_display = ('name', 'url', 'owner', 'created_at')
    list_filter = ('owner', 'created_at')
    search_fields = ('name', 'url', 'owner__username')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(NucleiTemplate)
class NucleiTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'created_at')
    list_filter = ('owner', 'created_at')
    search_fields = ('name', 'description', 'owner__username')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(ScanJob)
class ScanJobAdmin(admin.ModelAdmin):
    list_display = ('id', 'website', 'status', 'created_at', 'completed_at')
    list_filter = ('status', 'created_at')
    search_fields = ('website__name', 'celery_task_id')
    readonly_fields = ('created_at', 'completed_at')


@admin.register(ScanResult)
class ScanResultAdmin(admin.ModelAdmin):
    list_display = ('vulnerability_name', 'severity', 'job', 'target_url', 'created_at')
    list_filter = ('severity', 'created_at')
    search_fields = ('vulnerability_name', 'template_name', 'target_url')
    readonly_fields = ('created_at',)


@admin.register(NucleiConfig)
class NucleiConfigAdmin(admin.ModelAdmin):
    """
    Admin interface for Nuclei configuration.
    Only allows editing the single configuration instance.
    """
    list_display = ('__str__', 'timeout', 'rate_limit', 'concurrency', 'updated_at')
    readonly_fields = ('updated_at',)

    fieldsets = (
        ('Performance Settings', {
            'fields': ('timeout', 'rate_limit', 'concurrency'),
            'description': 'Configure scan performance and resource usage'
        }),
        ('Output Settings', {
            'fields': ('silent_mode', 'no_color', 'jsonl_output'),
            'description': 'Control output format (jsonl_output should stay enabled for proper parsing)'
        }),
        ('Network Settings', {
            'fields': ('retries', 'follow_redirects'),
            'description': 'Configure network behavior'
        }),
        ('Advanced Settings', {
            'fields': ('custom_args',),
            'description': 'Add custom Nuclei CLI arguments (use with caution)',
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('updated_at', 'updated_by'),
            'classes': ('collapse',)
        }),
    )

    def has_add_permission(self, request):
        # Only allow one instance
        return not NucleiConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        # Don't allow deletion of the config
        return False

    def save_model(self, request, obj, form, change):
        # Track who updated the config
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)

    def changelist_view(self, request, extra_context=None):
        # If config doesn't exist, create it and redirect to edit
        if not NucleiConfig.objects.exists():
            config = NucleiConfig.objects.create()
            from django.shortcuts import redirect
            from django.urls import reverse
            return redirect(reverse('admin:Dashboard_nucleiconfig_change', args=[config.pk]))
        return super().changelist_view(request, extra_context)


