"""FastAPI surface for the NutriTrack dashboard and analysis workflow."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from nutritrack.main import _build_dashboard_data
from nutritrack.models.schemas import GPSLocation, HealthScore, NutriTrackState, ProductInfo, TelemetryData, QRTraceability
from nutritrack.utils.llm_grok import get_grok_client
from nutritrack.utils.simulation import ScenarioType, _compute_health


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DASHBOARD_PATH = PROJECT_ROOT / "nutritrack" / "data" / "dashboard_data.json"

class AnalysisRequest(BaseModel):
    """Request body for a single on-demand simulation."""

    product_key: str = Field(default="dairy_yogurt")
    scenario: str = Field(default=ScenarioType.TEMP_SPIKE)
    hours_elapsed: float = Field(default=4.0, ge=0)
    user_query: str | None = None
    product: ProductInfo | None = None
    telemetry: TelemetryData | None = None
    gps: GPSLocation | None = None
    analysis_label: str | None = None


class AssistantRequest(AnalysisRequest):
    """Request body for Groq-powered smart assistant responses."""

    assistant_query: str = Field(..., min_length=1)
    include_dashboard_context: bool = Field(default=True)
    max_fleet_items: int = Field(default=3, ge=1, le=10)


app = FastAPI(
    title="NutriTrack API",
    version="1.0.0",
    description="FastAPI wrapper for the NutriTrack multi-agent simulation.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _load_cached_dashboard() -> dict | None:
    path = BACKEND_DASHBOARD_PATH
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
    return None


def _write_dashboard_exports(dashboard_data: dict) -> None:
    BACKEND_DASHBOARD_PATH.parent.mkdir(parents=True, exist_ok=True)
    BACKEND_DASHBOARD_PATH.write_text(json.dumps(dashboard_data, indent=2, default=str), encoding="utf-8")


def _generate_dashboard(refresh: bool = False) -> dict:
    if not refresh:
        cached = _load_cached_dashboard()
        if cached is not None:
            return cached

    # Static demo fixtures are disabled; keep dashboard driven by real/cached runs.
    dashboard_data = _build_dashboard_data([])
    _write_dashboard_exports(dashboard_data)
    return dashboard_data


def _build_real_state(payload: AnalysisRequest) -> NutriTrackState:
    """Build a live state directly from user-provided product and sensor data."""
    product = payload.product
    if product is None:
        from nutritrack.utils.simulation import PRODUCT_TEMPLATES

        product = PRODUCT_TEMPLATES.get(payload.product_key, PRODUCT_TEMPLATES["dairy_yogurt"]).model_copy()

    telemetry = payload.telemetry or TelemetryData(
        temperature_celsius=product.optimal_temp_min,
        humidity_percent=product.optimal_humidity_min,
        co2_ppm=product.max_co2_ppm * 0.4,
        vibration_g=0.1,
    )

    gps = payload.gps or GPSLocation(
        latitude=33.5731,
        longitude=-7.5898,
        city="Casablanca",
        country="Morocco",
    )

    health_score = _compute_health(product, telemetry, payload.hours_elapsed)

    state = NutriTrackState(
        product=product,
        telemetry=telemetry,
        gps=gps,
        health_score=health_score,
        traceability=QRTraceability(product_id=product.product_id),
    )
    state.user_query = payload.user_query
    return state


def _run_agent_reasoning(payload: AnalysisRequest) -> dict:
    """Execute the full agent graph on real input and format the result."""
    if payload.product is None and payload.telemetry is None and payload.gps is None:
        raise ValueError(
            "Real input required: provide product, telemetry, or gps data. "
            "Static simulation scenarios are disabled."
        )

    from nutritrack.graph import build_nutritrack_graph

    state = _build_real_state(payload)
    graph = build_nutritrack_graph()
    final_state = graph.invoke(state)
    return _build_dashboard_data([
        {
            "product": payload.analysis_label or "real_input",
            "scenario": payload.analysis_label or "real_world_input",
            "state": final_state,
            "log": graph.get_execution_log(),
        }
    ])


def _assistant_answer(payload: AssistantRequest) -> dict:
    """Generate a Groq assistant answer grounded in app data."""
    scenario_data = _run_agent_reasoning(payload)
    selected = scenario_data["scenarios"][0]

    dashboard_context = None
    if payload.include_dashboard_context:
        dashboard_context = _generate_dashboard(refresh=False)

    llm = get_grok_client()
    if not llm.enabled:
        return {
            "answer": "Assistant unavailable: Groq API key is not configured.",
            "key_points": [],
            "next_actions": [],
            "llm_available": False,
        }

    fleet_items: list[dict] = []
    if dashboard_context:
        for item in dashboard_context.get("scenarios", [])[: payload.max_fleet_items]:
            fleet_items.append(
                {
                    "product": item.get("product", {}).get("name", "unknown"),
                    "risk_level": item.get("risk_level", "low"),
                    "decision": item.get("decision", {}).get("action", "no_action"),
                    "health": item.get("health", {}).get("overall", 0),
                }
            )

    system_prompt = (
        "You are NutriTrack Smart Assistant powered by Groq. "
        "Answer ONLY from the provided application data. "
        "Return JSON with keys: answer, key_points, next_actions. "
        "answer is concise and operational. key_points and next_actions are arrays of short strings."
    )

    user_prompt = (
        f"User question: {payload.assistant_query}\n"
        f"Selected shipment context: {json.dumps(selected, default=str)[:9000]}\n"
        f"Fleet summary: {json.dumps((dashboard_context or {}).get('summary', {}), default=str)}\n"
        f"Fleet sample: {json.dumps(fleet_items, default=str)}"
    )

    result = llm.complete_json(system_prompt, user_prompt, max_tokens=700)
    if not result:
        return {
            "answer": "Groq assistant did not return a response.",
            "key_points": [],
            "next_actions": [],
            "llm_available": False,
        }

    key_points = result.get("key_points", [])
    next_actions = result.get("next_actions", [])

    return {
        "answer": str(result.get("answer", "")).strip()[:3000],
        "key_points": [str(p)[:300] for p in key_points[:6] if str(p).strip()] if isinstance(key_points, list) else [],
        "next_actions": [str(a)[:180] for a in next_actions[:6] if str(a).strip()] if isinstance(next_actions, list) else [],
        "llm_available": True,
        "provider": "groq",
        "model": llm.model,
    }


@app.get("/api/health")
def health_check() -> dict:
    return {"status": "ok", "service": "NutriTrack API"}


@app.get("/api/dashboard")
def get_dashboard(refresh: bool = False) -> dict:
    return _generate_dashboard(refresh=refresh)


@app.get("/api/scenarios")
def get_scenarios() -> dict:
    return {
        "descriptions": {
            ScenarioType.NORMAL: "Normal transport — all parameters within range",
            ScenarioType.TEMP_SPIKE: "Temperature spike — refrigeration unit partial failure",
            ScenarioType.HUMIDITY_DROP: "Humidity drop — seal breach or ventilation issue",
            ScenarioType.CO2_BUILDUP: "CO2 buildup — ventilation failure in sealed container",
            ScenarioType.SEVERE_DEGRADATION: "Severe multi-factor degradation — critical emergency",
            ScenarioType.MULTI_ANOMALY: "Multiple mild anomalies — compound risk scenario",
        }
    }


@app.post("/api/analyze")
def analyze_shipment(payload: AnalysisRequest) -> dict:
    try:
        scenario_data = _run_agent_reasoning(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "generated_at": scenario_data["generated_at"],
        "system": scenario_data["system"],
        "summary": scenario_data["summary"],
        "scenario": scenario_data["scenarios"][0],
    }


@app.post("/api/reason")
def reason_from_real_input(payload: AnalysisRequest) -> dict:
    """Explicit endpoint for real-world reasoning from live input data."""
    if payload.product is None and payload.telemetry is None and payload.gps is None:
        raise HTTPException(
            status_code=400,
            detail="Provide product, telemetry, or gps data to use real-input reasoning.",
        )

    try:
        scenario_data = _run_agent_reasoning(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "generated_at": scenario_data["generated_at"],
        "system": scenario_data["system"],
        "summary": scenario_data["summary"],
        "scenario": scenario_data["scenarios"][0],
    }


@app.post("/api/assistant")
def smart_assistant(payload: AssistantRequest) -> dict:
    """Groq smart assistant grounded in selected shipment and app-level data."""
    try:
        assistant = _assistant_answer(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return assistant
