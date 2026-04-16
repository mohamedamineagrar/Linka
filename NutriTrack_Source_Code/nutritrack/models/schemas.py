"""
NutriTrack-Agentic Flow — Pydantic Schemas & Shared State
===========================================================
All data models used across the multi-agent system.
Enforces strict validation (Guardrails) on every agent output.
"""

from __future__ import annotations
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal
from enum import Enum
from datetime import datetime
import uuid


# ──────────────────────────── Enums ────────────────────────────

class ProductType(str, Enum):
    DAIRY = "dairy"
    MEAT = "meat"
    SEAFOOD = "seafood"
    FRUITS = "fruits"
    VEGETABLES = "vegetables"
    PHARMACEUTICALS = "pharmaceuticals"

class AnomalyType(str, Enum):
    TEMPERATURE = "temperature"
    HUMIDITY = "humidity"
    CO2 = "co2"
    VIBRATION = "vibration"
    SEVERE_DEGRADATION = "severe_degradation"
    NONE = "none"

class ActionType(str, Enum):
    CHANGE_ROUTE = "change_route"
    ADJUST_TEMPERATURE = "adjust_temperature"
    TRIGGER_URGENT_DELIVERY = "trigger_urgent_delivery"
    REDIRECT_WAREHOUSE = "redirect_warehouse"
    REDIRECT_LOCAL_MARKET = "redirect_local_market"
    QUARANTINE = "quarantine"
    ADJUST_VENTILATION = "adjust_ventilation"
    ISOLATE_PRODUCT = "isolate_product"
    NO_ACTION = "no_action"

class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class DecisionStatus(str, Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    PENDING_HUMAN = "pending_human_approval"


# ──────────────────────────── Telemetry ────────────────────────

class TelemetryData(BaseModel):
    """IoT sensor readings from the transport vehicle."""
    temperature_celsius: float = Field(..., ge=-40, le=60, description="Temperature in Celsius")
    humidity_percent: float = Field(..., ge=0, le=100, description="Relative humidity %")
    co2_ppm: float = Field(..., ge=0, le=5000, description="CO2 level in ppm")
    vibration_g: float = Field(0.0, ge=0, le=10, description="Vibration in g-force")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("temperature_celsius")
    @classmethod
    def validate_temperature(cls, v):
        if v < -40 or v > 60:
            raise ValueError(f"Temperature {v}°C is outside sensor range [-40, 60]")
        return round(v, 2)


class GPSLocation(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    city: str = ""
    country: str = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ──────────────────────────── Product ──────────────────────────

class ProductInfo(BaseModel):
    product_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8].upper())
    product_type: ProductType
    name: str
    batch_id: str = ""
    origin: str = ""
    destination: str = ""
    optimal_temp_min: float = 0.0
    optimal_temp_max: float = 8.0
    optimal_humidity_min: float = 40.0
    optimal_humidity_max: float = 80.0
    max_co2_ppm: float = 1000.0
    shelf_life_hours: float = 72.0
    value_usd: float = 0.0
    weight_kg: float = 0.0


class HealthScore(BaseModel):
    """Nutritional & freshness health score (0-100)."""
    overall: float = Field(100.0, ge=0, le=100)
    nutrition_index: float = Field(100.0, ge=0, le=100)
    freshness_index: float = Field(100.0, ge=0, le=100)
    safety_index: float = Field(100.0, ge=0, le=100)
    degradation_rate: float = Field(0.0, ge=0, description="% per hour")
    estimated_remaining_hours: float = Field(72.0, ge=0)


# ──────────────────────────── Decisions ────────────────────────

class Decision(BaseModel):
    decision_id: str = Field(default_factory=lambda: f"DEC-{uuid.uuid4().hex[:6].upper()}")
    action: ActionType
    reason: str
    confidence: float = Field(..., ge=0, le=1)
    risk_level: RiskLevel
    status: DecisionStatus = DecisionStatus.PROPOSED
    requires_human_approval: bool = False
    estimated_cost_usd: float = 0.0
    estimated_savings_usd: float = 0.0
    agent_source: str = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    details: dict = Field(default_factory=dict)


class EconomicMetrics(BaseModel):
    total_value_at_risk: float = 0.0
    estimated_loss_without_action: float = 0.0
    estimated_loss_with_action: float = 0.0
    savings: float = 0.0
    action_cost: float = 0.0
    roi_percent: float = 0.0
    waste_reduction_percent: float = 0.0


# ──────────────────────────── Risk Map ─────────────────────────

class RiskZone(BaseModel):
    zone_id: str
    name: str
    latitude: float
    longitude: float
    radius_km: float = 50.0
    risk_type: str = "heat"
    risk_multiplier: float = 1.5
    description: str = ""


# ──────────────────────────── QR Traceability ──────────────────

class TraceEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    event_type: str
    location: Optional[GPSLocation] = None
    details: str = ""
    agent: str = ""


