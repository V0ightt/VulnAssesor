import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from django.conf import settings
from .models import SASTFinding, SASTFix
from .services import ProjectManager

def modify_code(project, file_path, new_content):
    """Modifies a file in the project workspace."""
    manager = ProjectManager(project)
    full_path = manager.resolve_path(file_path)
    
    # Security check
    if not str(full_path).startswith(str(manager.workspace_root.resolve())):
        raise ValueError("Invalid file path.")
         
    with full_path.open('w', encoding='utf-8') as f:
        f.write(new_content)
    
    return True

def report_vulnerability(
    scan_job,
    file_path,
    line_number,
    severity,
    title,
    description,
    code_snippet,
    confidence_score=None,
):
    """Creates a new SASTFinding."""
    finding = SASTFinding.objects.create(
        scan_job=scan_job,
        file_path=file_path,
        line_number=line_number,
        severity=severity,
        title=title,
        description=description,
        code_snippet=code_snippet,
        confidence_score=confidence_score,
    )
    return finding

def get_vulnerability_context(finding_id):
    """Returns context for a finding."""
    finding = SASTFinding.objects.get(id=finding_id)
    manager = ProjectManager(finding.scan_job.project)
    
    # Read file content around the line
    content = manager.get_file_content(finding.file_path)
    lines = content.splitlines()
    
    start_line = max(0, finding.line_number - 5)
    end_line = min(len(lines), finding.line_number + 5)
    
    context_lines = lines[start_line:end_line]
    return "\n".join(context_lines)

def apply_fix(
    finding_id,
    proposed_code,
    explanation,
    scope='SNIPPET',
    start_line=1,
    end_line=1,
    verification_status='NOT_VERIFIED',
    verification_reason='',
):
    """Creates a SASTFix for a finding."""
    finding = SASTFinding.objects.get(id=finding_id)
    fix = SASTFix.objects.create(
        finding=finding,
        proposed_code=proposed_code,
        explanation=explanation,
        scope=scope,
        start_line=start_line,
        end_line=end_line,
        verification_status=verification_status,
        verification_reason=verification_reason,
    )
    return fix

def push_fixes(project, commit_message="Applied SAST fixes"):
    """Pushes changes to the remote repository."""
    manager = ProjectManager(project)
    return manager.push_changes(commit_message)

def list_project_files(project):
    """Returns a list of all scannable files in the project."""
    manager = ProjectManager(project)
    return list(
        file_path for file_path in manager.iter_workspace_files(
            ignored_directories=get_ignored_directories(),
            allowed_extensions=None,
        ) if _is_allowed_text_file(Path(file_path))
    )

def read_file(project, file_path, start_line=1, end_line=None, max_lines=None, max_bytes=None):
    """Reads a file from the project workspace."""
    manager = ProjectManager(project)
    full_path = manager.resolve_path(file_path)
    normalized_path = manager.get_relative_path(full_path)
    if not _is_allowed_text_file(full_path):
        raise ValueError("File type is not allowed for SAST reads.")
    if full_path.stat().st_size > settings.SAST_SCAN_MAX_FILE_BYTES:
        raise ValueError("File exceeds the configured SAST maximum file size.")
    window = manager.get_file_lines(file_path, start_line=start_line, end_line=end_line, max_lines=max_lines)
    content = window['content']
    truncated = window['truncated']
    if max_bytes is not None:
        encoded = content.encode('utf-8')
        if len(encoded) > max_bytes:
            content = encoded[:max_bytes].decode('utf-8', errors='ignore')
            truncated = True
    return {
        'filepath': normalized_path,
        'start_line': window['start_line'],
        'end_line': window['end_line'],
        'total_lines': window['total_lines'],
        'content': content,
        'truncated': truncated,
    }


def get_allowed_extensions():
    return tuple(settings.SAST_SCAN_ALLOWED_EXTENSIONS)


def get_ignored_directories():
    return tuple(settings.SAST_SCAN_IGNORED_DIRECTORIES)


def _is_allowed_text_file(file_path):
    allowed_extensions = set(get_allowed_extensions())
    allowed_filenames = {
        '.env',
        'dockerfile',
        'makefile',
        'readme',
        'readme.md',
        'agents.md',
    }
    return (
        file_path.suffix.lower() in allowed_extensions
        or file_path.name.lower() in allowed_filenames
    )


def list_directory(project, directory=''):
    manager = ProjectManager(project)
    all_entries = manager.get_directory_structure(
        directory,
        ignored_directories=get_ignored_directories(),
        max_entries=settings.SAST_SCAN_MAX_DIRECTORY_ENTRIES + 1,
    )
    entries = all_entries[:settings.SAST_SCAN_MAX_DIRECTORY_ENTRIES]
    return {
        'directory': directory.replace('\\', '/').strip('/'),
        'entries': [
            {
                'name': entry['name'],
                'path': entry['path'],
                'type': 'directory' if entry['is_dir'] else 'file',
            }
            for entry in entries
        ],
        'truncated': len(all_entries) > settings.SAST_SCAN_MAX_DIRECTORY_ENTRIES,
    }


