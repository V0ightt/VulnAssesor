import json
import logging

from pydantic import ValidationError

logger = logging.getLogger(__name__)


class StructuredOutputMixin:
    max_output_tokens: int

    def _schema_prompt(self, schema):
        schema_json = json.dumps(schema.model_json_schema(), ensure_ascii=True)
        return (
            "Return only valid JSON. The JSON must match this schema exactly enough "
            f"for Pydantic validation:\n{schema_json}"
        )

    def _parse_json_payload(self, content):
        text = (content or '').strip()
        if text.startswith('```'):
            text = text.strip('`')
            if text.lower().startswith('json'):
                text = text[4:].strip()
        return json.loads(text)

    def _validate_structured_content(self, content, schema):
        payload = self._parse_json_payload(content)
        return schema.model_validate(payload)

    def _structured_retry_prompt(self, schema, validation_error):
        return (
            self._schema_prompt(schema)
            + "\n\nThe previous response failed validation. "
            + f"Validation error: {validation_error}. Return corrected JSON only."
        )

    def _parse_with_retry(self, schema, call_once, system_prompt, user_prompt):
        prompt = self._schema_prompt(schema)
        try:
            return self._validate_structured_content(
                call_once(system_prompt + "\n\n" + prompt, user_prompt),
                schema,
            )
        except (json.JSONDecodeError, ValidationError) as exc:
            logger.warning("Structured AI output failed validation; retrying once: %s", exc)
            retry_system_prompt = system_prompt + "\n\n" + self._structured_retry_prompt(schema, exc)
            return self._validate_structured_content(call_once(retry_system_prompt, user_prompt), schema)
