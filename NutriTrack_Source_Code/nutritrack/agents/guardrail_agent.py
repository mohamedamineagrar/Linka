"""
NutriTrack — Guardrail Agent
==============================
Safety, compliance, and output validation.
Prevents unsafe/illegal actions. Enforces regulatory requirements.
"""

from __future__ import annotations
from nutritrack.models.schemas import (
    NutriTrackState, GuardrailAgentOutput, ActionType, RiskLevel
)
from nutritrack.rag.pipeline import get_rag_pipeline


# ──────────────── Safety Rules ────────────────

FORBIDDEN_ACTIONS = {
    # Products below safety threshold cannot be sold
    ("safety_index_below_20", ActionType.REDIRECT_LOCAL_MARKET):
        "Cannot sell product with safety index below 20% — regulatory violation.",
    ("safety_index_below_20", ActionType.TRIGGER_URGENT_DELIVERY):
        "Cannot deliver unsafe product — liability risk.",
}

MANDATORY_RULES = [
    {
        "id": "GR-001",
        "rule": "Products with safety index < 20% MUST be quarantined.",
        "check": lambda s: s.health_score.safety_index >= 20 or
                          (s.final_decision and s.final_decision.action == ActionType.QUARANTINE),
    },
    {
        "id": "GR-002",
        "rule": "Temperature excursions > 15°C above optimal require human approval.",
        "check": lambda s: (s.telemetry.temperature_celsius <= s.product.optimal_temp_max + 15) or
                          s.requires_human_approval,
    },
    {
        "id": "GR-003",
        "rule": "Pharmaceutical products require zero-tolerance on temperature deviation > 2°C.",
        "check": lambda s: s.product.product_type.value != "pharmaceuticals" or
                          abs(s.telemetry.temperature_celsius -
                              (s.product.optimal_temp_min + s.product.optimal_temp_max) / 2) <= 2,
    },
    {
        "id": "GR-004",
        "rule": "All decisions must have confidence >= 0.3 to be executed.",
        "check": lambda s: not s.decisions or all(d.confidence >= 0.3 for d in s.decisions),
    },
    {
        "id": "GR-005",
        "rule": "Rerouting costs exceeding 30% of cargo value require human approval.",
        "check": lambda s: not s.economic_metrics or
                          s.economic_metrics.action_cost <= s.product.value_usd * 0.30 or
                          s.requires_human_approval,
    },
    {
        "id": "GR-006",
        "rule": "Product discard/quarantine requires human approval.",
        "check": lambda s: not s.decisions or
                          not any(d.action == ActionType.QUARANTINE for d in s.decisions) or
                          s.requires_human_approval,
    },
]


def guardrail_agent(state: NutriTrackState) -> NutriTrackState:
    """
    Guardrail Agent: Validates all proposed actions against safety rules.

    Three-layer validation:
    1. Regulatory compliance (RAG-based)
    2. Safety rule enforcement (deterministic)
    3. Output schema validation (Pydantic)
    """
    state.current_agent = "guardrail_agent"

    violations = []
    is_compliant = True
    modified_action = None
    safety_score = 1.0

    # ── Layer 1: Regulatory Compliance (RAG) ──
    rag = get_rag_pipeline()
    reg_data = rag.query_regulatory("Morocco", state.product.product_type.value)

    if reg_data["is_sufficient"]:
        # Check traceability requirement
        if not state.traceability.transport_history:
            violations.append(
                "REG-VIOLATION: Moroccan law (Loi 28-07) requires continuous digital transport logs. "
                "No transport history recorded."
            )
            safety_score -= 0.1

    # ── Layer 2: Safety Rules ──
    for rule in MANDATORY_RULES:
        try:
            if not rule["check"](state):
                violations.append(f"RULE {rule['id']}: {rule['rule']}")
                safety_score -= 0.15
                is_compliant = False
        except Exception as e:
            violations.append(f"RULE {rule['id']}: Check failed — {str(e)}")
            safety_score -= 0.05

    # ── Layer 3: Action-Specific Validation ──
    proposed = None
    if state.logistics_output:
        proposed = state.logistics_output.recommended_action
    if state.economic_output and state.economic_output.recommended_action != ActionType.NO_ACTION:
        proposed = state.economic_output.recommended_action

    if proposed:
        # Check forbidden combinations
        if state.health_score.safety_index < 20:
            key = ("safety_index_below_20", proposed)
            if key in FORBIDDEN_ACTIONS:
                violations.append(f"BLOCKED: {FORBIDDEN_ACTIONS[key]}")
                modified_action = ActionType.QUARANTINE
                is_compliant = False
                safety_score -= 0.3

        # Force human approval for high-stakes decisions
        if proposed in [ActionType.QUARANTINE, ActionType.REDIRECT_LOCAL_MARKET]:
            state.requires_human_approval = True
            state.human_approval_reason = (
                f"Action '{proposed.value}' requires human validation. "
                f"Product value: ${state.product.value_usd:,.0f}. "
                f"Health score: {state.health_score.overall}/100."
            )

        if (state.economic_metrics and
            state.economic_metrics.action_cost > state.product.value_usd * 0.30):
            state.requires_human_approval = True
            state.human_approval_reason = (
                f"Action cost (${state.economic_metrics.action_cost:,.0f}) exceeds 30% of "
                f"cargo value (${state.product.value_usd:,.0f}). Human approval required."
            )

    # ── Prompt Injection Detection ──
    if state.user_query:
        injection_patterns = [
            "ignore previous", "forget instructions", "system prompt",
            "override", "disregard", "jailbreak", "pretend you are",
        ]
        query_lower = state.user_query.lower()
        if any(p in query_lower for p in injection_patterns):
            violations.append(
                "SECURITY: Potential prompt injection detected in user query. "
                "Query sanitized and flagged."
            )
            state.user_query = "[SANITIZED — potential injection attempt]"
            safety_score -= 0.2

    # ── Compliance Notes ──
    compliance_notes = _build_compliance_notes(violations, reg_data, state)

    output = GuardrailAgentOutput(
        is_compliant=is_compliant and len(violations) == 0,
        violations=violations,
        modified_action=modified_action,
        compliance_notes=compliance_notes,
        safety_score=round(max(0, safety_score), 2),
    )

    state.guardrail_output = output
    return state


def _build_compliance_notes(violations, reg_data, state) -> str:
    """Build comprehensive compliance report."""
    notes = []

    if not violations:
        notes.append("✅ All safety checks passed. Action compliant with regulations.")
    else:
        notes.append(f"⚠️ {len(violations)} violation(s) detected:")
        for v in violations:
            notes.append(f"  • {v}")

    if state.requires_human_approval:
        notes.append(f"\n🔒 HUMAN APPROVAL REQUIRED: {state.human_approval_reason}")

    if reg_data["is_sufficient"]:
        notes.append(f"\n📋 Regulatory sources consulted: {', '.join(reg_data['sources'][:2])}")

    return "\n".join(notes)
