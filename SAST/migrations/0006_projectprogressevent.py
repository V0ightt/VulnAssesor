from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('SAST', '0005_project_ingestion_task_and_cancelled_status'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProjectProgressEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sequence', models.PositiveIntegerField(default=1)),
                ('phase', models.CharField(max_length=80)),
                ('event_type', models.CharField(max_length=40)),
                ('title', models.CharField(max_length=160)),
                ('detail', models.TextField(blank=True)),
                ('payload', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='progress_events', to='SAST.project')),
                ('scan_job', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='progress_events', to='SAST.sastscanjob')),
            ],
            options={
                'ordering': ['sequence', 'created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='projectprogressevent',
            index=models.Index(fields=['project', 'sequence'], name='SAST_projec_project_cd9288_idx'),
        ),
        migrations.AddIndex(
            model_name='projectprogressevent',
            index=models.Index(fields=['project', '-created_at'], name='SAST_projec_project_11e0de_idx'),
        ),
        migrations.AddIndex(
            model_name='projectprogressevent',
            index=models.Index(fields=['scan_job', 'sequence'], name='SAST_projec_scan_jo_c8d1a5_idx'),
        ),
        migrations.AddIndex(
            model_name='projectprogressevent',
            index=models.Index(fields=['event_type', '-created_at'], name='SAST_projec_event_t_5b0fdd_idx'),
        ),
    ]
