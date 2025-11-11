# Generated manually - Add database indexes for better query performance

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Dashboard', '0004_add_scan_cancellation'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='scanjob',
            index=models.Index(fields=['-created_at', 'status'], name='Dashboard_s_created_d63f91_idx'),
        ),
        migrations.AddIndex(
            model_name='scanjob',
            index=models.Index(fields=['status'], name='Dashboard_s_status_8a7c5e_idx'),
        ),
        migrations.AddIndex(
            model_name='scanjob',
            index=models.Index(fields=['celery_task_id'], name='Dashboard_s_celery__9e5d2a_idx'),
        ),
        migrations.AddIndex(
            model_name='scanresult',
            index=models.Index(fields=['job', 'severity'], name='Dashboard_s_job_id_a1b2c3_idx'),
        ),
        migrations.AddIndex(
            model_name='scanresult',
            index=models.Index(fields=['severity', '-created_at'], name='Dashboard_s_severit_d4e5f6_idx'),
        ),
    ]

