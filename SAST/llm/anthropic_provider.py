import json

from .base import StructuredOutputMixin
from .types import ToolCall, ToolResponse


class AnthropicProvider(StructuredOutputMixin):
    def __init__(self, api_key, base_url='', max_output_tokens=4096, request_timeout=120):
        try:
            from anthropic import Anthropic
        except ImportError as exc:
            raise ValueError("The anthropic package is not installed.") from exc

        client_kwargs = {
            'api_key': api_key,
            'timeout': request_timeout,
        }
        if base_url:
            client_kwargs['base_url'] = base_url
        self.client = Anthropic(**client_kwargs)
        self.max_output_tokens = max_output_tokens

    def start_conversation(self, system_prompt, user_prompt):
        return {
            'system': system_prompt,
            'messages': [{'role': 'user', 'content': user_prompt}],
        }

    def create_tool_response(self, model, conversation, tools):
        response = self.client.messages.create(
            model=model,
            system=conversation['system'],
            messages=conversation['messages'],
            tools=self._convert_tools(tools),
            max_tokens=self.max_output_tokens,
        )
        content = [self._content_block_to_dict(block) for block in response.content]
        conversation['messages'].append({'role': 'assistant', 'content': content})

        tool_calls = []
        text_chunks = []
        for block in content:
            if block.get('type') == 'tool_use':
                tool_calls.append(ToolCall(
                    call_id=block['id'],
                    name=block['name'],
                    arguments=json.dumps(block.get('input') or {}, ensure_ascii=True),
                ))
            elif block.get('type') == 'text' and block.get('text'):
                text_chunks.append(block['text'])

        return ToolResponse(output_text="\n".join(text_chunks), tool_calls=tool_calls)

    def append_tool_results(self, conversation, tool_results):
        conversation['messages'].append({
            'role': 'user',
            'content': [
                {
                    'type': 'tool_result',
                    'tool_use_id': tool_call.call_id,
                    'content': json.dumps(result, ensure_ascii=True),
                }
                for tool_call, result in tool_results
            ],
        })

    def parse_structured_output(self, model, schema, system_prompt, user_prompt):
        def call_once(current_system_prompt, current_user_prompt):
            response = self.client.messages.create(
                model=model,
                system=current_system_prompt,
                messages=[{'role': 'user', 'content': current_user_prompt}],
                max_tokens=self.max_output_tokens,
            )
            return self._extract_text(response.content)

        return self._parse_with_retry(schema, call_once, system_prompt, user_prompt)

    def _convert_tools(self, tools):
        converted = []
        for tool in tools:
            converted_tool = {
                'name': tool['name'],
                'description': tool.get('description', ''),
                'input_schema': tool.get('parameters', {}),
            }
            if tool.get('strict') is not None:
                converted_tool['strict'] = tool['strict']
            converted.append(converted_tool)
        return converted

    def _content_block_to_dict(self, block):
        if hasattr(block, 'model_dump'):
            return block.model_dump(mode='json', exclude_none=True)
        if isinstance(block, dict):
            return dict(block)
        return {
            key: value for key, value in vars(block).items()
            if not key.startswith('_')
        }

    def _extract_text(self, content_blocks):
        chunks = []
        for block in content_blocks:
            raw_block = self._content_block_to_dict(block)
            if raw_block.get('type') == 'text' and raw_block.get('text'):
                chunks.append(raw_block['text'])
        return "\n".join(chunks)
