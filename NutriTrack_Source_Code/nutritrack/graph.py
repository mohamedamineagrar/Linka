"""
NutriTrack — LangGraph Workflow Orchestration
===============================================
Defines the complete agent graph with conditional routing,
cyclic paths, and human-in-the-loop interrupts.

Architecture:
                    ┌─────────────┐
                    │  Supervisor  │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │ Biotic Agent │
                    └──────┬──────┘
                           │
                    ┌──────▼──────────┐
                    │ Anomaly Detector │
                    └──────┬──────────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
        critical_path  standard    no_action
              │            │            │
    ┌─────────▼──┐  ┌──────▼──┐        │
    │ Logistics  │  │Economics│        │
    │ + Econ     │  │  Only   │        │
    └─────┬──────┘  └────┬────┘        │
          │              │             │
          └──────┬───────┘             │
                 │                     │
          ┌──────▼──────┐              │
          │  Guardrail  │              │
          └──────┬──────┘              │
                 │                     │
          ┌──────▼──────────┐          │
          │ Recommendation  │◄─────────┘
          └──────┬──────────┘
                 │
          ┌──────▼────────┐
          │ Human Review?  │
          └──┬─────────┬──┘
             │         │
          approve    reject
             │         │
          ┌──▼─────────▼──┐
          │   Finalize     │
          └────────────────┘
"""

from __future__ import annotations
from typing import Any, Callable
from nutritrack.models.schemas import NutriTrackState

# Import all agents
from nutritrack.agents.supervisor import (
    supervisor_agent, should_escalate, needs_human_approval,
    human_review_node, finalize_node
)
from nutritrack.agents.biotic_agent import biotic_agent
from nutritrack.agents.anomaly_agent import anomaly_detection_agent
from nutritrack.agents.logistics_agent import logistics_agent
from nutritrack.agents.economic_agent import economic_agent
from nutritrack.agents.guardrail_agent import guardrail_agent
from nutritrack.agents.recommendation_agent import recommendation_agent


class StateGraph:
    """
    LangGraph-compatible state graph implementation.

    This implements the core LangGraph API:
    - add_node(name, function)
    - add_edge(from, to)
    - add_conditional_edges(from, condition_fn, mapping)
    - set_entry_point(name)
    - compile() → CompiledGraph
    """

    def __init__(self):
        self.nodes: dict[str, Callable] = {}
        self.edges: dict[str, list[str]] = {}
        self.conditional_edges: dict[str, tuple[Callable, dict]] = {}
        self.entry_point: str = ""
        self.end_nodes: set[str] = set()

    def add_node(self, name: str, func: Callable) -> "StateGraph":
        self.nodes[name] = func
        return self

    def add_edge(self, from_node: str, to_node: str) -> "StateGraph":
        if from_node not in self.edges:
            self.edges[from_node] = []
        self.edges[from_node].append(to_node)
        return self

    def add_conditional_edges(
        self, from_node: str, condition: Callable, mapping: dict[str, str]
    ) -> "StateGraph":
        self.conditional_edges[from_node] = (condition, mapping)
        return self

    def set_entry_point(self, name: str) -> "StateGraph":
        self.entry_point = name
        return self

    def set_finish_point(self, name: str) -> "StateGraph":
        self.end_nodes.add(name)
        return self

    def compile(self) -> "CompiledGraph":
        return CompiledGraph(self)


class CompiledGraph:
    """Compiled executable graph."""

    def __init__(self, graph: StateGraph):
        self.graph = graph
        self.execution_log: list[dict] = []

    def invoke(self, state: NutriTrackState) -> NutriTrackState:
        """Execute the graph from entry point to completion."""
        current = self.graph.entry_point
        self.execution_log = []
        visited = set()
        max_iterations = 20  # Safety limit

        iteration = 0
        while current and iteration < max_iterations:
            iteration += 1

            if current in self.graph.end_nodes and current in visited:
                break

            visited.add(current)

            # Execute node
            if current in self.graph.nodes:
                func = self.graph.nodes[current]
                self.execution_log.append({
                    "step": iteration,
                    "node": current,
                    "status": "executing",
                })
                try:
                    state = func(state)
                    self.execution_log[-1]["status"] = "completed"
                except Exception as e:
                    self.execution_log[-1]["status"] = f"error: {str(e)}"
                    state.errors.append(f"Agent {current} failed: {str(e)}")

            # Determine next node
            if current in self.graph.conditional_edges:
                condition, mapping = self.graph.conditional_edges[current]
                result = condition(state)
                next_node = mapping.get(result)
                self.execution_log[-1]["routing"] = f"{result} → {next_node}"
                current = next_node
            elif current in self.graph.edges:
                current = self.graph.edges[current][0]  # Take first edge
            elif current in self.graph.end_nodes:
                break
            else:
                break

        return state

    def get_execution_log(self) -> list[dict]:
        return self.execution_log


def build_nutritrack_graph() -> CompiledGraph:
    """
    Build the complete NutriTrack agent workflow graph.
    """
    graph = StateGraph()

    # ── Add all nodes ──
    graph.add_node("supervisor", supervisor_agent)
    graph.add_node("biotic", biotic_agent)
    graph.add_node("anomaly_detector", anomaly_detection_agent)
    graph.add_node("logistics", logistics_agent)
    graph.add_node("economic", economic_agent)
    graph.add_node("guardrail", guardrail_agent)
    graph.add_node("recommendation", recommendation_agent)
    graph.add_node("human_review", human_review_node)
    graph.add_node("finalize", finalize_node)

    # ── Set entry point ──
    graph.set_entry_point("supervisor")

    # ── Linear edges ──
    graph.add_edge("supervisor", "biotic")
    graph.add_edge("biotic", "anomaly_detector")

    # ── Conditional: After anomaly detection ──
    graph.add_conditional_edges("anomaly_detector", should_escalate, {
        "critical_path": "logistics",    # Full pipeline for critical
        "standard_path": "economic",     # Skip logistics for moderate
        "no_action": "recommendation",   # Skip to recommendation
    })

    # ── Critical path: logistics → economic ──
    graph.add_edge("logistics", "economic")

    # ── Both paths converge at guardrail ──
    graph.add_edge("economic", "guardrail")

    # ── Guardrail → Recommendation ──
    graph.add_edge("guardrail", "recommendation")

    # ── After recommendation: check if human approval needed ──
    graph.add_conditional_edges("recommendation", needs_human_approval, {
        "human_review": "human_review",
        "auto_execute": "finalize",
    })

    # ── Human review → Finalize ──
    graph.add_edge("human_review", "finalize")

    # ── End point ──
    graph.set_finish_point("finalize")

    return graph.compile()


def run_simulation(
    product_key: str = "dairy_yogurt",
    scenario: str = "temperature_spike",
    hours_elapsed: float = 4.0,
    user_query: str | None = None,
) -> tuple[NutriTrackState, list[dict]]:
    """
    Run a complete simulation through the agent graph.

    Returns:
        (final_state, execution_log)
    """
    from nutritrack.utils.simulation import generate_scenario

    # Generate initial state
    state = generate_scenario(product_key, scenario, hours_elapsed)

    if user_query:
        state.user_query = user_query

    # Build and execute graph
    graph = build_nutritrack_graph()
    final_state = graph.invoke(state)

    return final_state, graph.get_execution_log()
