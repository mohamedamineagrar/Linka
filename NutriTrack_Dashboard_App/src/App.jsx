// export { default } from "./NutriTrackAutonomousDashboard.jsx";
import React, { useState, useEffect, useRef } from "react";

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
  if (!anomalies.length) return <div style={{ color: "var(--text-dim)", fontSize: 13, padding: 12, textAlign: "center" }}>✅ No anomalies detected</div>;
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
              {a.type === "severe_degradation" ? "⚡ Compound Failure" : a.type === "temperature" ? "🌡️ Temperature" : a.type === "humidity" ? "💧 Humidity" : a.type === "co2" ? "🫧 CO₂" : `📳 ${a.type}`}
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
  const [assistantQuery, setAssistantQuery] = useState("");
  const [assistantResponse, setAssistantResponse] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [dashboardData, setDashboardData] = useState(null);
  const [dataStatus, setDataStatus] = useState("loading");
  const [dataError, setDataError] = useState("");
  const [liveReasoningForm, setLiveReasoningForm] = useState({});
  const [liveReasoningResult, setLiveReasoningResult] = useState(null);
  const [liveReasoningError, setLiveReasoningError] = useState("");
  const [liveReasoningLoading, setLiveReasoningLoading] = useState(false);

  useEffect(() => {
    let isMounted = true;

    async function loadDashboardData() {
      try {
        const response = await fetch(`/api/dashboard`, {
          headers: {
            Accept: "application/json",
          },
        });

        if (!response.ok) {
          throw new Error(`Unable to load dashboard data (${response.status})`);
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
  }, []);

  const data = dashboardData;
  const scenarios = Array.isArray(data?.scenarios) ? data.scenarios : [];
  const selected = scenarios[Math.min(selectedIdx, scenarios.length - 1)] || null;
  const summary = data?.summary || EMPTY_DASHBOARD_DATA.summary;

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
      user_query: selected.recommendation?.summary ? `Explain the live state of ${selected.product.name}.` : "",
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

  const handleAssistantQuery = async () => {
    if (!assistantQuery.trim() || !selected) return;
    setIsLoading(true);

    try {
      const response = await fetch(`/api/assistant`, {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          ...buildReasoningPayload(assistantQuery),
          assistant_query: assistantQuery,
          include_dashboard_context: true,
          max_fleet_items: 5,
        }),
      });

      if (!response.ok) {
        throw new Error(`Assistant request failed (${response.status})`);
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
      const response = await fetch(`/api/reason`, {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify(buildReasoningPayload()),
      });

      if (!response.ok) {
        throw new Error(`Reasoning request failed (${response.status})`);
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
    { id: "overview", label: "Overview", icon: "📊" },
    { id: "workflow", label: "Workflow", icon: "🔄" },
    { id: "economics", label: "Economics", icon: "💰" },
    { id: "assistant", label: "Assistant", icon: "🤖" },
    { id: "reasoning", label: "Live Reasoning", icon: "🧠" },
  ];

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
          <div style={{ width: 8, height: 8, borderRadius: "50%", background: "#10b981", animation: "pulse 2s infinite" }} />
          <span style={{ fontSize: 12, color: "#10b981", fontFamily: "var(--font-mono)" }}>
            {dataStatus === "ready" ? "API SYNCED" : dataStatus === "fallback" ? "LOCAL FALLBACK" : "SYNCING"} · {scenarios.length} shipments tracked
          </span>
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
      <div style={{ display: "grid", gridTemplateColumns: "320px 1fr", gap: 0, minHeight: "calc(100vh - 250px)" }}>
        {/* Sidebar — Shipment List */}
        <div style={{
          borderRight: "1px solid var(--border)",
          padding: "12px 16px",
          overflowY: "auto",
          maxHeight: "calc(100vh - 250px)",
        }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text-dim)", marginBottom: 12, fontFamily: "var(--font-mono)", textTransform: "uppercase", letterSpacing: "0.06em" }}>Active Shipments</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {scenarios.length > 0 ? (
              scenarios.map((s, i) => (
                <ScenarioCard key={i} scenario={s} isSelected={i === selectedIdx} onClick={() => setSelectedIdx(i)} />
              ))
            ) : (
              <div style={{ color: "var(--text-dim)", fontSize: 13, lineHeight: 1.7, padding: 12 }}>
                No shipment data loaded yet. The dashboard depends on the backend API.
              </div>
            )}
          </div>
        </div>

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
          {!hasDashboardData ? (
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

              {/* Anomalies */}
              <div style={{ background: "var(--card-bg)", borderRadius: 16, padding: 20 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                  <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text-dim)", fontFamily: "var(--font-mono)" }}>ANOMALIES</span>
                  <Badge text={selected.risk_level} color={RISK_COLORS[selected.risk_level]} />
                </div>
                <AnomalyList anomalies={selected.anomalies} />
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
                <div style={{ fontSize: 15, fontWeight: 700, color: "var(--text)", marginBottom: 8 }}>{selected.recommendation.summary}</div>
                <div style={{ fontSize: 13, color: "var(--text-dim)", lineHeight: 1.6, whiteSpace: "pre-wrap" }}>{selected.recommendation.explanation}</div>
                {selected.recommendation.alternatives.length > 0 && (
                  <div style={{ marginTop: 14 }}>
                    <div style={{ fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--text-dim)", marginBottom: 8, textTransform: "uppercase" }}>Alternatives</div>
                    <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                      {selected.recommendation.alternatives.map((alt, i) => (
                        <div key={i} style={{
                          padding: "10px 14px", borderRadius: 10, background: "var(--surface)",
                          border: "1px solid var(--border)", flex: "1 1 200px",
                        }}>
                          <div style={{ fontSize: 12, fontWeight: 600, color: "var(--accent-2)" }}>{alt.action?.replace(/_/g, " ") || alt.description?.slice(0, 30)}</div>
                          <div style={{ fontSize: 11, color: "var(--text-dim)", marginTop: 3 }}>{alt.description}</div>
                          <div style={{ fontSize: 10, color: "#f59e0b", marginTop: 3, fontStyle: "italic" }}>{alt.trade_off}</div>
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
                  Ask about the current shipment. Example: "What should I do with this product?" or "Is it safe to deliver?"
                </div>

                {/* Quick actions */}
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 16 }}>
                  {[
                    "What should I do with this product?",
                    "Is it safe to deliver?",
                    "Show me alternatives",
                    "Explain the risk",
                  ].map(q => (
                    <button key={q} onClick={() => { setAssistantQuery(q); }} style={{
                      padding: "6px 12px", borderRadius: 8, border: "1px solid var(--border)",
                      background: "var(--surface)", color: "var(--text-dim)", cursor: "pointer",
                      fontSize: 11, fontFamily: "var(--font-display)", transition: "all 0.2s",
                    }}>{q}</button>
                  ))}
                </div>

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
    </div>
  );
}
