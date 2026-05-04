import json

from openai import OpenAI

from .base import StructuredOutputMixin
from .types import ToolCall, ToolResponse


class OpenAIProvider(StructuredOutputMixin):
    def __init__(self, api_key, base_url='', max_output_tokens=4096, request_timeout=120):
        client_kwargs = {
            'api_key': api_key,
            'timeout': request_timeout,
        }
        if base_url:
            client_kwargs['base_url'] = base_url
        self.client = OpenAI(**client_kwargs)
        self.max_output_tokens = max_output_tokens

    def start_conversation(self, system_prompt, user_prompt):
        return [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt},
        ]

    def create_tool_response(self, model, conversation, tools):
        message = self._create_chat_completion(
            model=model,
            messages=conversation,
            tools=self._convert_tools(tools),
        ).choices[0].message

        conversation.append(self._message_to_dict(message))
        return ToolResponse(
            output_text=message.content or '',
            tool_calls=[
                ToolCall(
                    call_id=tool_call.id,
                    name=tool_call.function.name,
                    arguments=tool_call.function.arguments or '{}',
                )
                for tool_call in (message.tool_calls or [])
            ],
        )

    def append_tool_results(self, conversation, tool_results):
        for tool_call, result in tool_results:
            conversation.append({
                'role': 'tool',
                'tool_call_id': tool_call.call_id,
                'content': json.dumps(result, ensure_ascii=True),
            })

    def rebase_conversation(self, conversation, system_prompt, user_prompt, memory):
        context_window = memory.build_context_window()
        conversation[:] = [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt},
        ]
        if context_window:
            conversation.append({
                'role': 'user',
                'content': (
                    'Use this bounded scan memory instead of earlier raw tool outputs. '
                    'Do not assume evidence beyond these summaries and excerpts.\n\n'
                    f'{context_window}'
                ),
            })

    def parse_structured_output(self, model, schema, system_prompt, user_prompt):
        def call_once(current_system_prompt, current_user_prompt):
            response = self._create_chat_completion(
                model=model,
                messages=[
                    {'role': 'system', 'content': current_system_prompt},
                    {'role': 'user', 'content': current_user_prompt},
                ],
                response_format={'type': 'json_object'},
                max_tokens=self.max_output_tokens,
            )
            return response.choices[0].message.content or ''

        return self._parse_with_retry(schema, call_once, system_prompt, user_prompt)

    def _create_chat_completion(self, **kwargs):
        if 'max_tokens' not in kwargs:
            kwargs['max_tokens'] = self.max_output_tokens
        return self.client.chat.completions.create(**kwargs)

    def _convert_tools(self, tools):
        converted = []
        for tool in tools:
            function_def = {
                'name': tool['name'],
                'description': tool.get('description', ''),
                'parameters': tool.get('parameters', {}),
            }
            if tool.get('strict') is not None:
                function_def['strict'] = tool['strict']
            converted.append({
                'type': 'function',
                'function': function_def,
            })
        return converted

    def _message_to_dict(self, message):
        if hasattr(message, 'model_dump'):
            return message.model_dump(mode='json', exclude_none=True)

        payload = {
            'role': getattr(message, 'role', 'assistant'),
            'content': getattr(message, 'content', None),
        }
        tool_calls = getattr(message, 'tool_calls', None)
        if tool_calls:
            payload['tool_calls'] = [
                tool_call.model_dump(mode='json', exclude_none=True)
                if hasattr(tool_call, 'model_dump')
                else {
                    'id': tool_call.id,
                    'type': 'function',
                    'function': {
                        'name': tool_call.function.name,
                        'arguments': tool_call.function.arguments,
                    },
                }
                for tool_call in tool_calls
            ]
        return payload
