from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class ToolCall:
    call_id: str
    name: str
    arguments: str


@dataclass
class ToolResponse:
    output_text: str
    tool_calls: list[ToolCall]


class LLMProvider(Protocol):
    def start_conversation(self, system_prompt: str, user_prompt: str) -> Any:
        ...

    def create_tool_response(self, model: str, conversation: Any, tools: list[dict]) -> ToolResponse:
        ...

    def append_tool_results(self, conversation: Any, tool_results: list[tuple[ToolCall, dict]]) -> None:
        ...

    def parse_structured_output(self, model: str, schema: Any, system_prompt: str, user_prompt: str) -> Any:
        ...
