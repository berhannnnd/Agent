import importlib.util
import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_top_level_packages_define_runtime_gateway_and_cli_boundaries():
    assert importlib.util.find_spec("agent") is not None
    assert importlib.util.find_spec("gateway") is not None
    assert importlib.util.find_spec("cli") is not None


def test_agent_system_exposes_future_multi_agent_boundaries():
    assert importlib.util.find_spec("agent.orchestration") is not None
    assert importlib.util.find_spec("agent.orchestration.types") is not None
    assert importlib.util.find_spec("agent.capabilities.memory") is not None
    assert importlib.util.find_spec("agent.workflows") is not None
    assert importlib.util.find_spec("agent.workflows.types") is not None
    assert importlib.util.find_spec("agent.context") is not None
    assert importlib.util.find_spec("agent.state") is not None
    assert importlib.util.find_spec("agent.state.workspaces") is not None
    assert importlib.util.find_spec("agent.state.workspaces.metadata") is not None
    assert importlib.util.find_spec("agent.governance") is not None
    assert importlib.util.find_spec("agent.governance.credentials") is not None
    assert importlib.util.find_spec("agent.governance.audit") is not None
    assert importlib.util.find_spec("agent.governance.tracing") is not None
    assert importlib.util.find_spec("agent.models") is not None
    assert importlib.util.find_spec("agent.config") is not None
    assert importlib.util.find_spec("agent.specs") is not None
    assert importlib.util.find_spec("agent.state.agents") is not None
    assert importlib.util.find_spec("agent.capabilities") is not None
    assert importlib.util.find_spec("agent.capabilities.memory") is not None
    assert importlib.util.find_spec("agent.capabilities.sandbox") is not None
    assert importlib.util.find_spec("agent.capabilities.skills") is not None
    assert importlib.util.find_spec("agent.capabilities.tools") is not None
    assert importlib.util.find_spec("agent.assembly") is not None
    assert importlib.util.find_spec("agent.state.runs") is not None
    assert importlib.util.find_spec("agent.persistence") is not None
    assert importlib.util.find_spec("agent.state.identity") is not None
    assert importlib.util.find_spec("agent.tasks") is not None
    assert importlib.util.find_spec("agent.definitions") is None
    assert importlib.util.find_spec("agent.integrations") is None
    assert importlib.util.find_spec("agent.audit") is None
    assert importlib.util.find_spec("agent.identity") is None
    assert importlib.util.find_spec("agent.memory") is None
    assert importlib.util.find_spec("agent.runs") is None
    assert importlib.util.find_spec("agent.security") is None
    assert importlib.util.find_spec("agent.skills") is None
    assert importlib.util.find_spec("agent.storage") is None
    assert importlib.util.find_spec("agent.tools") is None
    assert importlib.util.find_spec("agent.tracing") is None


def test_agent_runtime_is_split_into_explicit_kernel_modules():
    assert importlib.util.find_spec("agent.runtime.loop") is not None
    assert importlib.util.find_spec("agent.context.compiler") is not None
    assert importlib.util.find_spec("agent.runtime.session") is not None
    assert importlib.util.find_spec("agent.context.window") is not None
    assert importlib.util.find_spec("agent.runtime.turns") is not None
    assert importlib.util.find_spec("agent.runtime.turns.model") is not None
    assert importlib.util.find_spec("agent.runtime.turns.tools") is not None
    assert importlib.util.find_spec("agent.governance.permissions") is not None
    assert importlib.util.find_spec("agent.runtime.checkpoints") is not None
    assert importlib.util.find_spec("agent.runtime.state") is not None
    assert importlib.util.find_spec("agent.context.compaction") is not None
    assert importlib.util.find_spec("agent.context.memory") is not None
    assert importlib.util.find_spec("agent.governance.sandbox") is not None
    assert importlib.util.find_spec("agent.governance.security") is not None


def test_agent_capabilities_expose_builtin_tool_boundaries():
    assert importlib.util.find_spec("agent.capabilities.tools.builtin") is not None
    assert importlib.util.find_spec("agent.capabilities.tools.context") is not None
    assert importlib.util.find_spec("agent.capabilities.sandbox.local") is not None
    assert importlib.util.find_spec("agent.capabilities.sandbox.docker") is not None


def test_agent_models_split_protocol_adapters_and_transports():
    assert importlib.util.find_spec("agent.models.adapters") is not None
    assert importlib.util.find_spec("agent.models.protocol") is not None
    assert importlib.util.find_spec("agent.models.transports") is not None


def test_gateway_exposes_protocol_boundary_packages():
    assert importlib.util.find_spec("gateway.auth") is not None
    assert importlib.util.find_spec("gateway.sessions") is not None
    assert importlib.util.find_spec("gateway.services.persistence") is not None
    assert importlib.util.find_spec("gateway.streaming") is not None


def test_legacy_app_package_is_not_importable():
    assert importlib.util.find_spec("app") is None


def test_cli_does_not_import_gateway():
    imports = _imports_under(ROOT / "cli")

    assert not [name for name in imports if name == "gateway" or name.startswith("gateway.")]


def test_agent_does_not_import_entrypoint_or_ui_packages():
    imports = _imports_under(ROOT / "agent")
    forbidden = ("gateway", "cli", "web", "fastapi", "typer", "rich", "prompt_toolkit")

    assert not [name for name in imports if name in forbidden or name.startswith(tuple("%s." % item for item in forbidden))]


def test_gateway_template_engine_and_provider_layers_are_not_importable():
    assert importlib.util.find_spec("gateway.engines") is None
    assert importlib.util.find_spec("gateway.shared.provider") is None


def _imports_under(root: Path) -> set[str]:
    imports: set[str] = set()
    for path in root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module)
    return imports
