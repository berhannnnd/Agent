# !/usr/bin/env python
# -*- coding: utf-8 -*-
# =====================================================
# @File   ：test_agent_providers.py
# @Date   ：2026/04/24 00:00
# @Author ：Zegen
#
# 2026/04/24   Create
# =====================================================

from app.agent.providers.adapters import (
    ClaudeMessagesAdapter,
    GeminiGenerateContentAdapter,
    OpenAIChatCompletionsAdapter,
    OpenAIResponsesAdapter,
)
from app.agent.providers.client import HttpxModelTransport, ModelClient, ModelClientConfig
from app.agent.providers.stream import parse_sse_json_line
from app.agent.schema import Message, ModelRequest, ToolCall, ToolSpec


class FakeTransport:
    def __init__(self, response=None, stream=None):
        self.response = response
        self.stream = list(stream or [])
        self.requests = []

    def post_json(self, path, payload, headers, timeout):
        self.requests.append(("post", path, payload, headers, timeout))
        return self.response

    def stream_json(self, path, payload, headers, timeout):
        self.requests.append(("stream", path, payload, headers, timeout))
        return iter(self.stream)

    async def async_post_json(self, path, payload, headers, timeout):
        return self.post_json(path, payload, headers, timeout)

    async def async_stream_json(self, path, payload, headers, timeout):
        for item in self.stream_json(path, payload, headers, timeout):
            yield item


class FakeStreamResponse:
    def __init__(self, lines):
        self.lines = [line.encode("utf-8") for line in lines]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def __iter__(self):
        return iter(self.lines)


def sample_request(provider="openai-chat", model="test-model"):
    return ModelRequest(
        provider=provider,
        model=model,
        messages=[
            Message.from_text("system", "Be concise."),
            Message.from_text("user", "hello"),
        ],
        tools=[
            ToolSpec(
                name="echo",
                description="Echo text",
                parameters={
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"],
                },
            )
        ],
    )


def test_transport_skips_sse_event_metadata():
    events = [
        parsed
        for parsed in [
            parse_sse_json_line("event: response.created"),
            parse_sse_json_line('data: {"type":"response.output_text.delta","delta":"ok"}'),
            parse_sse_json_line(""),
            parse_sse_json_line("event: response.completed"),
            parse_sse_json_line('data: {"type":"response.completed","response":{"output":[]}}'),
        ]
        if parsed is not None
    ]

    assert events == [
        {"type": "response.output_text.delta", "delta": "ok"},
        {"type": "response.completed", "response": {"output": []}},
    ]


def test_httpx_transport_uses_configured_proxy(monkeypatch):
    import asyncio

    captured = {}

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"ok": True}

    class FakeClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def post(self, url, json=None, headers=None, timeout=None):
            captured["url"] = url
            return FakeResponse()

    monkeypatch.setattr("app.agent.providers.transport.httpx.AsyncClient", FakeClient)

    response = asyncio.run(
        HttpxModelTransport("https://api.example/v1", proxy_url="http://127.0.0.1:7890").async_post_json(
            "/responses",
            {},
            {},
            30,
        )
    )

    assert response == {"ok": True}
    assert captured["proxy"] == "http://127.0.0.1:7890"
    assert captured["trust_env"] is False


def test_openai_chat_adapter_builds_payload_and_parses_tool_call():
    adapter = OpenAIChatCompletionsAdapter()
    payload = adapter.request_payload(sample_request())

    assert payload["messages"][0] == {"role": "system", "content": "Be concise."}
    assert payload["tools"][0]["function"]["name"] == "echo"
    assert payload["tool_choice"] == "auto"

    response = adapter.parse_response(
        {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "call-1",
                                "type": "function",
                                "function": {"name": "echo", "arguments": "{\"text\":\"hi\"}"},
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
        }
    )

    assert response.tool_calls[0].name == "echo"
    assert response.tool_calls[0].arguments == {"text": "hi"}
    assert response.stop_reason == "tool_calls"
    assert response.usage.total_tokens == 3


