"""NutriTrack Transport Agent.

Provides route optimization using OSRM, weather-aware heat-risk scoring using
Open-Meteo, and real-time rerouting suggestions for active shipments.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


OSRM_BASE = "https://router.project-osrm.org"
OPEN_METEO_BASE = "https://api.open-meteo.com/v1/forecast"
NOMINATIM_BASE = "https://nominatim.openstreetmap.org/search"

CITY_COORDINATE_FALLBACKS = {
    "casablanca": {"lat": 33.5731, "lon": -7.5898},
    "rabat": {"lat": 34.0209, "lon": -6.8416},
    "marrakech": {"lat": 31.6295, "lon": -7.9811},
    "agadir": {"lat": 30.4278, "lon": -9.5981},
    "tanger": {"lat": 35.7595, "lon": -5.8340},
    "fes": {"lat": 34.0331, "lon": -5.0003},
}


@dataclass
class RouteOption:
    distance_km: float
    duration_min: float
    points: list[dict[str, float]]
    source: str


def _get_json(url: str, timeout: int = 10) -> dict[str, Any] | None:
    try:
        with urlopen(url, timeout=timeout) as response:
            payload = response.read().decode("utf-8")
            return json.loads(payload)
    except (URLError, TimeoutError, json.JSONDecodeError):
        return None


def _get_json_with_headers(url: str, headers: dict[str, str], timeout: int = 10) -> Any:
    try:
        req = Request(url=url, headers=headers)
        with urlopen(req, timeout=timeout) as response:
            payload = response.read().decode("utf-8")
            return json.loads(payload)
    except (URLError, TimeoutError, json.JSONDecodeError):
        return None


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius * c


def _fallback_route(origin: dict[str, float], destination: dict[str, float]) -> RouteOption:
    distance_km = _haversine_km(origin["lat"], origin["lon"], destination["lat"], destination["lon"])
    duration_min = max(15.0, (distance_km / 58.0) * 60.0)
    return RouteOption(
        distance_km=round(distance_km, 2),
        duration_min=round(duration_min, 2),
        points=[
            {"lat": origin["lat"], "lon": origin["lon"]},
            {
                "lat": round((origin["lat"] + destination["lat"]) / 2, 6),
                "lon": round((origin["lon"] + destination["lon"]) / 2, 6),
            },
            {"lat": destination["lat"], "lon": destination["lon"]},
        ],
        source="fallback",
    )


def fetch_osrm_routes(origin: dict[str, float], destination: dict[str, float]) -> list[RouteOption]:
    coords = f"{origin['lon']},{origin['lat']};{destination['lon']},{destination['lat']}"
    params = urlencode({"alternatives": "true", "overview": "full", "geometries": "geojson"})
    url = f"{OSRM_BASE}/route/v1/driving/{coords}?{params}"
    payload = _get_json(url)

    if not payload or payload.get("code") != "Ok":
        return [_fallback_route(origin, destination)]

    options: list[RouteOption] = []
    for route in payload.get("routes", []):
        geometry = route.get("geometry", {})
        coordinates = geometry.get("coordinates", []) if isinstance(geometry, dict) else []
        points: list[dict[str, float]] = []
        for pair in coordinates:
            if isinstance(pair, list) and len(pair) >= 2:
                lon = float(pair[0])
                lat = float(pair[1])
                points.append({"lat": lat, "lon": lon})

        if len(points) < 2:
            continue

        options.append(
            RouteOption(
                distance_km=round(float(route.get("distance", 0.0)) / 1000.0, 2),
                duration_min=round(float(route.get("duration", 0.0)) / 60.0, 2),
                points=points,
                source="osrm",
            )
        )

    if not options:
        return [_fallback_route(origin, destination)]

    return options[:3]


def fetch_openmeteo_current(lat: float, lon: float) -> dict[str, float]:
    params = urlencode(
        {
            "latitude": f"{lat:.6f}",
            "longitude": f"{lon:.6f}",
            "current": "temperature_2m,relative_humidity_2m",
            "timezone": "auto",
        }
    )
    url = f"{OPEN_METEO_BASE}?{params}"
    payload = _get_json(url)
    if not payload:
        return {"temperature_c": 30.0, "humidity_pct": 50.0, "source": "fallback"}

    current = payload.get("current", {}) if isinstance(payload.get("current", {}), dict) else {}
    return {
        "temperature_c": float(current.get("temperature_2m", 30.0)),
        "humidity_pct": float(current.get("relative_humidity_2m", 50.0)),
        "source": "open-meteo",
    }


def compute_heat_risk(temperature_c: float, humidity_pct: float) -> dict[str, Any]:
    # Lightweight operational heat index approximation for decision support.
    score = (temperature_c * 1.6) + (humidity_pct * 0.25)
    normalized = max(0.0, min(1.0, (score - 35.0) / 35.0))
    if normalized >= 0.75:
        level = "critical"
    elif normalized >= 0.5:
        level = "high"
    elif normalized >= 0.25:
        level = "medium"
    else:
        level = "low"

    return {
        "score": round(normalized, 3),
        "level": level,
        "temperature_c": round(temperature_c, 2),
        "humidity_pct": round(humidity_pct, 2),
    }


def geocode_place(query: str) -> dict[str, float] | None:
    if not query or not query.strip():
        return None

    params = urlencode(
        {
            "q": query.strip(),
            "format": "jsonv2",
            "limit": "1",
            "addressdetails": "0",
        }
    )
    payload = _get_json_with_headers(
        f"{NOMINATIM_BASE}?{params}",
        headers={
            "User-Agent": "NutriTrack/1.0 (cold-chain-routing)",
            "Accept": "application/json",
        },
        timeout=10,
    )

    if isinstance(payload, list) and payload:
        first = payload[0]
        try:
            return {
                "lat": float(first.get("lat")),
                "lon": float(first.get("lon")),
            }
        except (TypeError, ValueError):
            return None

    normalized = query.strip().lower()
    return CITY_COORDINATE_FALLBACKS.get(normalized)


def build_openstreetmap_directions_url(origin: dict[str, float], destination: dict[str, float]) -> str:
    return (
        "https://www.openstreetmap.org/directions?engine=fossgis_osrm_car"
        f"&route={origin['lat']}%2C{origin['lon']}%3B{destination['lat']}%2C{destination['lon']}"
    )


def optimize_transport(
    origin: dict[str, float],
    destination: dict[str, float],
    *,
    current_position: dict[str, float] | None = None,
) -> dict[str, Any]:
    routes = fetch_osrm_routes(origin, destination)
    weather_probe = current_position or origin
    weather = fetch_openmeteo_current(weather_probe["lat"], weather_probe["lon"])
    risk = compute_heat_risk(weather["temperature_c"], weather["humidity_pct"])

    ranked = sorted(routes, key=lambda r: (r.duration_min, r.distance_km))
    primary = ranked[0]
    alternatives = ranked[1:]

    reroute_reasons: list[str] = []
    if risk["level"] in {"high", "critical"} and alternatives:
        primary = sorted(ranked, key=lambda r: (r.distance_km, r.duration_min))[0]
        reroute_reasons.append(
            "Heat risk elevated: selected shortest exposure route to protect shipment quality."
        )

    if primary.duration_min > 420:
        reroute_reasons.append("Long ETA detected: recommend cross-docking checkpoint for cold-chain stability.")

    suggestions = [
        "Increase reefer setpoint monitoring frequency to every 10 minutes.",
        "Dispatch driver alert if compartment temperature exceeds threshold for 15 minutes.",
    ]
    if reroute_reasons:
        suggestions.insert(0, reroute_reasons[0])

    return {
        "map_provider": "openstreetmap",
        "route_engine": primary.source,
        "weather": weather,
        "heat_risk": risk,
        "primary": {
            "distance_km": primary.distance_km,
            "duration_min": primary.duration_min,
            "points": primary.points,
        },
        "alternatives": [
            {
                "distance_km": alt.distance_km,
                "duration_min": alt.duration_min,
                "points": alt.points,
            }
            for alt in alternatives
        ],
        "reroute_reasons": reroute_reasons,
        "suggestions": suggestions,
    }
