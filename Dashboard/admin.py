from django.contrib import admin
from .models import Website

# Register your models here.

@admin.register(Website)
class WebsiteAdmin(admin.ModelAdmin):
    list_display = ('name', 'url', 'owner', 'created_at')
    list_filter = ('owner', 'created_at')
    search_fields = ('name', 'url', 'owner__username')
    readonly_fields = ('created_at', 'updated_at')
