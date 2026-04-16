"""
NutriTrack — Logistics Agent
==============================
Optimizes routing decisions based on anomaly data, risk zones, and time constraints.
Finds nearest warehouses and markets for emergency diversion.
"""

from __future__ import annotations
import math
from nutritrack.models.schemas import (
    NutriTrackState, LogisticsAgentOutput, ActionType, RiskLevel
)
from nutritrack.utils.risk_map import assess_risk, haversine_km


# ──────────────── Infrastructure Database ────────────────

WAREHOUSES = [
    {"name": "Casablanca Cold Hub", "lat": 33.5731, "lon": -7.5898, "capacity": "large", "has_cold_storage": True},
    {"name": "Rabat Logistics Center", "lat": 34.0209, "lon": -6.8416, "capacity": "medium", "has_cold_storage": True},
    {"name": "Meknès Agri Depot", "lat": 33.8935, "lon": -5.5473, "capacity": "medium", "has_cold_storage": True},
    {"name": "Marrakech Distribution", "lat": 31.6295, "lon": -7.9811, "capacity": "large", "has_cold_storage": True},
    {"name": "Tangier Port Cold Store", "lat": 35.7595, "lon": -5.8340, "capacity": "large", "has_cold_storage": True},
    {"name": "Agadir Seafood Hub", "lat": 30.4278, "lon": -9.5981, "capacity": "medium", "has_cold_storage": True},
    {"name": "Fès Storage Facility", "lat": 34.0331, "lon": -5.0003, "capacity": "small", "has_cold_storage": True},
    {"name": "Kenitra Relay Point", "lat": 34.2610, "lon": -6.5802, "capacity": "small", "has_cold_storage": False},
]

LOCAL_MARKETS = [
    {"name": "Marché Central Casablanca", "lat": 33.5890, "lon": -7.6115, "type": "central_market"},
    {"name": "Marché Gros Rabat", "lat": 34.0120, "lon": -6.8320, "type": "wholesale"},
    {"name": "Souk El Had Agadir", "lat": 30.4220, "lon": -9.5960, "type": "central_market"},
    {"name": "Marché de Gros Meknès", "lat": 33.8800, "lon": -5.5550, "type": "wholesale"},
    {"name": "Marché Municipal Tangier", "lat": 35.7650, "lon": -5.8100, "type": "central_market"},
]


