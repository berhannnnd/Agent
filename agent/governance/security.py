from __future__ import annotations

import base64
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol


SENSITIVE_KEY_PARTS = ("api_key", "authorization", "credential", "password", "secret", "token")


@dataclass(frozen=True)
class ProtectedPayload:
    ciphertext: str
    key_ref: str
    algorithm: str
    metadata: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ciphertext": self.ciphertext,
            "key_ref": self.key_ref,
            "algorithm": self.algorithm,
            "metadata": dict(self.metadata),
        }


class PayloadProtector(Protocol):
    def protect(self, payload: bytes, key_ref: str, metadata: Mapping[str, str] | None = None) -> ProtectedPayload:
        raise NotImplementedError()

    def unprotect(self, payload: ProtectedPayload) -> bytes:
        raise NotImplementedError()


class LocalBase64PayloadProtector:
    """Local test protector. Not encryption; production should provide KMS/Vault here."""

    algorithm = "local-base64-not-encryption"

    def protect(self, payload: bytes, key_ref: str, metadata: Mapping[str, str] | None = None) -> ProtectedPayload:
        return ProtectedPayload(
            ciphertext=base64.b64encode(payload).decode("ascii"),
            key_ref=key_ref,
            algorithm=self.algorithm,
            metadata=dict(metadata or {}),
        )

    def unprotect(self, payload: ProtectedPayload) -> bytes:
        if payload.algorithm != self.algorithm:
            raise ValueError("unsupported payload algorithm: %s" % payload.algorithm)
        return base64.b64decode(payload.ciphertext.encode("ascii"))


class SecretRedactor:
    def __init__(self, replacement: str = "[redacted]"):
        self.replacement = replacement

    def redact_mapping(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        return {str(key): self._redact_value(str(key), value) for key, value in payload.items()}

    def _redact_value(self, key: str, value: Any) -> Any:
        if _is_sensitive_key(key):
            return self.replacement
        if isinstance(value, Mapping):
            return self.redact_mapping(value)
        if isinstance(value, list):
            return [self._redact_value("", item) for item in value]
        return value


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(part in lowered for part in SENSITIVE_KEY_PARTS)
