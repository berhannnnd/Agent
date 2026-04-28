from pathlib import Path

from agent.config.loader import config_value, project_config
from agent.config.settings import AgentConfig


def test_project_config_defaults_feed_settings_classes():
    assert config_value("agent", "PROTOCOL", "") == "openai-chat"
    assert AgentConfig.model_fields["PROTOCOL"].default == "openai-chat"
    assert config_value("agent", "BUILTIN_TOOLS", "") == "filesystem.read,filesystem.list"
    assert AgentConfig.model_fields["BUILTIN_TOOLS"].default == "filesystem.read,filesystem.list"


def test_project_config_merges_local_over_defaults(tmp_path: Path, monkeypatch):
    defaults = tmp_path / "defaults.toml"
    local = tmp_path / "local.toml"
    defaults.write_text('[agent]\nbuiltin_tools = "filesystem.read"\nmax_tool_iterations = 3\n', encoding="utf-8")
    local.write_text('[agent]\nbuiltin_tools = "web.search"\n', encoding="utf-8")
    monkeypatch.setenv("AGENTS_DEFAULT_CONFIG", str(defaults))
    monkeypatch.setenv("AGENTS_LOCAL_CONFIG", str(local))
    project_config.cache_clear()
    try:
        assert config_value("agent", "BUILTIN_TOOLS", "") == "web.search"
        assert config_value("agent", "MAX_TOOL_ITERATIONS", 0) == 3
    finally:
        project_config.cache_clear()
