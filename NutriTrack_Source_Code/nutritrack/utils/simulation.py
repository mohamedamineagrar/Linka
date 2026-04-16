"""
NutriTrack — Simulation Engine
================================
Generate realistic transport scenarios for demonstration.
"""

from __future__ import annotations
import random
import math
from datetime import datetime, timedelta
from nutritrack.models.schemas import (
    NutriTrackState, ProductInfo, ProductType, TelemetryData,
    GPSLocation, HealthScore, QRTraceability, TraceEvent,
    RiskZone
)


# ──────────────── Product Templates ────────────────

PRODUCT_TEMPLATES = {
    "dairy_yogurt": ProductInfo(
        product_type=ProductType.DAIRY,
        name="Organic Yogurt Batch",
        batch_id="DY-2026-0415",
        origin="Meknès, Morocco",
        destination="Casablanca Distribution Center",
        optimal_temp_min=2.0,
        optimal_temp_max=6.0,
        optimal_humidity_min=60.0,
        optimal_humidity_max=85.0,
        max_co2_ppm=800.0,
        shelf_life_hours=120.0,
        value_usd=8500.0,
        weight_kg=2000.0,
    ),
    "seafood_shrimp": ProductInfo(
        product_type=ProductType.SEAFOOD,
        name="Fresh Atlantic Shrimp",
        batch_id="SS-2026-0415",
        origin="Agadir Port, Morocco",
        destination="Tangier Export Terminal",
        optimal_temp_min=-1.0,
        optimal_temp_max=2.0,
        optimal_humidity_min=85.0,
        optimal_humidity_max=95.0,
        max_co2_ppm=600.0,
        shelf_life_hours=48.0,
        value_usd=25000.0,
        weight_kg=1500.0,
    ),
    "meat_beef": ProductInfo(
        product_type=ProductType.MEAT,
        name="Premium Beef Cuts",
        batch_id="MB-2026-0415",
        origin="Fès, Morocco",
        destination="Marrakech Hotels Consortium",
        optimal_temp_min=0.0,
        optimal_temp_max=4.0,
        optimal_humidity_min=80.0,
        optimal_humidity_max=90.0,
        max_co2_ppm=700.0,
        shelf_life_hours=72.0,
        value_usd=18000.0,
        weight_kg=1200.0,
    ),
    "fruits_citrus": ProductInfo(
        product_type=ProductType.FRUITS,
        name="Moroccan Clementines Export",
        batch_id="FC-2026-0415",
        origin="Berkane, Morocco",
        destination="Rotterdam, Netherlands",
        optimal_temp_min=3.0,
        optimal_temp_max=8.0,
        optimal_humidity_min=85.0,
        optimal_humidity_max=95.0,
        max_co2_ppm=1000.0,
        shelf_life_hours=336.0,
        value_usd=45000.0,
        weight_kg=20000.0,
    ),
    "pharma_vaccines": ProductInfo(
        product_type=ProductType.PHARMACEUTICALS,
        name="COVID-19 Vaccine Batch",
        batch_id="PV-2026-0415",
        origin="Casablanca Pharma Hub",
        destination="Ouarzazate Regional Hospital",
        optimal_temp_min=2.0,
        optimal_temp_max=8.0,
        optimal_humidity_min=35.0,
        optimal_humidity_max=65.0,
        max_co2_ppm=500.0,
        shelf_life_hours=168.0,
        value_usd=120000.0,
        weight_kg=50.0,
    ),
}


# ──────────────── Route Waypoints ────────────────

ROUTE_WAYPOINTS = {
    "meknes_casablanca": [
        GPSLocation(latitude=33.8935, longitude=-5.5473, city="Meknès", country="Morocco"),
        GPSLocation(latitude=33.9716, longitude=-5.7470, city="El Hajeb", country="Morocco"),
        GPSLocation(latitude=33.6844, longitude=-6.3530, city="Khémisset", country="Morocco"),
        GPSLocation(latitude=33.9911, longitude=-6.8498, city="Rabat", country="Morocco"),
        GPSLocation(latitude=33.5731, longitude=-7.5898, city="Casablanca", country="Morocco"),
    ],
    "agadir_tangier": [
        GPSLocation(latitude=30.4278, longitude=-9.5981, city="Agadir", country="Morocco"),
        GPSLocation(latitude=31.6295, longitude=-8.0090, city="Marrakech", country="Morocco"),
        GPSLocation(latitude=32.3008, longitude=-9.2372, city="Safi", country="Morocco"),
        GPSLocation(latitude=33.2520, longitude=-8.5007, city="El Jadida", country="Morocco"),
        GPSLocation(latitude=33.5731, longitude=-7.5898, city="Casablanca", country="Morocco"),
        GPSLocation(latitude=34.0209, longitude=-6.8416, city="Rabat", country="Morocco"),
        GPSLocation(latitude=35.7595, longitude=-5.8340, city="Tangier", country="Morocco"),
    ],
}


# ──────────────── Scenario Generators ────────────────

class ScenarioType:
    NORMAL = "normal"
    TEMP_SPIKE = "temperature_spike"
    HUMIDITY_DROP = "humidity_drop"
    CO2_BUILDUP = "co2_buildup"
    SEVERE_DEGRADATION = "severe_degradation"
    MULTI_ANOMALY = "multi_anomaly"


