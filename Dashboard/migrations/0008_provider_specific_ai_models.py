from django.db import migrations, models


def copy_selected_provider_models(apps, schema_editor):
    AIConfig = apps.get_model('Dashboard', 'AIConfig')
    for config in AIConfig.objects.all():
        if config.provider == 'anthropic':
            config.anthropic_scan_model = config.openai_scan_model
            config.anthropic_fix_model = config.openai_fix_model
            config.anthropic_verify_model = config.openai_verify_model
        elif config.provider == 'deepseek':
            config.deepseek_scan_model = config.openai_scan_model
            config.deepseek_fix_model = config.openai_fix_model
            config.deepseek_verify_model = config.openai_verify_model
        config.save()


class Migration(migrations.Migration):

    dependencies = [
        ('Dashboard', '0007_add_ai_config'),
    ]

    operations = [
        migrations.RenameField(
            model_name='aiconfig',
            old_name='scan_model',
            new_name='openai_scan_model',
        ),
        migrations.RenameField(
            model_name='aiconfig',
            old_name='fix_model',
            new_name='openai_fix_model',
        ),
        migrations.RenameField(
            model_name='aiconfig',
            old_name='verify_model',
            new_name='openai_verify_model',
        ),
        migrations.AddField(
            model_name='aiconfig',
            name='anthropic_scan_model',
            field=models.CharField(default='claude-sonnet-4-5', max_length=120),
        ),
        migrations.AddField(
            model_name='aiconfig',
            name='anthropic_fix_model',
            field=models.CharField(default='claude-sonnet-4-5', max_length=120),
        ),
        migrations.AddField(
            model_name='aiconfig',
            name='anthropic_verify_model',
            field=models.CharField(default='claude-sonnet-4-5', max_length=120),
        ),
        migrations.AddField(
            model_name='aiconfig',
            name='deepseek_scan_model',
            field=models.CharField(default='deepseek-v4-flash', max_length=120),
        ),
        migrations.AddField(
            model_name='aiconfig',
            name='deepseek_fix_model',
            field=models.CharField(default='deepseek-v4-flash', max_length=120),
        ),
        migrations.AddField(
            model_name='aiconfig',
            name='deepseek_verify_model',
            field=models.CharField(default='deepseek-v4-flash', max_length=120),
        ),
        migrations.RunPython(copy_selected_provider_models, migrations.RunPython.noop),
    ]