def search_codebase(project, query, directory='', max_results=None):
    manager = ProjectManager(project)
    search_root = manager.resolve_path(directory)
    if not search_root.exists() or not search_root.is_dir():
        raise ValueError("Directory does not exist.")

    if shutil.which('rg'):
        try:
            return _search_with_ripgrep(manager, query, search_root, max_results=max_results)
        except subprocess.TimeoutExpired:
            return {
                'query': query,
                'directory': manager.get_relative_path(search_root) if search_root != manager.workspace_root.resolve() else '',
                'total_hits': 0,
                'truncated': True,
                'results': [],
                'error': 'ripgrep search timed out',
            }
        except Exception:
            return _search_with_python(manager, query, search_root, max_results=max_results)
    return _search_with_python(manager, query, search_root, max_results=max_results)


def _normalize_query(query):
    try:
        re.compile(query)
        return query
    except re.error:
        return re.escape(query)


def _truncate_preview(text, length=240):
    stripped = text.strip()
    if len(stripped) <= length:
        return stripped
    return stripped[:length - 3] + '...'


def _iter_search_globs():
    for extension in get_allowed_extensions():
        yield f'*{extension}'
    for filename in ('.env', 'Dockerfile', 'Makefile', 'README', 'README.md', 'agents.md'):
        yield filename
    for ignored in get_ignored_directories():
        yield f'!{ignored}/**'


def _search_with_ripgrep(manager, query, search_root, max_results=None):
    normalized_query = _normalize_query(query)
    command = [
        'rg',
        '--json',
        '--line-number',
        '--hidden',
        '-e',
        normalized_query,
        '--max-filesize',
        str(settings.SAST_SCAN_MAX_FILE_BYTES),
        '.',
    ]
    for glob in _iter_search_globs():
        command.extend(['--glob', glob])

    completed = subprocess.run(
        command,
        cwd=str(search_root),
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='ignore',
        check=False,
        timeout=settings.SAST_SCAN_RIPGREP_TIMEOUT,
    )

    if completed.returncode not in (0, 1):
        raise RuntimeError(completed.stderr.strip() or 'ripgrep search failed')

    results = []
    total_hits = 0
    max_results = max_results or settings.SAST_SCAN_MAX_SEARCH_RESULTS

    for line in completed.stdout.splitlines():
        payload = json.loads(line)
        if payload.get('type') != 'match':
            continue

        total_hits += 1
        if len(results) >= max_results:
            break

        data = payload['data']
        relative_path = Path(data['path']['text']).as_posix()
        absolute_path = (search_root / relative_path).resolve()
        results.append({
            'path': manager.get_relative_path(absolute_path),
            'line_number': data['line_number'],
            'match': _truncate_preview(data['lines']['text']),
        })

    return {
        'query': query,
        'directory': manager.get_relative_path(search_root) if search_root != manager.workspace_root.resolve() else '',
        'total_hits': total_hits,
        'truncated': total_hits > max_results or len(results) >= max_results,
        'results': results,
    }


def _search_with_python(manager, query, search_root, max_results=None):
    normalized_query = _normalize_query(query)
    pattern = re.compile(normalized_query)
    max_results = max_results or settings.SAST_SCAN_MAX_SEARCH_RESULTS
    results = []
    total_hits = 0
    ignored = set(get_ignored_directories())

    for root, dirs, filenames in os.walk(search_root):
        dirs[:] = [directory for directory in dirs if directory not in ignored]
        for filename in filenames:
            file_path = Path(root) / filename
            if not _is_allowed_text_file(file_path):
                continue
            try:
                if file_path.stat().st_size > settings.SAST_SCAN_MAX_FILE_BYTES:
                    continue
            except OSError:
                continue
            try:
                with file_path.open('r', encoding='utf-8', errors='ignore') as handle:
                    for line_number, line in enumerate(handle, start=1):
                        if not pattern.search(line):
                            continue
                        total_hits += 1
                        if len(results) < max_results:
                            results.append({
                                'path': manager.get_relative_path(file_path),
                                'line_number': line_number,
                                'match': _truncate_preview(line),
                            })
                        else:
                            return {
                                'query': query,
                                'directory': manager.get_relative_path(search_root) if search_root != manager.workspace_root.resolve() else '',
                                'total_hits': total_hits,
                                'truncated': True,
                                'results': results,
                            }
            except OSError:
                continue

    return {
        'query': query,
        'directory': manager.get_relative_path(search_root) if search_root != manager.workspace_root.resolve() else '',
        'total_hits': total_hits,
        'truncated': total_hits > max_results,
        'results': results,
    }