def logistics_agent(state: NutriTrackState) -> NutriTrackState:
    """
    Logistics Agent: Route optimization and emergency diversion logic.

    Decision tree:
    - CRITICAL anomaly → Redirect to nearest cold warehouse
    - HIGH anomaly + time pressure → Trigger urgent delivery or local market
    - MEDIUM anomaly → Evaluate alternative routes avoiding risk zones
    - LOW → Continue current route with monitoring
    """
    state.current_agent = "logistics_agent"

    anomaly_output = state.anomaly_output
    risk_level = anomaly_output.risk_level if anomaly_output else RiskLevel.LOW
    gps = state.gps
    product = state.product
    health = state.health_score

    # ── Find nearest infrastructure ──
    nearest_wh = _find_nearest(gps.latitude, gps.longitude, WAREHOUSES, cold_only=True)
    nearest_market = _find_nearest(gps.latitude, gps.longitude, LOCAL_MARKETS)

    # ── Assess geographic risk ──
    risk_zones, geo_risk = assess_risk(gps)
    state.risk_zones_crossed = risk_zones
    state.geographic_risk_score = geo_risk

    # ── Evaluate alternative routes ──
    alt_routes = _generate_alternatives(gps, product, risk_zones)

    # ── Decision Logic ──
    recommended_action = ActionType.NO_ACTION
    reason = ""
    eta = _estimate_eta(gps, product)

    if risk_level == RiskLevel.CRITICAL:
        if health.estimated_remaining_hours < eta:
            # Can't make it to destination — divert
            if health.safety_index < 30:
                recommended_action = ActionType.QUARANTINE
                reason = (
                    f"CRITICAL: Safety index at {health.safety_index}%. "
                    f"Product unsafe for consumption. Quarantine at nearest facility "
                    f"({nearest_wh['name']}, {nearest_wh['distance_km']:.0f}km away)."
                )
            elif nearest_wh["distance_km"] < nearest_market.get("distance_km", 999):
                recommended_action = ActionType.REDIRECT_WAREHOUSE
                reason = (
                    f"CRITICAL: Cannot reach destination ({eta:.1f}h) within product life "
                    f"({health.estimated_remaining_hours:.1f}h). Redirect to "
                    f"{nearest_wh['name']} ({nearest_wh['distance_km']:.0f}km)."
                )
            else:
                recommended_action = ActionType.REDIRECT_LOCAL_MARKET
                reason = (
                    f"CRITICAL: Divert to {nearest_market['name']} for emergency sale. "
                    f"Recover partial value before total loss."
                )
        else:
            recommended_action = ActionType.TRIGGER_URGENT_DELIVERY
            reason = (
                f"CRITICAL anomaly but delivery feasible if expedited. "
                f"ETA: {eta:.1f}h, remaining life: {health.estimated_remaining_hours:.1f}h."
            )

    elif risk_level == RiskLevel.HIGH:
        if health.estimated_remaining_hours < eta * 1.5:
            recommended_action = ActionType.TRIGGER_URGENT_DELIVERY
            reason = (
                f"HIGH risk with tight timeline. Expedite delivery. "
                f"ETA: {eta:.1f}h, remaining: {health.estimated_remaining_hours:.1f}h."
            )
        elif geo_risk > 0.5:
            recommended_action = ActionType.CHANGE_ROUTE
            reason = (
                f"HIGH risk + geographic risk zone ({', '.join(z.name for z in risk_zones)}). "
                f"Alternative route recommended to avoid heat exposure."
            )
        else:
            recommended_action = ActionType.ADJUST_TEMPERATURE
            reason = f"HIGH anomaly detected. Adjust cooling and monitor. ETA: {eta:.1f}h."

    elif risk_level == RiskLevel.MEDIUM:
        if geo_risk > 0.3:
            recommended_action = ActionType.CHANGE_ROUTE
            reason = f"Medium risk compounded by geographic zone. Consider alternative route."
        else:
            # Check for specific anomaly types
            if anomaly_output and any(a.anomaly_type.value == "humidity" for a in anomaly_output.anomalies):
                recommended_action = ActionType.ADJUST_VENTILATION
                reason = "Humidity anomaly — adjust ventilation settings."
            else:
                recommended_action = ActionType.ADJUST_TEMPERATURE
                reason = "Medium anomaly — fine-tune temperature control."

    else:
        recommended_action = ActionType.NO_ACTION
        reason = f"All parameters acceptable. Continue to destination. ETA: {eta:.1f}h."

    output = LogisticsAgentOutput(
        current_route=f"{product.origin} → {product.destination}",
        alternative_routes=alt_routes,
        nearest_warehouse=nearest_wh,
        nearest_market=nearest_market,
        eta_hours=eta,
        recommended_action=recommended_action,
        reason=reason,
    )

    state.logistics_output = output
    return state


def _find_nearest(lat: float, lon: float, locations: list[dict], cold_only: bool = False) -> dict:
    """Find nearest location from a list."""
    best = None
    best_dist = float("inf")
    for loc in locations:
        if cold_only and not loc.get("has_cold_storage", True):
            continue
        dist = haversine_km(lat, lon, loc["lat"], loc["lon"])
        if dist < best_dist:
            best_dist = dist
            best = {**loc, "distance_km": round(dist, 1)}
    return best or {"name": "Unknown", "distance_km": 999}


def _estimate_eta(gps, product) -> float:
    """Estimate hours to destination (simplified)."""
    # Simple distance-based estimate using major city coordinates
    dest_coords = {
        "Casablanca": (33.5731, -7.5898),
        "Tangier": (35.7595, -5.8340),
        "Marrakech": (31.6295, -7.9811),
        "Rotterdam": (51.9225, 4.47917),
        "Ouarzazate": (30.9189, -6.8934),
    }
    for city, (lat, lon) in dest_coords.items():
        if city.lower() in product.destination.lower():
            dist = haversine_km(gps.latitude, gps.longitude, lat, lon)
            return round(dist / 70, 1)  # Assume 70 km/h average
    return 6.0  # Default


def _generate_alternatives(gps, product, risk_zones) -> list[dict]:
    """Generate alternative route options."""
    alternatives = []
    if risk_zones:
        alternatives.append({
            "name": "Northern Bypass",
            "description": f"Avoid {', '.join(z.name for z in risk_zones[:2])} via highway A1",
            "extra_km": 45,
            "extra_hours": 0.8,
            "risk_reduction": "40-60%",
        })
        alternatives.append({
            "name": "Coastal Route",
            "description": "Follow Atlantic coast — cooler ambient temperatures",
            "extra_km": 70,
            "extra_hours": 1.2,
            "risk_reduction": "50-70%",
        })
    alternatives.append({
        "name": "Express Highway",
        "description": "Toll expressway — faster but no intermediate cold stops",
        "extra_km": -20,
        "extra_hours": -0.5,
        "risk_reduction": "20% (speed benefit)",
    })
    return alternatives
