from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable
from urllib.parse import urlparse


@dataclass
class WebSearchPolicy:
    max_results: int = 5
    max_credits_per_run: float = 10.0
    allow_domains: tuple[str, ...] = field(default_factory=tuple)
    deny_domains: tuple[str, ...] = field(default_factory=tuple)
    allow_advanced: bool = False
    allow_raw_content: bool = False
    _credits_by_run: dict[str, float] = field(default_factory=dict)

    def normalize_max_results(self, value: int | None = None) -> int:
        requested = int(value or self.max_results or 5)
        return max(1, min(requested, max(1, int(self.max_results or 5))))

    def validate_depth(self, depth: str, *, parameter: str) -> str:
        value = str(depth or "basic").strip().lower()
        allowed = {"basic", "advanced"} if parameter == "extract_depth" else {"basic", "advanced", "fast", "ultra_fast", "ultra-fast"}
        if value not in allowed:
            raise ValueError("unsupported %s: %s" % (parameter, depth))
        if value == "ultra-fast":
            value = "ultra_fast"
        if value in {"advanced", "ultra_fast"} and not self.allow_advanced:
            raise PermissionError("%s requires advanced web search permission" % value)
        return value

    def validate_raw_content(self, include_raw_content: bool) -> bool:
        if include_raw_content and not self.allow_raw_content:
            raise PermissionError("raw web content requires explicit permission")
        return bool(include_raw_content)

    def include_domains_for_request(self, include_domains: Iterable[str] = ()) -> tuple[str, ...]:
        requested = _clean_domains(include_domains)
        if requested:
            self._validate_domains(requested)
            return requested
        return self.allow_domains

    def exclude_domains_for_request(self, exclude_domains: Iterable[str] = ()) -> tuple[str, ...]:
        return _unique((*_clean_domains(exclude_domains), *self.deny_domains))

    def validate_urls(self, urls: Iterable[str]) -> tuple[str, ...]:
        clean_urls = tuple(str(url or "").strip() for url in urls if str(url or "").strip())
        if not clean_urls:
            raise ValueError("at least one URL is required")
        for url in clean_urls:
            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError("web tools only support http:// and https:// URLs")
            self._validate_domains((parsed.netloc.lower(),))
        return clean_urls

    def reserve_credits(self, run_id: str, credits: float) -> None:
        scope = str(run_id or "session")
        current = self._credits_by_run.get(scope, 0.0)
        next_value = current + max(0.0, float(credits or 0.0))
        if self.max_credits_per_run > 0 and next_value > self.max_credits_per_run:
            raise PermissionError("web search credit budget exceeded for run")
        self._credits_by_run[scope] = next_value

    def _validate_domains(self, domains: Iterable[str]) -> None:
        for domain in _clean_domains(domains):
            if any(_domain_matches(domain, denied) for denied in self.deny_domains):
                raise PermissionError("domain is denied: %s" % domain)
            if self.allow_domains and not any(_domain_matches(domain, allowed) for allowed in self.allow_domains):
                raise PermissionError("domain is not allowed: %s" % domain)


def _clean_domains(domains: Iterable[str]) -> tuple[str, ...]:
    values: list[str] = []
    for domain in domains or ():
        text = str(domain or "").strip().lower()
        if not text:
            continue
        if text.startswith(("http://", "https://")):
            text = urlparse(text).netloc.lower()
        values.append(text)
    return _unique(values)


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    result: list[str] = []
    seen = set()
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return tuple(result)


def _domain_matches(domain: str, pattern: str) -> bool:
    return domain == pattern or domain.endswith(".%s" % pattern)
