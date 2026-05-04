from .models import ScanProgressEvent


def record_scan_event(scan_job, phase, event_type, title, detail='', payload=None):
    if not scan_job:
        return None
    return ScanProgressEvent.record(
        scan_job=scan_job,
        phase=phase,
        event_type=event_type,
        title=title,
        detail=detail,
        payload=_safe_payload(payload or {}),
    )


def _safe_payload(payload):
    safe = {}
    for key, value in payload.items():
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            safe[key] = value if not isinstance(value, str) else value[:500]
        elif isinstance(value, (list, tuple)):
            safe[key] = [str(item)[:200] for item in value[:20]]
        elif isinstance(value, dict):
            safe[key] = {
                str(inner_key)[:80]: str(inner_value)[:200]
                for inner_key, inner_value in list(value.items())[:20]
            }
        else:
            safe[key] = str(value)[:200]
    return safe
