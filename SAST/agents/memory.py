import json
from collections import Counter
from dataclasses import dataclass


@dataclass
class MemoryEvent:
    summary_line: str
    evidence_excerpt: str
    token_estimate: int


class ScanMemoryManager:
    def __init__(self, soft_token_threshold, hard_token_threshold):
        self.soft_token_threshold = soft_token_threshold
        self.hard_token_threshold = hard_token_threshold
        self.summary_lines = []
        self.recent_events = []
        self.tool_counts = Counter()
        self.truncation_count = 0
        self.explored_paths = set()
        self.compactions = 0
        self.total_calls = 0

    def record_tool_result(self, tool_name, arguments, call_id, result):
        result_payload = result if isinstance(result, dict) else {'value': result}
        output_text = json.dumps(result_payload, ensure_ascii=True)
        event = MemoryEvent(
            summary_line=self._build_summary_line(tool_name, arguments, result_payload),
            evidence_excerpt=self._build_evidence_excerpt(tool_name, result_payload),
            token_estimate=max(1, len(output_text) // 4),
        )
        self.total_calls += 1
        self.tool_counts[tool_name] += 1
        if result_payload.get('truncated'):
            self.truncation_count += 1
        self._capture_paths(result_payload)
        self.recent_events.append(event)
        self._compact_if_needed()
        return {
            'type': 'scan_memory_summary',
            'call_id': call_id,
            'output': event.summary_line,
        }

    def build_input_items(self):
        context = self.build_context_window()
        return [{'role': 'user', 'content': context}] if context else []

    def build_context_window(self):
        chunks = []
        if self.summary_lines:
            chunks.append(
                'Compact summary of earlier tool results:\n'
                + '\n'.join(f'- {line}' for line in self.summary_lines[-20:])
            )
        if self.recent_events:
            recent_summaries = '\n'.join(
                f'- {event.summary_line}' for event in self.recent_events[-10:]
            )
            chunks.append('Recent tool result summaries:\n' + recent_summaries)
            excerpts = [
                event.evidence_excerpt
                for event in self.recent_events[-6:]
                if event.evidence_excerpt
            ]
            if excerpts:
                chunks.append('Bounded recent evidence excerpts:\n' + '\n\n'.join(excerpts))
        return '\n\n'.join(chunks).strip()

    def build_investigation_summary(self, final_response_text='', include_evidence_excerpts=False):
        chunks = []
        if self.summary_lines:
            chunks.append('Earlier exploration summary:\n' + '\n'.join(f'- {line}' for line in self.summary_lines[-20:]))
        if self.recent_events:
            recent_text = '\n'.join(
                f'- {event.summary_line}' for event in self.recent_events[-10:]
            )
            chunks.append('Recent tool results:\n' + recent_text)
            if include_evidence_excerpts:
                excerpts = [
                    event.evidence_excerpt
                    for event in self.recent_events[-6:]
                    if event.evidence_excerpt
                ]
                if excerpts:
                    chunks.append('Bounded recent evidence excerpts:\n' + '\n\n'.join(excerpts))
        if final_response_text:
            chunks.append('Model investigation summary:\n' + final_response_text.strip())
        return '\n\n'.join(chunk for chunk in chunks if chunk).strip()

    def build_metadata(self, stop_reason, final_response_text=''):
        return {
            'summary': self.build_investigation_summary(final_response_text),
            'tool_call_count': self.total_calls,
            'tool_counts': dict(self.tool_counts),
            'truncation_count': self.truncation_count,
            'explored_paths': sorted(self.explored_paths),
            'compactions': self.compactions,
            'stop_reason': stop_reason,
        }

    def _build_summary_line(self, tool_name, arguments, result_payload):
        if result_payload.get('error'):
            return f'{tool_name} returned error: {str(result_payload["error"])[:180]}'
        if tool_name == 'list_directory':
            directory = arguments.get('directory', '') or '.'
            entries = result_payload.get('entries', [])
            sample = ', '.join(entry.get('path', entry.get('name', '')) for entry in entries[:5]) or 'no entries'
            return f'Listed {directory}: {sample}'
        if tool_name == 'search_codebase':
            query = arguments.get('query', '')
            results = result_payload.get('results', [])
            sample = ', '.join(f"{item.get('path')}:{item.get('line_number')}" for item in results[:5]) or 'no matches'
            return f'Searched for `{query}` and found {result_payload.get("total_hits", 0)} hits ({sample})'
        if tool_name == 'read_file':
            filepath = arguments.get('filepath', '')
            start_line = result_payload.get('start_line', arguments.get('start_line', 1))
            end_line = result_payload.get('end_line', arguments.get('end_line', start_line))
            return f'Read {filepath}:{start_line}-{end_line}'
        return f'Used {tool_name}'

    def _build_evidence_excerpt(self, tool_name, result_payload):
        if result_payload.get('error'):
            return ''
        if tool_name == 'search_codebase':
            lines = []
            for item in result_payload.get('results', [])[:5]:
                match = (item.get('match') or '').strip()
                if match:
                    match = match[:220]
                lines.append(f"{item.get('path')}:{item.get('line_number')}: {match}")
            return '\n'.join(lines)
        if tool_name == 'read_file':
            content = (result_payload.get('content') or '').strip()
            if not content:
                return ''
            filepath = result_payload.get('filepath', '')
            start_line = result_payload.get('start_line', 1)
            end_line = result_payload.get('end_line', start_line)
            if len(content) > 1200:
                content = content[:1200] + '\n...[excerpt truncated]...'
            return f'{filepath}:{start_line}-{end_line}\n{content}'
        if tool_name == 'list_directory':
            sample = ', '.join(
                entry.get('path') or entry.get('name', '')
                for entry in result_payload.get('entries', [])[:20]
            )
            return f"Directory sample: {sample}" if sample else ''
        return ''

    def _capture_paths(self, result_payload):
        for entry in result_payload.get('entries', []):
            path = entry.get('path')
            if path:
                self.explored_paths.add(path)
        for entry in result_payload.get('results', []):
            path = entry.get('path')
            if path:
                self.explored_paths.add(path)
        filepath = result_payload.get('filepath')
        if filepath:
            self.explored_paths.add(filepath)

    def _compact_if_needed(self):
        while self._estimated_recent_tokens() > self.soft_token_threshold and len(self.recent_events) > 1:
            event = self.recent_events.pop(0)
            self.summary_lines.append(event.summary_line)
            self.compactions += 1

        if self._estimated_recent_tokens() > self.hard_token_threshold and self.recent_events:
            event = self.recent_events.pop(0)
            self.summary_lines.append(event.summary_line)
            self.compactions += 1

    def _estimated_recent_tokens(self):
        return sum(event.token_estimate for event in self.recent_events)


@dataclass
class ExplorationResult:
    final_response_text: str
    stop_reason: str
    memory: ScanMemoryManager


def merge_memory_metadata(metadata_items, stop_reason='completed'):
    metadata_items = [item or {} for item in metadata_items if item]
    tool_counts = Counter()
    explored_paths = set()
    summary_chunks = []
    total_tool_calls = 0
    truncation_count = 0
    compactions = 0

    for metadata in metadata_items:
        total_tool_calls += metadata.get('tool_call_count', 0)
        tool_counts.update(metadata.get('tool_counts', {}))
        truncation_count += metadata.get('truncation_count', 0)
        explored_paths.update(metadata.get('explored_paths', []))
        compactions += metadata.get('compactions', 0)
        if metadata.get('summary'):
            summary_chunks.append(metadata['summary'])

    return {
        'summary': '\n\n'.join(summary_chunks),
        'tool_call_count': total_tool_calls,
        'tool_counts': dict(tool_counts),
        'truncation_count': truncation_count,
        'explored_paths': sorted(explored_paths),
        'compactions': compactions,
        'stop_reason': stop_reason,
    }


def aggregate_scan_metadata(orchestrator_metadata=None, specialist_entries=None, stop_reason='completed'):
    specialist_entries = specialist_entries or []
    nested_specialists = [
        {
            'surface_id': entry.get('surface_id', ''),
            'vulnerability_type': entry.get('vulnerability_type', ''),
            'metadata': entry.get('metadata', {}),
        }
        for entry in specialist_entries
    ]
    aggregate = merge_memory_metadata(
        [orchestrator_metadata] + [entry['metadata'] for entry in nested_specialists],
        stop_reason=stop_reason,
    )
    aggregate['orchestrator'] = orchestrator_metadata or {}
    aggregate['specialists'] = nested_specialists
    return aggregate