def test_openai_responses_adapter_builds_payload_and_parses_function_call():
    adapter = OpenAIResponsesAdapter()
    payload = adapter.request_payload(sample_request("openai-responses"))

    assert payload["instructions"] == "Be concise."
    assert payload["input"][0] == {"role": "user", "content": "hello"}
    assert payload["tools"][0]["type"] == "function"
    assert payload["tools"][0]["name"] == "echo"

    response = adapter.parse_response(
        {
            "output": [
                {"type": "message", "content": [{"type": "output_text", "text": "thinking"}]},
                {
                    "type": "function_call",
                    "call_id": "call-1",
                    "name": "echo",
                    "arguments": "{\"text\":\"hi\"}",
                },
            ],
            "usage": {"input_tokens": 2, "output_tokens": 3, "total_tokens": 5},
            "status": "completed",
        }
    )

    assert response.content_text() == "thinking"
    assert response.tool_calls[0].id == "call-1"
    assert response.tool_calls[0].arguments == {"text": "hi"}
    assert response.message.raw["output"][1]["type"] == "function_call"


def test_openai_responses_payload_preserves_function_call_context():
    adapter = OpenAIResponsesAdapter()
    assistant = Message.from_text(
        "assistant",
        "",
        tool_calls=[ToolCall(id="call-1", name="echo", arguments={"text": "hi"})],
        raw={
            "output": [
                {
                    "type": "function_call",
                    "call_id": "call-1",
                    "name": "echo",
                    "arguments": "{\"text\":\"hi\"}",
                }
            ]
        },
    )
    request = ModelRequest(
        provider="openai-responses",
        model="test-model",
        messages=[
            Message.from_text("user", "hello"),
            assistant,
            Message.from_text("tool", "hi", tool_call_id="call-1", name="echo"),
        ],
    )

    payload = adapter.request_payload(request)

    assert payload["input"] == [
        {"role": "user", "content": "hello"},
        {
            "type": "function_call",
            "call_id": "call-1",
            "name": "echo",
            "arguments": "{\"text\":\"hi\"}",
        },
        {"type": "function_call_output", "call_id": "call-1", "output": "hi"},
    ]


def test_claude_messages_adapter_builds_payload_and_parses_tool_use():
    adapter = ClaudeMessagesAdapter()
    payload = adapter.request_payload(sample_request("claude-messages", "claude-test"))

    assert payload["system"] == "Be concise."
    assert payload["messages"][0]["role"] == "user"
    assert payload["tools"][0]["input_schema"]["required"] == ["text"]

    response = adapter.parse_response(
        {
            "content": [
                {"type": "text", "text": "use tool"},
                {"type": "tool_use", "id": "toolu-1", "name": "echo", "input": {"text": "hi"}},
            ],
            "stop_reason": "tool_use",
            "usage": {"input_tokens": 4, "output_tokens": 5},
        }
    )

    assert response.content_text() == "use tool"
    assert response.tool_calls[0].id == "toolu-1"
    assert response.tool_calls[0].arguments == {"text": "hi"}


def test_claude_messages_groups_consecutive_tool_results():
    adapter = ClaudeMessagesAdapter()
    request = ModelRequest(
        provider="claude-messages",
        model="claude-test",
        messages=[
            Message.from_text("user", "hello"),
            Message.from_text(
                "assistant",
                "",
                tool_calls=[
                    ToolCall(id="toolu-1", name="first", arguments={}),
                    ToolCall(id="toolu-2", name="second", arguments={}),
                ],
            ),
            Message.from_text("tool", "one", tool_call_id="toolu-1", name="first"),
            Message.from_text("tool", "two", tool_call_id="toolu-2", name="second"),
        ],
    )

    payload = adapter.request_payload(request)

    assert payload["messages"][2] == {
        "role": "user",
        "content": [
            {"type": "tool_result", "tool_use_id": "toolu-1", "content": "one"},
            {"type": "tool_result", "tool_use_id": "toolu-2", "content": "two"},
        ],
    }


def test_gemini_adapter_builds_payload_and_parses_function_call():
    adapter = GeminiGenerateContentAdapter()
    payload = adapter.request_payload(sample_request("gemini", "gemini-test"))

    assert payload["systemInstruction"]["parts"][0]["text"] == "Be concise."
    assert payload["contents"][0]["parts"][0]["text"] == "hello"
    assert payload["tools"][0]["functionDeclarations"][0]["name"] == "echo"

    response = adapter.parse_response(
        {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "use tool"},
                            {"functionCall": {"id": "call-1", "name": "echo", "args": {"text": "hi"}}},
                        ]
                    },
                    "finishReason": "STOP",
                }
            ],
            "usageMetadata": {"promptTokenCount": 1, "candidatesTokenCount": 2, "totalTokenCount": 3},
        }
    )

    assert response.content_text() == "use tool"
    assert response.tool_calls[0].name == "echo"
    assert response.usage.total_tokens == 3
    assert response.message.raw["content"]["parts"][1]["functionCall"]["id"] == "call-1"


