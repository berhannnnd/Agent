from typing import Any, Dict, List

from agent.schema import Message, ModelRequest, ModelResponse, ModelStreamEvent


class ProtocolParseError(ValueError):
    """Raised when a model protocol response cannot be parsed."""


class ProtocolAdapter:
    protocol = ""
    path = ""
    stream_path = ""

    def request_payload(self, request: ModelRequest, stream: bool = False) -> Dict[str, Any]:
        raise NotImplementedError()

    def parse_response(self, response: Dict[str, Any]) -> ModelResponse:
        raise NotImplementedError()

    def parse_stream_event(self, event: Dict[str, Any]) -> List[ModelStreamEvent]:
        return []

    def auth_headers(self, api_key: str, base_url: str) -> Dict[str, str]:
        """生成该协议的请求鉴权头。"""
        return {"Authorization": "Bearer %s" % api_key}
