from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('SAST', '0006_projectprogressevent'),
    ]

    operations = [
        migrations.AddField(
            model_name='sastscanjob',
            name='cancel_requested_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='sastscanjob',
            name='cancelled_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='cancelled_sast_scans',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='sastscanjob',
            name='celery_task_id',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='sastfinding',
            name='confidence_score',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='sastfinding',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='sastfix',
            name='verification_reason',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='sastfix',
            name='verification_status',
            field=models.CharField(
                choices=[
                    ('NOT_VERIFIED', 'Not Verified'),
                    ('PASSED', 'Passed'),
                    ('FAILED', 'Failed'),
                ],
                default='NOT_VERIFIED',
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='sastscanjob',
            name='status',
            field=models.CharField(
                choices=[
                    ('PENDING', 'Pending'),
                    ('CLONING', 'Cloning'),
                    ('SCANNING', 'Scanning'),
                    ('CANCELLING', 'Cancelling'),
                    ('COMPLETED', 'Completed'),
                    ('FAILED', 'Failed'),
                    ('CANCELLED', 'Cancelled'),
                ],
                default='PENDING',
                max_length=20,
            ),
        ),
        migrations.AddIndex(
            model_name='sastscanjob',
            index=models.Index(fields=['project', 'status', '-created_at'], name='SAST_sastsc_project_8d0f03_idx'),
        ),
        migrations.AddIndex(
            model_name='sastscanjob',
            index=models.Index(fields=['status', '-created_at'], name='SAST_sastsc_status_174f6b_idx'),
        ),
        migrations.AddIndex(
            model_name='sastscanjob',
            index=models.Index(fields=['celery_task_id'], name='SAST_sastsc_celery__33a04b_idx'),
        ),
        migrations.AddIndex(
            model_name='sastfinding',
            index=models.Index(fields=['scan_job', 'severity'], name='SAST_sastfi_scan_jo_765346_idx'),
        ),
        migrations.AddIndex(
            model_name='sastfinding',
            index=models.Index(fields=['scan_job', '-created_at'], name='SAST_sastfi_scan_jo_0119c8_idx'),
        ),
        migrations.AddIndex(
            model_name='sastfinding',
            index=models.Index(fields=['severity', '-created_at'], name='SAST_sastfi_severit_d14540_idx'),
        ),
        migrations.AddIndex(
            model_name='sastfix',
            index=models.Index(fields=['status', '-created_at'], name='SAST_sastfi_status_963960_idx'),
        ),
        migrations.AddIndex(
            model_name='sastfix',
            index=models.Index(fields=['verification_status', '-created_at'], name='SAST_sastfi_verific_e797b8_idx'),
        ),
    ]
