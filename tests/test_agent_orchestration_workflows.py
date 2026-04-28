import pytest

from agent.orchestration import AgentRole, AgentRoleKind, StaticAgentRouter
from agent.specs import AgentSpec
from agent.workflows import WorkflowEdge, WorkflowNode, WorkflowNodeKind, WorkflowPlan


def test_static_agent_router_selects_default_role():
    roles = [
        AgentRole("planner", AgentRoleKind.PLANNER, AgentSpec.from_overrides(agent_id="planner")),
        AgentRole("worker", AgentRoleKind.WORKER, AgentSpec.from_overrides(agent_id="worker")),
    ]

    decision = StaticAgentRouter(default_role_id="worker").route("implement this", roles)

    assert decision.target_role_id == "worker"
    assert decision.reason == "static default"


def test_workflow_plan_validates_and_orders_nodes():
    plan = WorkflowPlan(
        workflow_id="wf-1",
        nodes=[
            WorkflowNode("plan", WorkflowNodeKind.AGENT, "Plan"),
            WorkflowNode("execute", WorkflowNodeKind.TASK, "Execute"),
            WorkflowNode("review", WorkflowNodeKind.AGENT, "Review"),
        ],
        edges=[
            WorkflowEdge("plan", "execute"),
            WorkflowEdge("execute", "review"),
        ],
    )

    plan.validate()

    assert [node.node_id for node in plan.topological_nodes()] == ["plan", "execute", "review"]


def test_workflow_plan_rejects_cycles():
    plan = WorkflowPlan(
        workflow_id="wf-1",
        nodes=[
            WorkflowNode("a", WorkflowNodeKind.TASK, "A"),
            WorkflowNode("b", WorkflowNodeKind.TASK, "B"),
        ],
        edges=[
            WorkflowEdge("a", "b"),
            WorkflowEdge("b", "a"),
        ],
    )

    with pytest.raises(ValueError, match="cycle"):
        plan.validate()
