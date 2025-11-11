# Generated manually

from django.conf import settings
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('Dashboard', '0003_nucleiconfig'),
    ]

    operations = [
        migrations.AddField(
            model_name='scanjob',
            name='cancelled_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='cancelled_scans', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='scanjob',
            name='status',
            field=models.CharField(choices=[('PENDING', 'Pending'), ('RUNNING', 'Running'), ('COMPLETED', 'Completed'), ('FAILED', 'Failed'), ('CANCELLED', 'Cancelled')], default='PENDING', max_length=20),
        ),
        migrations.AddField(
            model_name='nucleiconfig',
            name='max_host_errors',
            field=models.IntegerField(default=30, help_text='Maximum errors before stopping scan on a host (1-100)', validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(100)]),
        ),
    ]

