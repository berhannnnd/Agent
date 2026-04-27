from app.agent.providers.adapters.claude import ClaudeMessagesAdapter
from app.agent.providers.adapters.gemini import GeminiGenerateContentAdapter
from app.agent.providers.adapters.openai_chat import OpenAIChatCompletionsAdapter
from app.agent.providers.adapters.openai_responses import OpenAIResponsesAdapter


_ADAPTERS = {
    "openai-chat": OpenAIChatCompletionsAdapter,
    "openai-responses": OpenAIResponsesAdapter,
    "claude-messages": ClaudeMessagesAdapter,
    "gemini": GeminiGenerateContentAdapter,
}


def adapter_for_provider(provider: str):
    from app.agent.providers.constants import normalize_provider

    standard = normalize_provider(provider)
    cls = _ADAPTERS.get(standard)
    if cls is None:
        raise ValueError("unsupported provider: %s" % provider)
    return cls()
