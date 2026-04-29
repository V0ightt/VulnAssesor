from Dashboard.models import AIConfig

from .anthropic_provider import AnthropicProvider
from .deepseek_provider import DeepSeekProvider
from .openai_provider import OpenAIProvider


def build_provider(ai_config):
    api_key = ai_config.require_api_key()
    settings = ai_config.selected_provider_settings()
    kwargs = {
        'api_key': api_key,
        'base_url': settings['base_url'],
        'max_output_tokens': settings['max_output_tokens'],
        'request_timeout': settings['request_timeout'],
    }

    if ai_config.provider == AIConfig.PROVIDER_OPENAI:
        return OpenAIProvider(**kwargs)
    if ai_config.provider == AIConfig.PROVIDER_ANTHROPIC:
        return AnthropicProvider(**kwargs)
    if ai_config.provider == AIConfig.PROVIDER_DEEPSEEK:
        return DeepSeekProvider(**kwargs)

    raise ValueError(f"Unsupported AI provider: {ai_config.provider}")
