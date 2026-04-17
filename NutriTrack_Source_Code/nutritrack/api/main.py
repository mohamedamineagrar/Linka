"""FastAPI surface for the NutriTrack dashboard and analysis workflow."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from urllib import error, request

from fastapi import Depends, FastAPI, Header, HTTPException, Path as ApiPath
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from nutritrack.agents.transport_agent import (
    build_openstreetmap_directions_url,
    geocode_place,
    optimize_transport,
)
from nutritrack.main import _build_dashboard_data
from nutritrack.models.schemas import GPSLocation, HealthScore, NutriTrackState, ProductInfo, TelemetryData, QRTraceability
from nutritrack.utils.llm_grok import get_grok_client
from nutritrack.utils.simulation import ScenarioType, _compute_health


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DASHBOARD_PATH = PROJECT_ROOT / "nutritrack" / "data" / "dashboard_data.json"
SHIPMENT_REQUESTS_PATH = PROJECT_ROOT / "nutritrack" / "data" / "shipment_requests.json"


@dataclass
class AuthUser:
    id: str
    email: str
    role: str


class AuthCredentials(BaseModel):
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=6)
    role: str = Field(default="client")


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    expires_in: int | None = None
    user: dict[str, Any]


def _is_truthy(value: str | None, default: bool = True) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_supabase_config() -> dict[str, str]:
    url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    anon_key = os.getenv("SUPABASE_ANON_KEY", "").strip()
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not url or not anon_key:
        raise HTTPException(
            status_code=503,
            detail="Supabase auth is not configured. Set SUPABASE_URL and SUPABASE_ANON_KEY.",
        )
    return {
        "url": url,
        "anon_key": anon_key,
        "service_key": service_key,
    }


def _auth_enforced() -> bool:
    return _is_truthy(os.getenv("SUPABASE_ENFORCE_AUTH"), default=True)


def _parse_auth_header(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    parts = authorization.strip().split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise HTTPException(status_code=401, detail="Invalid Authorization header format")
    return parts[1].strip()


def _supabase_request(
    *,
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    bearer_token: str | None = None,
    prefer_service_key: bool = False,
) -> dict[str, Any]:
    cfg = _get_supabase_config()
    key = cfg["service_key"] if prefer_service_key and cfg["service_key"] else cfg["anon_key"]
    auth_value = bearer_token or key
    headers = {
        "apikey": key,
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_value}",
    }

    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")

    req = request.Request(
        url=f"{cfg['url']}{path}",
        data=body,
        headers=headers,
        method=method,
    )

    try:
        with request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except error.HTTPError as exc:
        detail = "Supabase auth request failed"
        try:
            raw = exc.read().decode("utf-8")
            data = json.loads(raw) if raw else {}
            if isinstance(data, dict):
                detail = str(data.get("msg") or data.get("error_description") or data.get("error") or detail)
        except Exception:
            pass
        raise HTTPException(status_code=exc.code, detail=detail) from exc
    except error.URLError as exc:
        raise HTTPException(status_code=503, detail="Unable to reach Supabase auth service") from exc


def _extract_role(user: dict[str, Any]) -> str:
    app_meta = user.get("app_metadata") if isinstance(user.get("app_metadata"), dict) else {}
    user_meta = user.get("user_metadata") if isinstance(user.get("user_metadata"), dict) else {}
    return str(app_meta.get("role") or user_meta.get("role") or "client")


def _verify_access_token(token: str) -> AuthUser:
    user = _supabase_request(
        method="GET",
        path="/auth/v1/user",
        bearer_token=token,
    )
    user_id = str(user.get("id", "")).strip()
    email = str(user.get("email", "")).strip()
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return AuthUser(id=user_id, email=email, role=_extract_role(user))


def require_auth(authorization: str | None = Header(default=None)) -> AuthUser:
    if not _auth_enforced():
        return AuthUser(id="dev-user", email="dev@local", role="admin")
    token = _parse_auth_header(authorization)
    return _verify_access_token(token)


def _require_admin(current_user: AuthUser) -> None:
    if current_user.role.strip().lower() != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")


def _utc_iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_shipment_requests() -> list[dict[str, Any]]:
    if not SHIPMENT_REQUESTS_PATH.exists():
        return []
    try:
        payload = json.loads(SHIPMENT_REQUESTS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return payload if isinstance(payload, list) else []


def _save_shipment_requests(items: list[dict[str, Any]]) -> None:
    SHIPMENT_REQUESTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SHIPMENT_REQUESTS_PATH.write_text(json.dumps(items, indent=2), encoding="utf-8")


def _shipment_sort_key(item: dict[str, Any]) -> str:
    return str(item.get("created_at", ""))


def _normalize_lifecycle_stage(item: dict[str, Any]) -> str:
    stage = str(item.get("lifecycle_stage", "")).strip().lower()
    if stage in {"storage", "delivery", "destination"}:
        return stage

    status = str(item.get("status", "")).strip().lower()
    if status == "in_transit":
        return "delivery"
    if status in {"delivered", "completed"}:
        return "destination"
    return "storage"


def _append_lifecycle_event(item: dict[str, Any], *, stage: str, actor: str) -> None:
    history = item.get("lifecycle_history")
    if not isinstance(history, list):
        history = []

    history.append(
        {
            "stage": stage,
            "at": _utc_iso_now(),
            "by": actor,
        }
    )
    item["lifecycle_history"] = history


def _build_transport_plan(
    *,
    origin_label: str,
    destination_label: str,
    current_position: ShipmentCoordinate | None = None,
) -> dict[str, Any]:
    origin_coords = geocode_place(origin_label)
    if not origin_coords:
        raise HTTPException(status_code=400, detail=f"Unable to geocode origin: {origin_label}")

    destination_coords = geocode_place(destination_label)
    if not destination_coords:
        raise HTTPException(status_code=400, detail=f"Unable to geocode destination: {destination_label}")

    transport = optimize_transport(
        origin_coords,
        destination_coords,
        current_position=current_position.model_dump() if current_position else None,
    )
    transport["origin"] = {
        "label": origin_label,
        **origin_coords,
    }
    transport["destination"] = {
        "label": destination_label,
        **destination_coords,
    }
    transport["openstreetmap_directions_url"] = build_openstreetmap_directions_url(origin_coords, destination_coords)
    return transport

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


class ShipmentRequestCreate(BaseModel):
    quantity: float = Field(..., gt=0)
    destination: str = Field(..., min_length=2)
    origin: str = Field(default="Casablanca, Morocco", min_length=2)
    cargo_type: str = Field(default="general")
    notes: str = Field(default="")


class ShipmentCoordinate(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)


class ShipmentConfirmRequest(BaseModel):
    origin: str | None = None
    current_position: ShipmentCoordinate | None = None


class ShipmentStageUpdateRequest(BaseModel):
    stage: Literal["storage", "delivery", "destination"]


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


@app.post("/api/auth/signup", response_model=AuthResponse)
def auth_signup(payload: AuthCredentials) -> dict:
    normalized_email = payload.email.strip().lower()
    normalized_role = payload.role.strip().lower() if payload.role else "client"
    if normalized_role not in {"client", "admin"}:
        normalized_role = "client"
    response = _supabase_request(
        method="POST",
        path="/auth/v1/signup",
        payload={
            "email": normalized_email,
            "password": payload.password,
            "data": {
                "role": normalized_role,
            },
        },
    )
    return {
        "access_token": response.get("access_token", ""),
        "refresh_token": response.get("refresh_token"),
        "token_type": response.get("token_type", "bearer"),
        "expires_in": response.get("expires_in"),
        "user": response.get("user") or {},
    }


@app.post("/api/auth/login", response_model=AuthResponse)
def auth_login(payload: AuthCredentials) -> dict:
    normalized_email = payload.email.strip().lower()
    response = _supabase_request(
        method="POST",
        path="/auth/v1/token?grant_type=password",
        payload={
            "email": normalized_email,
            "password": payload.password,
        },
    )
    return {
        "access_token": response.get("access_token", ""),
        "refresh_token": response.get("refresh_token"),
        "token_type": response.get("token_type", "bearer"),
        "expires_in": response.get("expires_in"),
        "user": response.get("user") or {},
    }


@app.get("/api/auth/me")
def auth_me(current_user: AuthUser = Depends(require_auth)) -> dict:
    return {
        "id": current_user.id,
        "email": current_user.email,
        "role": current_user.role,
    }


@app.post("/api/shipment-requests")
def create_shipment_request(payload: ShipmentRequestCreate, current_user: AuthUser = Depends(require_auth)) -> dict:
    items = _load_shipment_requests()
    created = {
        "id": f"REQ-{len(items) + 1:05d}",
        "client_id": current_user.id,
        "client_email": current_user.email,
        "quantity": round(float(payload.quantity), 3),
        "destination": payload.destination.strip(),
        "origin": payload.origin.strip(),
        "cargo_type": payload.cargo_type.strip() or "general",
        "notes": payload.notes.strip(),
        "status": "pending_confirmation",
        "lifecycle_stage": "storage",
        "lifecycle_updated_at": _utc_iso_now(),
        "lifecycle_history": [
            {
                "stage": "storage",
                "at": _utc_iso_now(),
                "by": current_user.email,
            }
        ],
        "created_at": _utc_iso_now(),
        "confirmed_at": None,
        "confirmed_by": None,
        "transport_plan": None,
    }
    items.append(created)
    _save_shipment_requests(items)
    return created


@app.get("/api/shipment-requests")
def list_shipment_requests(current_user: AuthUser = Depends(require_auth)) -> dict:
    items = _load_shipment_requests()
    role = current_user.role.strip().lower()
    if role == "admin":
        visible = sorted(items, key=_shipment_sort_key, reverse=True)
    else:
        visible = [item for item in items if str(item.get("client_id", "")) == current_user.id]
        visible.sort(key=_shipment_sort_key, reverse=True)

    for item in visible:
        stage = _normalize_lifecycle_stage(item)
        item["lifecycle_stage"] = stage
        if not item.get("lifecycle_updated_at"):
            item["lifecycle_updated_at"] = item.get("confirmed_at") or item.get("created_at")
        if not isinstance(item.get("lifecycle_history"), list):
            item["lifecycle_history"] = []

    return {
        "items": visible,
        "total": len(visible),
        "role": current_user.role,
    }


@app.post("/api/shipment-requests/{request_id}/confirm")
def confirm_shipment_request(
    payload: ShipmentConfirmRequest,
    request_id: str = ApiPath(..., min_length=3),
    current_user: AuthUser = Depends(require_auth),
) -> dict:
    _require_admin(current_user)

    items = _load_shipment_requests()
    target_index = -1
    for index, item in enumerate(items):
        if str(item.get("id", "")) == request_id:
            target_index = index
            break

    if target_index < 0:
        raise HTTPException(status_code=404, detail="Shipment request not found")

    target = items[target_index]
    if str(target.get("status", "")).lower() == "confirmed":
        return target

    origin_label = payload.origin.strip() if payload.origin and payload.origin.strip() else str(target.get("origin", ""))
    destination_label = str(target.get("destination", ""))
    transport_plan = _build_transport_plan(
        origin_label=origin_label,
        destination_label=destination_label,
        current_position=payload.current_position,
    )

    target["origin"] = origin_label
    target["status"] = "confirmed"
    target["lifecycle_stage"] = "storage"
    target["lifecycle_updated_at"] = _utc_iso_now()
    target["confirmed_at"] = _utc_iso_now()
    target["confirmed_by"] = current_user.email
    target["transport_plan"] = transport_plan
    _append_lifecycle_event(target, stage="storage", actor=current_user.email)

    items[target_index] = target
    _save_shipment_requests(items)
    return target


@app.post("/api/shipment-requests/{request_id}/stage")
def update_shipment_stage(
    payload: ShipmentStageUpdateRequest,
    request_id: str = ApiPath(..., min_length=3),
    current_user: AuthUser = Depends(require_auth),
) -> dict:
    _require_admin(current_user)

    items = _load_shipment_requests()
    target_index = -1
    for index, item in enumerate(items):
        if str(item.get("id", "")) == request_id:
            target_index = index
            break

    if target_index < 0:
        raise HTTPException(status_code=404, detail="Shipment request not found")

    target = items[target_index]
    current_stage = _normalize_lifecycle_stage(target)
    requested_stage = payload.stage

    ordered_stages = ["storage", "delivery", "destination"]
    current_idx = ordered_stages.index(current_stage)
    requested_idx = ordered_stages.index(requested_stage)
    if requested_idx < current_idx:
        raise HTTPException(status_code=400, detail="Cannot move shipment lifecycle backward")
    if requested_idx > current_idx + 1:
        raise HTTPException(status_code=400, detail="Lifecycle must advance one stage at a time")

    if requested_stage == "delivery":
        if target.get("status") == "pending_confirmation" or not target.get("transport_plan"):
            raise HTTPException(status_code=400, detail="Confirm shipment before starting delivery")
        target["status"] = "in_transit"
    elif requested_stage == "destination":
        if current_stage != "delivery":
            raise HTTPException(status_code=400, detail="Shipment must be in delivery stage first")
        target["status"] = "delivered"
        target["delivered_at"] = _utc_iso_now()
    else:
        if target.get("status") == "pending_confirmation":
            target["status"] = "pending_confirmation"
        else:
            target["status"] = "confirmed"

    target["lifecycle_stage"] = requested_stage
    target["lifecycle_updated_at"] = _utc_iso_now()
    _append_lifecycle_event(target, stage=requested_stage, actor=current_user.email)

    items[target_index] = target
    _save_shipment_requests(items)
    return target


@app.delete("/api/shipment-requests/{request_id}")
def delete_shipment_request(
    request_id: str = ApiPath(..., min_length=3),
    current_user: AuthUser = Depends(require_auth),
) -> dict:
    _require_admin(current_user)

    items = _load_shipment_requests()
    target_index = -1
    for index, item in enumerate(items):
        if str(item.get("id", "")) == request_id:
            target_index = index
            break

    if target_index < 0:
        raise HTTPException(status_code=404, detail="Shipment request not found")

    removed = items.pop(target_index)
    _save_shipment_requests(items)
    return {
        "deleted": True,
        "id": request_id,
        "status": str(removed.get("status", "")),
    }


@app.get("/api/dashboard")
def get_dashboard(refresh: bool = False, _: AuthUser = Depends(require_auth)) -> dict:
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
def analyze_shipment(payload: AnalysisRequest, _: AuthUser = Depends(require_auth)) -> dict:
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
def reason_from_real_input(payload: AnalysisRequest, _: AuthUser = Depends(require_auth)) -> dict:
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
def smart_assistant(payload: AssistantRequest, _: AuthUser = Depends(require_auth)) -> dict:
    """Groq smart assistant grounded in selected shipment and app-level data."""
    try:
        assistant = _assistant_answer(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return assistant
