// src/pages/VehiclesPassing.js
import React, { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { Bar } from "react-chartjs-2";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
} from "chart.js";

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend);

const API_BASE_URL =
  process.env.NODE_ENV === "development" ? "http://127.0.0.1:8000" : "";

// ─── helpers ──────────────────────────────────────────────────────────────────

const VEHICLE_META = {
  cars:        { label: "Cars",        color: "#3b82f6", emoji: "🚗" },
  trucks:      { label: "Trucks",      color: "#ef4444", emoji: "🚛" },
  motorcycles: { label: "Motorcycles", color: "#f59e0b", emoji: "🏍️" },
  jeeps:       { label: "Jeeps",       color: "#10b981", emoji: "🚙" },
  tricycles:   { label: "Tricycles",   color: "#8b5cf6", emoji: "🛺" },
  other:       { label: "Other",       color: "#6b7280", emoji: "🚌" },
};

const VEHICLE_KEYS = Object.keys(VEHICLE_META);

function formatHour(h) {
  if (h === undefined || h === null) return "—";
  const suffix = h < 12 ? "AM" : "PM";
  const display = h === 0 ? 12 : h > 12 ? h - 12 : h;
  return `${display}:00 ${suffix}`;
}

function getPeakVehicleType(data) {
  if (!data) return null;
  let peak = null;
  let max = -1;
  VEHICLE_KEYS.forEach((k) => {
    const v = data[k] || 0;
    if (v > max) { max = v; peak = k; }
  });
  return peak && max > 0 ? { type: peak, count: max } : null;
}

// ─── PeakTimelinePanel ────────────────────────────────────────────────────────

