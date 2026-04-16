"""
NutriTrack — Anomaly Detection Agent
======================================
Detects anomalies across all telemetry channels.
Performs root cause analysis and predicts impact trajectory.
"""

from __future__ import annotations
from nutritrack.models.schemas import (
    NutriTrackState, AnomalyAgentOutput, AnomalyReport,
    AnomalyType, RiskLevel
)
from nutritrack.utils.llm_grok import get_grok_client


def anomaly_detection_agent(state: NutriTrackState) -> NutriTrackState:
    """
    Anomaly Detection Agent: Multi-dimensional anomaly analysis.

    Detection strategy:
    1. LLM-only anomaly detection across telemetry channels
    2. LLM-generated root cause analysis
    3. LLM-generated impact trajectory
    """
    state.current_agent = "anomaly_detection_agent"

    llm = get_grok_client()

    # 100% agentic mode: anomaly detection relies exclusively on LLM output.
    if not llm.enabled:
        state.llm_trace.append({
            "agent": "anomaly_detection_agent",
            "mode": "llm_only",
            "risk": RiskLevel.LOW.value,
            "anomaly_count": 0,
            "llm_available": False,
            "llm_request_succeeded": False,
        })
        state.errors.append("Anomaly LLM unavailable: set GROQ_API_KEY/GROK_API_KEY to enable detection.")
        state.anomaly_output = AnomalyAgentOutput(
            anomalies=[],
            risk_level=RiskLevel.LOW,
            root_cause_analysis="",
            predicted_impact="",
        )
        return state

    llm_detection = _llm_anomaly_detection(state)
    if llm_detection is None:
        state.llm_trace.append({
            "agent": "anomaly_detection_agent",
            "mode": "llm_only",
            "risk": RiskLevel.LOW.value,
            "anomaly_count": 0,
            "llm_available": True,
            "llm_request_succeeded": False,
        })
        state.errors.append("Anomaly LLM request failed. Detection skipped in LLM-only mode.")
        state.anomaly_output = AnomalyAgentOutput(
            anomalies=[],
            risk_level=RiskLevel.LOW,
            root_cause_analysis="",
            predicted_impact="",
        )
        return state

    llm_anomalies = _parse_llm_anomalies(state, llm_detection.get("anomalies", []))
    llm_risk = str(llm_detection.get("risk_level", "low")).lower()
    if llm_risk in {"low", "medium", "high", "critical"}:
        overall_risk = RiskLevel(llm_risk)
    else:
        overall_risk = _derive_risk_from_anomalies(llm_anomalies)

    output = AnomalyAgentOutput(
        anomalies=llm_anomalies,
        risk_level=overall_risk,
        root_cause_analysis=str(llm_detection.get("root_cause_analysis", ""))[:600],
        predicted_impact=str(llm_detection.get("predicted_impact", ""))[:600],
    )
    state.anomaly_output = output
    state.llm_trace.append({
        "agent": "anomaly_detection_agent",
        "mode": "llm_only",
        "risk": overall_risk.value,
        "anomaly_count": len(llm_anomalies),
        "llm_available": True,
        "llm_request_succeeded": True,
    })
    return state


