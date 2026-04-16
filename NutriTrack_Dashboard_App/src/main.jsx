import React from "react";
import { createRoot } from "react-dom/client";
import NutriTrackDashboard from "./App.jsx";

class AppErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, errorMessage: "" };
  }

  static getDerivedStateFromError(error) {
    return {
      hasError: true,
      errorMessage: error?.message || "Unknown rendering error",
    };
  }

  componentDidCatch(error, errorInfo) {
    console.error("Dashboard render error:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div
          style={{
            minHeight: "100vh",
            background: "#0a0a12",
            color: "#f3f4f6",
            fontFamily: "system-ui, sans-serif",
            display: "grid",
            placeItems: "center",
            padding: 24,
          }}
        >
          <div style={{ maxWidth: 760, width: "100%" }}>
            <h1 style={{ marginBottom: 8, color: "#ef4444" }}>Dashboard error</h1>
            <p style={{ marginBottom: 10 }}>
              The app encountered a runtime error instead of rendering a blank page.
            </p>
            <pre
              style={{
                background: "#111827",
                border: "1px solid #374151",
                borderRadius: 8,
                padding: 12,
                overflowX: "auto",
                whiteSpace: "pre-wrap",
              }}
            >
              {this.state.errorMessage}
            </pre>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <AppErrorBoundary>
      <NutriTrackDashboard />
    </AppErrorBoundary>
  </React.StrictMode>
);
