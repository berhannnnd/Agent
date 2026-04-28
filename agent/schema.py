# !/usr/bin/env python
# -*- coding: utf-8 -*-
# =====================================================
# @File   ：schema.py
# @Date   ：2026/04/24 00:00
# @Author ：Zegen
#
# 2026/04/24   Create
# =====================================================

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


def _copy_mapping(value: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    return deepcopy(value) if value else {}


def _copy_raw(value: Any) -> Any:
    return deepcopy(value) if value is not None else None


@dataclass(frozen=True)
class ContentBlock:
    type: str
    text: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    raw: Any = None

    @classmethod
    def from_text(cls, text: str, raw: Any = None) -> "ContentBlock":
        return cls(type="text", text=text, raw=raw)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "ContentBlock":
        return cls(
            type=payload["type"],
            text=payload.get("text", ""),
            data=_copy_mapping(payload.get("data")),
            raw=_copy_raw(payload.get("raw")),
        )

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"type": self.type}
        if self.text:
            payload["text"] = self.text
        if self.data:
            payload["data"] = _copy_mapping(self.data)
        if self.raw is not None:
            payload["raw"] = _copy_raw(self.raw)
        return payload


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    raw: Any = None

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "ToolCall":
        return cls(
            id=payload.get("id", ""),
            name=payload["name"],
            arguments=_copy_mapping(payload.get("arguments")),
            raw=_copy_raw(payload.get("raw")),
        )

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "id": self.id,
            "name": self.name,
            "arguments": _copy_mapping(self.arguments),
        }
        if self.raw is not None:
            payload["raw"] = _copy_raw(self.raw)
        return payload


@dataclass(frozen=True)
class ToolResult:
    tool_call_id: str
    name: str
    content: str
    is_error: bool = False
    raw: Any = None

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "ToolResult":
        return cls(
            tool_call_id=payload.get("tool_call_id", ""),
            name=payload["name"],
            content=payload.get("content", ""),
            is_error=bool(payload.get("is_error", False)),
            raw=_copy_raw(payload.get("raw")),
        )

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "tool_call_id": self.tool_call_id,
            "name": self.name,
            "content": self.content,
            "is_error": self.is_error,
        }
        if self.raw is not None:
            payload["raw"] = _copy_raw(self.raw)
        return payload


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    source: str = ""
    raw: Any = None

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "ToolSpec":
        return cls(
            name=payload["name"],
            description=payload.get("description", ""),
            parameters=_copy_mapping(payload.get("parameters")),
            source=payload.get("source", ""),
            raw=_copy_raw(payload.get("raw")),
        )

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "name": self.name,
            "description": self.description,
            "parameters": _copy_mapping(self.parameters),
        }
        if self.source:
            payload["source"] = self.source
        if self.raw is not None:
            payload["raw"] = _copy_raw(self.raw)
        return payload


@dataclass(frozen=True)
class Message:
    role: str
    content: List[ContentBlock] = field(default_factory=list)
    name: str = ""
    tool_call_id: str = ""
    tool_calls: List[ToolCall] = field(default_factory=list)
    raw: Any = None

    @classmethod
    def from_text(cls, role: str, text: str, **kwargs: Any) -> "Message":
        return cls(role=role, content=[ContentBlock.from_text(text)], **kwargs)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "Message":
        content = payload.get("content", [])
        if isinstance(content, str):
            blocks = [ContentBlock.from_text(content)]
        else:
            blocks = [ContentBlock.from_dict(item) for item in content]
        return cls(
            role=payload["role"],
            content=blocks,
            name=payload.get("name", ""),
            tool_call_id=payload.get("tool_call_id", ""),
            tool_calls=[ToolCall.from_dict(item) for item in payload.get("tool_calls", [])],
            raw=_copy_raw(payload.get("raw")),
        )

    def content_text(self) -> str:
        return "".join(block.text for block in self.content if block.type == "text")

    def approx_token_count(self) -> int:
        """基于字节启发式的 token 估算（约 4 bytes/token）。"""
        text = self.content_text()
        # 包含 tool_calls 的 JSON 序列化开销
        overhead = 0
        for call in self.tool_calls:
            overhead += len(call.name.encode("utf-8"))
            overhead += len(json.dumps(call.arguments).encode("utf-8"))
        return max(1, (len(text.encode("utf-8")) + overhead) // 4)

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "role": self.role,
            "content": [block.to_dict() for block in self.content],
        }
        if self.name:
            payload["name"] = self.name
        if self.tool_call_id:
            payload["tool_call_id"] = self.tool_call_id
        if self.tool_calls:
            payload["tool_calls"] = [call.to_dict() for call in self.tool_calls]
        if self.raw is not None:
            payload["raw"] = _copy_raw(self.raw)
        return payload


@dataclass(frozen=True)
class ModelUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    raw: Any = None

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
        }
        if self.raw is not None:
            payload["raw"] = _copy_raw(self.raw)
        return payload


@dataclass(frozen=True)
class ModelRequest:
    protocol: str
    model: str
    messages: List[Message]
    tools: List[ToolSpec] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    raw: Any = None


@dataclass(frozen=True)
class ModelResponse:
    message: Message
    usage: Optional[ModelUsage] = None
    stop_reason: str = ""
    raw: Any = None

    @property
    def tool_calls(self) -> List[ToolCall]:
        return list(self.message.tool_calls)

    def content_text(self) -> str:
        return self.message.content_text()

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"message": self.message.to_dict()}
        if self.usage:
            payload["usage"] = self.usage.to_dict()
        if self.stop_reason:
            payload["stop_reason"] = self.stop_reason
        if self.raw is not None:
            payload["raw"] = _copy_raw(self.raw)
        return payload


@dataclass(frozen=True)
class ModelStreamEvent:
    type: str
    delta: str = ""
    tool_call: Optional[ToolCall] = None
    response: Optional[ModelResponse] = None
    usage: Optional[ModelUsage] = None
    raw: Any = None


@dataclass(frozen=True)
class RuntimeEvent:
    type: str
    name: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    raw: Any = None

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "type": self.type,
            "name": self.name,
            "payload": _copy_mapping(self.payload),
        }
        if self.raw is not None:
            payload["raw"] = _copy_raw(self.raw)
        return payload