def test_gemini_payload_preserves_raw_model_content():
    adapter = GeminiGenerateContentAdapter()
    assistant = Message.from_text(
        "assistant",
        "",
        tool_calls=[ToolCall(id="call-1", name="echo", arguments={"text": "hi"})],
        raw={
            "content": {
                "role": "model",
                "parts": [
                    {
                        "functionCall": {"id": "call-1", "name": "echo", "args": {"text": "hi"}},
                        "thoughtSignature": "signature",
                    }
                ],
            }
        },
    )
    request = ModelRequest(
        provider="gemini",
        model="gemini-test",
        messages=[
            Message.from_text("user", "hello"),
            assistant,
            Message.from_text("tool", "hi", tool_call_id="call-1", name="echo"),
        ],
    )

    payload = adapter.request_payload(request)

    assert payload["contents"][1]["parts"][0]["thoughtSignature"] == "signature"


def test_gemini_groups_consecutive_function_responses():
    adapter = GeminiGenerateContentAdapter()
    request = ModelRequest(
        provider="gemini",
        model="gemini-test",
        messages=[
            Message.from_text("user", "hello"),
            Message.from_text(
                "assistant",
                "",
                tool_calls=[
                    ToolCall(id="call-1", name="first", arguments={}),
                    ToolCall(id="call-2", name="second", arguments={}),
                ],
            ),
            Message.from_text("tool", "one", tool_call_id="call-1", name="first"),
            Message.from_text("tool", "two", tool_call_id="call-2", name="second"),
        ],
    )

    payload = adapter.request_payload(request)

    assert payload["contents"][2] == {
        "role": "user",
        "parts": [
            {"functionResponse": {"id": "call-1", "name": "first", "response": {"result": "one"}}},
            {"functionResponse": {"id": "call-2", "name": "second", "response": {"result": "two"}}},
        ],
    }


def test_model_client_posts_to_provider_path_and_parses_response():
    transport = FakeTransport(
        {
            "choices": [
                {
                    "message": {"role": "assistant", "content": "done"},
                    "finish_reason": "stop",
                }
            ]
        }
    )
    client = ModelClient(
        ModelClientConfig(
            provider="openai-chat",
            model="test-model",
            api_key="test-key",
            base_url="https://api.test.local/v1/chat/completions",
        ),
        transport=transport,
    )

    response = client.complete(sample_request())

    method, path, payload, headers, timeout = transport.requests[0]
    assert client.config.base_url == "https://api.test.local/v1"
    assert path == "/chat/completions"
    assert payload["model"] == "test-model"
    assert headers["Authorization"] == "Bearer test-key"
    assert response.content_text() == "done"


def test_model_client_uses_api_key_header_for_azure_openai_v1():
    transport = FakeTransport(
        {
            "output": [
                {"type": "message", "content": [{"type": "output_text", "text": "done"}]},
            ],
            "status": "completed",
        }
    )
    client = ModelClient(
        ModelClientConfig(
            provider="openai-responses",
            model="gpt-5.4-5",
            api_key="azure-key",
            base_url="https://example-resource.openai.azure.com/openai/v1",
        ),
        transport=transport,
    )

    response = client.complete(sample_request("openai-responses", "gpt-5.4-5"))

    method, path, payload, headers, timeout = transport.requests[0]
    assert path == "/responses"
    assert payload["model"] == "gpt-5.4-5"
    assert headers == {"api-key": "azure-key"}
    assert response.content_text() == "done"


