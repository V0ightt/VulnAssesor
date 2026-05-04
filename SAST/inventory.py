from collections import Counter
from pathlib import Path

from django.conf import settings

from .services import ProjectManager
from .sast_tools import (
    get_allowed_extensions,
    get_ignored_directories,
    search_codebase,
)


LANGUAGE_BY_EXTENSION = {
    '.py': 'Python',
    '.js': 'JavaScript',
    '.jsx': 'JavaScript',
    '.ts': 'TypeScript',
    '.tsx': 'TypeScript',
    '.java': 'Java',
    '.go': 'Go',
    '.rs': 'Rust',
    '.php': 'PHP',
    '.rb': 'Ruby',
    '.cs': 'C#',
    '.c': 'C/C++',
    '.cc': 'C/C++',
    '.cpp': 'C/C++',
    '.html': 'HTML',
    '.xml': 'XML',
    '.sql': 'SQL',
    '.sh': 'Shell',
}

ENTRYPOINT_NAMES = {
    'manage.py',
    'app.py',
    'main.py',
    'server.py',
    'wsgi.py',
    'asgi.py',
    'urls.py',
    'routes.py',
    'package.json',
    'Dockerfile',
    'docker-compose.yml',
    'docker-compose.yaml',
    'pom.xml',
    'build.gradle',
    'go.mod',
    'Cargo.toml',
}

SINK_SEARCHES = {
    'SQL_INJECTION': r'raw\(|execute\(|executemany\(|SELECT\s+|INSERT\s+|UPDATE\s+|DELETE\s+',
    'XSS': r'innerHTML|dangerouslySetInnerHTML|mark_safe|safe\s*\}|render_template|HttpResponse\(',
    'AUTH_BYPASS': r'login_required|permission|authenticate|is_authenticated|has_perm|authorize',
    'PATH_TRAVERSAL': r'open\(|Path\(|send_file|FileResponse|extractall|ZipFile|os\.path\.join',
    'COMMAND_INJECTION': r'subprocess|os\.system|popen|shell=True|exec\(',
    'SSRF': r'requests\.|httpx\.|urllib|fetch\(|axios\.',
    'DESERIALIZATION': r'pickle\.loads|yaml\.load|marshal\.loads|ObjectInputStream|deserialize',
    'SECRETS': r'api[_-]?key|secret|password|token',
    'FILE_UPLOAD': r'upload|FileField|request\.FILES|multipart',
    'TEMPLATE_INJECTION': r'Template\(|render\(|jinja|Handlebars|Mustache',
}


def build_repository_inventory(project):
    manager = ProjectManager(project)
    top_level = manager.get_directory_structure(
        '',
        ignored_directories=get_ignored_directories(),
        max_entries=settings.SAST_SCAN_MAX_DIRECTORY_ENTRIES,
    )

    file_count = 0
    skipped_large_files = 0
    extension_counts = Counter()
    language_counts = Counter()
    entrypoint_candidates = []
    max_files = settings.SAST_SCAN_INVENTORY_MAX_FILES

    for relative_path in manager.iter_workspace_files(
        ignored_directories=get_ignored_directories(),
        allowed_extensions=get_allowed_extensions(),
    ):
        if file_count >= max_files:
            break
        full_path = manager.resolve_path(relative_path)
        try:
            size = full_path.stat().st_size
        except OSError:
            continue
        if size > settings.SAST_SCAN_MAX_FILE_BYTES:
            skipped_large_files += 1
            continue

        file_count += 1
        path = Path(relative_path)
        suffix = path.suffix.lower()
        extension_counts[suffix or path.name.lower()] += 1
        language_counts[LANGUAGE_BY_EXTENSION.get(suffix, 'Other')] += 1
        if path.name in ENTRYPOINT_NAMES or path.name.lower() in ENTRYPOINT_NAMES:
            entrypoint_candidates.append(relative_path)

    sink_candidates = {}
    for vulnerability_type, query in SINK_SEARCHES.items():
        try:
            result = search_codebase(
                project,
                query,
                '',
                max_results=settings.SAST_SCAN_MAX_SINK_CANDIDATES,
            )
        except Exception as exc:
            sink_candidates[vulnerability_type] = {
                'error': str(exc),
                'total_hits': 0,
                'samples': [],
            }
            continue

        sink_candidates[vulnerability_type] = {
            'total_hits': result.get('total_hits', 0),
            'truncated': result.get('truncated', False),
            'samples': [
                {
                    'path': item.get('path', ''),
                    'line_number': item.get('line_number'),
                    'match': item.get('match', ''),
                }
                for item in result.get('results', [])[:settings.SAST_SCAN_MAX_SINK_CANDIDATES]
            ],
        }

    return {
        'file_count': file_count,
        'inventory_truncated': file_count >= max_files,
        'skipped_large_files': skipped_large_files,
        'language_counts': dict(language_counts),
        'extension_counts': dict(extension_counts.most_common(20)),
        'top_level': [
            {
                'name': entry['name'],
                'path': entry['path'],
                'type': 'directory' if entry['is_dir'] else 'file',
            }
            for entry in top_level
        ],
        'entrypoint_candidates': entrypoint_candidates[:50],
        'sink_candidates': sink_candidates,
    }
