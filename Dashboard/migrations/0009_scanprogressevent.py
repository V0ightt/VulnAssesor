from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('Dashboard', '0008_provider_specific_ai_models'),
    ]

    operations = [
        migrations.CreateModel(
            name='ScanProgressEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sequence', models.PositiveIntegerField(default=1)),
                ('phase', models.CharField(max_length=80)),
                ('event_type', models.CharField(max_length=40)),
                ('title', models.CharField(max_length=160)),
                ('detail', models.TextField(blank=True)),
                ('payload', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('scan_job', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='progress_events', to='Dashboard.scanjob')),
            ],
            options={
                'ordering': ['sequence', 'created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='scanprogressevent',
            index=models.Index(fields=['scan_job', 'sequence'], name='Dashboard_s_scan_jo_e6a891_idx'),
        ),
        migrations.AddIndex(
            model_name='scanprogressevent',
            index=models.Index(fields=['scan_job', '-created_at'], name='Dashboard_s_scan_jo_03572f_idx'),
        ),
        migrations.AddIndex(
            model_name='scanprogressevent',
            index=models.Index(fields=['event_type', '-created_at'], name='Dashboard_s_event_t_26b51a_idx'),
        ),
    ]