def test_model_client_streams_openai_chat_tool_calls():
    transport = FakeTransport(
        stream=[
            {"choices": [{"delta": {"content": "use "}}]},
            {"choices": [{"delta": {"content": "tool"}}]},
            {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": "call-1",
                                    "type": "function",
                                    "function": {"name": "echo", "arguments": ""},
                                }
                            ]
                        }
                    }
                ]
            },
            {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": "{\"text\""}}]}}]},
            {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": ":\"hi\"}"}}]}}]},
        ]
    )
    client = ModelClient(
        ModelClientConfig(provider="openai-chat", model="test-model", api_key="test-key"),
        transport=transport,
    )

    events = list(client.stream(sample_request()))
    final = events[-1].response

    assert "".join(event.delta for event in events if event.type == "text_delta") == "use tool"
    assert final.content_text() == "use tool"
    assert final.tool_calls[0].id == "call-1"
    assert final.tool_calls[0].name == "echo"
    assert final.tool_calls[0].arguments == {"text": "hi"}


def test_model_client_streams_openai_responses_completed_event():
    transport = FakeTransport(
        stream=[
            {"type": "response.output_text.delta", "delta": "done"},
            {
                "type": "response.completed",
                "response": {
                    "output": [
                        {"type": "message", "content": [{"type": "output_text", "text": "done"}]},
                    ],
                    "status": "completed",
                },
            },
        ]
    )
    client = ModelClient(
        ModelClientConfig(provider="openai-responses", model="test-model", api_key="test-key"),
        transport=transport,
    )

    events = list(client.stream(sample_request("openai-responses")))

    assert events[-1].response.content_text() == "done"


def test_model_client_streams_openai_responses_tool_calls():
    transport = FakeTransport(
        stream=[
            {"type": "response.output_text.delta", "delta": "use tool"},
            {
                "type": "response.output_item.added",
                "item": {
                    "id": "fc-1",
                    "type": "function_call",
                    "call_id": "call-1",
                    "name": "echo",
                    "arguments": "",
                },
            },
            {"type": "response.function_call_arguments.delta", "delta": "{\"text\""},
            {"type": "response.function_call_arguments.delta", "delta": ":\"hi\"}"},
        ]
    )
    client = ModelClient(
        ModelClientConfig(provider="openai-responses", model="test-model", api_key="test-key"),
        transport=transport,
    )

    events = list(client.stream(sample_request("openai-responses")))
    final = events[-1].response

    assert final.content_text() == "use tool"
    assert final.tool_calls[0].id == "call-1"
    assert final.tool_calls[0].name == "echo"
    assert final.tool_calls[0].arguments == {"text": "hi"}
    assert final.message.raw["output"][0]["type"] == "function_call"


def test_model_client_streams_claude_messages_tool_calls():
    transport = FakeTransport(
        stream=[
            {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "use tool"}},
            {
                "type": "content_block_start",
                "index": 1,
                "content_block": {"type": "tool_use", "id": "toolu-1", "name": "echo", "input": {}},
            },
            {
                "type": "content_block_delta",
                "index": 1,
                "delta": {"type": "input_json_delta", "partial_json": "{\"text\""},
            },
            {
                "type": "content_block_delta",
                "index": 1,
                "delta": {"type": "input_json_delta", "partial_json": ":\"hi\"}"},
            },
        ]
    )
    client = ModelClient(
        ModelClientConfig(provider="claude-messages", model="claude-test", api_key="test-key"),
        transport=transport,
    )

    events = list(client.stream(sample_request("claude-messages", "claude-test")))
    final = events[-1].response

    assert final.content_text() == "use tool"
    assert final.tool_calls[0].id == "toolu-1"
    assert final.tool_calls[0].name == "echo"
    assert final.tool_calls[0].arguments == {"text": "hi"}


def test_model_client_streams_gemini_tool_calls():
    transport = FakeTransport(
        stream=[
            {"candidates": [{"content": {"parts": [{"text": "use tool"}]}}]},
            {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {"functionCall": {"id": "call-1", "name": "echo", "args": {"text": "hi"}}}
                            ]
                        }
                    }
                ]
            },
        ]
    )
    client = ModelClient(
        ModelClientConfig(provider="gemini", model="gemini-test", api_key="test-key"),
        transport=transport,
    )

    events = list(client.stream(sample_request("gemini", "gemini-test")))
    final = events[-1].response

    assert final.content_text() == "use tool"
    assert final.tool_calls[0].id == "call-1"
    assert final.tool_calls[0].name == "echo"
    assert final.tool_calls[0].arguments == {"text": "hi"}
