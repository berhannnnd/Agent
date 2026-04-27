import importlib.util


def test_top_level_packages_define_runtime_gateway_and_cli_boundaries():
    assert importlib.util.find_spec("agent") is not None
    assert importlib.util.find_spec("gateway") is not None
    assert importlib.util.find_spec("cli") is not None


def test_agent_system_exposes_future_multi_agent_boundaries():
    assert importlib.util.find_spec("agent.orchestration") is not None
    assert importlib.util.find_spec("agent.memory") is not None
    assert importlib.util.find_spec("agent.workflows") is not None


def test_agent_runtime_is_split_into_explicit_kernel_modules():
    assert importlib.util.find_spec("agent.runtime.loop") is not None
    assert importlib.util.find_spec("agent.runtime.prompt") is not None
    assert importlib.util.find_spec("agent.runtime.session") is not None
    assert importlib.util.find_spec("agent.runtime.compaction") is not None
    assert importlib.util.find_spec("agent.runtime.tool_orchestrator") is not None
    assert importlib.util.find_spec("agent.runtime.permissions") is not None
    assert importlib.util.find_spec("agent.runtime.checkpoints") is not None
    assert importlib.util.find_spec("agent.runtime.state") is not None


def test_gateway_exposes_protocol_boundary_packages():
    assert importlib.util.find_spec("gateway.auth") is not None
    assert importlib.util.find_spec("gateway.sessions") is not None
    assert importlib.util.find_spec("gateway.streaming") is not None


def test_legacy_app_package_is_not_importable():
    assert importlib.util.find_spec("app") is None
