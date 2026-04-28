from agent.models.adapters.claude import ClaudeMessagesAdapter
from agent.models.adapters.gemini import GeminiGenerateContentAdapter
from agent.models.adapters.openai_chat import OpenAIChatCompletionsAdapter
from agent.models.adapters.openai_responses import OpenAIResponsesAdapter


_ADAPTERS = {
    "openai-chat": OpenAIChatCompletionsAdapter,
    "openai-responses": OpenAIResponsesAdapter,
    "claude-messages": ClaudeMessagesAdapter,
    "gemini": GeminiGenerateContentAdapter,
}


def adapter_for_protocol(protocol: str):
    from agent.models.constants import normalize_protocol

    standard = normalize_protocol(protocol)
    cls = _ADAPTERS.get(standard)
    if cls is None:
        raise ValueError("unsupported model protocol: %s" % protocol)
    return cls()