def _derive_risk_from_anomalies(anomalies: list[AnomalyReport]) -> RiskLevel:
    if any(a.severity == RiskLevel.CRITICAL for a in anomalies):
        return RiskLevel.CRITICAL
    if any(a.severity == RiskLevel.HIGH for a in anomalies):
        return RiskLevel.HIGH
    if any(a.severity == RiskLevel.MEDIUM for a in anomalies):
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def _llm_anomaly_detection(state: NutriTrackState) -> dict | None:
    llm = get_grok_client()

    system_prompt = (
        "You are an industrial anomaly detector for cold-chain logistics. "
        "Return JSON only with keys: anomalies, risk_level, root_cause_analysis, predicted_impact. "
        "anomalies must be an array of objects with keys: anomaly_type, severity, value_observed, description, trend. "
        "anomaly_type must be one of: temperature, humidity, co2, vibration, severe_degradation, none. "
        "trend must be one of: rising, falling, stable, fluctuating. "
        "risk_level must be low/medium/high/critical. "
        "If no anomaly is found, return anomalies as [] and risk_level as low. "
        "Do not invent sensor data; stay grounded in provided telemetry and product thresholds."
    )
    user_prompt = (
        f"Product={state.product.name} type={state.product.product_type.value}\n"
        f"Telemetry: temp={state.telemetry.temperature_celsius}, humidity={state.telemetry.humidity_percent}, "
        f"co2={state.telemetry.co2_ppm}, vibration={state.telemetry.vibration_g}\n"
        f"Thresholds: temp=[{state.product.optimal_temp_min},{state.product.optimal_temp_max}], "
        f"humidity=[{state.product.optimal_humidity_min},{state.product.optimal_humidity_max}], "
        f"max_co2={state.product.max_co2_ppm}, max_vibration=2.0\n"
        f"Health overall={state.health_score.overall}, safety={state.health_score.safety_index}, "
        f"remaining_hours={state.health_score.estimated_remaining_hours}"
    )

    result = llm.complete_json(system_prompt, user_prompt, max_tokens=450)
    if not result:
        return None

    return {
        "anomalies": result.get("anomalies", []),
        "risk_level": str(result.get("risk_level", "low")).lower(),
        "root_cause_analysis": str(result.get("root_cause_analysis", ""))[:600],
        "predicted_impact": str(result.get("predicted_impact", ""))[:600],
    }


def _parse_llm_anomalies(state: NutriTrackState, raw_anomalies: list[dict]) -> list[AnomalyReport]:
    parsed: list[AnomalyReport] = []
    product = state.product

    if not isinstance(raw_anomalies, list):
        return parsed

    for item in raw_anomalies[:6]:
        if not isinstance(item, dict):
            continue

        anomaly_type_name = str(item.get("anomaly_type", "none")).lower()
        severity_name = str(item.get("severity", "low")).lower()

        if anomaly_type_name not in {a.value for a in AnomalyType}:
            anomaly_type_name = AnomalyType.NONE.value
        if severity_name not in {r.value for r in RiskLevel}:
            severity_name = RiskLevel.LOW.value
        if anomaly_type_name == AnomalyType.NONE.value:
            continue

        try:
            value_observed = float(item.get("value_observed", 0.0))
        except (TypeError, ValueError):
            value_observed = 0.0

        if anomaly_type_name == AnomalyType.TEMPERATURE.value:
            expected_min, expected_max = product.optimal_temp_min, product.optimal_temp_max
        elif anomaly_type_name == AnomalyType.HUMIDITY.value:
            expected_min, expected_max = product.optimal_humidity_min, product.optimal_humidity_max
        elif anomaly_type_name == AnomalyType.CO2.value:
            expected_min, expected_max = 0.0, product.max_co2_ppm
        elif anomaly_type_name == AnomalyType.VIBRATION.value:
            expected_min, expected_max = 0.0, 2.0
        else:
            expected_min, expected_max = 0.0, 0.0

        trend_name = str(item.get("trend", "stable")).lower()
        if trend_name not in {"rising", "falling", "stable", "fluctuating"}:
            trend_name = "stable"

        if value_observed < expected_min:
            denominator = max(abs(expected_min), 1.0)
            deviation_percent = round((expected_min - value_observed) / denominator * 100, 1)
        elif value_observed > expected_max:
            denominator = max(abs(expected_max), 1.0)
            deviation_percent = round((value_observed - expected_max) / denominator * 100, 1)
        else:
            deviation_percent = 0.0

        parsed.append(AnomalyReport(
            anomaly_type=AnomalyType(anomaly_type_name),
            severity=RiskLevel(severity_name),
            value_observed=value_observed,
            value_expected_min=expected_min,
            value_expected_max=expected_max,
            deviation_percent=deviation_percent,
            trend=trend_name,
            description=str(item.get("description", ""))[:300],
        ))

    return parsed