class QRTraceability(BaseModel):
    product_id: str
    qr_code: str = ""
    transport_history: list[TraceEvent] = Field(default_factory=list)
    decision_log: list[Decision] = Field(default_factory=list)
    chain_of_custody: list[str] = Field(default_factory=list)


# ──────────────────────────── Anomaly ──────────────────────────

class AnomalyReport(BaseModel):
    anomaly_type: AnomalyType
    severity: RiskLevel
    value_observed: float
    value_expected_min: float
    value_expected_max: float
    deviation_percent: float = 0.0
    duration_minutes: float = 0.0
    trend: Literal["rising", "falling", "stable", "fluctuating"] = "stable"
    description: str = ""


# ──────────────────────────── RAG Context ──────────────────────

class RAGContext(BaseModel):
    query: str = ""
    retrieved_chunks: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    is_sufficient: bool = False


# ──────────────────────────── Agent Outputs ────────────────────

class BioticAgentOutput(BaseModel):
    health_score: HealthScore
    anomaly: Optional[AnomalyReport] = None
    rag_context: RAGContext = Field(default_factory=RAGContext)
    nutritional_assessment: str = ""
    recommendations: list[str] = Field(default_factory=list)

class AnomalyAgentOutput(BaseModel):
    anomalies: list[AnomalyReport] = Field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.LOW
    root_cause_analysis: str = ""
    predicted_impact: str = ""

class LogisticsAgentOutput(BaseModel):
    current_route: str = ""
    alternative_routes: list[dict] = Field(default_factory=list)
    nearest_warehouse: Optional[dict] = None
    nearest_market: Optional[dict] = None
    eta_hours: float = 0.0
    recommended_action: ActionType = ActionType.NO_ACTION
    reason: str = ""

class EconomicAgentOutput(BaseModel):
    metrics: EconomicMetrics = Field(default_factory=EconomicMetrics)
    recommended_action: ActionType = ActionType.NO_ACTION
    cost_benefit_analysis: str = ""
    priority: RiskLevel = RiskLevel.LOW

class GuardrailAgentOutput(BaseModel):
    is_compliant: bool = True
    violations: list[str] = Field(default_factory=list)
    modified_action: Optional[ActionType] = None
    compliance_notes: str = ""
    safety_score: float = Field(1.0, ge=0, le=1)

class RecommendationOutput(BaseModel):
    summary: str = ""
    primary_action: ActionType = ActionType.NO_ACTION
    explanation: str = ""
    alternative_actions: list[dict] = Field(default_factory=list)
    confidence: float = 0.0


# ──────────────────────────── SHARED STATE ─────────────────────

class NutriTrackState(BaseModel):
    """
    Central shared state passed through all agents in the LangGraph workflow.
    This is the single source of truth for the entire pipeline.
    """
    # Core identifiers
    session_id: str = Field(default_factory=lambda: f"SES-{uuid.uuid4().hex[:8].upper()}")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Product info
    product: ProductInfo = Field(default_factory=lambda: ProductInfo(
        product_type=ProductType.DAIRY, name="Default Product"
    ))

    # Sensor data
    telemetry: TelemetryData = Field(default_factory=lambda: TelemetryData(
        temperature_celsius=4.0, humidity_percent=60.0, co2_ppm=400.0
    ))
    gps: GPSLocation = Field(default_factory=lambda: GPSLocation(
        latitude=33.5731, longitude=-7.5898, city="Casablanca", country="Morocco"
    ))

    # Health assessment
    health_score: HealthScore = Field(default_factory=HealthScore)

    # Agent outputs
    biotic_output: Optional[BioticAgentOutput] = None
    anomaly_output: Optional[AnomalyAgentOutput] = None
    logistics_output: Optional[LogisticsAgentOutput] = None
    economic_output: Optional[EconomicAgentOutput] = None
    guardrail_output: Optional[GuardrailAgentOutput] = None
    recommendation_output: Optional[RecommendationOutput] = None

    # Decision pipeline
    decisions: list[Decision] = Field(default_factory=list)
    final_decision: Optional[Decision] = None

    # Human-in-the-loop
    requires_human_approval: bool = False
    human_approval_reason: str = ""
    human_approved: Optional[bool] = None
    human_feedback: str = ""

    # Risk map
    risk_zones_crossed: list[RiskZone] = Field(default_factory=list)
    geographic_risk_score: float = Field(0.0, ge=0, le=1)

    # Traceability
    traceability: QRTraceability = Field(default_factory=lambda: QRTraceability(product_id=""))

    # Economic
    economic_metrics: EconomicMetrics = Field(default_factory=EconomicMetrics)

    # RAG
    rag_context: RAGContext = Field(default_factory=RAGContext)

    # Workflow control
    current_agent: str = ""
    workflow_complete: bool = False
    errors: list[str] = Field(default_factory=list)
    autonomy_context: dict = Field(default_factory=dict)
    llm_trace: list[dict] = Field(default_factory=list)

    # User query (for smart assistant)
    user_query: Optional[str] = None

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
