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
    1. Threshold-based detection (immediate)
    2. Trend analysis (predictive)
    3. Cross-correlation between parameters
    4. Root cause hypothesis generation
    """
    state.current_agent = "anomaly_detection_agent"

    product = state.product
    telemetry = state.telemetry
    anomalies: list[AnomalyReport] = []

    llm = get_grok_client()
    if llm.enabled:
        llm_detection = _llm_anomaly_detection(state)
        if llm_detection:
            llm_anomalies = _parse_llm_anomalies(state, llm_detection.get("anomalies", []))
            llm_risk = str(llm_detection.get("risk_level", "low")).lower()
            if llm_risk in {"low", "medium", "high", "critical"}:
                overall_risk = RiskLevel(llm_risk)
            else:
                overall_risk = RiskLevel.LOW

            output = AnomalyAgentOutput(
                anomalies=llm_anomalies,
                risk_level=overall_risk,
                root_cause_analysis=str(llm_detection.get("root_cause_analysis", ""))[:600],
                predicted_impact=str(llm_detection.get("predicted_impact", ""))[:600],
            )
            state.anomaly_output = output
            state.llm_trace.append({
                "agent": "anomaly_detection_agent",
                "mode": "groq_primary",
                "risk": overall_risk.value,
                "anomaly_count": len(llm_anomalies),
                "llm_available": True,
                "llm_request_succeeded": True,
            })
            return state

    # ── Temperature Anomaly ──
    temp = telemetry.temperature_celsius
    if temp > product.optimal_temp_max:
        dev = temp - product.optimal_temp_max
        severity = _classify_severity(dev, thresholds=[2, 5, 10])
        anomalies.append(AnomalyReport(
            anomaly_type=AnomalyType.TEMPERATURE,
            severity=severity,
            value_observed=temp,
            value_expected_min=product.optimal_temp_min,
            value_expected_max=product.optimal_temp_max,
            deviation_percent=round(dev / max(product.optimal_temp_max, 1) * 100, 1),
            trend="rising",
            description=f"Temperature excursion: {temp}°C ({dev:.1f}°C above max). "
                        f"Severity: {severity.value}.",
        ))
    elif temp < product.optimal_temp_min:
        dev = product.optimal_temp_min - temp
        severity = _classify_severity(dev, thresholds=[2, 5, 10])
        anomalies.append(AnomalyReport(
            anomaly_type=AnomalyType.TEMPERATURE,
            severity=severity,
            value_observed=temp,
            value_expected_min=product.optimal_temp_min,
            value_expected_max=product.optimal_temp_max,
            deviation_percent=round(dev / max(abs(product.optimal_temp_min), 1) * 100, 1),
            trend="falling",
            description=f"Sub-optimal temperature: {temp}°C ({dev:.1f}°C below min). "
                        f"Risk of freeze damage." if temp < 0 else
                        f"Sub-optimal temperature: {temp}°C ({dev:.1f}°C below min).",
        ))

    # ── Humidity Anomaly ──
    hum = telemetry.humidity_percent
    if hum < product.optimal_humidity_min:
        dev = product.optimal_humidity_min - hum
        severity = _classify_severity(dev, thresholds=[10, 20, 40])
        anomalies.append(AnomalyReport(
            anomaly_type=AnomalyType.HUMIDITY,
            severity=severity,
            value_observed=hum,
            value_expected_min=product.optimal_humidity_min,
            value_expected_max=product.optimal_humidity_max,
            deviation_percent=round(dev / product.optimal_humidity_min * 100, 1),
            trend="falling",
            description=f"Low humidity: {hum}% (min: {product.optimal_humidity_min}%). "
                        f"Surface dehydration risk.",
        ))
    elif hum > product.optimal_humidity_max:
        dev = hum - product.optimal_humidity_max
        severity = _classify_severity(dev, thresholds=[5, 10, 20])
        anomalies.append(AnomalyReport(
            anomaly_type=AnomalyType.HUMIDITY,
            severity=severity,
            value_observed=hum,
            value_expected_min=product.optimal_humidity_min,
            value_expected_max=product.optimal_humidity_max,
            deviation_percent=round(dev / (100 - product.optimal_humidity_max) * 100, 1),
            trend="rising",
            description=f"High humidity: {hum}% (max: {product.optimal_humidity_max}%). "
                        f"Fungal growth risk.",
        ))

    # ── CO2 Anomaly ──
    co2 = telemetry.co2_ppm
    if co2 > product.max_co2_ppm:
        dev = co2 - product.max_co2_ppm
        severity = _classify_severity(dev, thresholds=[200, 500, 1000])
        anomalies.append(AnomalyReport(
            anomaly_type=AnomalyType.CO2,
            severity=severity,
            value_observed=co2,
            value_expected_min=0,
            value_expected_max=product.max_co2_ppm,
            deviation_percent=round(dev / product.max_co2_ppm * 100, 1),
            trend="rising",
            description=f"CO2 buildup: {co2}ppm (max: {product.max_co2_ppm}ppm). "
                        f"Ventilation failure suspected.",
        ))

    # ── Vibration Anomaly ──
    vib = telemetry.vibration_g
    if vib > 2.0:
        severity = _classify_severity(vib - 2.0, thresholds=[1, 3, 5])
        anomalies.append(AnomalyReport(
            anomaly_type=AnomalyType.VIBRATION,
            severity=severity,
            value_observed=vib,
            value_expected_min=0,
            value_expected_max=2.0,
            deviation_percent=round((vib - 2.0) / 2.0 * 100, 1),
            trend="stable",
            description=f"Excessive vibration: {vib}g. Road quality or mechanical issue.",
        ))

    # ── Cross-correlation: Severe Degradation Check ──
    critical_count = sum(1 for a in anomalies if a.severity in [RiskLevel.HIGH, RiskLevel.CRITICAL])
    if critical_count >= 2:
        anomalies.append(AnomalyReport(
            anomaly_type=AnomalyType.SEVERE_DEGRADATION,
            severity=RiskLevel.CRITICAL,
            value_observed=critical_count,
            value_expected_min=0,
            value_expected_max=0,
            description=f"SEVERE: {critical_count} critical anomalies detected simultaneously. "
                        f"Compound degradation effect — product integrity at extreme risk.",
        ))

    # ── Overall Risk Level ──
    if any(a.severity == RiskLevel.CRITICAL for a in anomalies):
        overall_risk = RiskLevel.CRITICAL
    elif any(a.severity == RiskLevel.HIGH for a in anomalies):
        overall_risk = RiskLevel.HIGH
    elif any(a.severity == RiskLevel.MEDIUM for a in anomalies):
        overall_risk = RiskLevel.MEDIUM
    else:
        overall_risk = RiskLevel.LOW

    # ── Root Cause Analysis ──
    root_cause = _analyze_root_cause(anomalies, telemetry)
    predicted_impact = _predict_impact(anomalies, state.health_score)

    if llm.enabled:
        state.llm_trace.append({
            "agent": "anomaly_detection_agent",
            "mode": "rule_fallback",
            "risk": overall_risk.value,
            "anomaly_count": len(anomalies),
            "llm_available": False,
            "llm_request_succeeded": False,
        })

    output = AnomalyAgentOutput(
        anomalies=anomalies,
        risk_level=overall_risk,
        root_cause_analysis=root_cause,
        predicted_impact=predicted_impact,
    )

    state.anomaly_output = output
    return state


def _classify_severity(deviation: float, thresholds: list[float]) -> RiskLevel:
    """Classify anomaly severity based on deviation thresholds."""
    if deviation >= thresholds[2]:
        return RiskLevel.CRITICAL
    elif deviation >= thresholds[1]:
        return RiskLevel.HIGH
    elif deviation >= thresholds[0]:
        return RiskLevel.MEDIUM
    else:
        return RiskLevel.LOW


def _analyze_root_cause(anomalies: list[AnomalyReport], telemetry) -> str:
    """Generate root cause hypothesis."""
    if not anomalies:
        return "No anomalies detected. All parameters within operational limits."

    causes = []
    types = {a.anomaly_type for a in anomalies}

    if AnomalyType.TEMPERATURE in types and AnomalyType.HUMIDITY in types:
        causes.append(
            "Simultaneous temperature and humidity deviation suggests "
            "refrigeration unit malfunction or container seal failure."
        )
    elif AnomalyType.TEMPERATURE in types:
        if telemetry.temperature_celsius > 20:
            causes.append("Significant temperature spike — likely compressor failure or power outage.")
        else:
            causes.append("Moderate temperature elevation — possible thermostat drift or partial door seal issue.")

    if AnomalyType.CO2 in types:
        causes.append("CO2 buildup indicates ventilation system failure or blocked air circulation.")

    if AnomalyType.VIBRATION in types:
        causes.append("Excessive vibration — poor road conditions or suspension/mounting issue.")

    return " | ".join(causes) if causes else "Anomaly detected but root cause unclear — recommend manual inspection."


def _predict_impact(anomalies: list[AnomalyReport], health) -> str:
    """Predict impact trajectory."""
    if not anomalies:
        return "No impact expected. Product on track for safe delivery."

    worst = max(anomalies, key=lambda a: [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL].index(a.severity))

    if worst.severity == RiskLevel.CRITICAL:
        return (
            f"CRITICAL IMPACT: At current degradation rate ({health.degradation_rate}%/hr), "
            f"product will reach unsafe levels within {max(1, health.estimated_remaining_hours):.0f} hours. "
            f"Immediate intervention required."
        )
    elif worst.severity == RiskLevel.HIGH:
        return (
            f"HIGH IMPACT: Degradation accelerating. Estimated {health.estimated_remaining_hours:.0f} hours "
            f"remaining before quality threshold breach. Corrective action strongly recommended."
        )
    elif worst.severity == RiskLevel.MEDIUM:
        return (
            f"MODERATE IMPACT: Quality degradation above baseline but manageable. "
            f"Monitor closely. ~{health.estimated_remaining_hours:.0f} hours remaining."
        )
    else:
        return f"LOW IMPACT: Minor deviation detected. {health.estimated_remaining_hours:.0f} hours remaining."


def _llm_anomaly_detection(state: NutriTrackState) -> dict | None:
    llm = get_grok_client()

    system_prompt = (
        "You are an industrial anomaly detector for cold-chain logistics. "
        "Return JSON only with keys: anomalies, risk_level, root_cause_analysis, predicted_impact. "
        "anomalies must be an array of objects with keys: anomaly_type, severity, value_observed, description. "
        "anomaly_type must be one of: temperature, humidity, co2, vibration, severe_degradation, none. "
        "risk_level must be low/medium/high/critical. "
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

        parsed.append(AnomalyReport(
            anomaly_type=AnomalyType(anomaly_type_name),
            severity=RiskLevel(severity_name),
            value_observed=value_observed,
            value_expected_min=expected_min,
            value_expected_max=expected_max,
            description=str(item.get("description", ""))[:300],
        ))

    return parsed