def generate_scenario(
    product_key: str = "dairy_yogurt",
    scenario: str = ScenarioType.TEMP_SPIKE,
    hours_elapsed: float = 4.0,
) -> NutriTrackState:
    """Generate a complete simulation state for testing."""

    product = PRODUCT_TEMPLATES.get(product_key, PRODUCT_TEMPLATES["dairy_yogurt"]).model_copy()

    # Base telemetry (normal)
    temp = random.uniform(product.optimal_temp_min, product.optimal_temp_max)
    humidity = random.uniform(product.optimal_humidity_min, product.optimal_humidity_max)
    co2 = random.uniform(300, product.max_co2_ppm * 0.7)
    vibration = random.uniform(0.1, 0.5)

    # Apply scenario anomalies
    if scenario == ScenarioType.TEMP_SPIKE:
        temp = product.optimal_temp_max + random.uniform(4, 12)
    elif scenario == ScenarioType.HUMIDITY_DROP:
        humidity = random.uniform(15, 35)
    elif scenario == ScenarioType.CO2_BUILDUP:
        co2 = product.max_co2_ppm + random.uniform(200, 1500)
    elif scenario == ScenarioType.SEVERE_DEGRADATION:
        temp = product.optimal_temp_max + random.uniform(8, 20)
        humidity = random.uniform(10, 30)
        co2 = product.max_co2_ppm + random.uniform(500, 2000)
    elif scenario == ScenarioType.MULTI_ANOMALY:
        temp = product.optimal_temp_max + random.uniform(3, 8)
        humidity = product.optimal_humidity_min - random.uniform(10, 25)
        co2 = product.max_co2_ppm + random.uniform(100, 500)

    telemetry = TelemetryData(
        temperature_celsius=round(temp, 1),
        humidity_percent=round(max(0, min(100, humidity)), 1),
        co2_ppm=round(max(0, co2), 0),
        vibration_g=round(vibration, 2),
    )

    # Calculate initial health score based on deviations
    health = _compute_health(product, telemetry, hours_elapsed)

    # Pick a GPS location along a route
    route_key = list(ROUTE_WAYPOINTS.keys())[0]
    waypoints = ROUTE_WAYPOINTS[route_key]
    waypoint_idx = min(int(hours_elapsed / 2), len(waypoints) - 1)
    gps = waypoints[waypoint_idx].model_copy()

    # Build traceability
    trace = QRTraceability(
        product_id=product.product_id,
        qr_code=f"QR-NT-{product.product_id}-{product.batch_id}",
    )
    for i in range(waypoint_idx + 1):
        trace.transport_history.append(TraceEvent(
            event_type="waypoint_reached",
            location=waypoints[i],
            details=f"Arrived at {waypoints[i].city}",
            agent="logistics_tracker",
        ))

    state = NutriTrackState(
        product=product,
        telemetry=telemetry,
        gps=gps,
        health_score=health,
        traceability=trace,
    )

    return state


def _compute_health(product: ProductInfo, telemetry: TelemetryData, hours: float) -> HealthScore:
    """Compute health score based on deviations from optimal."""
    # Temperature deviation
    temp_dev = 0.0
    if telemetry.temperature_celsius > product.optimal_temp_max:
        temp_dev = (telemetry.temperature_celsius - product.optimal_temp_max) / product.optimal_temp_max
    elif telemetry.temperature_celsius < product.optimal_temp_min:
        temp_dev = (product.optimal_temp_min - telemetry.temperature_celsius) / max(abs(product.optimal_temp_min), 1)

    # Humidity deviation
    hum_dev = 0.0
    if telemetry.humidity_percent < product.optimal_humidity_min:
        hum_dev = (product.optimal_humidity_min - telemetry.humidity_percent) / product.optimal_humidity_min
    elif telemetry.humidity_percent > product.optimal_humidity_max:
        hum_dev = (telemetry.humidity_percent - product.optimal_humidity_max) / (100 - product.optimal_humidity_max)

    # CO2 deviation
    co2_dev = max(0, (telemetry.co2_ppm - product.max_co2_ppm) / product.max_co2_ppm)

    # Composite degradation
    degradation_factor = (temp_dev * 0.5 + hum_dev * 0.25 + co2_dev * 0.25)
    degradation_rate = min(15, degradation_factor * 10)  # % per hour

    total_degradation = min(80, degradation_rate * hours)

    freshness = max(10, 100 - total_degradation * 1.2)
    nutrition = max(15, 100 - total_degradation * 0.8)
    safety = max(5, 100 - total_degradation * 1.5)
    overall = (freshness * 0.3 + nutrition * 0.3 + safety * 0.4)

    remaining_hours = max(0, product.shelf_life_hours - hours - (total_degradation / max(degradation_rate, 0.1)))

    return HealthScore(
        overall=round(overall, 1),
        nutrition_index=round(nutrition, 1),
        freshness_index=round(freshness, 1),
        safety_index=round(safety, 1),
        degradation_rate=round(degradation_rate, 2),
        estimated_remaining_hours=round(remaining_hours, 1),
    )


def get_scenario_descriptions() -> dict[str, str]:
    return {
        ScenarioType.NORMAL: "Normal transport — all parameters within range",
        ScenarioType.TEMP_SPIKE: "Temperature spike — refrigeration unit partial failure",
        ScenarioType.HUMIDITY_DROP: "Humidity drop — seal breach or ventilation issue",
        ScenarioType.CO2_BUILDUP: "CO2 buildup — ventilation failure in sealed container",
        ScenarioType.SEVERE_DEGRADATION: "Severe multi-factor degradation — critical emergency",
        ScenarioType.MULTI_ANOMALY: "Multiple mild anomalies — compound risk scenario",
    }
