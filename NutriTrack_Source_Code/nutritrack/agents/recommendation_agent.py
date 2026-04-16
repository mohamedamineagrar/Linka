"""
NutriTrack — Smart Recommendation Agent
=========================================
ChatGPT-like assistant that synthesizes all agent outputs
into actionable, human-readable recommendations.
"""

from __future__ import annotations
from nutritrack.models.schemas import (
    NutriTrackState, RecommendationOutput, ActionType, RiskLevel, Decision,
    DecisionStatus
)
from nutritrack.utils.llm_grok import get_grok_client


def recommendation_agent(state: NutriTrackState) -> NutriTrackState:
    """
    Smart Recommendation Agent: Synthesizes all agent outputs.

    Acts as the "brain" that creates the final recommendation
    considering all perspectives: biotic, anomaly, logistics,
    economic, and guardrail constraints.
    """
    state.current_agent = "recommendation_agent"

    anomaly = state.anomaly_output
    economic = state.economic_output
    guardrail = state.guardrail_output

    candidate_action = _candidate_action_from_agents(state)
    llm = get_grok_client()

    primary_action = ActionType.NO_ACTION
    confidence = 0.0
    summary = ""
    explanation = ""
    alternatives: list[dict] = []

    # Strict mode: recommendations are generated only by Groq LLM.
    llm_result = _llm_recommendation(state, candidate_action) if llm.enabled else None

    if llm_result:
        action_name = str(llm_result.get("primary_action", "")).lower()
        if action_name in {a.value for a in ActionType}:
            primary_action = ActionType(action_name)
        else:
            primary_action = ActionType.NO_ACTION

        try:
            confidence = float(llm_result.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0

        confidence = max(0.0, min(1.0, confidence))
        summary = str(llm_result.get("summary", ""))[:500]
        explanation = str(llm_result.get("explanation", ""))[:2000]

        llm_alts = llm_result.get("alternative_actions", [])
        if isinstance(llm_alts, list):
            parsed_alts = []
            for item in llm_alts[:3]:
                if isinstance(item, dict):
                    action = str(item.get("action", "")).lower()
                    parsed_alts.append({
                        "action": action if action in {a.value for a in ActionType} else "",
                        "description": str(item.get("description", ""))[:240],
                        "trade_off": str(item.get("trade_off", ""))[:180],
                    })
            alternatives = parsed_alts

        state.llm_trace.append({
            "agent": "recommendation_agent",
            "action": primary_action.value,
            "confidence": round(confidence, 2),
            "mode": "grok_strict",
            "provider": "groq",
            "model": llm.model,
            "llm_available": True,
            "llm_request_succeeded": True,
        })
    else:
        state.errors.append(
            "Recommendation generation failed: Groq LLM unavailable or returned invalid output."
        )
        summary = "LLM recommendation unavailable"
        explanation = (
            "Groq LLM did not return a valid recommendation. "
            "No heuristic fallback is applied in strict LLM mode."
        )
        alternatives = []
        confidence = 0.0
        primary_action = ActionType.NO_ACTION

        state.llm_trace.append({
            "agent": "recommendation_agent",
            "action": primary_action.value,
            "confidence": 0.0,
            "mode": "grok_strict",
            "provider": "groq",
            "model": llm.model,
            "llm_available": False,
            "llm_request_succeeded": False,
            "fallback_heuristic_used": False,
        })

    output = RecommendationOutput(
        summary=summary,
        primary_action=primary_action,
        explanation=explanation,
        alternative_actions=alternatives,
        confidence=round(confidence, 2),
    )

    # ── Create Decision record ──
    decision = Decision(
        action=primary_action,
        reason=explanation[:500] if explanation else "No valid LLM recommendation generated",
        confidence=confidence,
        risk_level=anomaly.risk_level if anomaly else RiskLevel.LOW,
        status=DecisionStatus.PENDING_HUMAN if state.requires_human_approval else DecisionStatus.PROPOSED,
        requires_human_approval=state.requires_human_approval,
        estimated_cost_usd=economic.metrics.action_cost if economic else 0,
        estimated_savings_usd=economic.metrics.savings if economic else 0,
        agent_source="recommendation_agent",
        details={
            "health_score": state.health_score.overall,
            "anomaly_count": len(anomaly.anomalies) if anomaly else 0,
            "geographic_risk": state.geographic_risk_score,
            "guardrail_compliant": guardrail.is_compliant if guardrail else True,
            "recommendation_mode": "grok_strict",
            "llm_provider": "groq",
            "llm_model": llm.model,
            "llm_available": bool(llm_result),
            "llm_enabled": llm.enabled if llm else False,
            "candidate_action_from_agents": candidate_action.value,
        }
    )

    state.decisions.append(decision)
    state.final_decision = decision
    state.recommendation_output = output

    # ── Update traceability ──
    from nutritrack.models.schemas import TraceEvent
    state.traceability.decision_log.append(decision)
    state.traceability.transport_history.append(TraceEvent(
        event_type="decision_made",
        location=state.gps,
        details=f"Action: {primary_action.value} | Confidence: {confidence:.0%}",
        agent="recommendation_agent",
    ))

    return state


def _candidate_action_from_agents(state: NutriTrackState) -> ActionType:
    """Build a candidate action from upstream agents as context for Groq."""
    guardrail = state.guardrail_output
    economic = state.economic_output
    logistics = state.logistics_output

    if guardrail and guardrail.modified_action:
        return guardrail.modified_action
    if economic and economic.recommended_action != ActionType.NO_ACTION:
        return economic.recommended_action
    if logistics and logistics.recommended_action != ActionType.NO_ACTION:
        return logistics.recommended_action
    return ActionType.NO_ACTION


def _llm_recommendation(state: NutriTrackState, fallback_action: ActionType) -> dict | None:
    llm = get_grok_client()

    allowed_actions = [a.value for a in ActionType]
    system_prompt = (
        "You are the NutriTrack recommendation model (Groq). "
        "Use ONLY the provided data from sensors and upstream agent outputs. "
        "Return JSON with keys: summary, primary_action, explanation, confidence, alternative_actions. "
        "primary_action must be one of the allowed actions. confidence is float 0..1. "
        "alternative_actions is an array of {action, description, trade_off}. "
        "Never invent external facts or thresholds not justified by the provided data. "
        "Prioritize safety and compliance over economic gain."
    )

    anomalies = state.anomaly_output.anomalies if state.anomaly_output else []
    anomaly_text = "none" if not anomalies else ", ".join(
        f"{a.anomaly_type.value}:{a.severity.value}" for a in anomalies
    )

    user_prompt = (
        f"Allowed actions: {allowed_actions}\n"
        f"Candidate action from upstream agents: {fallback_action.value}\n"
        f"Product: {state.product.name} ({state.product.product_type.value}) value={state.product.value_usd}\n"
        f"Product constraints: temp=[{state.product.optimal_temp_min},{state.product.optimal_temp_max}], "
        f"humidity=[{state.product.optimal_humidity_min},{state.product.optimal_humidity_max}], "
        f"max_co2={state.product.max_co2_ppm}\n"
        f"Telemetry: temp={state.telemetry.temperature_celsius}, humidity={state.telemetry.humidity_percent}, "
        f"co2={state.telemetry.co2_ppm}, vibration={state.telemetry.vibration_g}\n"
        f"Health: overall={state.health_score.overall}, safety={state.health_score.safety_index}, "
        f"remaining_hours={state.health_score.estimated_remaining_hours}\n"
        f"Anomalies: {anomaly_text}\n"
        f"Risk level: {state.anomaly_output.risk_level.value if state.anomaly_output else 'low'}\n"
        f"Anomaly root cause: {state.anomaly_output.root_cause_analysis if state.anomaly_output else 'none'}\n"
        f"Predicted impact: {state.anomaly_output.predicted_impact if state.anomaly_output else 'none'}\n"
        f"Biotic assessment: {state.biotic_output.nutritional_assessment if state.biotic_output else 'none'}\n"
        f"Biotic recommendations: {state.biotic_output.recommendations if state.biotic_output else []}\n"
        f"Logistics recommendation: {state.logistics_output.recommended_action.value if state.logistics_output else 'none'}\n"
        f"Logistics reason: {state.logistics_output.reason if state.logistics_output else 'none'}\n"
        f"ETA hours: {state.logistics_output.eta_hours if state.logistics_output else 'none'}\n"
        f"Economic ROI: {state.economic_metrics.roi_percent}\n"
        f"Economic savings: {state.economic_metrics.savings}\n"
        f"Economic action cost: {state.economic_metrics.action_cost}\n"
        f"Guardrail compliant: {state.guardrail_output.is_compliant if state.guardrail_output else True}\n"
        f"Guardrail violations: {state.guardrail_output.violations if state.guardrail_output else []}\n"
        f"Guardrail modified action: {state.guardrail_output.modified_action.value if state.guardrail_output and state.guardrail_output.modified_action else 'none'}\n"
        f"Geo risk score: {state.geographic_risk_score}\n"
        f"Risk zones: {[z.name for z in state.risk_zones_crossed]}\n"
        f"Needs human approval: {state.requires_human_approval}\n"
        f"User query: {state.user_query or 'none'}"
    )

    result = llm.complete_json(system_prompt, user_prompt, max_tokens=700)
    if not result:
        return None
    return result
