// export { default } from "./NutriTrackAutonomousDashboard.jsx";
import React, { useState, useEffect } from "react";
import { CircleMarker, MapContainer, Polyline, Popup, TileLayer, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";

const EMPTY_DASHBOARD_DATA = {
  summary: {
    total_shipments: 0,
    total_cargo_value: 0,
    total_savings: 0,
    avg_waste_reduction: 0,
    total_anomalies: 0,
    human_interventions: 0,
    guardrail_violations: 0,
  },
  risk_zones: [],
  scenarios: [],
};

const AGENT_COLORS = {
  supervisor: "#6366f1",
  biotic: "#10b981",
  anomaly_detector: "#f59e0b",
  logistics: "#3b82f6",
  economic: "#8b5cf6",
  guardrail: "#ef4444",
  recommendation: "#06b6d4",
  human_review: "#f97316",
  finalize: "#64748b",
};

const RISK_COLORS = { low: "#10b981", medium: "#f59e0b", high: "#f97316", critical: "#ef4444" };
const PRODUCT_ICONS = { dairy: "🥛", seafood: "🦐", pharmaceuticals: "💉", meat: "🥩", fruits: "🍊" };
const AUTH_TOKEN_STORAGE_KEY = "nutritrack_access_token";

const DEFAULT_MAP_CENTER = [33.5731, -7.5898];
const LIFECYCLE_STEPS = ["storage", "delivery", "destination"];


function normalizeLifecycleStage(requestItem) {
  const stage = String(requestItem?.lifecycle_stage || "").toLowerCase();
  if (LIFECYCLE_STEPS.includes(stage)) {
    return stage;
  }

  const status = String(requestItem?.status || "").toLowerCase();
  if (status === "in_transit") return "delivery";
  if (status === "delivered" || status === "completed") return "destination";
  return "storage";
}


function LifecycleProgress({ stage }) {
  const labels = {
    storage: "Stockage",
    delivery: "Livraison",
    destination: "Destination",
  };
  const activeIdx = Math.max(0, LIFECYCLE_STEPS.indexOf(stage));

  return (
    <div style={{ display: "grid", gap: 8 }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        {LIFECYCLE_STEPS.map((step, idx) => {
          const reached = idx <= activeIdx;
          const current = idx === activeIdx;
          return (
            <div key={step} style={{ display: "flex", alignItems: "center", flex: 1, gap: 6 }}>
              <div
                style={{
                  width: 12,
                  height: 12,
                  borderRadius: "50%",
                  background: reached ? (current ? "#06b6d4" : "#10b981") : "#334155",
                  border: reached ? "none" : "1px solid #64748b",
                  flexShrink: 0,
                }}
              />
              <div style={{ fontSize: 11, color: reached ? "var(--text)" : "var(--text-dim)", fontWeight: current ? 700 : 500 }}>
                {labels[step]}
              </div>
              {idx < LIFECYCLE_STEPS.length - 1 && (
                <div style={{ height: 2, flex: 1, background: idx < activeIdx ? "#10b981" : "#334155" }} />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}


function MapAutoBounds({ points }) {
  const map = useMap();

  useEffect(() => {
    if (!Array.isArray(points) || points.length === 0) {
      return;
    }

    if (points.length === 1) {
      map.setView(points[0], 11);
      return;
    }

    map.fitBounds(points, {
      padding: [24, 24],
      maxZoom: 12,
    });
  }, [map, points]);

  return null;
}


function DashboardLocationMap({ selected }) {
  const lat = Number(selected?.location?.lat ?? NaN);
  const lon = Number(selected?.location?.lon ?? NaN);
  const hasPoint = Number.isFinite(lat) && Number.isFinite(lon);
  const center = hasPoint ? [lat, lon] : DEFAULT_MAP_CENTER;

  return (
    <div style={{ height: 280, borderRadius: 12, overflow: "hidden", border: "1px solid var(--border)" }}>
      <MapContainer
        center={center}
        zoom={hasPoint ? 9 : 6}
        style={{ width: "100%", height: "100%" }}
        scrollWheelZoom={true}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {hasPoint && (
          <CircleMarker center={[lat, lon]} radius={9} pathOptions={{ color: "#6366f1", fillColor: "#6366f1", fillOpacity: 0.7 }}>
            <Popup>
              {selected?.product?.name || "Shipment"}<br />
              {selected?.location?.city || "Location"}
            </Popup>
          </CircleMarker>
        )}
      </MapContainer>
    </div>
  );
}


function ShipmentTrackingMap({ transportPlan, lifecycleStage = "storage" }) {
  const routePoints = Array.isArray(transportPlan?.primary?.points)
    ? transportPlan.primary.points
        .map((point) => [Number(point?.lat), Number(point?.lon)])
        .filter((pair) => Number.isFinite(pair[0]) && Number.isFinite(pair[1]))
    : [];

  const origin = transportPlan?.origin;
  const destination = transportPlan?.destination;

  const originPoint = Number.isFinite(Number(origin?.lat)) && Number.isFinite(Number(origin?.lon))
    ? [Number(origin.lat), Number(origin.lon)]
    : null;
  const destinationPoint = Number.isFinite(Number(destination?.lat)) && Number.isFinite(Number(destination?.lon))
    ? [Number(destination.lat), Number(destination.lon)]
    : null;

  const derivedRoute = routePoints.length >= 2
    ? routePoints
    : [originPoint, destinationPoint].filter(Boolean);

  const center = derivedRoute[0] || originPoint || destinationPoint || DEFAULT_MAP_CENTER;
  const lastPoint =
    lifecycleStage === "destination"
      ? destinationPoint
      : lifecycleStage === "delivery"
        ? (derivedRoute.length > 0 ? derivedRoute[derivedRoute.length - 1] : null)
        : originPoint;

  return (
    <div style={{ height: 250, borderRadius: 12, overflow: "hidden", border: "1px solid var(--border)" }}>
      <MapContainer center={center} zoom={7} style={{ width: "100%", height: "100%" }} scrollWheelZoom={true}>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        <MapAutoBounds points={derivedRoute.length ? derivedRoute : [center]} />

        {derivedRoute.length >= 2 && (
          <Polyline positions={derivedRoute} pathOptions={{ color: "#3b82f6", weight: 4 }} />
        )}

        {originPoint && (
          <CircleMarker center={originPoint} radius={8} pathOptions={{ color: "#10b981", fillColor: "#10b981", fillOpacity: 0.8 }}>
            <Popup>Origin: {origin?.label || "Unknown"}</Popup>
          </CircleMarker>
        )}

        {destinationPoint && (
          <CircleMarker center={destinationPoint} radius={8} pathOptions={{ color: "#ef4444", fillColor: "#ef4444", fillOpacity: 0.8 }}>
            <Popup>Destination: {destination?.label || "Unknown"}</Popup>
          </CircleMarker>
        )}

        {lastPoint && (
          <CircleMarker center={lastPoint} radius={7} pathOptions={{ color: "#f59e0b", fillColor: "#f59e0b", fillOpacity: 0.85 }}>
            <Popup>Current stage position: {lifecycleStage}</Popup>
          </CircleMarker>
        )}
      </MapContainer>
    </div>
  );
}

// ── Components ──

function KPICard({ label, value, sub, color, icon }) {
  return (
    <div style={{
      background: "var(--card-bg)",
      borderRadius: 16,
      padding: "20px 24px",
      borderLeft: `4px solid ${color}`,
      minWidth: 0,
    }}>
      <div style={{ fontSize: 13, color: "var(--text-dim)", letterSpacing: "0.04em", textTransform: "uppercase", fontFamily: "var(--font-mono)" }}>{label}</div>
      <div style={{ fontSize: 32, fontWeight: 700, color, marginTop: 6, fontFamily: "var(--font-display)", lineHeight: 1 }}>{icon && <span style={{ marginRight: 8 }}>{icon}</span>}{value}</div>
      {sub && <div style={{ fontSize: 12, color: "var(--text-dim)", marginTop: 4 }}>{sub}</div>}
    </div>
  );
}

function HealthGauge({ score, size = 120 }) {
  const r = (size - 16) / 2;
  const circ = 2 * Math.PI * r;
  const pct = score / 100;
  const offset = circ * (1 - pct * 0.75);
  const color = score > 70 ? "#10b981" : score > 40 ? "#f59e0b" : "#ef4444";

  return (
    <svg width={size} height={size * 0.85} viewBox={`0 0 ${size} ${size * 0.85}`}>
      <path d={`M ${size * 0.1} ${size * 0.7} A ${r} ${r} 0 1 1 ${size * 0.9} ${size * 0.7}`}
        fill="none" stroke="var(--border)" strokeWidth={8} strokeLinecap="round" />
      <path d={`M ${size * 0.1} ${size * 0.7} A ${r} ${r} 0 1 1 ${size * 0.9} ${size * 0.7}`}
        fill="none" stroke={color} strokeWidth={8} strokeLinecap="round"
        strokeDasharray={circ * 0.75} strokeDashoffset={offset}
        style={{ transition: "stroke-dashoffset 1s ease" }} />
      <text x={size / 2} y={size * 0.55} textAnchor="middle" fill={color}
        style={{ fontSize: size * 0.28, fontWeight: 800, fontFamily: "var(--font-display)" }}>{score}</text>
      <text x={size / 2} y={size * 0.72} textAnchor="middle" fill="var(--text-dim)"
        style={{ fontSize: size * 0.1, fontFamily: "var(--font-mono)" }}>/ 100</text>
    </svg>
  );
}

function MiniBar({ value, max = 100, color, label, width = "100%" }) {
  return (
    <div style={{ width }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "var(--text-dim)", marginBottom: 3, fontFamily: "var(--font-mono)" }}>
        <span>{label}</span><span>{value}</span>
      </div>
      <div style={{ height: 6, background: "var(--border)", borderRadius: 3, overflow: "hidden" }}>
        <div style={{ height: "100%", width: `${(value / max) * 100}%`, background: color, borderRadius: 3, transition: "width 0.8s ease" }} />
      </div>
    </div>
  );
}

function Badge({ text, color }) {
  return (
    <span style={{
      display: "inline-block",
      padding: "3px 10px",
      borderRadius: 20,
      fontSize: 11,
      fontWeight: 600,
      background: `${color}18`,
      color,
      border: `1px solid ${color}30`,
      fontFamily: "var(--font-mono)",
      textTransform: "uppercase",
      letterSpacing: "0.05em",
    }}>{text}</span>
  );
}

function ExecutionFlow({ log }) {
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 4, alignItems: "center" }}>
      {log.map((entry, i) => (
        <div key={i} style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <div style={{
            padding: "4px 10px",
            borderRadius: 8,
            fontSize: 11,
            fontWeight: 600,
            background: `${AGENT_COLORS[entry.node] || "#64748b"}20`,
            color: AGENT_COLORS[entry.node] || "#64748b",
            border: `1px solid ${AGENT_COLORS[entry.node] || "#64748b"}30`,
            fontFamily: "var(--font-mono)",
            whiteSpace: "nowrap",
          }}>
            {entry.node.replace("_", " ")}
          </div>
          {i < log.length - 1 && <span style={{ color: "var(--text-dim)", fontSize: 10 }}>→</span>}
        </div>
      ))}
    </div>
  );
}

function TelemetryPanel({ telemetry, product }) {
  const optimalTemp = product.type === "dairy" ? "2-6°C" : product.type === "seafood" ? "-1-2°C" : product.type === "meat" ? "0-4°C" : product.type === "pharmaceuticals" ? "2-8°C" : "3-8°C";
  const tempColor = product.type === "seafood" && telemetry.temperature > 2 ? "#ef4444" : telemetry.temperature > 8 ? "#ef4444" : telemetry.temperature > 6 ? "#f59e0b" : "#10b981";

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
      {[
        { label: "Temperature", value: `${telemetry.temperature}°C`, optimal: optimalTemp, color: tempColor, icon: "🌡️" },
        { label: "Humidity", value: `${telemetry.humidity}%`, optimal: "60-95%", color: telemetry.humidity < 40 ? "#ef4444" : "#10b981", icon: "💧" },
        { label: "CO₂", value: `${telemetry.co2} ppm`, optimal: "<800 ppm", color: telemetry.co2 > 800 ? "#f59e0b" : "#10b981", icon: "🫧" },
        { label: "Vibration", value: `${telemetry.vibration}g`, optimal: "<2.0g", color: telemetry.vibration > 2 ? "#f59e0b" : "#10b981", icon: "📳" },
      ].map((m) => (
        <div key={m.label} style={{ background: "var(--surface)", borderRadius: 10, padding: 12 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: 12, color: "var(--text-dim)", fontFamily: "var(--font-mono)" }}>{m.icon} {m.label}</span>
            <span style={{ fontSize: 10, color: "var(--text-dim)" }}>opt: {m.optimal}</span>
          </div>
          <div style={{ fontSize: 22, fontWeight: 700, color: m.color, marginTop: 4, fontFamily: "var(--font-display)" }}>{m.value}</div>
        </div>
      ))}
    </div>
  );
}

function ScenarioCard({ scenario, isSelected, onClick }) {
  const s = scenario;
  const riskColor = RISK_COLORS[s.risk_level];
  const icon = PRODUCT_ICONS[s.product.type] || "📦";

  return (
    <div onClick={onClick} style={{
      background: isSelected ? "var(--card-bg-active)" : "var(--card-bg)",
      borderRadius: 14,
      padding: "16px 18px",
      cursor: "pointer",
      border: isSelected ? "2px solid var(--accent)" : "2px solid transparent",
      transition: "all 0.2s",
      position: "relative",
      overflow: "hidden",
    }}>
      {isSelected && <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: 3, background: "var(--accent)" }} />}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "start", gap: 8 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 15, fontWeight: 700, color: "var(--text)", display: "flex", alignItems: "center", gap: 6 }}>
            <span>{icon}</span>
            <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{s.product.name}</span>
          </div>
          <div style={{ fontSize: 11, color: "var(--text-dim)", marginTop: 3, fontFamily: "var(--font-mono)" }}>
            {s.product.origin} → {s.product.destination}
          </div>
        </div>
        <Badge text={s.risk_level} color={riskColor} />
      </div>
      <div style={{ display: "flex", gap: 16, marginTop: 12, fontSize: 12 }}>
        <div>
          <div style={{ color: "var(--text-dim)", fontFamily: "var(--font-mono)", fontSize: 10 }}>HEALTH</div>
          <div style={{ fontWeight: 700, color: s.health.overall > 70 ? "#10b981" : s.health.overall > 40 ? "#f59e0b" : "#ef4444" }}>{s.health.overall}</div>
        </div>
        <div>
          <div style={{ color: "var(--text-dim)", fontFamily: "var(--font-mono)", fontSize: 10 }}>VALUE</div>
          <div style={{ fontWeight: 700, color: "var(--text)" }}>${(s.product.value_usd / 1000).toFixed(0)}k</div>
        </div>
        <div>
          <div style={{ color: "var(--text-dim)", fontFamily: "var(--font-mono)", fontSize: 10 }}>ACTION</div>
          <div style={{ fontWeight: 600, color: "var(--accent)", fontSize: 11 }}>{s.decision.action.replace(/_/g, " ")}</div>
        </div>
      </div>
    </div>
  );
}

