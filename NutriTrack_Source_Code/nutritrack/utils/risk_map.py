"""
NutriTrack — Risk Map Layer
============================
Geographic risk zones that affect cold chain integrity.
"""

from __future__ import annotations
import math
from nutritrack.models.schemas import RiskZone, GPSLocation


# Predefined risk zones (Morocco-centric + international)
RISK_ZONES: list[RiskZone] = [
    RiskZone(
        zone_id="RZ-001",
        name="Marrakech Heat Corridor",
        latitude=31.6295,
        longitude=-7.9811,
        radius_km=80,
        risk_type="extreme_heat",
        risk_multiplier=1.8,
        description="Summer temperatures exceed 45°C. Refrigeration units under extreme stress."
    ),
    RiskZone(
        zone_id="RZ-002",
        name="Atlas Mountain Pass",
        latitude=31.0500,
        longitude=-7.8800,
        radius_km=60,
        risk_type="altitude_refrigeration",
        risk_multiplier=1.4,
        description="High altitude reduces refrigeration efficiency by 15-20%."
    ),
    RiskZone(
        zone_id="RZ-003",
        name="Tangier Port Congestion",
        latitude=35.7595,
        longitude=-5.8340,
        radius_km=25,
        risk_type="congestion_delay",
        risk_multiplier=1.5,
        description="Port congestion causes 2-4 hour average delays in peak season."
    ),
    RiskZone(
        zone_id="RZ-004",
        name="Saharan Border Region",
        latitude=30.0000,
        longitude=-5.0000,
        radius_km=150,
        risk_type="extreme_heat_infrastructure",
        risk_multiplier=2.0,
        description="Extreme heat combined with limited cold chain infrastructure."
    ),
    RiskZone(
        zone_id="RZ-005",
        name="Casablanca Urban Traffic",
        latitude=33.5731,
        longitude=-7.5898,
        radius_km=20,
        risk_type="traffic_delay",
        risk_multiplier=1.2,
        description="Urban traffic can add 1-2 hours to delivery, affecting perishables."
    ),
    RiskZone(
        zone_id="RZ-006",
        name="Agadir Coastal Humidity",
        latitude=30.4278,
        longitude=-9.5981,
        radius_km=40,
        risk_type="high_humidity",
        risk_multiplier=1.3,
        description="Coastal humidity >90% can affect product packaging integrity."
    ),
]


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance between two points."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def assess_risk(location: GPSLocation) -> tuple[list[RiskZone], float]:
    """
    Assess geographic risk for a given GPS location.

    Returns:
        (list of crossed risk zones, aggregate risk score 0-1)
    """
    crossed = []
    max_multiplier = 1.0

    for zone in RISK_ZONES:
        dist = haversine_km(location.latitude, location.longitude,
                            zone.latitude, zone.longitude)
        if dist <= zone.radius_km:
            crossed.append(zone)
            max_multiplier = max(max_multiplier, zone.risk_multiplier)

    # Normalize to 0-1 score
    if not crossed:
        risk_score = 0.0
    else:
        risk_score = min(1.0, (max_multiplier - 1.0) / 1.0)  # 2.0 multiplier = 1.0 score

    return crossed, round(risk_score, 3)


def get_all_risk_zones() -> list[dict]:
    """Return all risk zones as dicts for visualization."""
    return [z.model_dump() for z in RISK_ZONES]
