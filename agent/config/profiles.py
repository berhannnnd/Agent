from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from agent.config.loader import project_config
from agent.config.paths import ENV_FILE
from agent.models.constants import normalize_protocol


@dataclass(frozen=True)
class ModelProfile:
    """A named model endpoint profile selected by UI entrypoints."""

    name: str
    protocol: str
    model: str
    base_url: str
    api_key: str = ""
    aliases: tuple[str, ...] = field(default_factory=tuple)
    source: str = "config"

    @property
    def configured(self) -> bool:
        return bool(self.protocol and self.model and self.api_key)

    @property
    def endpoint(self) -> str:
        parsed = urlparse(self.base_url)
        return parsed.netloc or self.base_url

    def matches(self, query: str) -> bool:
        needle = _normalize_query(query)
        if not needle:
            return False
        values = {self.name, self.protocol, self.model, self.endpoint, *self.aliases}
        normalized_values = {_normalize_query(value) for value in values if value}
        if needle in normalized_values:
            return True
        return any(needle in value for value in normalized_values)


def build_model_profiles(settings) -> list[ModelProfile]:
    env_profiles = _configured_profiles_from_env()
    profiles = [
        _profile(
            "openai-chat",
            "openai-chat",
            settings.models.openai.MODEL,
            settings.models.openai.BASE_URL,
            settings.models.openai.API_KEY,
            aliases=("openai", "chat"),
        ),
        _profile(
            "openai-responses",
            "openai-responses",
            settings.models.openai_responses.MODEL or settings.models.openai.MODEL,
            settings.models.openai_responses.BASE_URL or settings.models.openai.BASE_URL,
            settings.models.openai_responses.API_KEY or settings.models.openai.API_KEY,
            aliases=("responses", "response"),
        ),
        _profile(
            "claude-messages",
            "claude-messages",
            settings.agent.CLAUDE_MODEL or settings.models.anthropic.MODEL,
            settings.agent.CLAUDE_BASE_URL or settings.models.anthropic.BASE_URL,
            settings.agent.CLAUDE_API_KEY or settings.models.anthropic.API_KEY,
            aliases=("claude", "anthropic"),
        ),
        _profile(
            "gemini",
            "gemini",
            settings.models.gemini.MODEL,
            settings.models.gemini.BASE_URL,
            settings.models.gemini.API_KEY,
            aliases=("google",),
        ),
    ]
    profiles.extend(env_profiles)
    profiles.extend(_configured_profiles_from_toml())
    return [profile for profile in _dedupe_profiles(profiles) if profile.configured]


def active_profile_name(profiles: list[ModelProfile], protocol: str, model: str, base_url: str = "") -> str:
    active_protocol = normalize_protocol(protocol)
    for profile in profiles:
        if profile.protocol == active_protocol and profile.model == model:
            if not base_url or profile.base_url.rstrip("/") == base_url.rstrip("/"):
                return profile.name
    return ""


def resolve_model_profile(profiles: list[ModelProfile], query: str) -> ModelProfile | None:
    exact = _normalize_query(query)
    if not exact:
        return None
    for profile in profiles:
        values = (profile.name, profile.protocol, *profile.aliases)
        if exact in {_normalize_query(value) for value in values if value}:
            return profile
    matches = [profile for profile in profiles if profile.matches(query)]
    if len(matches) == 1:
        return matches[0]
    return None


def _profile(
    name: str,
    protocol: str,
    model: str,
    base_url: str,
    api_key: str,
    *,
    aliases: tuple[str, ...] = (),
    source: str = "config",
) -> ModelProfile:
    return ModelProfile(
        name=name,
        protocol=normalize_protocol(protocol),
        model=str(model or "").strip(),
        base_url=str(base_url or "").strip(),
        api_key=str(api_key or "").strip(),
        aliases=tuple(alias for alias in aliases if alias),
        source=source,
    )


def _configured_profiles_from_toml() -> list[ModelProfile]:
    raw_profiles = ((project_config().get("models") or {}).get("profiles") or {})
    if not isinstance(raw_profiles, dict):
        return []
    profiles: list[ModelProfile] = []
    for name, raw in raw_profiles.items():
        if not isinstance(raw, dict):
            continue
        aliases = raw.get("aliases") or []
        if isinstance(aliases, str):
            aliases = [item.strip() for item in aliases.split(",")]
        api_key = str(raw.get("api_key") or "").strip()
        api_key_env = str(raw.get("api_key_env") or "").strip()
        if api_key_env:
            api_key = _env_value(api_key_env) or api_key
        profiles.append(
            _profile(
                str(name),
                str(raw.get("protocol") or ""),
                str(raw.get("model") or ""),
                str(raw.get("base_url") or ""),
                api_key,
                aliases=tuple(str(item).strip() for item in aliases if str(item).strip()),
                source="models.profiles",
            )
        )
    return profiles


def _configured_profiles_from_env() -> list[ModelProfile]:
    env = _env_mapping()
    names = _profile_names_from_env(env)
    profiles: list[ModelProfile] = []
    for name in names:
        key = _env_profile_key(name)
        aliases = _csv(env.get("%s_ALIASES" % key, ""))
        api_key = env.get("%s_API_KEY" % key, "")
        api_key_env = env.get("%s_API_KEY_ENV" % key, "")
        if api_key_env:
            api_key = env.get(api_key_env, "") or _env_value(api_key_env) or api_key
        profiles.append(
            _profile(
                name,
                env.get("%s_PROTOCOL" % key, ""),
                env.get("%s_MODEL" % key, ""),
                env.get("%s_BASE_URL" % key, ""),
                api_key,
                aliases=tuple(aliases),
                source=".env",
            )
        )
    return profiles


def _dedupe_profiles(profiles: list[ModelProfile]) -> list[ModelProfile]:
    result: list[ModelProfile] = []
    seen: set[str] = set()
    for profile in profiles:
        if not profile.name or profile.name in seen:
            continue
        seen.add(profile.name)
        result.append(profile)
    return result


def _normalize_query(value: str) -> str:
    return str(value or "").strip().lower().replace("_", "-")


def _profile_names_from_env(env: dict[str, str]) -> list[str]:
    explicit = _csv(env.get("AGENT_MODEL_PROFILES", ""))
    discovered: list[str] = []
    prefix = "AGENT_MODEL_PROFILE_"
    for key in env:
        if not key.startswith(prefix):
            continue
        suffix = key[len(prefix) :]
        for field in ("_PROTOCOL", "_MODEL", "_BASE_URL", "_API_KEY", "_API_KEY_ENV", "_ALIASES"):
            if suffix.endswith(field):
                discovered.append(suffix[: -len(field)].lower().replace("_", "-"))
                break
    return _unique([*explicit, *discovered])


def _env_profile_key(name: str) -> str:
    normalized = str(name or "").strip().upper().replace("-", "_").replace(".", "_")
    return "AGENT_MODEL_PROFILE_%s" % normalized


def _env_mapping() -> dict[str, str]:
    values = _env_file_mapping()
    values.update({key: value for key, value in os.environ.items() if isinstance(value, str)})
    return values


def _env_file_mapping() -> dict[str, str]:
    env_path = Path(ENV_FILE)
    if not env_path.is_file():
        return {}
    values: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _env_value(name: str) -> str:
    value = os.environ.get(name)
    if value:
        return value
    return _env_file_mapping().get(name, "")


def _csv(value: str) -> list[str]:
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = str(value or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result