function PeakTimelinePanel({ locationFilter, locations }) {
  const [timeline, setTimeline] = useState([]);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState(null);
  const [daysBack, setDaysBack] = useState(7);
  const [sortBy, setSortBy]     = useState("datetime");
  const [filterType, setFilterType] = useState("all");

  const fetchTimeline = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      params.append("days_back", daysBack);
      if (locationFilter && locationFilter !== "all")
        params.append("location_id", locationFilter);

      let url = `${API_BASE_URL}/api/groups/?${params}`;
      const groupsRes = await axios.get(url);
      const groups = groupsRes.data?.groups || groupsRes.data || [];

      const rows = [];
      for (const group of groups) {
        try {
          const groupDetailRes = await axios.get(
            `${API_BASE_URL}/api/groups/${group.id}/analysis/`
          );
          const detail = groupDetailRes.data?.aggregated_analysis || groupDetailRes.data;
          if (!detail) continue;

          const mapped = {
            cars:        detail.car_count        || 0,
            trucks:      detail.truck_count       || 0,
            motorcycles: detail.motorcycle_count  || 0,
            jeeps:       detail.bus_count         || 0,
            tricycles:   detail.bicycle_count     || 0,
            other:       detail.other_count       || 0,
            total:       detail.total_vehicles    || 0,
          };

          const peak = getPeakVehicleType(mapped);
          if (!peak) continue;

          rows.push({
            id:           group.id,
            date:         group.date,
            locationName: group.location?.name || group.location?.display_name || "—",
            timeRange:    group.time_range || detail.time_range || "—",
            peakType:     peak.type,
            peakCount:    peak.count,
            total:        mapped.total,
            breakdown:    mapped,
            peakPct:      mapped.total > 0
              ? ((peak.count / mapped.total) * 100).toFixed(1)
              : "0.0",
          });
        } catch (_) {
          // skip individual group errors
        }
      }

      setTimeline(rows);
    } catch (err) {
      setError(err.response?.data?.error || err.message || "Failed to load timeline");
    } finally {
      setLoading(false);
    }
  }, [locationFilter, daysBack]);

  useEffect(() => { fetchTimeline(); }, [fetchTimeline]);

  const displayed = timeline
    .filter((r) => filterType === "all" || r.peakType === filterType)
    .sort((a, b) => {
      if (sortBy === "count")    return b.peakCount - a.peakCount;
      if (sortBy === "type")     return a.peakType.localeCompare(b.peakType);
      return new Date(b.date) - new Date(a.date);
    });

  const typeFrequency = {};
  timeline.forEach((r) => {
    typeFrequency[r.peakType] = (typeFrequency[r.peakType] || 0) + 1;
  });
  const dominantType = Object.entries(typeFrequency).sort((a, b) => b[1] - a[1])[0];

  return (
    <div className="peak-timeline-container" style={{ fontFamily: "'Segoe UI', system-ui, sans-serif" }}>
      {/* Header strip - using app gradient */}
      <div
        style={{
          background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
          borderRadius: "12px 12px 0 0",
          padding: "20px 24px",
          color: "white",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          flexWrap: "wrap",
          gap: "12px",
        }}
      >
        <div>
          <h2 style={{ margin: 0, fontSize: "18px", fontWeight: 700, letterSpacing: "-0.3px" }}>
            📅 Peak Vehicle Type — Date &amp; Time Log
          </h2>
          <p style={{ margin: "4px 0 0", fontSize: "13px", opacity: 0.85 }}>
            Which vehicle type dominated each recorded session
          </p>
        </div>

        {!loading && timeline.length > 0 && (
          <div style={{ display: "flex", gap: "16px", flexWrap: "wrap" }}>
            <Chip
              label="Sessions"
              value={timeline.length}
              bg="rgba(255,255,255,0.15)"
            />
            {dominantType && (
              <Chip
                label="Most Dominant"
                value={`${VEHICLE_META[dominantType[0]]?.emoji} ${VEHICLE_META[dominantType[0]]?.label}`}
                bg="rgba(255,255,255,0.15)"
              />
            )}
          </div>
        )}
      </div>

      {/* Controls - using app colors */}
      <div
        style={{
          background: "#f8fafc",
          border: "1px solid #e2e8f0",
          borderTop: "none",
          padding: "14px 20px",
          display: "flex",
          gap: "12px",
          flexWrap: "wrap",
          alignItems: "center",
        }}
      >
        <ControlLabel label="Days Back">
          <select
            style={selectStyle}
            value={daysBack}
            onChange={(e) => setDaysBack(Number(e.target.value))}
          >
            {[7, 14, 30, 60, 90].map((d) => (
              <option key={d} value={d}>
                Last {d} days
              </option>
            ))}
          </select>
        </ControlLabel>

        <ControlLabel label="Filter Type">
          <select
            style={selectStyle}
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
          >
            <option value="all">All Types</option>
            {VEHICLE_KEYS.map((k) => (
              <option key={k} value={k}>
                {VEHICLE_META[k].emoji} {VEHICLE_META[k].label}
              </option>
            ))}
          </select>
        </ControlLabel>

        <ControlLabel label="Sort By">
          <select
            style={selectStyle}
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
          >
            <option value="datetime">Date (newest first)</option>
            <option value="count">Peak Count (highest)</option>
            <option value="type">Vehicle Type</option>
          </select>
        </ControlLabel>

        <button
          onClick={fetchTimeline}
          style={{
            marginLeft: "auto",
            padding: "8px 16px",
            background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
            color: "white",
            border: "none",
            borderRadius: "6px",
            cursor: "pointer",
            fontSize: "13px",
            fontWeight: 600,
            transition: "all 0.3s ease",
          }}
          onMouseEnter={(e) => {
            e.target.style.background = "linear-gradient(135deg, #764ba2 0%, #667eea 100%)";
            e.target.style.transform = "translateY(-1px)";
            e.target.style.boxShadow = "0 4px 12px rgba(102, 126, 234, 0.4)";
          }}
          onMouseLeave={(e) => {
            e.target.style.background = "linear-gradient(135deg, #667eea 0%, #764ba2 100%)";
            e.target.style.transform = "translateY(0)";
            e.target.style.boxShadow = "none";
          }}
        >
          🔄 Refresh
        </button>
      </div>

      {/* Body */}
      <div
        style={{
          border: "1px solid #e2e8f0",
          borderTop: "none",
          borderRadius: "0 0 12px 12px",
          overflow: "hidden",
        }}
      >
        {loading && (
          <div style={centeredMsg}>
            <Spinner /> &nbsp; Loading peak timeline…
          </div>
        )}

        {!loading && error && (
          <div style={{ ...centeredMsg, color: "#b91c1c" }}>⚠️ {error}</div>
        )}

        {!loading && !error && displayed.length === 0 && (
          <div style={centeredMsg}>
            No data found. Process some traffic videos first.
          </div>
        )}

        {!loading && !error && displayed.length > 0 && (
          <>
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13.5px" }}>
                <thead>
                  <tr style={{ background: "#f1f5f9", borderBottom: "2px solid #e2e8f0" }}>
                    {["Date", "Time Range", "Location", "Peak Vehicle Type", "Peak Count", "% of Total", "Total Vehicles", "Breakdown"].map(
                      (h) => (
                        <th
                          key={h}
                          style={{
                            padding: "11px 14px",
                            textAlign: "left",
                            fontWeight: 700,
                            color: "#374151",
                            whiteSpace: "nowrap",
                            fontSize: "12px",
                            textTransform: "uppercase",
                            letterSpacing: "0.5px",
                          }}
                        >
                          {h}
                        </th>
                      )
                    )}
                  </tr>
                </thead>
                <tbody>
                  {displayed.map((row, idx) => {
                    const meta = VEHICLE_META[row.peakType] || {};
                    return (
                      <tr
                        key={row.id}
                        style={{
                          background: idx % 2 === 0 ? "white" : "#fafafa",
                          borderBottom: "1px solid #f0f0f0",
                          transition: "background 0.15s",
                        }}
                        onMouseEnter={(e) =>
                          (e.currentTarget.style.background = "#eff6ff")
                        }
                        onMouseLeave={(e) =>
                          (e.currentTarget.style.background =
                            idx % 2 === 0 ? "white" : "#fafafa")
                        }
                      >
                        <td style={tdStyle}>
                          <div style={{ fontWeight: 700, color: "#1e3a5f" }}>
                            {formatDate(row.date)}
                          </div>
                          <div style={{ fontSize: "11px", color: "#9ca3af" }}>
                            {dayName(row.date)}
                          </div>
                        </td>

                        <td style={tdStyle}>
                          <span
                            style={{
                              background: "#e0f2fe",
                              color: "#0369a1",
                              borderRadius: "4px",
                              padding: "2px 8px",
                              fontSize: "12px",
                              fontWeight: 600,
                              whiteSpace: "nowrap",
                            }}
                          >
                            🕐 {row.timeRange}
                          </span>
                        </td>

                        <td style={tdStyle}>
                          <span style={{ color: "#374151" }}>{row.locationName}</span>
                        </td>

                        <td style={tdStyle}>
                          <span
                            style={{
                              display: "inline-flex",
                              alignItems: "center",
                              gap: "6px",
                              background: meta.color + "18",
                              color: meta.color,
                              border: `1.5px solid ${meta.color}40`,
                              borderRadius: "20px",
                              padding: "4px 12px",
                              fontWeight: 700,
                              fontSize: "13px",
                            }}
                          >
                            <span style={{ fontSize: "16px" }}>{meta.emoji}</span>
                            {meta.label}
                          </span>
                        </td>

                        <td style={tdStyle}>
                          <span style={{ fontWeight: 700, fontSize: "15px", color: meta.color }}>
                            {row.peakCount.toLocaleString()}
                          </span>
                        </td>

                        <td style={tdStyle}>
                          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                            <div
                              style={{
                                flex: 1,
                                height: "6px",
                                background: "#e5e7eb",
                                borderRadius: "3px",
                                minWidth: "60px",
                                overflow: "hidden",
                              }}
                            >
                              <div
                                style={{
                                  width: `${Math.min(100, parseFloat(row.peakPct))}%`,
                                  height: "100%",
                                  background: meta.color,
                                  borderRadius: "3px",
                                  transition: "width 0.6s ease",
                                }}
                              />
                            </div>
                            <span style={{ fontWeight: 600, color: "#374151", fontSize: "12px", minWidth: "36px" }}>
                              {row.peakPct}%
                            </span>
                          </div>
                        </td>

                        <td style={tdStyle}>
                          <span style={{ fontWeight: 600, color: "#374151" }}>
                            {row.total.toLocaleString()}
                          </span>
                        </td>

                        <td style={tdStyle}>
                          <BreakdownDots breakdown={row.breakdown} total={row.total} />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div
              style={{
                background: "#f8fafc",
                borderTop: "1px solid #e2e8f0",
                padding: "12px 20px",
                display: "flex",
                gap: "24px",
                flexWrap: "wrap",
                fontSize: "13px",
                color: "#6b7280",
              }}
            >
              <span>
                Showing <strong style={{ color: "#667eea" }}>{displayed.length}</strong> of{" "}
                <strong style={{ color: "#667eea" }}>{timeline.length}</strong> sessions
              </span>
              <span>
                Type frequency:{" "}
                {Object.entries(typeFrequency)
                  .sort((a, b) => b[1] - a[1])
                  .map(([type, cnt]) => (
                    <span key={type} style={{ marginRight: "10px" }}>
                      {VEHICLE_META[type]?.emoji} {VEHICLE_META[type]?.label}:{" "}
                      <strong style={{ color: "#667eea" }}>{cnt}</strong>×
                    </span>
                  ))}
              </span>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// ─── Small sub-components ─────────────────────────────────────────────────────

function Chip({ label, value, bg }) {
  return (
    <div
      style={{
        background: bg || "rgba(255,255,255,0.15)",
        borderRadius: "8px",
        padding: "6px 12px",
        textAlign: "center",
      }}
    >
      <div style={{ fontSize: "10px", opacity: 0.8, textTransform: "uppercase", letterSpacing: "0.5px" }}>
        {label}
      </div>
      <div style={{ fontSize: "14px", fontWeight: 700 }}>{value}</div>
    </div>
  );
}

function ControlLabel({ label, children }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
      <span style={{ fontSize: "10px", fontWeight: 700, color: "#6b7280", textTransform: "uppercase", letterSpacing: "0.5px" }}>
        {label}
      </span>
      {children}
    </div>
  );
}

function BreakdownDots({ breakdown, total }) {
  return (
    <div style={{ display: "flex", gap: "4px", alignItems: "center", flexWrap: "wrap" }}>
      {VEHICLE_KEYS.map((k) => {
        const count = breakdown[k] || 0;
        if (count === 0) return null;
        const pct = total > 0 ? ((count / total) * 100).toFixed(0) : 0;
        const meta = VEHICLE_META[k];
        return (
          <span
            key={k}
            title={`${meta.label}: ${count.toLocaleString()} (${pct}%)`}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "2px",
              background: meta.color + "18",
              color: meta.color,
              borderRadius: "4px",
              padding: "1px 5px",
              fontSize: "10px",
              fontWeight: 600,
              cursor: "default",
            }}
          >
            {meta.emoji} {count.toLocaleString()}
          </span>
        );
      })}
    </div>
  );
}

function Spinner() {
  return (
    <div
      style={{
        display: "inline-block",
        width: "18px",
        height: "18px",
        border: "3px solid #e2e8f0",
        borderTop: "3px solid #667eea",
        borderRadius: "50%",
        animation: "spin 0.8s linear infinite",
      }}
    />
  );
}

// ─── Styles / helpers ─────────────────────────────────────────────────────────

const selectStyle = {
  padding: "6px 10px",
  border: "1px solid #d1d5db",
  borderRadius: "6px",
  fontSize: "13px",
  background: "white",
  color: "#374151",
  cursor: "pointer",
};

const tdStyle = {
  padding: "11px 14px",
  verticalAlign: "middle",
};

const centeredMsg = {
  padding: "48px",
  textAlign: "center",
  color: "#6b7280",
  fontSize: "14px",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  gap: "8px",
};

function formatDate(dateStr) {
  if (!dateStr) return "—";
  const d = new Date(dateStr + "T00:00:00");
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function dayName(dateStr) {
  if (!dateStr) return "";
  const d = new Date(dateStr + "T00:00:00");
  return d.toLocaleDateString("en-US", { weekday: "long" });
}

// ─── Main VehiclesPassing component ──────────────────────────────────────────

function VehiclesPassing() {
  const [timePeriod, setTimePeriod]       = useState("today");
  const [vehicleData, setVehicleData]     = useState(null);
  const [loading, setLoading]             = useState(true);
  const [error, setError]                 = useState(null);
  const [locationFilter, setLocationFilter] = useState("all");
  const [locations, setLocations]         = useState([]);
  const [dateRange, setDateRange]         = useState("last_7_days");
  const [selectedGroup, setSelectedGroup] = useState(null);
  const [dateGroups, setDateGroups]       = useState([]);
  const [activeTab, setActiveTab]         = useState("overview");

  useEffect(() => {
    fetchLocations();
    fetchVehicleData();
  }, [timePeriod, locationFilter, dateRange, selectedGroup]);

  const fetchLocations = async () => {
    try {
      const res = await axios.get(`${API_BASE_URL}/api/locations/`);
      setLocations(res.data);
    } catch (err) {
      console.error("Error fetching locations:", err);
    }
  };

  const fetchDateGroups = async (locationId) => {
    try {
      const res = await axios.get(`${API_BASE_URL}/api/locations/${locationId}/groups/`);
      setDateGroups(res.data);
    } catch (err) {
      console.error("Error fetching date groups:", err);
    }
  };

  const fetchVehicleData = async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams();
      if (selectedGroup) {
        params.append("group_id", selectedGroup);
      } else {
        if (locationFilter && locationFilter !== "all") params.append("location_id", locationFilter);
        if (timePeriod && timePeriod !== "all") params.append("period", timePeriod);
        if (dateRange && dateRange !== "all") params.append("date_range", dateRange);
      }
      const res = await axios.get(`${API_BASE_URL}/api/vehicles/?${params}`);
      const apiData = res.data;

      if (apiData && typeof apiData === "object") {
        let mappedData;
        if (apiData.today || apiData.yesterday || apiData.week || apiData.month) {
          const cur = apiData[timePeriod] || {};
          mappedData = {
            cars:             cur.cars             || cur.car_count        || 0,
            trucks:           cur.trucks           || cur.truck_count      || 0,
            motorcycles:      cur.motorcycles      || cur.motorcycle_count || 0,
            jeeps:            cur.jeeps            || cur.bus_count        || 0,
            tricycles:        cur.tricycles        || cur.bicycle_count    || 0,
            other:            cur.other            || cur.other_count      || 0,
            total:            cur.total            || cur.total_vehicles   || 0,
            directional_total: cur.directional_count || cur.directional_total || 0,
            summary: apiData.summary || { total_analyses: 0, average_daily: 0, data_source: "Traffic Analysis Database" },
          };
        } else {
          mappedData = {
            cars:             apiData.car_count    || apiData.cars        || 0,
            trucks:           apiData.truck_count  || apiData.trucks      || 0,
            motorcycles:      apiData.motorcycle_count || apiData.motorcycles || 0,
            jeeps:            apiData.bus_count    || apiData.jeeps       || 0,
            tricycles:        apiData.bicycle_count || apiData.tricycles  || 0,
            other:            apiData.other_count  || apiData.other       || 0,
            total:            apiData.total_vehicles || apiData.total     || 0,
            directional_total: apiData.directional_count || apiData.directional_total || 0,
            location:         apiData.location_name || apiData.location,
            date:             apiData.analysis_date || apiData.date,
            summary: {
              total_analyses: apiData.total_analyses || 1,
              average_daily:  apiData.average_daily  || 0,
              data_source:    apiData.data_source     || "Traffic Analysis",
              peak_hour:      apiData.peak_hour,
              congestion_level: apiData.congestion_level,
            },
          };
        }
        if (mappedData.total === 0)
          mappedData.total = mappedData.cars + mappedData.trucks + mappedData.motorcycles + mappedData.jeeps + mappedData.tricycles + mappedData.other;

        setVehicleData(mappedData);
        if (locationFilter !== "all") fetchDateGroups(locationFilter);
        setError(null);
      } else {
        setVehicleData(getEmptyVehicleData());
        setError("Invalid data format from server");
      }
    } catch (err) {
      const msg = err.response?.data?.error || err.message || "Failed to load vehicle data";
      setError(`API Error: ${msg}`);
      setVehicleData(getEmptyVehicleData());
    } finally {
      setLoading(false);
    }
  };

  const getEmptyVehicleData = () => ({
    cars: 0, trucks: 0, motorcycles: 0, jeeps: 0, tricycles: 0, other: 0,
    total: 0, directional_total: 0,
    summary: { total_analyses: 0, average_daily: 0, data_source: "Check if videos have been processed and analyzed" },
  });

  if (loading) {
    return (
      <div className="main-content">
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "400px" }}>
          <div style={{ textAlign: "center" }}>
            <div style={{ fontSize: "18px", color: "#666", marginBottom: "16px" }}>Loading vehicle data...</div>
            <div style={{ width: "40px", height: "40px", border: "4px solid #f3f3f3", borderTop: "4px solid #667eea", borderRadius: "50%", margin: "0 auto", animation: "spin 1s linear infinite" }} />
          </div>
        </div>
      </div>
    );
  }

  const currentData    = vehicleData || getEmptyVehicleData();
  const totalVehicles  = currentData.total || 0;
  const directionalTotal = currentData.directional_total || 0;
  const peakNow        = getPeakVehicleType(currentData);

  const barChartData = {
    labels: VEHICLE_KEYS.map((k) => VEHICLE_META[k].label),
    datasets: [
      {
        label: "Vehicle Count",
        data: VEHICLE_KEYS.map((k) => currentData[k] || 0),
        backgroundColor: VEHICLE_KEYS.map((k) => VEHICLE_META[k].color + "b3"),
        borderColor:     VEHICLE_KEYS.map((k) => VEHICLE_META[k].color),
        borderWidth: 1,
      },
    ],
  };

  const vehicleRows = VEHICLE_KEYS.map((k) => ({ type: VEHICLE_META[k].label, count: currentData[k] || 0, key: k }));

  const tabs = [
    { id: "overview",       label: "📊 Overview" },
    { id: "peak-timeline",  label: "📅 Peak by Date & Time" },
  ];

  return (
    <div className="main-content">
      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
        .tab-btn { transition: all 0.2s; }
        .tab-btn:hover { opacity: 0.85; }
      `}</style>

      <header style={{ marginBottom: "24px" }}>
        <h1 style={{ fontSize: "32px", fontWeight: "bold", color: "#2d3748", margin: "0 0 8px 0" }}>
          Vehicle Composition Analysis
        </h1>
        <p style={{ color: "#666", margin: 0 }}>Detailed breakdown of vehicle types from traffic analysis</p>
      </header>

      {error && (
        <div style={{ backgroundColor: "#fff3cd", border: "1px solid #ffeaa7", color: "#856404", padding: "12px 16px", borderRadius: "4px", marginBottom: "24px" }}>
          {error}
        </div>
      )}

      {/* Tab navigation - using app colors */}
      <div style={{ display: "flex", gap: "4px", marginBottom: "24px", borderBottom: "2px solid #e2e8f0", paddingBottom: "0" }}>
        {tabs.map((tab) => (
          <button
            key={tab.id}
            className="tab-btn"
            onClick={() => setActiveTab(tab.id)}
            style={{
              padding: "10px 20px",
              border: "none",
              background: activeTab === tab.id ? "linear-gradient(135deg, #667eea 0%, #764ba2 100%)" : "transparent",
              color: activeTab === tab.id ? "white" : "#4b5563",
              borderRadius: "8px 8px 0 0",
              cursor: "pointer",
              fontWeight: activeTab === tab.id ? 700 : 500,
              fontSize: "14px",
              position: "relative",
              bottom: "-2px",
              borderBottom: activeTab === tab.id ? "2px solid #667eea" : "2px solid transparent",
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Overview Tab */}
      {activeTab === "overview" && (
        <div style={{ animation: "fadeIn 0.3s ease" }}>
          {/* Filters */}
          <div className="dashboard-card" style={{ marginBottom: "24px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
              <h2 style={{ fontSize: "20px", fontWeight: "600", color: "#2d3748", margin: 0 }}>Vehicle Type Distribution</h2>
              <button 
                onClick={fetchVehicleData} 
                style={{ 
                  padding: "8px 16px", 
                  background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
                  color: "white",
                  border: "none",
                  borderRadius: "6px",
                  cursor: "pointer",
                  fontSize: "14px",
                  fontWeight: 600,
                  transition: "all 0.3s ease",
                }}
                onMouseEnter={(e) => {
                  e.target.style.background = "linear-gradient(135deg, #764ba2 0%, #667eea 100%)";
                  e.target.style.transform = "translateY(-1px)";
                  e.target.style.boxShadow = "0 4px 12px rgba(102, 126, 234, 0.4)";
                }}
                onMouseLeave={(e) => {
                  e.target.style.background = "linear-gradient(135deg, #667eea 0%, #764ba2 100%)";
                  e.target.style.transform = "translateY(0)";
                  e.target.style.boxShadow = "none";
                }}
              >
                🔄 Refresh Data
              </button>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "16px" }}>
              <div>
                <label style={{ display: "block", marginBottom: "8px", fontWeight: "500", fontSize: "14px" }}>Time Period</label>
                <select className="select-input" value={timePeriod} onChange={(e) => { setTimePeriod(e.target.value); setSelectedGroup(null); }} style={{ width: "100%" }}>
                  <option value="today">Today</option>
                  <option value="yesterday">Yesterday</option>
                  <option value="week">This Week</option>
                  <option value="month">This Month</option>
                  <option value="all">All Time</option>
                </select>
              </div>

              <div>
                <label style={{ display: "block", marginBottom: "8px", fontWeight: "500", fontSize: "14px" }}>Location</label>
                <select className="select-input" value={locationFilter} onChange={(e) => { setLocationFilter(e.target.value); setSelectedGroup(null); if (e.target.value !== "all") fetchDateGroups(e.target.value); else setDateGroups([]); }} style={{ width: "100%" }}>
                  <option value="all">All Locations</option>
                  {locations.map((loc) => (<option key={loc.id} value={loc.id}>{loc.display_name}</option>))}
                </select>
              </div>

              <div>
                <label style={{ display: "block", marginBottom: "8px", fontWeight: "500", fontSize: "14px" }}>Date Range</label>
                <select className="select-input" value={dateRange} onChange={(e) => { setDateRange(e.target.value); setSelectedGroup(null); }} style={{ width: "100%" }}>
                  <option value="last_7_days">Last 7 Days</option>
                  <option value="last_30_days">Last 30 Days</option>
                  <option value="last_90_days">Last 90 Days</option>
                  <option value="all">All Time</option>
                </select>
              </div>

              {dateGroups.length > 0 && (
                <div>
                  <label style={{ display: "block", marginBottom: "8px", fontWeight: "500", fontSize: "14px" }}>Date Group</label>
                  <select className="select-input" value={selectedGroup || ""} onChange={(e) => setSelectedGroup(e.target.value || null)} style={{ width: "100%" }}>
                    <option value="">All Groups</option>
                    {dateGroups.map((g) => (<option key={g.id} value={g.id}>{g.date}</option>))}
                  </select>
                </div>
              )}
            </div>

            {currentData.summary && (
              <div style={{ marginTop: "16px", padding: "12px", backgroundColor: "#f0f9ff", borderRadius: "6px", border: "1px solid #bae6fd" }}>
                <div style={{ fontSize: "14px", color: "#0369a1" }}>
                  <strong>Data Source:</strong> {currentData.summary.data_source} •{" "}
                  <strong>Total Analyses:</strong> {currentData.summary.total_analyses || 0} •{" "}
                  <strong>Total Vehicles:</strong> {totalVehicles.toLocaleString()}
                  {currentData.summary.average_daily > 0 && (<> • <strong>Avg Daily:</strong> {currentData.summary.average_daily.toLocaleString()}</>)}
                  {currentData.summary.congestion_level && (<> • <strong>Congestion:</strong> {currentData.summary.congestion_level}</>)}
                </div>
              </div>
            )}
          </div>

          {/* Current Peak Banner */}
          {peakNow && (
            <div
              style={{
                background: `linear-gradient(135deg, ${VEHICLE_META[peakNow.type].color}22 0%, ${VEHICLE_META[peakNow.type].color}08 100%)`,
                border: `2px solid ${VEHICLE_META[peakNow.type].color}55`,
                borderRadius: "12px",
                padding: "16px 24px",
                marginBottom: "24px",
                display: "flex",
                alignItems: "center",
                gap: "16px",
                flexWrap: "wrap",
              }}
            >
              <span style={{ fontSize: "36px" }}>{VEHICLE_META[peakNow.type].emoji}</span>
              <div>
                <div style={{ fontSize: "12px", fontWeight: 700, color: "#6b7280", textTransform: "uppercase", letterSpacing: "0.5px" }}>
                  🏆 Most Common Vehicle — {timePeriod}
                </div>
                <div style={{ fontSize: "22px", fontWeight: 800, color: VEHICLE_META[peakNow.type].color }}>
                  {VEHICLE_META[peakNow.type].label}
                </div>
                <div style={{ fontSize: "13px", color: "#374151" }}>
                  {peakNow.count.toLocaleString()} vehicles &nbsp;•&nbsp;{" "}
                  {totalVehicles > 0 ? ((peakNow.count / totalVehicles) * 100).toFixed(1) : "0.0"}% of total
                </div>
              </div>
              <button
                onClick={() => setActiveTab("peak-timeline")}
                style={{
                  marginLeft: "auto",
                  padding: "8px 16px",
                  background: VEHICLE_META[peakNow.type].color,
                  color: "white",
                  border: "none",
                  borderRadius: "8px",
                  cursor: "pointer",
                  fontWeight: 700,
                  fontSize: "13px",
                  transition: "all 0.3s ease",
                }}
                onMouseEnter={(e) => {
                  e.target.style.transform = "translateY(-1px)";
                  e.target.style.boxShadow = "0 4px 12px rgba(0,0,0,0.2)";
                }}
                onMouseLeave={(e) => {
                  e.target.style.transform = "translateY(0)";
                  e.target.style.boxShadow = "none";
                }}
              >
                See full timeline →
              </button>
            </div>
          )}

          {/* Total Vehicles Card - using app gradient */}
          <div style={{ 
            background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)", 
            borderRadius: "12px", 
            padding: "24px", 
            color: "white", 
            marginBottom: "32px", 
            boxShadow: "0 4px 6px rgba(0,0,0,0.1)" 
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <p style={{ fontSize: "14px", opacity: 0.9, margin: "0 0 8px 0" }}>Total Vehicles ({timePeriod})</p>
                <p style={{ fontSize: "36px", fontWeight: "bold", margin: "0 0 8px 0" }}>{totalVehicles.toLocaleString()}</p>
                {directionalTotal > 0 && (<p style={{ fontSize: "14px", opacity: 0.9, margin: 0 }}>{directionalTotal.toLocaleString()} vehicles counted directionally</p>)}
              </div>
              <div style={{ textAlign: "right" }}>
                <p style={{ fontSize: "14px", opacity: 0.9, margin: "0 0 8px 0" }}>Period: {timePeriod.charAt(0).toUpperCase() + timePeriod.slice(1)}</p>
                <p style={{ fontSize: "16px", fontWeight: "600", margin: 0 }}>{currentData.location || "All Locations"}</p>
                {currentData.date && (<p style={{ fontSize: "12px", opacity: 0.8, margin: "4px 0 0 0" }}>As of {new Date(currentData.date).toLocaleDateString()}</p>)}
              </div>
            </div>
            {totalVehicles === 0 && (
              <div style={{ textAlign: "center", padding: "20px", backgroundColor: "rgba(255,255,255,0.1)", borderRadius: "8px", marginTop: "16px" }}>
                <p style={{ margin: 0, fontSize: "14px", opacity: 0.9 }}>No vehicle data found. Process some traffic videos first.</p>
              </div>
            )}
          </div>

          {/* Stat Cards */}
          <div className="stats-grid">
            {VEHICLE_KEYS.map((k, i) => {
              const meta  = VEHICLE_META[k];
              const value = currentData[k] || 0;
              const isPeak = peakNow?.type === k && totalVehicles > 0;
              return (
                <div
                  className="stat-card"
                  key={i}
                  style={{ position: "relative", outline: isPeak ? `2px solid ${meta.color}` : "none" }}
                >
                  {isPeak && (
                    <div style={{ 
                      position: "absolute", 
                      top: "-10px", 
                      right: "12px", 
                      background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
                      color: "white", 
                      fontSize: "10px", 
                      fontWeight: 800, 
                      borderRadius: "20px", 
                      padding: "2px 8px", 
                      letterSpacing: "0.5px" 
                    }}>
                      🏆 PEAK
                    </div>
                  )}
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                    <div>
                      <div className="stat-value" style={{ color: value === 0 ? "#9ca3af" : "#2d3748" }}>
                        {value.toLocaleString()}
                      </div>
                      <div className="stat-label">{meta.emoji} {meta.label}</div>
                    </div>
                    <div style={{ width: "40px", height: "40px", borderRadius: "8px", backgroundColor: meta.color, opacity: 0.2 }} />
                  </div>
                  <div style={{ fontSize: "12px", color: "#666", marginTop: "8px" }}>
                    {((value / totalVehicles) * 100 || 0).toFixed(1)}% of total
                  </div>
                </div>
              );
            })}
          </div>

          {/* Bar Chart */}
          <div style={{ marginBottom: "32px" }}>
            <div className="dashboard-card">
              <div className="card-header">
                <h3 className="card-title">Vehicle Type Distribution</h3>
                <p style={{ fontSize: "14px", color: "#666" }}>
                  Total Vehicles: {totalVehicles.toLocaleString()} | Directional Count: {directionalTotal.toLocaleString()}
                </p>
              </div>
              <div style={{ height: "400px", padding: "20px" }}>
                {totalVehicles > 0 ? (
                  <Bar
                    data={barChartData}
                    options={{
                      responsive: true,
                      maintainAspectRatio: false,
                      plugins: {
                        legend: { display: false },
                        tooltip: {
                          callbacks: {
                            label(ctx) {
                              const v = ctx.raw || 0;
                              const pct = totalVehicles > 0 ? ((v / totalVehicles) * 100).toFixed(1) : "0.0";
                              return `${ctx.dataset.label}: ${v.toLocaleString()} (${pct}%)`;
                            },
                          },
                        },
                      },
                      scales: {
                        y: {
                          beginAtZero: true,
                          title: { display: true, text: "Number of Vehicles" },
                          ticks: { callback: (v) => v.toLocaleString() },
                        },
                      },
                    }}
                  />
                ) : (
                  <div style={{ height: "100%", display: "flex", alignItems: "center", justifyContent: "center", color: "#666", fontSize: "16px" }}>
                    No vehicle data available to display
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Detailed Table */}
          <div className="dashboard-card">
            <div className="card-header">
              <h3 className="card-title">Detailed Vehicle Breakdown</h3>
              <p style={{ fontSize: "14px", color: "#666" }}>Generated: {new Date().toLocaleDateString()}</p>
            </div>
            <div className="table-container">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Vehicle Type</th>
                    <th>Count</th>
                    <th>Percentage of Total</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {vehicleRows.map((vehicle, idx) => {
                    const pct = totalVehicles > 0 ? ((vehicle.count / totalVehicles) * 100).toFixed(1) : "0.0";
                    const isPeak = peakNow?.type === vehicle.key && totalVehicles > 0;
                    return (
                      <tr key={idx}>
                        <td style={{ fontWeight: "600" }}>
                          {VEHICLE_META[vehicle.key]?.emoji} {vehicle.type}
                        </td>
                        <td>{vehicle.count.toLocaleString()}</td>
                        <td>{pct}%</td>
                        <td>
                          {isPeak && (
                            <span style={{ 
                              background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)", 
                              color: "white", 
                              borderRadius: "12px", 
                              padding: "2px 10px", 
                              fontSize: "11px", 
                              fontWeight: 700 
                            }}>
                              🏆 Peak
                            </span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                  <tr style={{ backgroundColor: "#f9fafb", fontWeight: "bold" }}>
                    <td>TOTAL</td>
                    <td>{totalVehicles.toLocaleString()}</td>
                    <td>100%</td>
                    <td />
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Peak Timeline Tab */}
      {activeTab === "peak-timeline" && (
        <div style={{ animation: "fadeIn 0.3s ease" }}>
          <PeakTimelinePanel
            locationFilter={locationFilter}
            locations={locations}
          />
        </div>
      )}
    </div>
  );
}

export default VehiclesPassing;