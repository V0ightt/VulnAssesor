"""
Django management command to load Nuclei templates from the nuclei-templates directory.
"""
import yaml
from pathlib import Path
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from Dashboard.models import NucleiTemplate


class Command(BaseCommand):
    help = 'Load Nuclei templates from the nuclei-templates directory into the database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user',
            type=str,
            help='Username to assign templates to (default: creates/uses "system" user)',
        )
        parser.add_argument(
            '--overwrite',
            action='store_true',
            help='Overwrite existing templates with the same ID',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be loaded without actually loading',
        )

    def handle(self, *args, **options):
        # Get the base directory (project root)
        base_dir = Path(__file__).resolve().parent.parent.parent.parent
        templates_dir = base_dir / 'nuclei-templates'

        if not templates_dir.exists():
            self.stdout.write(self.style.ERROR(f'Templates directory not found: {templates_dir}'))
            return

        # Get or create the user
        username = options.get('user', 'system')
        try:
            user = User.objects.get(username=username)
            self.stdout.write(self.style.SUCCESS(f'Using user: {username}'))
        except User.DoesNotExist:
            if username == 'system':
                # Create system user
                user = User.objects.create_user(
                    username='system',
                    email='system@vulnassesor.local',
                    password=''.join([chr(i) for i in range(97, 123)]),  # Random password
                    is_staff=False,
                    is_active=True
                )
                self.stdout.write(self.style.SUCCESS(f'Created system user'))
            else:
                self.stdout.write(self.style.ERROR(f'User "{username}" not found'))
                return

        # Find all YAML files
        yaml_files = list(templates_dir.glob('*.yaml')) + list(templates_dir.glob('*.yml'))

        if not yaml_files:
            self.stdout.write(self.style.WARNING(f'No YAML files found in {templates_dir}'))
            return

        self.stdout.write(self.style.SUCCESS(f'Found {len(yaml_files)} template file(s)'))

        loaded_count = 0
        skipped_count = 0
        error_count = 0

        for yaml_file in yaml_files:
            try:
                # Read the YAML file
                with open(yaml_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    template_data = yaml.safe_load(content)

                # Extract metadata
                template_id = template_data.get('id', yaml_file.stem)
                info = template_data.get('info', {})
                name = info.get('name', yaml_file.stem)
                description = info.get('description', '')

                # Check if template already exists
                existing = NucleiTemplate.objects.filter(
                    owner=user,
                    name=name
                ).first()

                if existing and not options['overwrite']:
                    self.stdout.write(
                        self.style.WARNING(f'⊗ Skipped: {name} (already exists)')
                    )
                    skipped_count += 1
                    continue

                if options['dry_run']:
                    self.stdout.write(
                        self.style.NOTICE(f'[DRY RUN] Would load: {name}')
                    )
                    loaded_count += 1
                    continue

                # Create or update template
                if existing and options['overwrite']:
                    existing.description = description
                    existing.template_content = content
                    existing.save()
                    self.stdout.write(
                        self.style.SUCCESS(f'✓ Updated: {name}')
                    )
                else:
                    NucleiTemplate.objects.create(
                        name=name,
                        description=description,
                        template_content=content,
                        owner=user
                    )
                    self.stdout.write(
                        self.style.SUCCESS(f'✓ Loaded: {name}')
                    )

                loaded_count += 1

            except yaml.YAMLError as e:
                self.stdout.write(
                    self.style.ERROR(f'✗ YAML Error in {yaml_file.name}: {e}')
                )
                error_count += 1
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'✗ Error loading {yaml_file.name}: {e}')
                )
                error_count += 1

        # Summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 50))
        self.stdout.write(self.style.SUCCESS(f'Summary:'))
        self.stdout.write(self.style.SUCCESS(f'  Loaded: {loaded_count}'))
        if skipped_count:
            self.stdout.write(self.style.WARNING(f'  Skipped: {skipped_count}'))
        if error_count:
            self.stdout.write(self.style.ERROR(f'  Errors: {error_count}'))
        self.stdout.write(self.style.SUCCESS('=' * 50))

        if options['dry_run']:
            self.stdout.write(self.style.NOTICE('This was a dry run. No changes were made.'))

