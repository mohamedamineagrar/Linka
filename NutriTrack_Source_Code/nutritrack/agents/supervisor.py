"""
NutriTrack — Supervisor Agent (Orchestrator)
==============================================
Hierarchical coordinator that manages agent execution flow.
Implements the LangGraph state machine with conditional routing.
"""

from __future__ import annotations
from nutritrack.models.schemas import NutriTrackState, RiskLevel
from nutritrack.utils.llm_grok import get_grok_client


def supervisor_agent(state: NutriTrackState) -> NutriTrackState:
    """
    Supervisor: Entry point that initializes the workflow
    and sets up routing metadata.
    """
    state.current_agent = "supervisor"

    llm = get_grok_client()
    state.autonomy_context["llm_enabled"] = llm.enabled

    if llm.enabled:
        plan = _build_autonomous_plan(state)
        if plan:
            state.autonomy_context["plan"] = plan
            state.llm_trace.append({"agent": "supervisor", "plan": plan})
            if plan.get("require_human_review"):
                state.requires_human_approval = True
                state.human_approval_reason = (
                    "Autonomous supervisor flagged this shipment for manual confirmation: "
                    f"{plan.get('notes', 'High-stakes execution path.')}"
                )

    return state


def _build_autonomous_plan(state: NutriTrackState) -> dict | None:
    llm = get_grok_client()
    system_prompt = (
        "You are the autonomous supervisor for a cold-chain multi-agent system. "
        "Return only JSON with keys: intent, priority, focus, notes, require_human_review. "
        "priority must be one of: low, medium, high, critical. "
        "focus must be one of: safety, economics, speed, balanced."
    )
    user_prompt = (
        f"Product: {state.product.name} ({state.product.product_type.value})\n"
        f"Telemetry: temp={state.telemetry.temperature_celsius}, "
        f"humidity={state.telemetry.humidity_percent}, co2={state.telemetry.co2_ppm}, "
        f"vibration={state.telemetry.vibration_g}\n"
        f"User query: {state.user_query or 'none'}\n"
        "Generate an execution plan for downstream agents."
    )

    result = llm.complete_json(system_prompt, user_prompt, max_tokens=350)
    if not result:
        return None

    priority = str(result.get("priority", "medium")).lower()
    if priority not in {"low", "medium", "high", "critical"}:
        priority = "medium"

    focus = str(result.get("focus", "balanced")).lower()
    if focus not in {"safety", "economics", "speed", "balanced"}:
        focus = "balanced"

    return {
        "intent": str(result.get("intent", "autonomous monitoring"))[:160],
        "priority": priority,
        "focus": focus,
        "notes": str(result.get("notes", ""))[:500],
        "require_human_review": bool(result.get("require_human_review", False)),
    }


def should_escalate(state: NutriTrackState) -> str:
    """
    Conditional routing after anomaly detection.
    Determines which path the workflow takes.

    Returns:
        - "critical_path" if anomalies are severe
        - "standard_path" if manageable
        - "no_action" if everything is fine
    """
    if state.anomaly_output is None:
        return "standard_path"

    risk = state.anomaly_output.risk_level

    if risk in [RiskLevel.CRITICAL, RiskLevel.HIGH]:
        return "critical_path"
    elif risk == RiskLevel.MEDIUM:
        return "standard_path"
    else:
        return "no_action"


def needs_human_approval(state: NutriTrackState) -> str:
    """
    Conditional routing after guardrail check.
    Determines if human-in-the-loop is needed.
    """
    if state.requires_human_approval:
        return "human_review"
    return "auto_execute"


def human_review_node(state: NutriTrackState) -> NutriTrackState:
    """
    Human-in-the-Loop checkpoint.
    In production, this would pause and await external input.
    For simulation, we auto-approve with conditions.
    """
    state.current_agent = "human_review"

    # Simulation: auto-approve unless safety is critically low
    if state.health_score.safety_index < 15:
        state.human_approved = True
        state.human_feedback = (
            "HUMAN REVIEWER: Approved quarantine. Safety index critically low. "
            "Product must not enter food supply."
        )
    elif state.economic_metrics.action_cost > state.product.value_usd * 0.5:
        state.human_approved = False
        state.human_feedback = (
            "HUMAN REVIEWER: Rejected — action cost exceeds 50% of cargo value. "
            "Reassess alternatives."
        )
    else:
        state.human_approved = True
        state.human_feedback = (
            "HUMAN REVIEWER: Approved. Proceed with recommended action. "
            "Monitor outcomes and report."
        )

    # Update decision status
    if state.final_decision:
        from nutritrack.models.schemas import DecisionStatus
        if state.human_approved:
            state.final_decision.status = DecisionStatus.APPROVED
        else:
            state.final_decision.status = DecisionStatus.REJECTED

    return state


def finalize_node(state: NutriTrackState) -> NutriTrackState:
    """
    Final node: Mark workflow as complete.
    Generate QR traceability data.
    """
    state.current_agent = "finalize"
    state.workflow_complete = True

    # Update QR code with final state
    state.traceability.product_id = state.product.product_id
    if not state.traceability.qr_code:
        state.traceability.qr_code = f"QR-NT-{state.product.product_id}"

    return state
