from .models import ProjectProgressEvent


def record_project_event(project, phase, event_type, title, detail='', payload=None, scan_job=None):
    if not project:
        return None
    return ProjectProgressEvent.record(
        project=project,
        scan_job=scan_job,
        phase=phase,
        event_type=event_type,
        title=title,
        detail=detail,
        payload=_safe_payload(payload or {}),
    )


def record_scan_event(scan_job, phase, event_type, title, detail='', payload=None):
    if not scan_job:
        return None
    return record_project_event(
        scan_job.project,
        phase=phase,
        event_type=event_type,
        title=title,
        detail=detail,
        payload=payload,
        scan_job=scan_job,
    )


def summarize_tool_result(tool_name, arguments, result):
    payload = result if isinstance(result, dict) else {'value': result}
    if tool_name == 'list_directory':
        entries = payload.get('entries', [])
        return {
            'directory': arguments.get('directory', '') or '.',
            'entry_count': len(entries),
            'sample_paths': [entry.get('path') or entry.get('name') for entry in entries[:8]],
            'truncated': bool(payload.get('truncated')),
            'error': payload.get('error', ''),
        }
    if tool_name == 'search_codebase':
        results = payload.get('results', [])
        return {
            'query': arguments.get('query', ''),
            'directory': arguments.get('directory', '') or '.',
            'total_hits': payload.get('total_hits', len(results)),
            'sample_matches': [
                f"{item.get('path')}:{item.get('line_number')}"
                for item in results[:8]
            ],
            'truncated': bool(payload.get('truncated')),
            'error': payload.get('error', ''),
        }
    if tool_name == 'read_file':
        return {
            'filepath': arguments.get('filepath', ''),
            'start_line': payload.get('start_line', arguments.get('start_line', 1)),
            'end_line': payload.get('end_line', arguments.get('end_line')),
            'total_lines': payload.get('total_lines'),
            'truncated': bool(payload.get('truncated')),
            'error': payload.get('error', ''),
        }
    return {'tool': tool_name, 'error': payload.get('error', '')}


def _safe_payload(payload):
    safe = {}
    blocked_keys = {'content', 'code', 'code_snippet', 'fixed_code', 'proposed_code', 'output'}
    for key, value in payload.items():
        key_text = str(key)
        if key_text in blocked_keys or value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            safe[key_text[:80]] = value if not isinstance(value, str) else value[:500]
        elif isinstance(value, (list, tuple)):
            safe[key_text[:80]] = [str(item)[:200] for item in value[:20] if item is not None]
        elif isinstance(value, dict):
            safe[key_text[:80]] = {
                str(inner_key)[:80]: str(inner_value)[:200]
                for inner_key, inner_value in list(value.items())[:20]
                if str(inner_key) not in blocked_keys
            }
        else:
            safe[key_text[:80]] = str(value)[:200]
    return safe
