"""
NutriTrack-Agentic Flow — Demo Export Runner
=============================================
Runs the multi-agent simulation and exports dashboard data.
"""

from __future__ import annotations
import sys
import os
import json
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nutritrack.graph import run_simulation, build_nutritrack_graph
from nutritrack.utils.simulation import (
    generate_scenario, get_scenario_descriptions, ScenarioType,
    PRODUCT_TEMPLATES
)
from nutritrack.utils.risk_map import get_all_risk_zones, assess_risk
from nutritrack.rag.pipeline import get_rag_pipeline
from nutritrack.models.schemas import NutriTrackState


def run_demo():
    """Run demonstration scenarios and print results."""

    print("=" * 80)
    print("  NutriTrack-Agentic Flow — Multi-Agent System Demo")
    print("  Production-Ready Cold Chain Intelligence Platform")
    print("=" * 80)

    scenarios = [
        ("dairy_yogurt", ScenarioType.TEMP_SPIKE, 4.0,
         "The yogurt batch temperature is rising. What should I do?"),
        ("seafood_shrimp", ScenarioType.SEVERE_DEGRADATION, 6.0,
         "Shrimp quality is degrading fast. Emergency options?"),
        ("pharma_vaccines", ScenarioType.MULTI_ANOMALY, 2.0,
         "Vaccine transport showing multiple issues. Assess risk."),
        ("meat_beef", ScenarioType.HUMIDITY_DROP, 3.0, None),
        ("fruits_citrus", ScenarioType.NORMAL, 8.0, None),
    ]

    all_results = []

    for product_key, scenario, hours, query in scenarios:
        print(f"\n{'─' * 80}")
        print(f"  SCENARIO: {product_key} | {scenario} | {hours}h elapsed")
        if query:
            print(f"  USER QUERY: {query}")
        print(f"{'─' * 80}")

        state, log = run_simulation(product_key, scenario, hours, query)
        all_results.append({
            "product": product_key,
            "scenario": scenario,
            "state": state,
            "log": log,
        })

        # Print execution flow
        print("\n  📋 EXECUTION FLOW:")
        for entry in log:
            routing = f" → {entry.get('routing', '')}" if 'routing' in entry else ""
            status_icon = "✅" if entry["status"] == "completed" else "❌"
            print(f"    {status_icon} Step {entry['step']}: {entry['node']} [{entry['status']}]{routing}")

        # Print key results
        print(f"\n  📊 HEALTH SCORE: {state.health_score.overall}/100")
        print(f"     Nutrition: {state.health_score.nutrition_index} | "
              f"Freshness: {state.health_score.freshness_index} | "
              f"Safety: {state.health_score.safety_index}")
        print(f"     Degradation rate: {state.health_score.degradation_rate}%/hr")
        print(f"     Remaining life: {state.health_score.estimated_remaining_hours}h")

        if state.anomaly_output:
            print(f"\n  ⚠️  ANOMALIES: {len(state.anomaly_output.anomalies)} detected")
            print(f"     Risk level: {state.anomaly_output.risk_level.value}")
            for a in state.anomaly_output.anomalies[:3]:
                print(f"     • {a.anomaly_type.value}: {a.description[:80]}...")

        if state.recommendation_output:
            print(f"\n  🎯 RECOMMENDATION:")
            print(f"     {state.recommendation_output.summary}")
            print(f"     Action: {state.recommendation_output.primary_action.value}")
            print(f"     Confidence: {state.recommendation_output.confidence:.0%}")

        if state.economic_metrics:
            m = state.economic_metrics
            print(f"\n  💰 ECONOMICS:")
            print(f"     Savings: ${m.savings:,.0f} | Cost: ${m.action_cost:,.0f} | ROI: {m.roi_percent:.0f}%")
            print(f"     Waste reduction: {m.waste_reduction_percent:.0f}%")

        if state.requires_human_approval:
            print(f"\n  🔒 HUMAN APPROVAL: Required — {state.human_approval_reason[:80]}")
            print(f"     Decision: {'APPROVED' if state.human_approved else 'REJECTED'}")
            print(f"     Feedback: {state.human_feedback[:80]}")

        if state.guardrail_output:
            g = state.guardrail_output
            status = "✅ COMPLIANT" if g.is_compliant else f"⚠️ {len(g.violations)} VIOLATION(S)"
            print(f"\n  🛡️ GUARDRAILS: {status} | Safety score: {g.safety_score:.0%}")

        if state.risk_zones_crossed:
            print(f"\n  🗺️ RISK ZONES: {', '.join(z.name for z in state.risk_zones_crossed)}")
            print(f"     Geographic risk: {state.geographic_risk_score:.0%}")

        print(f"\n  🏷️ QR TRACE: {state.traceability.qr_code}")
        print(f"     Events: {len(state.traceability.transport_history)}")

    # Generate JSON output for dashboard
    dashboard_data = _build_dashboard_data(all_results)
    export_paths = _write_dashboard_exports(dashboard_data)
    print(f"\n{'=' * 80}")
    for export_path in export_paths:
        print(f"  Dashboard data exported to: {export_path}")
    print(f"{'=' * 80}")

    return all_results