function ActiveShipmentLiveCard({ requestItem, onOpen }) {
  const stage = normalizeLifecycleStage(requestItem);
  const stageColor = stage === "delivery" ? "#06b6d4" : stage === "destination" ? "#10b981" : "#f59e0b";

  return (
    <div
      onClick={onOpen}
      style={{
        background: "var(--surface)",
        borderRadius: 12,
        padding: "12px 14px",
        cursor: "pointer",
        border: `1px solid ${stageColor}55`,
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: "var(--text)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {requestItem.id} · live shipment
          </div>
          <div style={{ fontSize: 10, color: "var(--text-dim)", fontFamily: "var(--font-mono)", marginTop: 3 }}>
            {requestItem.origin} → {requestItem.destination}
          </div>
        </div>
        <Badge text={stage} color={stageColor} />
      </div>

      <div style={{ marginTop: 8, display: "flex", justifyContent: "space-between", gap: 8, fontSize: 11 }}>
        <span style={{ color: "var(--text-dim)" }}>Qty: {requestItem.quantity}</span>
        <span style={{ color: stageColor, fontWeight: 600 }}>tracking active</span>
      </div>
    </div>
  );
}

function AgentWorkflowDiagram({ log }) {
  const nodes = [
    { id: "supervisor", label: "Supervisor", x: 50, y: 15, icon: "🎛️" },
    { id: "biotic", label: "Biotic", x: 50, y: 28, icon: "🧬" },
    { id: "anomaly_detector", label: "Anomaly", x: 50, y: 41, icon: "⚠️" },
    { id: "logistics", label: "Logistics", x: 25, y: 54, icon: "🚛" },
    { id: "economic", label: "Economic", x: 50, y: 54, icon: "💰" },
    { id: "guardrail", label: "Guardrail", x: 50, y: 67, icon: "🛡️" },
    { id: "recommendation", label: "Recommend", x: 75, y: 54, icon: "🎯" },
    { id: "human_review", label: "Human", x: 75, y: 67, icon: "👤" },
    { id: "finalize", label: "Finalize", x: 50, y: 82, icon: "✅" },
  ];

  const activeNodes = new Set(log.map(l => l.node));

  return (
    <div style={{ position: "relative", height: 260, background: "var(--surface)", borderRadius: 12, overflow: "hidden" }}>
      <svg width="100%" height="100%" viewBox="0 0 100 100" preserveAspectRatio="xMidYMid meet">
        {/* Edges */}
        {[
          [50, 20, 50, 25], [50, 33, 50, 38], [50, 46, 25, 51], [50, 46, 50, 51], [50, 46, 75, 51],
          [25, 59, 50, 64], [50, 59, 50, 64], [50, 72, 50, 79], [75, 59, 75, 64], [75, 72, 50, 79],
        ].map(([x1, y1, x2, y2], i) => (
          <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke="var(--border)" strokeWidth={0.4} strokeDasharray="1,1" />
        ))}
        {/* Nodes */}
        {nodes.map(n => {
          const active = activeNodes.has(n.id);
          const col = AGENT_COLORS[n.id] || "#64748b";
          return (
            <g key={n.id}>
              <rect x={n.x - 10} y={n.y - 5} width={20} height={10} rx={3}
                fill={active ? `${col}25` : "var(--card-bg)"}
                stroke={active ? col : "var(--border)"}
                strokeWidth={active ? 0.6 : 0.3} />
              <text x={n.x} y={n.y + 0.5} textAnchor="middle" dominantBaseline="middle"
                fill={active ? col : "var(--text-dim)"}
                style={{ fontSize: 3.2, fontWeight: active ? 700 : 400, fontFamily: "system-ui" }}>
                {n.icon} {n.label}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function EconomicsChart({ economics }) {
  const maxVal = Math.max(economics.loss_without_action, economics.loss_with_action + economics.action_cost, 1);
  const barH = 32;

  return (
    <div style={{ padding: "8px 0" }}>
      {[
        { label: "Loss (no action)", value: economics.loss_without_action, color: "#ef4444" },
        { label: "Loss (with action)", value: economics.loss_with_action, color: "#f59e0b" },
        { label: "Action Cost", value: economics.action_cost, color: "#6366f1" },
        { label: "Net Savings", value: economics.savings, color: "#10b981" },
      ].map((bar) => (
        <div key={bar.label} style={{ marginBottom: 10 }}>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "var(--text-dim)", marginBottom: 3, fontFamily: "var(--font-mono)" }}>
            <span>{bar.label}</span>
            <span style={{ fontWeight: 600, color: bar.color }}>${bar.value.toLocaleString()}</span>
          </div>
          <div style={{ height: 8, background: "var(--surface)", borderRadius: 4, overflow: "hidden" }}>
            <div style={{ height: "100%", width: `${Math.max(2, (bar.value / maxVal) * 100)}%`, background: bar.color, borderRadius: 4, transition: "width 0.8s ease" }} />
          </div>
        </div>
      ))}
    </div>
  );
}

function AnomalyList({ anomalies }) {
  if (!anomalies.length) return <div style={{ color: "var(--text-dim)", fontSize: 13, padding: 12, textAlign: "center" }}>No anomaly items returned by the model for this shipment.</div>;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {anomalies.map((a, i) => (
        <div key={i} style={{
          padding: "10px 14px",
          borderRadius: 10,
          background: `${RISK_COLORS[a.severity]}08`,
          borderLeft: `3px solid ${RISK_COLORS[a.severity]}`,
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: "var(--text)", textTransform: "capitalize" }}>
              {String(a.type || "anomaly").replace(/_/g, " ")}
            </span>
            <Badge text={a.severity} color={RISK_COLORS[a.severity]} />
          </div>
          <div style={{ fontSize: 11, color: "var(--text-dim)", marginTop: 4 }}>{a.description}</div>
        </div>
      ))}
    </div>
  );
}

function QRTrace({ traceability, product }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 16, padding: 12, background: "var(--surface)", borderRadius: 10 }}>
      <div style={{
        width: 64, height: 64, background: "white", borderRadius: 8,
        display: "flex", alignItems: "center", justifyContent: "center",
        border: "2px solid var(--border)",
      }}>
        <svg width={48} height={48} viewBox="0 0 48 48">
          {/* Simplified QR pattern */}
          {Array.from({ length: 6 }, (_, r) =>
            Array.from({ length: 6 }, (_, c) => {
              const hash = ((r * 7 + c * 13 + product.id.charCodeAt(0)) % 3);
              return hash > 0 ? <rect key={`${r}-${c}`} x={4 + c * 7} y={4 + r * 7} width={6} height={6} rx={1} fill="#1a1a2e" /> : null;
            })
          )}
          <rect x={2} y={2} width={16} height={16} rx={2} fill="none" stroke="#1a1a2e" strokeWidth={2} />
          <rect x={30} y={2} width={16} height={16} rx={2} fill="none" stroke="#1a1a2e" strokeWidth={2} />
          <rect x={2} y={30} width={16} height={16} rx={2} fill="none" stroke="#1a1a2e" strokeWidth={2} />
        </svg>
      </div>
      <div>
        <div style={{ fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--accent)", fontWeight: 600 }}>{traceability.qr_code}</div>
        <div style={{ fontSize: 11, color: "var(--text-dim)", marginTop: 2 }}>{traceability.events} trace events recorded</div>
        <div style={{ fontSize: 10, color: "var(--text-dim)", marginTop: 1 }}>Full chain-of-custody audit trail</div>
      </div>
    </div>
  );
}

// ── Main Dashboard ──

export default function NutriTrackDashboard() {
  const [selectedIdx, setSelectedIdx] = useState(1);
  const [activeTab, setActiveTab] = useState("overview");
  const [authMode, setAuthMode] = useState("login");
  const [authEmail, setAuthEmail] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [authRole, setAuthRole] = useState("client");
  const [authLoading, setAuthLoading] = useState(false);
  const [authError, setAuthError] = useState("");
  const [authNotice, setAuthNotice] = useState("");
  const [authToken, setAuthToken] = useState(() => {
    if (typeof window === "undefined") return "";
    return window.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY) || "";
  });
  const [authUser, setAuthUser] = useState(null);
  const [authBooting, setAuthBooting] = useState(true);
  const [assistantQuery, setAssistantQuery] = useState("");
  const [assistantResponse, setAssistantResponse] = useState(null);
  const [assistantSuggestions, setAssistantSuggestions] = useState([]);
  const [assistantSuggestionsLoading, setAssistantSuggestionsLoading] = useState(false);
  const [assistantSuggestionsError, setAssistantSuggestionsError] = useState("");
  const [liveRecommendation, setLiveRecommendation] = useState(null);
  const [liveRecommendationLoading, setLiveRecommendationLoading] = useState(false);
  const [liveRecommendationError, setLiveRecommendationError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [dashboardData, setDashboardData] = useState(null);
  const [dataStatus, setDataStatus] = useState("loading");
  const [dataError, setDataError] = useState("");
  const [liveReasoningForm, setLiveReasoningForm] = useState({});
  const [liveReasoningResult, setLiveReasoningResult] = useState(null);
  const [liveReasoningError, setLiveReasoningError] = useState("");
  const [liveReasoningLoading, setLiveReasoningLoading] = useState(false);
  const [shipmentRequests, setShipmentRequests] = useState([]);
  const [shipmentRequestsLoading, setShipmentRequestsLoading] = useState(false);
  const [shipmentRequestsError, setShipmentRequestsError] = useState("");
  const [submitShipmentLoading, setSubmitShipmentLoading] = useState(false);
  const [confirmShipmentLoadingId, setConfirmShipmentLoadingId] = useState("");
  const [stageUpdateLoadingId, setStageUpdateLoadingId] = useState("");
  const [deleteShipmentLoadingId, setDeleteShipmentLoadingId] = useState("");
  const [shipmentForm, setShipmentForm] = useState({
    quantity: "",
    destination: "",
    origin: "Casablanca, Morocco",
    cargo_type: "general",
    notes: "",
  });

  const persistAuthToken = (token) => {
    if (typeof window === "undefined") return;
    if (token) {
      window.localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, token);
    } else {
      window.localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
    }
  };

  const parseErrorDetail = async (response) => {
    try {
      const payload = await response.json();
      if (payload && typeof payload.detail === "string") return payload.detail;
      if (payload && typeof payload.error === "string") return payload.error;
    } catch (_error) {
      // Ignore non-JSON errors and return fallback message.
    }
    return `Request failed (${response.status})`;
  };

  const apiFetch = async (path, options = {}, tokenOverride = undefined) => {
    const tokenToUse = tokenOverride !== undefined ? tokenOverride : authToken;
    const incomingHeaders = options.headers || {};
    const headers = {
      ...incomingHeaders,
    };

    if (tokenToUse) {
      headers.Authorization = `Bearer ${tokenToUse}`;
    }

    return fetch(path, {
      ...options,
      headers,
    });
  };

  const clearAuthSession = (message = "") => {
    persistAuthToken("");
    setAuthToken("");
    setAuthUser(null);
    setDashboardData(null);
    setDataStatus("loading");
    setDataError("");
    if (message) {
      setAuthError(message);
    }
  };

  const handleLogout = () => {
    clearAuthSession("");
  };

  const handleAuthSubmit = async () => {
    if (!authEmail.trim() || !authPassword.trim()) {
      setAuthError("Email and password are required.");
      return;
    }

    setAuthLoading(true);
    setAuthError("");
    setAuthNotice("");

    try {
      const endpoint = authMode === "signup" ? "/api/auth/signup" : "/api/auth/login";
      const response = await fetch(endpoint, {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          email: authEmail.trim(),
          password: authPassword,
          role: authRole,
        }),
      });

      if (!response.ok) {
        throw new Error(await parseErrorDetail(response));
      }

      const payload = await response.json();
      const token = String(payload.access_token || "");
      if (!token) {
        if (authMode === "signup") {
          setAuthMode("login");
          setAuthPassword("");
          setAuthNotice(
            "Account created. Check your email for confirmation, then log in."
          );
          return;
        }
        throw new Error("Login succeeded but no access token was returned.");
      }

      persistAuthToken(token);
      setAuthToken(token);

      const meResponse = await apiFetch(
        "/api/auth/me",
        {
          method: "GET",
          headers: {
            Accept: "application/json",
          },
        },
        token
      );
      if (!meResponse.ok) {
        throw new Error(await parseErrorDetail(meResponse));
      }

      const mePayload = await meResponse.json();
      setAuthUser({
        id: String(mePayload.id || ""),
        email: String(mePayload.email || authEmail.trim()),
        role: String(mePayload.role || "client"),
      });
      if (authMode === "login" && authRole && String(mePayload.role || "client") !== authRole) {
        setAuthNotice(`Connected role is ${String(mePayload.role || "client")}, not ${authRole}.`);
      }
      setAuthPassword("");
      if (authMode !== "login") {
        setAuthNotice("");
      }
    } catch (error) {
      clearAuthSession("");
      setAuthError(error instanceof Error ? error.message : "Authentication failed");
      setAuthNotice("");
    } finally {
      setAuthLoading(false);
    }
  };

  useEffect(() => {
    let active = true;

    async function hydrateAuthState() {
      if (!authToken) {
        if (active) {
          setAuthBooting(false);
        }
        return;
      }

      try {
        const response = await apiFetch("/api/auth/me", {
          method: "GET",
          headers: {
            Accept: "application/json",
          },
        });

        if (!response.ok) {
          throw new Error(await parseErrorDetail(response));
        }

        const me = await response.json();
        if (!active) return;

        setAuthUser({
          id: String(me.id || ""),
          email: String(me.email || ""),
          role: String(me.role || "client"),
        });
      } catch (_error) {
        if (!active) return;
        clearAuthSession("Session expired. Please log in again.");
      } finally {
        if (active) {
          setAuthBooting(false);
        }
      }
    }

    hydrateAuthState();

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let isMounted = true;

    async function loadDashboardData() {
      if (!authUser || String(authUser.role || "client").toLowerCase() !== "admin") {
        return;
      }

      setDataStatus("loading");
      try {
        const response = await apiFetch(`/api/dashboard`, {
          headers: {
            Accept: "application/json",
          },
        });

        if (!response.ok) {
          throw new Error(await parseErrorDetail(response));
        }

        const payload = await response.json();
        if (!isMounted) return;

        setDashboardData(payload);
        setDataStatus("ready");
        setDataError("");
      } catch (error) {
        if (!isMounted) return;

        setDataStatus("fallback");
        setDataError(error instanceof Error ? error.message : "Failed to load dashboard data");
      }
    }

    loadDashboardData();

    return () => {
      isMounted = false;
    };
  }, [authUser]);

  useEffect(() => {
    if (!authUser) return;

    loadShipmentRequests();
    const timer = window.setInterval(() => {
      loadShipmentRequests();
    }, 30000);

    return () => {
      window.clearInterval(timer);
    };
  }, [authUser]);

  const data = dashboardData;
  const scenarios = Array.isArray(data?.scenarios) ? data.scenarios : [];
  const selected = scenarios[Math.min(selectedIdx, scenarios.length - 1)] || null;
  const summary = data?.summary || EMPTY_DASHBOARD_DATA.summary;
  const userRole = String(authUser?.role || "client").toLowerCase();
  const isAdmin = userRole === "admin";
  const isClient = !isAdmin;
  const inDeliveryRequests = shipmentRequests.filter(
    (requestItem) => normalizeLifecycleStage(requestItem) === "delivery"
  );
  const activeShipmentCount = scenarios.length + inDeliveryRequests.length;

  const loadShipmentRequests = async () => {
    if (!authUser) return;

    setShipmentRequestsLoading(true);
    setShipmentRequestsError("");
    try {
      const response = await apiFetch("/api/shipment-requests", {
        method: "GET",
        headers: {
          Accept: "application/json",
        },
      });

      if (!response.ok) {
        throw new Error(await parseErrorDetail(response));
      }

      const payload = await response.json();
      setShipmentRequests(Array.isArray(payload.items) ? payload.items : []);
    } catch (error) {
      setShipmentRequests([]);
      setShipmentRequestsError(error instanceof Error ? error.message : "Unable to load shipment requests");
    } finally {
      setShipmentRequestsLoading(false);
    }
  };

  const handleShipmentFormField = (field, value) => {
    setShipmentForm((previous) => ({
      ...previous,
      [field]: value,
    }));
  };

  const handleCreateShipmentRequest = async () => {
    if (!shipmentForm.quantity || Number(shipmentForm.quantity) <= 0) {
      setShipmentRequestsError("Please enter a valid quantity.");
      return;
    }
    if (!shipmentForm.destination.trim()) {
      setShipmentRequestsError("Destination is required.");
      return;
    }

    setSubmitShipmentLoading(true);
    setShipmentRequestsError("");
    try {
      const response = await apiFetch("/api/shipment-requests", {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          quantity: Number(shipmentForm.quantity),
          destination: shipmentForm.destination,
          origin: shipmentForm.origin || "Casablanca, Morocco",
          cargo_type: shipmentForm.cargo_type || "general",
          notes: shipmentForm.notes || "",
        }),
      });

      if (!response.ok) {
        throw new Error(await parseErrorDetail(response));
      }

      setShipmentForm({
        quantity: "",
        destination: "",
        origin: shipmentForm.origin || "Casablanca, Morocco",
        cargo_type: shipmentForm.cargo_type || "general",
        notes: "",
      });
      await loadShipmentRequests();
    } catch (error) {
      setShipmentRequestsError(error instanceof Error ? error.message : "Unable to create shipment request");
    } finally {
      setSubmitShipmentLoading(false);
    }
  };

  const handleConfirmShipmentRequest = async (requestId) => {
    setConfirmShipmentLoadingId(requestId);
    setShipmentRequestsError("");
    try {
      const response = await apiFetch(`/api/shipment-requests/${requestId}/confirm`, {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({}),
      });

      if (!response.ok) {
        throw new Error(await parseErrorDetail(response));
      }

      await loadShipmentRequests();
    } catch (error) {
      setShipmentRequestsError(error instanceof Error ? error.message : "Unable to confirm shipment request");
    } finally {
      setConfirmShipmentLoadingId("");
    }
  };

  const handleUpdateLifecycleStage = async (requestId, stage) => {
    setStageUpdateLoadingId(`${requestId}:${stage}`);
    setShipmentRequestsError("");
    try {
      const response = await apiFetch(`/api/shipment-requests/${requestId}/stage`, {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ stage }),
      });

      if (!response.ok) {
        throw new Error(await parseErrorDetail(response));
      }

      await loadShipmentRequests();
    } catch (error) {
      setShipmentRequestsError(error instanceof Error ? error.message : "Unable to update shipment lifecycle stage");
    } finally {
      setStageUpdateLoadingId("");
    }
  };

  const handleDeleteShipmentRequest = async (requestId) => {
    setDeleteShipmentLoadingId(requestId);
    setShipmentRequestsError("");
    try {
      const response = await apiFetch(`/api/shipment-requests/${requestId}`, {
        method: "DELETE",
        headers: {
          Accept: "application/json",
        },
      });

      if (!response.ok) {
        throw new Error(await parseErrorDetail(response));
      }

      await loadShipmentRequests();
    } catch (error) {
      setShipmentRequestsError(error instanceof Error ? error.message : "Unable to delete shipment request");
    } finally {
      setDeleteShipmentLoadingId("");
    }
  };

  useEffect(() => {
    if (!selected) return;

    setLiveReasoningForm({
      product_id: selected.product.id,
      product_type: selected.product.type,
      name: selected.product.name,
      batch_id: selected.product.batch_id || selected.product.id,
      origin: selected.product.origin,
      destination: selected.product.destination,
      optimal_temp_min: selected.product.optimal_temp_min ?? 0,
      optimal_temp_max: selected.product.optimal_temp_max ?? 8,
      optimal_humidity_min: selected.product.optimal_humidity_min ?? 40,
      optimal_humidity_max: selected.product.optimal_humidity_max ?? 80,
      max_co2_ppm: selected.product.max_co2_ppm ?? 1000,
      shelf_life_hours: selected.product.shelf_life_hours ?? 72,
      value_usd: selected.product.value_usd,
      weight_kg: selected.product.weight_kg ?? 0,
      temperature_celsius: selected.telemetry.temperature,
      humidity_percent: selected.telemetry.humidity,
      co2_ppm: selected.telemetry.co2,
      vibration_g: selected.telemetry.vibration,
      latitude: selected.location.lat,
      longitude: selected.location.lon,
      city: selected.location.city,
      country: selected.location.country || "Morocco",
      hours_elapsed: 4,
      user_query: "",
      analysis_label: "live_dashboard_input",
    });
    setLiveReasoningResult(null);
    setLiveReasoningError("");
  }, [selected]);

  const hasDashboardData = Boolean(selected);

  const buildReasoningPayload = (queryOverride) => ({
    analysis_label: liveReasoningForm.analysis_label,
    user_query: queryOverride ?? liveReasoningForm.user_query,
    product: {
      product_id: liveReasoningForm.product_id,
      product_type: liveReasoningForm.product_type,
      name: liveReasoningForm.name,
      batch_id: liveReasoningForm.batch_id,
      origin: liveReasoningForm.origin,
      destination: liveReasoningForm.destination,
      optimal_temp_min: Number(liveReasoningForm.optimal_temp_min),
      optimal_temp_max: Number(liveReasoningForm.optimal_temp_max),
      optimal_humidity_min: Number(liveReasoningForm.optimal_humidity_min),
      optimal_humidity_max: Number(liveReasoningForm.optimal_humidity_max),
      max_co2_ppm: Number(liveReasoningForm.max_co2_ppm),
      shelf_life_hours: Number(liveReasoningForm.shelf_life_hours),
      value_usd: Number(liveReasoningForm.value_usd),
      weight_kg: Number(liveReasoningForm.weight_kg),
    },
    telemetry: {
      temperature_celsius: Number(liveReasoningForm.temperature_celsius),
      humidity_percent: Number(liveReasoningForm.humidity_percent),
      co2_ppm: Number(liveReasoningForm.co2_ppm),
      vibration_g: Number(liveReasoningForm.vibration_g),
    },
    gps: {
      latitude: Number(liveReasoningForm.latitude),
      longitude: Number(liveReasoningForm.longitude),
      city: liveReasoningForm.city,
      country: liveReasoningForm.country,
    },
    hours_elapsed: Number(liveReasoningForm.hours_elapsed),
  });

  const buildAssistantPayloadFromSelected = (scenario, queryOverride) => ({
    analysis_label: "dashboard_selected_scenario",
    user_query: queryOverride ?? "",
    product: {
      product_id: scenario?.product?.id || "",
      product_type: scenario?.product?.type || "dairy",
      name: scenario?.product?.name || "Unknown Product",
      batch_id: scenario?.product?.batch_id || scenario?.product?.id || "",
      origin: scenario?.product?.origin || "",
      destination: scenario?.product?.destination || "",
      optimal_temp_min: Number(scenario?.product?.optimal_temp_min ?? 0),
      optimal_temp_max: Number(scenario?.product?.optimal_temp_max ?? 8),
      optimal_humidity_min: Number(scenario?.product?.optimal_humidity_min ?? 40),
      optimal_humidity_max: Number(scenario?.product?.optimal_humidity_max ?? 80),
      max_co2_ppm: Number(scenario?.product?.max_co2_ppm ?? 1000),
      shelf_life_hours: Number(scenario?.product?.shelf_life_hours ?? 72),
      value_usd: Number(scenario?.product?.value_usd ?? 0),
      weight_kg: Number(scenario?.product?.weight_kg ?? 0),
    },
    telemetry: {
      temperature_celsius: Number(scenario?.telemetry?.temperature ?? 0),
      humidity_percent: Number(scenario?.telemetry?.humidity ?? 0),
      co2_ppm: Number(scenario?.telemetry?.co2 ?? 0),
      vibration_g: Number(scenario?.telemetry?.vibration ?? 0),
    },
    gps: {
      latitude: Number(scenario?.location?.lat ?? 0),
      longitude: Number(scenario?.location?.lon ?? 0),
      city: scenario?.location?.city || "",
      country: scenario?.location?.country || "Morocco",
    },
    hours_elapsed: 4,
  });

  useEffect(() => {
    let cancelled = false;

    async function loadAssistantSuggestions() {
      if (!selected) {
        setAssistantSuggestions([]);
        setAssistantSuggestionsError("");
        return;
      }

      setAssistantSuggestionsLoading(true);
      setAssistantSuggestionsError("");
      try {
        const response = await apiFetch(`/api/assistant`, {
          method: "POST",
          headers: {
            Accept: "application/json",
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            ...buildAssistantPayloadFromSelected(
              selected,
              `Generate exactly 4 short user questions for a logistics operator about this shipment. ` +
              `Return the questions in next_actions only. No explanations.`
            ),
            assistant_query:
              "Generate operational user questions based on current shipment context.",
            include_dashboard_context: true,
            max_fleet_items: 3,
          }),
        });

        if (!response.ok) {
          throw new Error(await parseErrorDetail(response));
        }

        const payload = await response.json();
        const candidateSuggestions = Array.isArray(payload.next_actions)
          ? payload.next_actions
              .map((item) => String(item || "").trim())
              .filter(Boolean)
              .slice(0, 4)
          : [];

        if (!cancelled) {
          if (candidateSuggestions.length > 0) {
            setAssistantSuggestions(candidateSuggestions);
          } else {
            setAssistantSuggestions([]);
            setAssistantSuggestionsError("LLM returned no suggestions for this shipment.");
          }
        }
      } catch (_error) {
        if (!cancelled) {
          setAssistantSuggestions([]);
          setAssistantSuggestionsError("Unable to fetch LLM suggestions right now.");
        }
      } finally {
        if (!cancelled) {
          setAssistantSuggestionsLoading(false);
        }
      }
    }

    loadAssistantSuggestions();

    return () => {
      cancelled = true;
    };
  }, [selected]);

  useEffect(() => {
    let cancelled = false;

    async function loadLiveRecommendation() {
      if (!selected) {
        setLiveRecommendation(null);
        setLiveRecommendationError("");
        return;
      }

      setLiveRecommendationLoading(true);
      setLiveRecommendationError("");
      try {
        const response = await apiFetch(`/api/assistant`, {
          method: "POST",
          headers: {
            Accept: "application/json",
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            ...buildAssistantPayloadFromSelected(
              selected,
              "Generate an operational recommendation for this shipment including: summary, key risks, and immediate actions."
            ),
            assistant_query:
              "Provide the best operational recommendation now for this shipment and list immediate actions.",
            include_dashboard_context: true,
            max_fleet_items: 5,
          }),
        });

        if (!response.ok) {
          throw new Error(await parseErrorDetail(response));
        }

        const payload = await response.json();
        const keyPoints = Array.isArray(payload.key_points)
          ? payload.key_points.map((item) => String(item || "").trim()).filter(Boolean)
          : [];
        const nextActions = Array.isArray(payload.next_actions)
          ? payload.next_actions.map((item) => String(item || "").trim()).filter(Boolean)
          : [];

        if (!cancelled) {
          setLiveRecommendation({
            summary: String(payload.answer || "").trim(),
            explanation: keyPoints,
            actions: nextActions,
          });
        }
      } catch (_error) {
        if (!cancelled) {
          setLiveRecommendation(null);
          setLiveRecommendationError("Unable to generate live LLM recommendation for this shipment.");
        }
      } finally {
        if (!cancelled) {
          setLiveRecommendationLoading(false);
        }
      }
    }

    loadLiveRecommendation();

    return () => {
      cancelled = true;
    };
  }, [selected]);

  const handleAssistantQuery = async () => {
    if (!assistantQuery.trim() || !selected) return;
    setIsLoading(true);

    try {
      const response = await apiFetch(`/api/assistant`, {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          ...buildAssistantPayloadFromSelected(selected, assistantQuery),
          assistant_query: assistantQuery,
          include_dashboard_context: true,
          max_fleet_items: 5,
        }),
      });

      if (!response.ok) {
        throw new Error(await parseErrorDetail(response));
      }

      const payload = await response.json();
      const keyPoints = Array.isArray(payload.key_points) ? payload.key_points : [];
      const nextActions = Array.isArray(payload.next_actions) ? payload.next_actions : [];

      setAssistantResponse(
        `${payload.answer || "No assistant answer returned."}\n\n` +
        `${keyPoints.length ? "Key points:\n- " + keyPoints.join("\n- ") + "\n\n" : ""}` +
        `${nextActions.length ? "Next actions:\n- " + nextActions.join("\n- ") : ""}`
      );
    } catch (error) {
      setAssistantResponse(error instanceof Error ? error.message : "Assistant request failed");
    } finally {
      setIsLoading(false);
      setAssistantQuery("");
    }
  };

  const handleLiveReasoning = async () => {
    if (!liveReasoningForm.name) return;

    setLiveReasoningLoading(true);
    setLiveReasoningError("");

    try {
      const response = await apiFetch(`/api/reason`, {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify(buildReasoningPayload()),
      });

      if (!response.ok) {
        throw new Error(await parseErrorDetail(response));
      }

      const payload = await response.json();
      setLiveReasoningResult(payload);
    } catch (error) {
      setLiveReasoningError(error instanceof Error ? error.message : "Failed to run live reasoning");
    } finally {
      setLiveReasoningLoading(false);
    }
  };

  const updateLiveReasoningField = (field, value) => {
    setLiveReasoningForm((previous) => ({
      ...previous,
      [field]: value,
    }));
  };

  const tabs = [
    ...(isAdmin
      ? [
          { id: "overview", label: "Overview", icon: "📊" },
          { id: "workflow", label: "Workflow", icon: "🔄" },
          { id: "economics", label: "Economics", icon: "💰" },
          { id: "assistant", label: "Assistant", icon: "🤖" },
          { id: "reasoning", label: "Live Reasoning", icon: "🧠" },
          { id: "shipments", label: "Shipments", icon: "🚚" },
        ]
      : [{ id: "shipments", label: "Client Portal", icon: "📦" }]),
  ];

  const showDashboardSidebar = isAdmin && activeTab !== "shipments" && scenarios.length > 0;

  useEffect(() => {
    if (!tabs.some((tab) => tab.id === activeTab)) {
      setActiveTab(tabs[0]?.id || "shipments");
    }
  }, [tabs, activeTab]);

  return (
    <div style={{
      "--bg": "#0a0a12",
      "--card-bg": "#12121e",
      "--card-bg-active": "#181830",
      "--surface": "#0e0e1a",
      "--border": "#1e1e35",
      "--text": "#e4e4ef",
      "--text-dim": "#6b6b8a",
      "--accent": "#6366f1",
      "--accent-2": "#06b6d4",
      "--font-display": "'DM Sans', system-ui, sans-serif",
      "--font-mono": "'JetBrains Mono', 'SF Mono', monospace",
      background: "var(--bg)",
      color: "var(--text)",
      minHeight: "100vh",
      fontFamily: "var(--font-display)",
      padding: 0,
      margin: 0,
    }}>
      <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet" />

      {authBooting ? (
        <div style={{
          minHeight: "100vh",
          display: "grid",
          placeItems: "center",
          padding: 24,
        }}>
          <div style={{
            width: "100%",
            maxWidth: 420,
            background: "var(--card-bg)",
            borderRadius: 16,
            border: "1px solid var(--border)",
            padding: 24,
            textAlign: "center",
          }}>
            <div style={{ fontSize: 14, color: "var(--text-dim)", fontFamily: "var(--font-mono)" }}>Checking authentication...</div>
          </div>
        </div>
      ) : !authUser ? (
        <div style={{
          minHeight: "100vh",
          display: "grid",
          placeItems: "center",
          padding: 24,
          background: "radial-gradient(circle at 20% 20%, #1a1a35 0%, #0a0a12 55%)",
        }}>
          <div style={{
            width: "100%",
            maxWidth: 440,
            background: "var(--card-bg)",
            borderRadius: 18,
            border: "1px solid var(--border)",
            padding: 24,
            boxShadow: "0 20px 40px rgba(0,0,0,0.35)",
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
              <div>
                <div style={{ fontSize: 22, fontWeight: 800 }}>Secure Access</div>
                <div style={{ fontSize: 12, color: "var(--text-dim)", fontFamily: "var(--font-mono)", marginTop: 4 }}>Supabase JWT authentication</div>
              </div>
              <div style={{ fontSize: 20 }}>🔐</div>
            </div>

            <div style={{ display: "flex", gap: 6, marginBottom: 14, background: "var(--surface)", padding: 4, borderRadius: 10 }}>
              <button
                onClick={() => setAuthMode("login")}
                style={{
                  flex: 1,
                  padding: "8px 10px",
                  borderRadius: 8,
                  border: "none",
                  background: authMode === "login" ? "var(--accent)" : "transparent",
                  color: authMode === "login" ? "#fff" : "var(--text-dim)",
                  cursor: "pointer",
                  fontWeight: 700,
                }}
              >
                Login
              </button>
              <button
                onClick={() => setAuthMode("signup")}
                style={{
                  flex: 1,
                  padding: "8px 10px",
                  borderRadius: 8,
                  border: "none",
                  background: authMode === "signup" ? "var(--accent)" : "transparent",
                  color: authMode === "signup" ? "#fff" : "var(--text-dim)",
                  cursor: "pointer",
                  fontWeight: 700,
                }}
              >
                Signup
              </button>
            </div>

            <div style={{ display: "grid", gap: 10 }}>
              <label style={{ display: "grid", gap: 6 }}>
                <span style={{ fontSize: 11, color: "var(--text-dim)", fontFamily: "var(--font-mono)" }}>Email</span>
                <input
                  type="email"
                  value={authEmail}
                  onChange={(event) => setAuthEmail(event.target.value)}
                  placeholder="you@example.com"
                  style={{
                    padding: "10px 12px",
                    borderRadius: 10,
                    border: "1px solid var(--border)",
                    background: "var(--surface)",
                    color: "var(--text)",
                    outline: "none",
                  }}
                />
              </label>
              <label style={{ display: "grid", gap: 6 }}>
                <span style={{ fontSize: 11, color: "var(--text-dim)", fontFamily: "var(--font-mono)" }}>Password</span>
                <input
                  type="password"
                  value={authPassword}
                  onChange={(event) => setAuthPassword(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") {
                      handleAuthSubmit();
                    }
                  }}
                  placeholder="Your secure password"
                  style={{
                    padding: "10px 12px",
                    borderRadius: 10,
                    border: "1px solid var(--border)",
                    background: "var(--surface)",
                    color: "var(--text)",
                    outline: "none",
                  }}
                />
              </label>
              <label style={{ display: "grid", gap: 6 }}>
                <span style={{ fontSize: 11, color: "var(--text-dim)", fontFamily: "var(--font-mono)" }}>Role</span>
                <select
                  value={authRole}
                  onChange={(event) => setAuthRole(event.target.value)}
                  style={{
                    padding: "10px 12px",
                    borderRadius: 10,
                    border: "1px solid var(--border)",
                    background: "var(--surface)",
                    color: "var(--text)",
                    outline: "none",
                  }}
                >
                  <option value="client">Client</option>
                  <option value="admin">Admin</option>
                </select>
              </label>
            </div>

            {authError && (
              <div style={{ marginTop: 12, borderRadius: 10, padding: "10px 12px", background: "#ef444415", color: "#ef4444", fontSize: 12, fontFamily: "var(--font-mono)" }}>
                {authError}
              </div>
            )}

            {authNotice && (
              <div style={{ marginTop: 12, borderRadius: 10, padding: "10px 12px", background: "#10b98115", color: "#10b981", fontSize: 12, fontFamily: "var(--font-mono)" }}>
                {authNotice}
              </div>
            )}

            <button
              onClick={handleAuthSubmit}
              disabled={authLoading}
              style={{
                width: "100%",
                marginTop: 14,
                padding: "11px 14px",
                borderRadius: 10,
                border: "none",
                background: "linear-gradient(135deg, #6366f1, #06b6d4)",
                color: "#fff",
                fontWeight: 700,
                cursor: "pointer",
                opacity: authLoading ? 0.65 : 1,
              }}
            >
              {authLoading ? "Authenticating..." : authMode === "login" ? "Login" : "Create account"}
            </button>
          </div>
        </div>
      ) : (
        <>

      {/* Header */}
      <div style={{
        background: "linear-gradient(135deg, #12121e 0%, #1a1a35 100%)",
        borderBottom: "1px solid var(--border)",
        padding: "18px 24px",
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        flexWrap: "wrap",
        gap: 12,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{
            width: 40, height: 40, borderRadius: 12,
            background: "linear-gradient(135deg, #6366f1, #06b6d4)",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 20,
          }}>🧬</div>
          <div>
            <div style={{ fontSize: 18, fontWeight: 800, letterSpacing: "-0.02em" }}>NutriTrack</div>
            <div style={{ fontSize: 11, color: "var(--text-dim)", fontFamily: "var(--font-mono)" }}>Agentic Flow · Multi-Agent Intelligence</div>
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <div style={{ fontSize: 11, color: "var(--text-dim)", fontFamily: "var(--font-mono)" }}>
            {authUser.email} · {authUser.role}
          </div>
          <div style={{ width: 8, height: 8, borderRadius: "50%", background: "#10b981", animation: "pulse 2s infinite" }} />
          <span style={{ fontSize: 12, color: "#10b981", fontFamily: "var(--font-mono)" }}>
            {dataStatus === "ready" ? "API SYNCED" : dataStatus === "fallback" ? "LOCAL FALLBACK" : "SYNCING"} · {isAdmin ? `${activeShipmentCount} shipments tracked` : `${shipmentRequests.length} client requests`}
          </span>
          <button
            onClick={handleLogout}
            style={{
              marginLeft: 8,
              padding: "7px 12px",
              borderRadius: 9,
              border: "1px solid var(--border)",
              background: "var(--surface)",
              color: "var(--text-dim)",
              cursor: "pointer",
              fontSize: 11,
              fontFamily: "var(--font-mono)",
            }}
          >
            Logout
          </button>
        </div>
      </div>

      {dataError && (
        <div style={{ margin: "10px 24px 0", padding: "10px 14px", borderRadius: 12, background: "#f59e0b15", color: "#f59e0b", fontSize: 12, fontFamily: "var(--font-mono)" }}>
          Backend sync failed. {dataError}
        </div>
      )}

      {/* KPI Strip */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
        gap: 12,
        padding: "16px 24px",
      }}>
        <KPICard label="Cargo Value" value={`$${(summary.total_cargo_value / 1000).toFixed(0)}k`} color="#6366f1" icon="" sub="5 active shipments" />
        <KPICard label="Savings" value={`$${(summary.total_savings / 1000).toFixed(1)}k`} color="#10b981" icon="" sub="via intelligent routing" />
        <KPICard label="Waste Reduction" value={`${summary.avg_waste_reduction}%`} color="#06b6d4" icon="" sub="vs. baseline operations" />
        <KPICard label="Anomalies" value={summary.total_anomalies} color="#f59e0b" icon="" sub={`${summary.guardrail_violations} guardrail violations`} />
        <KPICard label="Human Reviews" value={summary.human_interventions} color="#f97316" icon="" sub="critical decisions" />
      </div>

      {/* Main Layout */}
      <div style={{ display: "grid", gridTemplateColumns: showDashboardSidebar ? "320px 1fr" : "1fr", gap: 0, minHeight: "calc(100vh - 250px)" }}>
        {/* Sidebar — Shipment List */}
        {showDashboardSidebar && (
          <div style={{
            borderRight: "1px solid var(--border)",
            padding: "12px 16px",
            overflowY: "auto",
            maxHeight: "calc(100vh - 250px)",
          }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text-dim)", marginBottom: 12, fontFamily: "var(--font-mono)", textTransform: "uppercase", letterSpacing: "0.06em" }}>Active Shipments</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {scenarios.length > 0 &&
                scenarios.map((s, i) => (
                  <ScenarioCard key={i} scenario={s} isSelected={i === selectedIdx} onClick={() => setSelectedIdx(i)} />
                ))}

              {inDeliveryRequests.map((requestItem) => (
                <ActiveShipmentLiveCard
                  key={`live-${requestItem.id}`}
                  requestItem={requestItem}
                  onOpen={() => setActiveTab("shipments")}
                />
              ))}

              {scenarios.length === 0 && inDeliveryRequests.length === 0 && (
                <div style={{ color: "var(--text-dim)", fontSize: 13, lineHeight: 1.7, padding: 12 }}>
                  No shipment data loaded yet. The dashboard depends on the backend API.
                </div>
              )}
            </div>
          </div>
        )}

        {/* Main Content */}
        <div style={{ padding: "16px 24px", overflowY: "auto", maxHeight: "calc(100vh - 250px)" }}>
          {/* Tabs */}
          <div style={{ display: "flex", gap: 4, marginBottom: 20, background: "var(--surface)", borderRadius: 12, padding: 4, width: "fit-content" }}>
            {tabs.map(t => (
              <button key={t.id} onClick={() => setActiveTab(t.id)} style={{
                padding: "8px 16px",
                borderRadius: 8,
                border: "none",
                background: activeTab === t.id ? "var(--accent)" : "transparent",
                color: activeTab === t.id ? "white" : "var(--text-dim)",
                cursor: "pointer",
                fontSize: 13,
                fontWeight: 600,
                fontFamily: "var(--font-display)",
                transition: "all 0.2s",
              }}>{t.icon} {t.label}</button>
            ))}
          </div>

          {/* Tab Content */}
          {activeTab !== "shipments" && !hasDashboardData ? (
            <div style={{ background: "var(--card-bg)", borderRadius: 16, padding: 24 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-dim)", fontFamily: "var(--font-mono)", marginBottom: 10 }}>WAITING FOR BACKEND DATA</div>
              <div style={{ color: "var(--text-dim)", lineHeight: 1.7, fontSize: 13 }}>
                The deployed UI no longer contains embedded shipment fixtures. It now waits for live data from the FastAPI backend.
              </div>
            </div>
          ) : activeTab === "overview" && selected ? (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
              {/* Health Score */}
              <div style={{ background: "var(--card-bg)", borderRadius: 16, padding: 20 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-dim)", fontFamily: "var(--font-mono)", marginBottom: 12 }}>HEALTH SCORE</div>
                <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
                  <HealthGauge score={selected.health.overall} />
                  <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 10 }}>
                    <MiniBar label="Nutrition" value={selected.health.nutrition} color="#10b981" />
                    <MiniBar label="Freshness" value={selected.health.freshness} color="#06b6d4" />
                    <MiniBar label="Safety" value={selected.health.safety} color="#ef4444" />
                    <div style={{ fontSize: 11, color: "var(--text-dim)", fontFamily: "var(--font-mono)", marginTop: 4 }}>
                      ⏱ {selected.health.remaining_hours}h remaining · {selected.health.degradation_rate}%/hr degradation
                    </div>
                  </div>
                </div>
              </div>

              {/* Telemetry */}
              <div style={{ background: "var(--card-bg)", borderRadius: 16, padding: 20 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-dim)", fontFamily: "var(--font-mono)", marginBottom: 12 }}>IoT TELEMETRY</div>
                <TelemetryPanel telemetry={selected.telemetry} product={selected.product} />
              </div>

              {/* Live Map */}
              <div style={{ gridColumn: "1 / -1", background: "var(--card-bg)", borderRadius: 16, padding: 20 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                  <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text-dim)", fontFamily: "var(--font-mono)" }}>LIVE SHIPMENT MAP</span>
                  <span style={{ fontSize: 11, color: "var(--text-dim)", fontFamily: "var(--font-mono)" }}>
                    OpenStreetMap tracking
                  </span>
                </div>
                <DashboardLocationMap selected={selected} />
              </div>

              {/* Anomalies */}
              <div style={{ background: "var(--card-bg)", borderRadius: 16, padding: 20 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                  <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text-dim)", fontFamily: "var(--font-mono)" }}>ANOMALIES</span>
                  <Badge text={selected.risk_level} color={RISK_COLORS[selected.risk_level]} />
                </div>
                <AnomalyList anomalies={selected.anomalies} />
                {(selected.anomaly_analysis?.root_cause || selected.anomaly_analysis?.predicted_impact) && (
                  <div style={{ marginTop: 12, display: "grid", gap: 8 }}>
                    {selected.anomaly_analysis?.root_cause && (
                      <div style={{ background: "var(--surface)", borderRadius: 10, padding: 10 }}>
                        <div style={{ fontSize: 10, color: "var(--text-dim)", fontFamily: "var(--font-mono)", marginBottom: 4 }}>ROOT CAUSE (LLM)</div>
                        <div style={{ fontSize: 12, color: "var(--text)", lineHeight: 1.5 }}>{selected.anomaly_analysis.root_cause}</div>
                      </div>
                    )}
                    {selected.anomaly_analysis?.predicted_impact && (
                      <div style={{ background: "var(--surface)", borderRadius: 10, padding: 10 }}>
                        <div style={{ fontSize: 10, color: "var(--text-dim)", fontFamily: "var(--font-mono)", marginBottom: 4 }}>PREDICTED IMPACT (LLM)</div>
                        <div style={{ fontSize: 12, color: "var(--text)", lineHeight: 1.5 }}>{selected.anomaly_analysis.predicted_impact}</div>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Decision + Guardrail */}
              <div style={{ background: "var(--card-bg)", borderRadius: 16, padding: 20 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-dim)", fontFamily: "var(--font-mono)", marginBottom: 12 }}>DECISION & COMPLIANCE</div>
                <div style={{ background: "var(--surface)", borderRadius: 10, padding: 14, marginBottom: 12 }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: "var(--accent)" }}>🎯 {selected.decision.action.replace(/_/g, " ").toUpperCase()}</div>
                  <div style={{ fontSize: 11, color: "var(--text-dim)", marginTop: 4 }}>
                    Confidence: {(selected.decision.confidence * 100).toFixed(0)}% · Status: {selected.decision.status.replace(/_/g, " ")}
                  </div>
                  {selected.decision.requires_human && (
                    <div style={{ marginTop: 8, padding: "6px 10px", borderRadius: 6, background: selected.decision.human_approved ? "#10b98115" : "#f59e0b15", fontSize: 11, fontWeight: 600, color: selected.decision.human_approved ? "#10b981" : "#f59e0b" }}>
                      👤 {selected.decision.human_approved ? "Approved by human reviewer" : "Pending human approval"}
                    </div>
                  )}
                </div>
                <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  <div style={{
                    width: 10, height: 10, borderRadius: "50%",
                    background: selected.guardrail.compliant ? "#10b981" : "#ef4444",
                  }} />
                  <span style={{ fontSize: 12, color: "var(--text)" }}>
                    {selected.guardrail.compliant ? "All guardrails passed" : `${selected.guardrail.violations} violation(s) detected`}
                  </span>
                  <span style={{ fontSize: 11, color: "var(--text-dim)", fontFamily: "var(--font-mono)", marginLeft: "auto" }}>
                    Safety: {(selected.guardrail.safety_score * 100).toFixed(0)}%
                  </span>
                </div>
                {/* QR */}
                <div style={{ marginTop: 14 }}>
                  <QRTrace traceability={selected.traceability} product={selected.product} />
                </div>
              </div>

              {/* Recommendation */}
              <div style={{ gridColumn: "1 / -1", background: "var(--card-bg)", borderRadius: 16, padding: 20, borderLeft: `4px solid ${RISK_COLORS[selected.risk_level]}` }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-dim)", fontFamily: "var(--font-mono)", marginBottom: 8 }}>SMART RECOMMENDATION</div>
                {liveRecommendationLoading && (
                  <div style={{ fontSize: 12, color: "var(--text-dim)", fontFamily: "var(--font-mono)" }}>
                    Generating recommendation from LLM...
                  </div>
                )}
                {!liveRecommendationLoading && liveRecommendationError && (
                  <div style={{ fontSize: 12, color: "#f59e0b", fontFamily: "var(--font-mono)" }}>
                    {liveRecommendationError}
                  </div>
                )}
                {!liveRecommendationLoading && !liveRecommendationError && liveRecommendation && (
                  <>
                    <div style={{ fontSize: 15, fontWeight: 700, color: "var(--text)", marginBottom: 8 }}>{liveRecommendation.summary || "No recommendation text returned by LLM."}</div>
                    {liveRecommendation.explanation.length > 0 && (
                      <div style={{ fontSize: 13, color: "var(--text-dim)", lineHeight: 1.6, whiteSpace: "pre-wrap" }}>
                        {"- " + liveRecommendation.explanation.join("\n- ")}
                      </div>
                    )}
                  </>
                )}
                {!liveRecommendationLoading && !liveRecommendationError && liveRecommendation?.actions?.length > 0 && (
                  <div style={{ marginTop: 14 }}>
                    <div style={{ fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--text-dim)", marginBottom: 8, textTransform: "uppercase" }}>Immediate Actions</div>
                    <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                      {liveRecommendation.actions.map((actionText, i) => (
                        <div key={i} style={{
                          padding: "10px 14px", borderRadius: 10, background: "var(--surface)",
                          border: "1px solid var(--border)", flex: "1 1 200px",
                        }}>
                          <div style={{ fontSize: 12, fontWeight: 600, color: "var(--accent-2)" }}>{actionText}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          ) : null}

          {activeTab === "workflow" && selected && (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
              <div style={{ background: "var(--card-bg)", borderRadius: 16, padding: 20 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-dim)", fontFamily: "var(--font-mono)", marginBottom: 12 }}>AGENT GRAPH</div>
                <AgentWorkflowDiagram log={selected.execution_log} />
              </div>
              <div style={{ background: "var(--card-bg)", borderRadius: 16, padding: 20 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-dim)", fontFamily: "var(--font-mono)", marginBottom: 12 }}>EXECUTION LOG</div>
                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  {selected.execution_log.map((entry, i) => (
                    <div key={i} style={{
                      display: "flex", alignItems: "center", gap: 10, padding: "8px 12px",
                      borderRadius: 8, background: "var(--surface)",
                    }}>
                      <div style={{
                        width: 24, height: 24, borderRadius: 6, display: "flex", alignItems: "center",
                        justifyContent: "center", fontSize: 11, fontWeight: 700,
                        background: `${AGENT_COLORS[entry.node] || "#64748b"}25`,
                        color: AGENT_COLORS[entry.node] || "#64748b",
                        fontFamily: "var(--font-mono)",
                      }}>{entry.step}</div>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontSize: 12, fontWeight: 600, color: AGENT_COLORS[entry.node] || "var(--text)" }}>
                          {entry.node.replace(/_/g, " ")}
                        </div>
                        {entry.routing && (
                          <div style={{ fontSize: 10, color: "var(--text-dim)", fontFamily: "var(--font-mono)" }}>
                            ↳ {entry.routing}
                          </div>
                        )}
                      </div>
                      <div style={{
                        width: 8, height: 8, borderRadius: "50%",
                        background: entry.status === "completed" ? "#10b981" : "#ef4444",
                      }} />
                    </div>
                  ))}
                </div>
              </div>
              {/* Execution Flow */}
              <div style={{ gridColumn: "1 / -1", background: "var(--card-bg)", borderRadius: 16, padding: 20 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-dim)", fontFamily: "var(--font-mono)", marginBottom: 12 }}>PIPELINE FLOW</div>
                <ExecutionFlow log={selected.execution_log} />
                <div style={{ marginTop: 16, fontSize: 12, color: "var(--text-dim)", lineHeight: 1.7 }}>
                  <strong style={{ color: "var(--text)" }}>Orchestration: LangGraph</strong> — Hierarchical coordination with Supervisor pattern.
                  Conditional routing based on anomaly severity: critical path (full pipeline) vs standard path (skip logistics) vs no-action path (direct to recommendation).
                  {selected.decision.requires_human && " Human-in-the-loop triggered for high-stakes decision validation."}
                </div>
              </div>
            </div>
          )}

          {activeTab === "economics" && selected && (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
              <div style={{ background: "var(--card-bg)", borderRadius: 16, padding: 20 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-dim)", fontFamily: "var(--font-mono)", marginBottom: 12 }}>COST-BENEFIT ANALYSIS</div>
                <EconomicsChart economics={selected.economics} />
              </div>
              <div style={{ background: "var(--card-bg)", borderRadius: 16, padding: 20 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-dim)", fontFamily: "var(--font-mono)", marginBottom: 12 }}>KEY METRICS</div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                  {[
                    { label: "ROI", value: `${selected.economics.roi}%`, color: selected.economics.roi > 0 ? "#10b981" : "#ef4444" },
                    { label: "Waste Reduction", value: `${selected.economics.waste_reduction}%`, color: "#06b6d4" },
                    { label: "Cargo Value", value: `$${selected.product.value_usd.toLocaleString()}`, color: "#6366f1" },
                    { label: "Net Savings", value: `$${selected.economics.savings.toLocaleString()}`, color: "#10b981" },
                  ].map(m => (
                    <div key={m.label} style={{ background: "var(--surface)", borderRadius: 10, padding: 14, textAlign: "center" }}>
                      <div style={{ fontSize: 10, color: "var(--text-dim)", fontFamily: "var(--font-mono)", textTransform: "uppercase" }}>{m.label}</div>
                      <div style={{ fontSize: 22, fontWeight: 800, color: m.color, marginTop: 4, fontFamily: "var(--font-display)" }}>{m.value}</div>
                    </div>
                  ))}
                </div>
              </div>
              {/* Aggregate */}
              <div style={{ gridColumn: "1 / -1", background: "var(--card-bg)", borderRadius: 16, padding: 20 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-dim)", fontFamily: "var(--font-mono)", marginBottom: 16 }}>FLEET-WIDE PERFORMANCE</div>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 12 }}>
                  {scenarios.map((s, i) => {
                    const icon = PRODUCT_ICONS[s.product.type];
                    return (
                      <div key={i} onClick={() => setSelectedIdx(i)} style={{
                        background: i === selectedIdx ? "var(--card-bg-active)" : "var(--surface)",
                        borderRadius: 12, padding: 14, cursor: "pointer", textAlign: "center",
                        border: i === selectedIdx ? "1px solid var(--accent)" : "1px solid transparent",
                        transition: "all 0.2s",
                      }}>
                        <div style={{ fontSize: 24 }}>{icon}</div>
                        <div style={{ fontSize: 11, fontWeight: 600, marginTop: 4, color: "var(--text)" }}>{s.product.name.split(" ").slice(0, 2).join(" ")}</div>
                        <div style={{ fontSize: 18, fontWeight: 800, color: RISK_COLORS[s.risk_level], marginTop: 4 }}>{s.health.overall}</div>
                        <div style={{ fontSize: 10, color: "var(--text-dim)", fontFamily: "var(--font-mono)" }}>
                          ${(s.economics.savings / 1000).toFixed(1)}k saved
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}

          {activeTab === "assistant" && selected && (
            <div style={{ maxWidth: 700 }}>
              <div style={{ background: "var(--card-bg)", borderRadius: 16, padding: 24 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-dim)", fontFamily: "var(--font-mono)", marginBottom: 16 }}>🤖 SMART ASSISTANT</div>
                <div style={{ fontSize: 13, color: "var(--text-dim)", marginBottom: 16 }}>
                  Ask about the current shipment. The assistant and recommendation panel are generated live by the LLM.
                </div>

                {/* LLM-generated quick actions */}
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 16 }}>
                  {assistantSuggestionsLoading && (
                    <span style={{ fontSize: 11, color: "var(--text-dim)", fontFamily: "var(--font-mono)" }}>
                      Generating LLM suggestions...
                    </span>
                  )}
                  {!assistantSuggestionsLoading && assistantSuggestions.map((q) => (
                    <button key={q} onClick={() => { setAssistantQuery(q); }} style={{
                      padding: "6px 12px", borderRadius: 8, border: "1px solid var(--border)",
                      background: "var(--surface)", color: "var(--text-dim)", cursor: "pointer",
                      fontSize: 11, fontFamily: "var(--font-display)", transition: "all 0.2s",
                    }}>{q}</button>
                  ))}
                </div>
                {!assistantSuggestionsLoading && assistantSuggestionsError && (
                  <div style={{ marginBottom: 12, fontSize: 11, color: "var(--text-dim)", fontFamily: "var(--font-mono)" }}>
                    {assistantSuggestionsError}
                  </div>
                )}

                {/* Input */}
                <div style={{ display: "flex", gap: 8 }}>
                  <input
                    value={assistantQuery}
                    onChange={e => setAssistantQuery(e.target.value)}
                    onKeyDown={e => e.key === "Enter" && handleAssistantQuery()}
                    placeholder={`Ask about ${selected.product.name}...`}
                    style={{
                      flex: 1, padding: "10px 14px", borderRadius: 10,
                      border: "1px solid var(--border)", background: "var(--surface)",
                      color: "var(--text)", fontSize: 13, fontFamily: "var(--font-display)",
                      outline: "none",
                    }}
                  />
                  <button onClick={handleAssistantQuery} disabled={isLoading} style={{
                    padding: "10px 20px", borderRadius: 10, border: "none",
                    background: "var(--accent)", color: "white", cursor: "pointer",
                    fontSize: 13, fontWeight: 600, fontFamily: "var(--font-display)",
                    opacity: isLoading ? 0.6 : 1,
                  }}>{isLoading ? "..." : "Ask"}</button>
                </div>

                {/* Response */}
                {assistantResponse && (
                  <div style={{
                    marginTop: 16, padding: 18, borderRadius: 12,
                    background: "var(--surface)", borderLeft: "3px solid var(--accent)",
                  }}>
                    <div style={{ fontSize: 10, fontFamily: "var(--font-mono)", color: "var(--accent)", marginBottom: 8 }}>ASSISTANT RESPONSE</div>
                    <div style={{ fontSize: 13, color: "var(--text)", lineHeight: 1.7, whiteSpace: "pre-wrap" }}>
                      {assistantResponse}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {activeTab === "shipments" && (
            <div style={{ display: "grid", gridTemplateColumns: isAdmin ? "1fr" : "1fr 1fr", gap: 16 }}>
              {isClient && (
                <div style={{ background: "var(--card-bg)", borderRadius: 16, padding: 20 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-dim)", fontFamily: "var(--font-mono)", marginBottom: 12 }}>
                    CLIENT SHIPMENT REQUEST
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                    <label style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 11, color: "var(--text-dim)", fontFamily: "var(--font-mono)" }}>
                      <span>Quantity</span>
                      <input
                        type="number"
                        min="0"
                        step="0.1"
                        value={shipmentForm.quantity}
                        onChange={(event) => handleShipmentFormField("quantity", event.target.value)}
                        style={{ padding: "10px 12px", borderRadius: 10, border: "1px solid var(--border)", background: "var(--surface)", color: "var(--text)", fontSize: 13, outline: "none" }}
                      />
                    </label>
                    <label style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 11, color: "var(--text-dim)", fontFamily: "var(--font-mono)" }}>
                      <span>Cargo Type</span>
                      <input
                        value={shipmentForm.cargo_type}
                        onChange={(event) => handleShipmentFormField("cargo_type", event.target.value)}
                        style={{ padding: "10px 12px", borderRadius: 10, border: "1px solid var(--border)", background: "var(--surface)", color: "var(--text)", fontSize: 13, outline: "none" }}
                      />
                    </label>
                    <label style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 11, color: "var(--text-dim)", fontFamily: "var(--font-mono)", gridColumn: "1 / -1" }}>
                      <span>Destination</span>
                      <input
                        value={shipmentForm.destination}
                        onChange={(event) => handleShipmentFormField("destination", event.target.value)}
                        placeholder="Example: Rabat, Morocco"
                        style={{ padding: "10px 12px", borderRadius: 10, border: "1px solid var(--border)", background: "var(--surface)", color: "var(--text)", fontSize: 13, outline: "none" }}
                      />
                    </label>
                    <label style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 11, color: "var(--text-dim)", fontFamily: "var(--font-mono)", gridColumn: "1 / -1" }}>
                      <span>Origin</span>
                      <input
                        value={shipmentForm.origin}
                        onChange={(event) => handleShipmentFormField("origin", event.target.value)}
                        style={{ padding: "10px 12px", borderRadius: 10, border: "1px solid var(--border)", background: "var(--surface)", color: "var(--text)", fontSize: 13, outline: "none" }}
                      />
                    </label>
                    <label style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 11, color: "var(--text-dim)", fontFamily: "var(--font-mono)", gridColumn: "1 / -1" }}>
                      <span>Notes</span>
                      <textarea
                        rows={3}
                        value={shipmentForm.notes}
                        onChange={(event) => handleShipmentFormField("notes", event.target.value)}
                        style={{ padding: "10px 12px", borderRadius: 10, border: "1px solid var(--border)", background: "var(--surface)", color: "var(--text)", fontSize: 13, outline: "none", resize: "vertical" }}
                      />
                    </label>
                  </div>
                  <div style={{ marginTop: 14, display: "flex", gap: 8 }}>
                    <button
                      onClick={handleCreateShipmentRequest}
                      disabled={submitShipmentLoading}
                      style={{
                        padding: "10px 16px",
                        borderRadius: 10,
                        border: "none",
                        background: "var(--accent)",
                        color: "#fff",
                        cursor: "pointer",
                        fontWeight: 700,
                        opacity: submitShipmentLoading ? 0.6 : 1,
                      }}
                    >
                      {submitShipmentLoading ? "Sending..." : "Send shipment request"}
                    </button>
                  </div>
                </div>
              )}

              <div style={{ background: "var(--card-bg)", borderRadius: 16, padding: 20 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-dim)", fontFamily: "var(--font-mono)" }}>
                    {isAdmin ? "DASHBOARD REQUESTS" : "MY REQUESTS"}
                  </div>
                  <button
                    onClick={loadShipmentRequests}
                    style={{ padding: "6px 10px", borderRadius: 8, border: "1px solid var(--border)", background: "var(--surface)", color: "var(--text-dim)", cursor: "pointer", fontSize: 11 }}
                  >
                    Refresh
                  </button>
                </div>

                {shipmentRequestsLoading && (
                  <div style={{ fontSize: 12, color: "var(--text-dim)", fontFamily: "var(--font-mono)" }}>Loading shipment requests...</div>
                )}

                {!shipmentRequestsLoading && shipmentRequests.length === 0 && (
                  <div style={{ fontSize: 13, color: "var(--text-dim)", lineHeight: 1.6 }}>
                    No shipment requests yet.
                  </div>
                )}

                {!shipmentRequestsLoading && shipmentRequests.length > 0 && (
                  <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                    {shipmentRequests.map((requestItem) => {
                      const isPending = requestItem.status === "pending_confirmation";
                      const isConfirmed = requestItem.status === "confirmed";
                      const transportPlan = requestItem.transport_plan || null;
                      const lifecycleStage = normalizeLifecycleStage(requestItem);
                      const canStartDelivery = isAdmin && lifecycleStage === "storage" && !isPending && Boolean(transportPlan);
                      const canFinishDelivery = isAdmin && lifecycleStage === "delivery";
                      return (
                        <div key={requestItem.id} style={{ background: "var(--surface)", borderRadius: 12, border: "1px solid var(--border)", padding: 12 }}>
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
                            <div>
                              <div style={{ fontSize: 12, fontWeight: 700, color: "var(--text)" }}>{requestItem.id} · {requestItem.cargo_type}</div>
                              <div style={{ fontSize: 11, color: "var(--text-dim)", fontFamily: "var(--font-mono)", marginTop: 3 }}>
                                Qty {requestItem.quantity} · {requestItem.origin} → {requestItem.destination}
                              </div>
                            </div>
                            <Badge text={requestItem.status.replace(/_/g, " ")} color={isConfirmed ? "#10b981" : "#f59e0b"} />
                          </div>

                          {requestItem.notes && (
                            <div style={{ marginTop: 8, fontSize: 12, color: "var(--text-dim)" }}>{requestItem.notes}</div>
                          )}

                          <div style={{ marginTop: 10 }}>
                            <LifecycleProgress stage={lifecycleStage} />
                          </div>

                          {isAdmin && isPending && (
                            <div style={{ marginTop: 10 }}>
                              <button
                                onClick={() => handleConfirmShipmentRequest(requestItem.id)}
                                disabled={confirmShipmentLoadingId === requestItem.id}
                                style={{
                                  padding: "8px 12px",
                                  borderRadius: 9,
                                  border: "none",
                                  background: "#10b981",
                                  color: "#fff",
                                  cursor: "pointer",
                                  fontWeight: 700,
                                  opacity: confirmShipmentLoadingId === requestItem.id ? 0.6 : 1,
                                }}
                              >
                                {confirmShipmentLoadingId === requestItem.id ? "Confirming..." : "Confirm and dispatch Transport Agent"}
                              </button>
                            </div>
                          )}

                          {(canStartDelivery || canFinishDelivery) && (
                            <div style={{ marginTop: 10, display: "flex", gap: 8, flexWrap: "wrap" }}>
                              {canStartDelivery && (
                                <button
                                  onClick={() => handleUpdateLifecycleStage(requestItem.id, "delivery")}
                                  disabled={stageUpdateLoadingId === `${requestItem.id}:delivery`}
                                  style={{
                                    padding: "8px 12px",
                                    borderRadius: 9,
                                    border: "none",
                                    background: "#0ea5e9",
                                    color: "#fff",
                                    cursor: "pointer",
                                    fontWeight: 700,
                                    opacity: stageUpdateLoadingId === `${requestItem.id}:delivery` ? 0.6 : 1,
                                  }}
                                >
                                  {stageUpdateLoadingId === `${requestItem.id}:delivery` ? "Updating..." : "Start delivery"}
                                </button>
                              )}
                              {canFinishDelivery && (
                                <button
                                  onClick={() => handleUpdateLifecycleStage(requestItem.id, "destination")}
                                  disabled={stageUpdateLoadingId === `${requestItem.id}:destination`}
                                  style={{
                                    padding: "8px 12px",
                                    borderRadius: 9,
                                    border: "none",
                                    background: "#10b981",
                                    color: "#fff",
                                    cursor: "pointer",
                                    fontWeight: 700,
                                    opacity: stageUpdateLoadingId === `${requestItem.id}:destination` ? 0.6 : 1,
                                  }}
                                >
                                  {stageUpdateLoadingId === `${requestItem.id}:destination` ? "Updating..." : "Mark arrived destination"}
                                </button>
                              )}
                            </div>
                          )}

                          {isAdmin && (
                            <div style={{ marginTop: 10, display: "flex", justifyContent: "flex-end" }}>
                              <button
                                onClick={() => handleDeleteShipmentRequest(requestItem.id)}
                                disabled={deleteShipmentLoadingId === requestItem.id}
                                style={{
                                  padding: "7px 11px",
                                  borderRadius: 8,
                                  border: "1px solid #7f1d1d",
                                  background: "#7f1d1d33",
                                  color: "#fecaca",
                                  cursor: "pointer",
                                  fontWeight: 700,
                                  fontSize: 11,
                                  opacity: deleteShipmentLoadingId === requestItem.id ? 0.6 : 1,
                                }}
                              >
                                {deleteShipmentLoadingId === requestItem.id ? "Deleting..." : "Delete shipment"}
                              </button>
                            </div>
                          )}

                          {(isConfirmed || lifecycleStage === "delivery" || lifecycleStage === "destination") && transportPlan && (
                            <div style={{ marginTop: 10, paddingTop: 10, borderTop: "1px solid var(--border)", display: "grid", gap: 8 }}>
                              <div style={{ fontSize: 12, color: "var(--text)" }}>
                                Route: {Number(transportPlan.primary?.distance_km || 0).toFixed(1)} km · ETA {Number(transportPlan.primary?.duration_min || 0).toFixed(0)} min
                              </div>
                              <div style={{ fontSize: 12, color: "var(--text-dim)" }}>
                                Lifecycle: {lifecycleStage}
                              </div>
                              <div style={{ fontSize: 12, color: "var(--text-dim)" }}>
                                Heat risk: {transportPlan.heat_risk?.level || "unknown"} (score {transportPlan.heat_risk?.score ?? "n/a"}) · Weather {transportPlan.weather?.temperature_c ?? "n/a"}°C / {transportPlan.weather?.humidity_pct ?? "n/a"}%
                              </div>
                              {Array.isArray(transportPlan.suggestions) && transportPlan.suggestions.length > 0 && (
                                <div style={{ fontSize: 12, color: "var(--text-dim)", whiteSpace: "pre-wrap" }}>
                                  {"- " + transportPlan.suggestions.join("\n- ")}
                                </div>
                              )}
                              <ShipmentTrackingMap transportPlan={transportPlan} lifecycleStage={lifecycleStage} />
                              {transportPlan.openstreetmap_directions_url && (
                                <a
                                  href={transportPlan.openstreetmap_directions_url}
                                  target="_blank"
                                  rel="noreferrer"
                                  style={{ fontSize: 12, color: "var(--accent-2)", textDecoration: "none", fontWeight: 600 }}
                                >
                                  Open route in OpenStreetMap
                                </a>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}

                {shipmentRequestsError && (
                  <div style={{ marginTop: 12, fontSize: 12, color: "#ef4444", fontFamily: "var(--font-mono)" }}>{shipmentRequestsError}</div>
                )}
              </div>
            </div>
          )}

          {activeTab === "reasoning" && selected && (
            <div style={{ display: "grid", gridTemplateColumns: "1.1fr 0.9fr", gap: 16 }}>
              <div style={{ background: "var(--card-bg)", borderRadius: 16, padding: 20 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-dim)", fontFamily: "var(--font-mono)", marginBottom: 12 }}>LIVE AGENT INPUT</div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                  {[
                    ["name", "Product name"],
                    ["product_type", "Product type"],
                    ["origin", "Origin"],
                    ["destination", "Destination"],
                    ["value_usd", "Value USD"],
                    ["batch_id", "Batch ID"],
                    ["temperature_celsius", "Temperature °C"],
                    ["humidity_percent", "Humidity %"],
                    ["co2_ppm", "CO2 ppm"],
                    ["vibration_g", "Vibration g"],
                    ["latitude", "Latitude"],
                    ["longitude", "Longitude"],
                    ["city", "City"],
                    ["country", "Country"],
                    ["hours_elapsed", "Hours elapsed"],
                  ].map(([field, label]) => (
                    <label key={field} style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 11, color: "var(--text-dim)", fontFamily: "var(--font-mono)" }}>
                      <span>{label}</span>
                      <input
                        value={liveReasoningForm[field] ?? ""}
                        onChange={(event) => updateLiveReasoningField(field, event.target.value)}
                        style={{
                          padding: "10px 12px",
                          borderRadius: 10,
                          border: "1px solid var(--border)",
                          background: "var(--surface)",
                          color: "var(--text)",
                          fontSize: 13,
                          fontFamily: "var(--font-display)",
                          outline: "none",
                        }}
                      />
                    </label>
                  ))}
                </div>

                <div style={{ marginTop: 12 }}>
                  <label style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 11, color: "var(--text-dim)", fontFamily: "var(--font-mono)" }}>
                    <span>User query</span>
                    <textarea
                      value={liveReasoningForm.user_query ?? ""}
                      onChange={(event) => updateLiveReasoningField("user_query", event.target.value)}
                      rows={4}
                      style={{
                        padding: "10px 12px",
                        borderRadius: 10,
                        border: "1px solid var(--border)",
                        background: "var(--surface)",
                        color: "var(--text)",
                        fontSize: 13,
                        fontFamily: "var(--font-display)",
                        outline: "none",
                        resize: "vertical",
                      }}
                    />
                  </label>
                </div>

                <div style={{ marginTop: 16, display: "flex", gap: 8, flexWrap: "wrap" }}>
                  <button
                    onClick={handleLiveReasoning}
                    disabled={liveReasoningLoading}
                    style={{
                      padding: "10px 18px",
                      borderRadius: 10,
                      border: "none",
                      background: "var(--accent)",
                      color: "white",
                      cursor: "pointer",
                      fontSize: 13,
                      fontWeight: 600,
                      fontFamily: "var(--font-display)",
                      opacity: liveReasoningLoading ? 0.6 : 1,
                    }}
                  >
                    {liveReasoningLoading ? "Reasoning..." : "Run live reasoning"}
                  </button>
                  <button
                    onClick={() => setLiveReasoningForm((previous) => ({ ...previous, analysis_label: "live_dashboard_input" }))}
                    style={{
                      padding: "10px 18px",
                      borderRadius: 10,
                      border: "1px solid var(--border)",
                      background: "var(--surface)",
                      color: "var(--text-dim)",
                      cursor: "pointer",
                      fontSize: 13,
                      fontWeight: 600,
                      fontFamily: "var(--font-display)",
                    }}
                  >
                    Keep label
                  </button>
                </div>

                {liveReasoningError && (
                  <div style={{ marginTop: 14, padding: 12, borderRadius: 10, background: "#ef444415", color: "#ef4444", fontSize: 12, fontFamily: "var(--font-mono)" }}>
                    {liveReasoningError}
                  </div>
                )}
              </div>

              <div style={{ background: "var(--card-bg)", borderRadius: 16, padding: 20 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-dim)", fontFamily: "var(--font-mono)", marginBottom: 12 }}>BACKEND RESPONSE</div>
                {liveReasoningResult ? (
                  <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                    <div style={{ background: "var(--surface)", borderRadius: 12, padding: 14 }}>
                      <div style={{ fontSize: 10, fontFamily: "var(--font-mono)", color: "var(--text-dim)", marginBottom: 6 }}>SUMMARY</div>
                      <div style={{ fontSize: 13, color: "var(--text)", lineHeight: 1.6, whiteSpace: "pre-wrap" }}>{liveReasoningResult.scenario?.recommendation?.summary}</div>
                    </div>
                    <div style={{ background: "var(--surface)", borderRadius: 12, padding: 14 }}>
                      <div style={{ fontSize: 10, fontFamily: "var(--font-mono)", color: "var(--text-dim)", marginBottom: 6 }}>EXPLANATION</div>
                      <div style={{ fontSize: 13, color: "var(--text)", lineHeight: 1.6, whiteSpace: "pre-wrap" }}>{liveReasoningResult.scenario?.recommendation?.explanation}</div>
                    </div>
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 12 }}>
                      <div style={{ background: "var(--surface)", borderRadius: 12, padding: 14 }}>
                        <div style={{ fontSize: 10, fontFamily: "var(--font-mono)", color: "var(--text-dim)", marginBottom: 6 }}>ACTION</div>
                        <div style={{ fontSize: 16, fontWeight: 700, color: "var(--accent)" }}>{liveReasoningResult.scenario?.decision?.action?.replace(/_/g, " ")}</div>
                      </div>
                      <div style={{ background: "var(--surface)", borderRadius: 12, padding: 14 }}>
                        <div style={{ fontSize: 10, fontFamily: "var(--font-mono)", color: "var(--text-dim)", marginBottom: 6 }}>HEALTH</div>
                        <div style={{ fontSize: 16, fontWeight: 700, color: "var(--text)" }}>{liveReasoningResult.scenario?.health?.overall}/100</div>
                      </div>
                    </div>
                    <div style={{ background: "var(--surface)", borderRadius: 12, padding: 14 }}>
                      <div style={{ fontSize: 10, fontFamily: "var(--font-mono)", color: "var(--text-dim)", marginBottom: 6 }}>RAW JSON</div>
                      <pre style={{ margin: 0, whiteSpace: "pre-wrap", wordBreak: "break-word", fontSize: 11, color: "var(--text-dim)" }}>{JSON.stringify(liveReasoningResult.scenario, null, 2)}</pre>
                    </div>
                  </div>
                ) : (
                  <div style={{ color: "var(--text-dim)", fontSize: 13, lineHeight: 1.7 }}>
                    Select a shipment, adjust the fields, then run live reasoning to call the backend agent graph with your own input.
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      <style>{`
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
        * { box-sizing: border-box; margin: 0; }
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #1e1e35; border-radius: 3px; }
      `}</style>
        </>
      )}
    </div>
  );
}
