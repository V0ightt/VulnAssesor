import os
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import AIConfig, ScanJob, ScanProgressEvent, Website


class AIConfigTests(TestCase):
    def test_singleton_defaults_and_key_status(self):
        with mock.patch.dict(os.environ, {'OPENAI_API_KEY': 'test-secret'}, clear=True):
            config = AIConfig.get_config()
            self.assertEqual(config.provider, 'openai')
            self.assertEqual(config.scan_model, 'gpt-5-nano')
            self.assertEqual(config.anthropic_scan_model, 'claude-sonnet-4-5')
            self.assertEqual(config.deepseek_scan_model, 'deepseek-v4-flash')
            self.assertEqual(config.selected_api_key_env_var(), 'OPENAI_API_KEY')
            self.assertTrue(config.key_statuses()['openai']['configured'])
            self.assertFalse(config.key_statuses()['anthropic']['configured'])

    def test_configuration_view_saves_ai_settings_without_secret_values(self):
        user = User.objects.create_user(username='admin', password='pass12345')
        self.client.force_login(user)

        with mock.patch.dict(os.environ, {'DEEPSEEK_API_KEY': 'deep-secret'}, clear=True):
            response = self.client.post(reverse('nuclei_config'), {
                'config_section': 'ai',
                'provider': 'deepseek',
                'openai_scan_model': 'gpt-5-nano',
                'openai_fix_model': 'gpt-5-nano',
                'anthropic_scan_model': 'claude-sonnet-4-5',
                'anthropic_fix_model': 'claude-sonnet-4-5',
                'deepseek_scan_model': 'deepseek-custom-scan',
                'deepseek_fix_model': 'deepseek-custom-fix',
                'openai_api_key_env_var': 'OPENAI_API_KEY',
                'anthropic_api_key_env_var': 'ANTHROPIC_API_KEY',
                'deepseek_api_key_env_var': 'DEEPSEEK_API_KEY',
                'openai_base_url': '',
                'anthropic_base_url': '',
                'deepseek_base_url': 'https://api.deepseek.com',
                'max_output_tokens': '8192',
                'request_timeout': '180',
            })

        self.assertEqual(response.status_code, 302)
        config = AIConfig.get_config()
        self.assertEqual(config.provider, 'deepseek')
        self.assertEqual(config.scan_model, 'deepseek-custom-scan')
        self.assertEqual(config.fix_model, 'deepseek-custom-fix')
        self.assertEqual(config.openai_scan_model, 'gpt-5-nano')
        self.assertEqual(config.anthropic_scan_model, 'claude-sonnet-4-5')
        self.assertEqual(config.max_output_tokens, 8192)
        self.assertEqual(config.updated_by, user)

        with mock.patch.dict(os.environ, {'DEEPSEEK_API_KEY': 'deep-secret'}, clear=True):
            response = self.client.get(reverse('nuclei_config') + '?tab=ai')

        self.assertContains(response, 'DEEPSEEK_API_KEY')
        self.assertNotContains(response, 'deep-secret')

    def test_selected_provider_models_are_independent(self):
        config = AIConfig.get_config()
        config.openai_scan_model = 'openai-scan'
        config.openai_fix_model = 'openai-fix'
        config.anthropic_scan_model = 'claude-scan'
        config.anthropic_fix_model = 'claude-fix'
        config.deepseek_scan_model = 'deepseek-scan'
        config.deepseek_fix_model = 'deepseek-fix'

        config.provider = 'anthropic'
        self.assertEqual(config.selected_provider_settings()['scan_model'], 'claude-scan')
        self.assertEqual(config.fix_model, 'claude-fix')
        self.assertNotIn('verify_model', config.selected_provider_settings())

        config.provider = 'openai'
        self.assertEqual(config.selected_provider_settings()['scan_model'], 'openai-scan')
        self.assertEqual(config.fix_model, 'openai-fix')


class DashboardProgressTests(TestCase):
    def test_scan_progress_events_are_ordered_and_pruned(self):
        user = User.objects.create_user(username='owner', password='pass12345')
        website = Website.objects.create(name='App', url='https://example.com', owner=user)
        scan = ScanJob.objects.create(website=website, status='RUNNING')

        for index in range(ScanProgressEvent.MAX_EVENTS_PER_SCAN + 5):
            ScanProgressEvent.record(
                scan_job=scan,
                phase='test',
                event_type='heartbeat',
                title=f'event {index}',
            )

        events = list(scan.progress_events.all())
        self.assertEqual(len(events), ScanProgressEvent.MAX_EVENTS_PER_SCAN)
        self.assertEqual(events, sorted(events, key=lambda event: event.sequence))
        self.assertEqual(events[-1].title, f'event {ScanProgressEvent.MAX_EVENTS_PER_SCAN + 4}')

    def test_live_operations_partial_is_user_scoped(self):
        owner = User.objects.create_user(username='owner', password='pass12345')
        other = User.objects.create_user(username='other', password='pass12345')
        owner_site = Website.objects.create(name='Owner Site', url='https://owner.example', owner=owner)
        other_site = Website.objects.create(name='Other Site', url='https://other.example', owner=other)
        owner_scan = ScanJob.objects.create(website=owner_site, status='RUNNING')
        other_scan = ScanJob.objects.create(website=other_site, status='RUNNING')
        ScanProgressEvent.record(owner_scan, 'execute', 'heartbeat', 'Owner event')
        ScanProgressEvent.record(other_scan, 'execute', 'heartbeat', 'Other event')

        self.client.force_login(owner)
        response = self.client.get(reverse('dashboard_live_operations'), HTTP_HX_REQUEST='true')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Owner Site')
        self.assertContains(response, 'Owner event')
        self.assertNotContains(response, 'Other Site')
        self.assertNotContains(response, 'Other event')