def _build_dashboard_data(results: list) -> dict:
    """Build structured data for the dashboard UI."""
    scenarios_data = []
    for r in results:
        state: NutriTrackState = r["state"]
        scenarios_data.append({
            "product": {
                "id": state.product.product_id,
                "name": state.product.name,
                "type": state.product.product_type.value,
                "origin": state.product.origin,
                "destination": state.product.destination,
                "value_usd": state.product.value_usd,
            },
            "scenario": r["scenario"],
            "telemetry": {
                "temperature": state.telemetry.temperature_celsius,
                "humidity": state.telemetry.humidity_percent,
                "co2": state.telemetry.co2_ppm,
                "vibration": state.telemetry.vibration_g,
            },
            "health": {
                "overall": state.health_score.overall,
                "nutrition": state.health_score.nutrition_index,
                "freshness": state.health_score.freshness_index,
                "safety": state.health_score.safety_index,
                "degradation_rate": state.health_score.degradation_rate,
                "remaining_hours": state.health_score.estimated_remaining_hours,
            },
            "location": {
                "lat": state.gps.latitude,
                "lon": state.gps.longitude,
                "city": state.gps.city,
            },
            "anomalies": [
                {
                    "type": a.anomaly_type.value,
                    "severity": a.severity.value,
                    "value": a.value_observed,
                    "description": a.description,
                }
                for a in (state.anomaly_output.anomalies if state.anomaly_output else [])
            ],
            "anomaly_analysis": {
                "root_cause": state.anomaly_output.root_cause_analysis if state.anomaly_output else "",
                "predicted_impact": state.anomaly_output.predicted_impact if state.anomaly_output else "",
            },
            "risk_level": state.anomaly_output.risk_level.value if state.anomaly_output else "low",
            "decision": {
                "action": state.final_decision.action.value if state.final_decision else "no_action",
                "confidence": state.final_decision.confidence if state.final_decision else 0,
                "status": state.final_decision.status.value if state.final_decision else "none",
                "requires_human": state.requires_human_approval,
                "human_approved": state.human_approved,
                "llm_available": state.final_decision.details.get("llm_available", False) if state.final_decision and state.final_decision.details else False,
                "llm_enabled": state.final_decision.details.get("llm_enabled", False) if state.final_decision and state.final_decision.details else False,
                "recommendation_mode": state.final_decision.details.get("recommendation_mode", "unknown") if state.final_decision and state.final_decision.details else "unknown",
            },
            "economics": {
                "savings": state.economic_metrics.savings,
                "action_cost": state.economic_metrics.action_cost,
                "roi": state.economic_metrics.roi_percent,
                "waste_reduction": state.economic_metrics.waste_reduction_percent,
                "loss_without_action": state.economic_metrics.estimated_loss_without_action,
                "loss_with_action": state.economic_metrics.estimated_loss_with_action,
            },
            "guardrail": {
                "compliant": state.guardrail_output.is_compliant if state.guardrail_output else True,
                "violations": len(state.guardrail_output.violations) if state.guardrail_output else 0,
                "safety_score": state.guardrail_output.safety_score if state.guardrail_output else 1.0,
            },
            "geographic_risk": state.geographic_risk_score,
            "risk_zones": [z.name for z in state.risk_zones_crossed],
            "traceability": {
                "qr_code": state.traceability.qr_code,
                "events": len(state.traceability.transport_history),
            },
            "execution_log": r["log"],
            "recommendation": {
                "summary": state.recommendation_output.summary if state.recommendation_output else "",
                "explanation": state.recommendation_output.explanation if state.recommendation_output else "",
                "alternatives": state.recommendation_output.alternative_actions if state.recommendation_output else [],
            },
        })

    # Aggregate metrics
    total_value = sum(s["product"]["value_usd"] for s in scenarios_data)
    total_savings = sum(s["economics"]["savings"] for s in scenarios_data)
    avg_waste_reduction = sum(s["economics"]["waste_reduction"] for s in scenarios_data) / max(len(scenarios_data), 1)
    total_anomalies = sum(len(s["anomalies"]) for s in scenarios_data)

    return {
        "generated_at": datetime.utcnow().isoformat(),
        "system": "NutriTrack-Agentic Flow v1.0",
        "summary": {
            "total_shipments": len(scenarios_data),
            "total_cargo_value": total_value,
            "total_savings": round(total_savings, 2),
            "avg_waste_reduction": round(avg_waste_reduction, 1),
            "total_anomalies": total_anomalies,
            "human_interventions": sum(1 for s in scenarios_data if s["decision"]["requires_human"]),
            "guardrail_violations": sum(s["guardrail"]["violations"] for s in scenarios_data),
        },
        "risk_zones": get_all_risk_zones(),
        "scenarios": scenarios_data,
    }


def _write_dashboard_exports(dashboard_data: dict) -> list[str]:
    """Write dashboard data to the backend export location."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    export_paths = [os.path.join(project_root, "nutritrack", "data", "dashboard_data.json")]

    written_paths: list[str] = []
    for output_path in export_paths:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as handle:
            json.dump(dashboard_data, handle, indent=2, default=str)
        written_paths.append(os.path.abspath(output_path))

    return written_paths


if __name__ == "__main__":
    run_demo()
