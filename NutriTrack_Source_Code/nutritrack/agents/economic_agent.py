"""
NutriTrack — Economic Decision Agent
======================================
Cost-benefit analysis for every proposed action.
Optimizes for maximum value recovery while minimizing waste.
"""

from __future__ import annotations
from nutritrack.models.schemas import (
    NutriTrackState, EconomicAgentOutput, EconomicMetrics,
    ActionType, RiskLevel
)
from nutritrack.rag.pipeline import get_rag_pipeline


# Cost models (USD)
ACTION_COSTS = {
    ActionType.CHANGE_ROUTE: lambda v: v * 0.15,          # 15% premium
    ActionType.ADJUST_TEMPERATURE: lambda v: 50 + v * 0.01,  # Fixed + variable
    ActionType.TRIGGER_URGENT_DELIVERY: lambda v: v * 0.25,  # 25% premium
    ActionType.REDIRECT_WAREHOUSE: lambda v: 200 + v * 0.05,
    ActionType.REDIRECT_LOCAL_MARKET: lambda v: 100,
    ActionType.QUARANTINE: lambda v: 300 + v * 0.02,
    ActionType.ADJUST_VENTILATION: lambda v: 30,
    ActionType.ISOLATE_PRODUCT: lambda v: 150,
    ActionType.NO_ACTION: lambda v: 0,
}

# Recovery rates (% of original value)
RECOVERY_RATES = {
    ActionType.CHANGE_ROUTE: 0.90,
    ActionType.ADJUST_TEMPERATURE: 0.95,
    ActionType.TRIGGER_URGENT_DELIVERY: 0.85,
    ActionType.REDIRECT_WAREHOUSE: 0.70,
    ActionType.REDIRECT_LOCAL_MARKET: 0.45,
    ActionType.QUARANTINE: 0.10,  # Minimal recovery (insurance/salvage)
    ActionType.ADJUST_VENTILATION: 0.95,
    ActionType.ISOLATE_PRODUCT: 0.60,
    ActionType.NO_ACTION: None,  # Depends on health
}


def economic_agent(state: NutriTrackState) -> NutriTrackState:
    """
    Economic Decision Agent: Cost-benefit optimizer.

    Evaluates:
    1. Value at risk (current product value × degradation)
    2. Cost of each possible action
    3. Expected recovery for each action
    4. ROI and waste reduction potential
    """
    state.current_agent = "economic_agent"

    product = state.product
    health = state.health_score
    logistics = state.logistics_output
    anomaly = state.anomaly_output

    # ── RAG: Economic data ──
    rag = get_rag_pipeline()
    econ_data = rag.query_economics(
        logistics.recommended_action.value if logistics else "general"
    )

    # ── Calculate value at risk ──
    health_factor = health.overall / 100.0
    current_value = product.value_usd * health_factor
    loss_without_action = _estimate_loss_no_action(product, health)

    # ── Evaluate proposed action ──
    proposed_action = logistics.recommended_action if logistics else ActionType.NO_ACTION
    action_cost = ACTION_COSTS.get(proposed_action, lambda v: 0)(product.value_usd)
    recovery_rate = RECOVERY_RATES.get(proposed_action, 0.5)

    if recovery_rate is None:
        # NO_ACTION: recovery depends on health trajectory
        if health.overall > 80:
            recovery_rate = 0.95
        elif health.overall > 60:
            recovery_rate = 0.75
        elif health.overall > 40:
            recovery_rate = 0.50
        else:
            recovery_rate = 0.20

    estimated_recovery = product.value_usd * recovery_rate
    loss_with_action = product.value_usd - estimated_recovery + action_cost
    savings = loss_without_action - loss_with_action

    roi = (savings / action_cost * 100) if action_cost > 0 else 0
    waste_reduction = ((loss_without_action - loss_with_action) / max(loss_without_action, 1)) * 100

    metrics = EconomicMetrics(
        total_value_at_risk=round(product.value_usd - current_value, 2),
        estimated_loss_without_action=round(loss_without_action, 2),
        estimated_loss_with_action=round(loss_with_action, 2),
        savings=round(max(0, savings), 2),
        action_cost=round(action_cost, 2),
        roi_percent=round(roi, 1),
        waste_reduction_percent=round(max(0, waste_reduction), 1),
    )

    # ── Cost-Benefit Analysis ──
    cba = _generate_cba(product, proposed_action, metrics, econ_data)

    # ── Priority Assessment ──
    if savings > product.value_usd * 0.3:
        priority = RiskLevel.CRITICAL
    elif savings > product.value_usd * 0.15:
        priority = RiskLevel.HIGH
    elif savings > product.value_usd * 0.05:
        priority = RiskLevel.MEDIUM
    else:
        priority = RiskLevel.LOW

    # ── Check if better alternative exists ──
    best_action = proposed_action
    best_savings = savings
    for action, cost_fn in ACTION_COSTS.items():
        if action == proposed_action or action == ActionType.NO_ACTION:
            continue
        alt_cost = cost_fn(product.value_usd)
        alt_recovery = RECOVERY_RATES.get(action, 0.5)
        if alt_recovery is None:
            continue
        alt_loss = product.value_usd - (product.value_usd * alt_recovery) + alt_cost
        alt_savings = loss_without_action - alt_loss
        if alt_savings > best_savings * 1.15:  # 15% better threshold
            best_action = action
            best_savings = alt_savings

    output = EconomicAgentOutput(
        metrics=metrics,
        recommended_action=best_action if best_action != proposed_action else proposed_action,
        cost_benefit_analysis=cba,
        priority=priority,
    )

    state.economic_output = output
    state.economic_metrics = metrics
    return state


def _estimate_loss_no_action(product, health) -> float:
    """Estimate total loss if no action is taken."""
    if health.overall < 30:
        return product.value_usd * 0.90  # 90% loss
    elif health.overall < 50:
        return product.value_usd * 0.65
    elif health.overall < 70:
        return product.value_usd * 0.35
    elif health.overall < 85:
        return product.value_usd * 0.15
    else:
        return product.value_usd * 0.05


def _generate_cba(product, action, metrics, econ_data) -> str:
    """Generate human-readable cost-benefit analysis."""
    rag_note = ""
    if econ_data["is_sufficient"]:
        rag_note = f" (Supported by: {', '.join(econ_data['sources'][:2])})"

    return (
        f"COST-BENEFIT ANALYSIS for {action.value}:\n"
        f"├─ Product value: ${product.value_usd:,.0f}\n"
        f"├─ Value at risk: ${metrics.total_value_at_risk:,.0f}\n"
        f"├─ Loss without action: ${metrics.estimated_loss_without_action:,.0f}\n"
        f"├─ Action cost: ${metrics.action_cost:,.0f}\n"
        f"├─ Loss with action: ${metrics.estimated_loss_with_action:,.0f}\n"
        f"├─ Net savings: ${metrics.savings:,.0f}\n"
        f"├─ ROI: {metrics.roi_percent:.0f}%\n"
        f"├─ Waste reduction: {metrics.waste_reduction_percent:.0f}%\n"
        f"└─ Recommendation: {'EXECUTE' if metrics.savings > 0 else 'RECONSIDER'}"
        f"{rag_note}"
    )
