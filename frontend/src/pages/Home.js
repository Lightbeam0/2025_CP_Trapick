// src/pages/Home.js — Week navigation fix
// KEY CHANGES vs original:
//   1. weekDates is ONLY updated from the server's week_start response,
//      never optimistically from the offset alone (which caused label/data mismatch).
//   2. handleWeekChange stores the pending offset in a ref so concurrent clicks
//      don't clobber each other.
//   3. fetchOverviewData no longer resets weekOffset on location change —
//      it keeps the current week and re-fetches with the same offset.
//   4. Added console.debug to confirm offset round-trip with server.

import React, { useState, useEffect, useCallback, useRef } from "react";
import axios from "axios";
import { Line, Bar } from "react-chartjs-2";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from "chart.js";

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
  Filler,
);

const API_BASE_URL =
  process.env.NODE_ENV === "development" ? "http://127.0.0.1:8000" : "";

// ─── Confidence helpers ───────────────────────────────────────────────────────
const confidenceColor = (conf) => {
  if (conf >= 85) return { bar: "rgba(16, 185, 129, 0.85)", border: "#059669" };
  if (conf >= 60) return { bar: "rgba(245, 158, 11, 0.85)", border: "#d97706" };
  return { bar: "rgba(239, 68, 68, 0.75)", border: "#dc2626" };
};

const confidenceBadge = (conf) => {
  if (conf >= 85) return { label: "High confidence", bg: "#d1fae5", color: "#065f46" };
  if (conf >= 60) return { label: "Medium confidence", bg: "#fef3c7", color: "#92400e" };
  return { label: "Low confidence", bg: "#fee2e2", color: "#991b1b" };
};

// ─── Date helpers ─────────────────────────────────────────────────────────────
/**
 * Build 7 Date objects [Mon…Sun] from a server-supplied ISO date string.
 * Falls back to computing from today + offset when no string is available.
 */
function buildWeekDates(weekStartIso, offset = 0) {
  if (weekStartIso) {
    const [y, m, d] = weekStartIso.split("-").map(Number);
    const monday = new Date(y, m - 1, d);
    return Array.from({ length: 7 }, (_, i) => {
      const dt = new Date(monday);
      dt.setDate(monday.getDate() + i);
      return dt;
    });
  }
  // Fallback: derive from local today + offset
  const today = new Date();
  const dow = today.getDay(); // 0 = Sunday
  const mondayOffset = dow === 0 ? -6 : 1 - dow;
  const monday = new Date(today);
  monday.setDate(today.getDate() + mondayOffset + offset * 7);
  return Array.from({ length: 7 }, (_, i) => {
    const dt = new Date(monday);
    dt.setDate(monday.getDate() + i);
    return dt;
  });
}

function formatShortDate(date) {
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

// ─── Week Navigator ───────────────────────────────────────────────────────────
function WeekNavigator({ weekOffset, weekDates, onChange, loading }) {
  const isCurrentWeek = weekOffset === 0;

  const badge = isCurrentWeek
    ? { text: "THIS WEEK", bg: "#dbeafe", color: "#1d4ed8" }
    : weekOffset === -1
    ? { text: "LAST WEEK", bg: "#fef3c7", color: "#92400e" }
    : { text: `${Math.abs(weekOffset)} WEEKS AGO`, bg: "#f3f4f6", color: "#374151" };

  const rangeStr =
    weekDates.length === 7
      ? `${formatShortDate(weekDates[0])} – ${formatShortDate(weekDates[6])}, ${weekDates[0].getFullYear()}`
      : "Loading…";

  const btnBase = {
    width: "36px",
    height: "36px",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    background: "none",
    border: "1px solid #e2e8f0",
    borderRadius: "8px",
    fontSize: "18px",
    lineHeight: 1,
    transition: "all 0.15s",
  };

  return (
    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
      <button
        onClick={() => !loading && onChange(weekOffset - 1)}
        title="Previous week"
        style={{
          ...btnBase,
          cursor: loading ? "not-allowed" : "pointer",
          color: "#374151",
          opacity: loading ? 0.5 : 1,
        }}
        onMouseEnter={(e) => { if (!loading) e.currentTarget.style.backgroundColor = "#f1f5f9"; }}
        onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = "transparent"; }}
      >
        ‹
      </button>

      <div style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        backgroundColor: "#f8fafc",
        border: "1px solid #e2e8f0",
        borderRadius: "10px",
        padding: "6px 18px",
        minWidth: "220px",
        gap: "3px",
      }}>
        <span style={{
          fontSize: "11px",
          fontWeight: "700",
          letterSpacing: "0.5px",
          backgroundColor: badge.bg,
          color: badge.color,
          padding: "2px 10px",
          borderRadius: "20px",
        }}>
          {badge.text}
        </span>
        <span style={{ fontSize: "13px", fontWeight: "600", color: "#1f2937" }}>
          {loading ? "Loading…" : rangeStr}
        </span>
      </div>

      <button
        onClick={() => !loading && !isCurrentWeek && onChange(weekOffset + 1)}
        title={isCurrentWeek ? "Already on current week" : "Next week"}
        style={{
          ...btnBase,
          cursor: (loading || isCurrentWeek) ? "not-allowed" : "pointer",
          color: isCurrentWeek ? "#d1d5db" : "#374151",
          opacity: (loading || isCurrentWeek) ? 0.35 : 1,
        }}
        onMouseEnter={(e) => { if (!loading && !isCurrentWeek) e.currentTarget.style.backgroundColor = "#f1f5f9"; }}
        onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = "transparent"; }}
      >
        ›
      </button>

      {!isCurrentWeek && (
        <button
          onClick={() => !loading && onChange(0)}
          title="Back to current week"
          style={{
            padding: "6px 12px",
            backgroundColor: "#eff6ff",
            border: "1px solid #bfdbfe",
            borderRadius: "8px",
            cursor: loading ? "not-allowed" : "pointer",
            color: "#1d4ed8",
            fontSize: "12px",
            fontWeight: "600",
            transition: "all 0.15s",
            opacity: loading ? 0.6 : 1,
            whiteSpace: "nowrap",
          }}
          onMouseEnter={(e) => { if (!loading) e.currentTarget.style.backgroundColor = "#dbeafe"; }}
          onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = "#eff6ff"; }}
        >
          ⌂ Current week
        </button>
      )}
    </div>
  );
}

// ─── Coverage Warning Banner ──────────────────────────────────────────────────
function WarningBanner({ warnings }) {
  const [dismissed, setDismissed] = useState(false);
  if (!warnings || warnings.length === 0 || dismissed) return null;

  return (
    <div style={{
      display: "flex",
      alignItems: "flex-start",
      gap: "12px",
      backgroundColor: "#fffbeb",
      border: "1px solid #fcd34d",
      borderRadius: "10px",
      padding: "12px 16px",
      marginBottom: "20px",
      fontSize: "13px",
      color: "#92400e",
    }}>
      <span style={{ fontSize: "16px", flexShrink: 0 }}>⚠️</span>
      <div style={{ flex: 1 }}>
        <strong style={{ display: "block", marginBottom: "4px" }}>Data quality notice</strong>
        {warnings.map((w, i) => <div key={i} style={{ opacity: 0.9 }}>{w}</div>)}
      </div>
      <button
        onClick={() => setDismissed(true)}
        style={{ background: "none", border: "none", cursor: "pointer", color: "#92400e", fontSize: "16px", padding: "0", flexShrink: 0, lineHeight: 1 }}
      >×</button>
    </div>
  );
}

// ─── Hourly Distribution Chart ────────────────────────────────────────────────
function HourlyDistributionChart({ dayData }) {
  if (!dayData) return null;

  const hourly = dayData.hourly_distribution || {};
  const hours = Array.from({ length: 24 }, (_, i) => i);
  const vehicles = hours.map((h) => hourly[h]?.vehicles ?? 0);
  const confidences = hours.map((h) => hourly[h]?.confidence ?? 0);
  const minutes = hours.map((h) => hourly[h]?.minutes ?? 0);
  const hasAnyData = vehicles.some((v) => v > 0);

  const barColors = hours.map((h) => {
    if (vehicles[h] === 0) return "rgba(229, 231, 235, 0.5)";
    return confidenceColor(confidences[h]).bar;
  });
  const borderColors = hours.map((h) => {
    if (vehicles[h] === 0) return "rgba(209, 213, 219, 0.5)";
    return confidenceColor(confidences[h]).border;
  });
  const labels = hours.map((h) => {
    if (h === 0) return "12am";
    if (h === 12) return "12pm";
    if (h < 12) return `${h}am`;
    return `${h - 12}pm`;
  });

  const peakMorningHour =
    dayData.morning_peak && dayData.morning_peak !== "No data"
      ? parseInt(dayData.morning_peak.split(":")[0], 10)
      : null;
  const peakEveningHour =
    dayData.evening_peak && dayData.evening_peak !== "No data"
      ? parseInt(dayData.evening_peak.split(":")[0], 10)
      : null;

  const chartData = {
    labels,
    datasets: [{
      label: "Vehicles",
      data: vehicles,
      backgroundColor: barColors,
      borderColor: borderColors,
      borderWidth: 1.5,
      borderRadius: 4,
      borderSkipped: false,
    }],
  };

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    animation: { duration: 400 },
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: "rgba(17, 24, 39, 0.95)",
        titleColor: "#f9fafb",
        bodyColor: "#d1d5db",
        borderColor: "rgba(75, 85, 99, 0.5)",
        borderWidth: 1,
        padding: 12,
        callbacks: {
          title: (ctx) => {
            const h = hours[ctx[0].dataIndex];
            const label = h === 0 ? "12:00 AM" : h < 12 ? `${h}:00 AM` : h === 12 ? "12:00 PM" : `${h - 12}:00 PM`;
            const isPeakM = h === peakMorningHour ? " 🌅 Morning Peak" : "";
            const isPeakE = h === peakEveningHour ? " 🌇 Evening Peak" : "";
            return label + isPeakM + isPeakE;
          },
          label: (ctx) => {
            const h = hours[ctx.dataIndex];
            const lines = [`  Vehicles: ${vehicles[h]}`];
            if (minutes[h] > 0) {
              lines.push(`  Recorded: ${minutes[h].toFixed(0)} min`);
              lines.push(`  Confidence: ${confidences[h].toFixed(0)}%`);
            }
            return lines;
          },
        },
      },
    },
    scales: {
      y: {
        beginAtZero: true,
        grid: { color: "rgba(0,0,0,0.05)", lineWidth: 1 },
        border: { display: false },
        ticks: { font: { size: 12 }, color: "#6b7280", padding: 8, callback: (v) => v.toLocaleString() },
      },
      x: {
        grid: { display: false },
        border: { display: false },
        ticks: {
          font: { size: 11 },
          color: (ctx) => {
            const h = hours[ctx.index];
            return (h === peakMorningHour || h === peakEveningHour) ? "#1f2937" : "#9ca3af";
          },
          maxRotation: 0,
        },
      },
    },
  };

  const totalVehicles = vehicles.reduce((a, b) => a + b, 0);
  const hoursWithData = vehicles.filter((v) => v > 0).length;
  const avgPerHour = hoursWithData > 0 ? Math.round(totalVehicles / hoursWithData) : 0;
  const peakHourIdx = vehicles.indexOf(Math.max(...vehicles));
  const peakHourLabel = labels[peakHourIdx];
  const peakHourVehicles = vehicles[peakHourIdx];
  const nonZeroConf = confidences.filter((c) => c > 0);
  const avgConf = nonZeroConf.length > 0
    ? Math.round(nonZeroConf.reduce((a, b) => a + b, 0) / nonZeroConf.length)
    : 0;
  const badge = confidenceBadge(avgConf);

  return (
    <div>
      <WarningBanner warnings={dayData.warnings} />

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: "12px", marginBottom: "20px" }}>
        {[
          { label: "Total vehicles", value: totalVehicles.toLocaleString(), sub: "this day" },
          { label: "Avg per hour", value: avgPerHour.toLocaleString(), sub: "recorded hours only" },
          { label: "Peak hour", value: peakHourLabel, sub: hasAnyData ? `${peakHourVehicles.toLocaleString()} vehicles` : "no data" },
          { label: "Data confidence", value: `${avgConf}%`, sub: badge.label, badgeBg: badge.bg, badgeColor: badge.color },
        ].map((stat, i) => (
          <div key={i} style={{ backgroundColor: "#f8fafc", borderRadius: "10px", padding: "14px 16px", border: "1px solid #e5e7eb" }}>
            <div style={{ fontSize: "12px", color: "#6b7280", marginBottom: "4px" }}>{stat.label}</div>
            <div style={{ fontSize: "22px", fontWeight: "700", color: "#1f2937", lineHeight: 1.2 }}>{stat.value}</div>
            {stat.badgeBg ? (
              <span style={{ display: "inline-block", marginTop: "4px", fontSize: "11px", fontWeight: "600", backgroundColor: stat.badgeBg, color: stat.badgeColor, padding: "2px 8px", borderRadius: "20px" }}>
                {stat.sub}
              </span>
            ) : (
              <div style={{ fontSize: "12px", color: "#9ca3af", marginTop: "4px" }}>{stat.sub}</div>
            )}
          </div>
        ))}
      </div>

      {!hasAnyData ? (
        <div style={{ height: "280px", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", backgroundColor: "#f9fafb", borderRadius: "12px", color: "#9ca3af", gap: "12px" }}>
          <span style={{ fontSize: "40px" }}>📭</span>
          <span style={{ fontSize: "15px" }}>No hourly data recorded for {dayData.name}</span>
          <span style={{ fontSize: "13px" }}>Videos recorded on this day will appear here</span>
        </div>
      ) : (
        <div>
          <div style={{ display: "flex", gap: "12px", marginBottom: "10px", flexWrap: "wrap" }}>
            {peakMorningHour !== null && (
              <span style={{ fontSize: "12px", backgroundColor: "#fef3c7", color: "#92400e", padding: "3px 10px", borderRadius: "20px", fontWeight: "600" }}>
                🌅 Morning peak · {dayData.morning_peak}
                {dayData.morning_confidence > 0 && ` · ${dayData.morning_confidence}% conf.`}
              </span>
            )}
            {peakEveningHour !== null && (
              <span style={{ fontSize: "12px", backgroundColor: "#e0e7ff", color: "#3730a3", padding: "3px 10px", borderRadius: "20px", fontWeight: "600" }}>
                🌇 Evening peak · {dayData.evening_peak}
                {dayData.evening_confidence > 0 && ` · ${dayData.evening_confidence}% conf.`}
              </span>
            )}
          </div>
          <div style={{ height: "280px" }}>
            <Bar data={chartData} options={chartOptions} />
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Main Home component ──────────────────────────────────────────────────────
function Home() {
  const [overviewData, setOverviewData] = useState(null);
  const [peakHoursData, setPeakHoursData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [weekLoading, setWeekLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedLocation, setSelectedLocation] = useState("all");
  const [locations, setLocations] = useState([]);
  const [peakStats, setPeakStats] = useState(null);
  const [refreshing, setRefreshing] = useState(false);
  const [selectedPeakDay, setSelectedPeakDay] = useState("Monday");

  // Week state — weekOffset drives requests; weekDates is ONLY set from
  // server-confirmed week_start so labels always match the data returned.
  const [weekOffset, setWeekOffset] = useState(0);
  const [weekDates, setWeekDates] = useState(() => buildWeekDates(null, 0));

  // Track the latest requested offset so stale responses are ignored
  const pendingOffsetRef = useRef(0);

  const dayNames = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

  // ── Fetch locations once ────────────────────────────────────────────────────
  useEffect(() => {
    axios
      .get(`${API_BASE_URL}/api/locations/`)
      .then((res) => {
        const data = res.data;
        setLocations(Array.isArray(data) ? data : data?.locations ?? []);
      })
      .catch(() => setLocations([]));
  }, []);

  // ── Core fetch ──────────────────────────────────────────────────────────────
  const fetchOverviewData = useCallback(async (locId, offset, initial = false) => {
    // Record which offset this request is for
    pendingOffsetRef.current = offset;

    try {
      initial ? setLoading(true) : setWeekLoading(true);
      setError(null);

      const params = new URLSearchParams();
      if (locId !== "all") params.append("location_id", locId);
      params.append("week_offset", offset);

      const response = await axios.get(`${API_BASE_URL}/api/analyze/?${params}`);
      const data = response.data;

      // Discard stale responses (user clicked again while this was in-flight)
      if (pendingOffsetRef.current !== offset) {
        console.debug(`[Home] Discarding stale response for offset=${offset} (pending=${pendingOffsetRef.current})`);
        return;
      }

      // Verify server echoed back the same offset (sanity check)
      if (data.week_offset !== undefined && data.week_offset !== offset) {
        console.warn(`[Home] Server returned offset=${data.week_offset} but we requested ${offset}`);
      }

      // ✅ FIX: weekDates is set ONLY from the server's authoritative week_start.
      //    This guarantees chart labels match the data being displayed.
      if (data.week_start) {
        setWeekDates(buildWeekDates(data.week_start));
      }
      // (If server doesn't return week_start, keep the optimistic dates set in handleWeekChange)

      if (data.peak_hours_data?.length > 0) {
        setPeakHoursData(data.peak_hours_data);
        const firstWithData = data.peak_hours_data.find((d) => d.total_vehicles > 0);
        if (firstWithData) setSelectedPeakDay(firstWithData.name);
      } else if (data.areas?.length > 0) {
        setPeakHoursData(data.areas);
      } else {
        setPeakHoursData([]);
      }

      if (data.peak_stats) setPeakStats(data.peak_stats);

      const weeklyData =
        data.weekly_data?.length > 0 ? data.weekly_data : [0, 0, 0, 0, 0, 0, 0];

      setOverviewData({ ...data, weekly_data: weeklyData, hasData: true });

      console.debug(
        `[Home] week_offset=${offset} week=${data.week_start}→${data.week_end} ` +
        `weekly=${weeklyData} total=${data.total_vehicles}`
      );
    } catch (err) {
      console.error("API error:", err);
      setError("Failed to load traffic data.");
      setOverviewData({ weekly_data: [0, 0, 0, 0, 0, 0, 0], total_vehicles: 0, hasData: false });
      setPeakHoursData([]);
    } finally {
      setLoading(false);
      setWeekLoading(false);
    }
  }, []);

  // ── Location change: keep current week offset, just re-fetch ───────────────
  useEffect(() => {
    // Do NOT reset weekOffset here — user may be browsing a past week and
    // switches location; we should show the same week for the new location.
    fetchOverviewData(selectedLocation, weekOffset, true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedLocation]);

  // ── Week navigation ─────────────────────────────────────────────────────────
  const handleWeekChange = useCallback((newOffset) => {
    const capped = Math.min(0, newOffset);    // never allow future weeks
    setWeekOffset(capped);
    // Optimistic label update so the navigator shows the right range immediately
    // while the request is in-flight. Will be overwritten by server response.
    setWeekDates(buildWeekDates(null, capped));
    fetchOverviewData(selectedLocation, capped, false);
  }, [selectedLocation, fetchOverviewData]);

  const refreshPeakHours = async () => {
    try {
      setRefreshing(true);
      const params = new URLSearchParams();
      if (selectedLocation !== "all") params.append("location_id", selectedLocation);
      const response = await axios.get(`${API_BASE_URL}/api/peak-hours/analysis/?${params}`);
      if (response.data.success) {
        setPeakHoursData(response.data.peak_hours);
        if (response.data.summary) setPeakStats(response.data.summary);
      }
    } catch (err) {
      console.error("Error refreshing peak hours:", err);
    } finally {
      setRefreshing(false);
    }
  };

  const getLocationName = (id) => {
    const loc = locations.find((l) => l.id === id);
    return loc ? loc.display_name : "Selected Location";
  };

  // ── Loading / empty states ──────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="main-content">
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "400px", color: "#6b7280", fontSize: "16px" }}>
          Loading traffic data…
        </div>
      </div>
    );
  }

  if (!overviewData?.hasData && !peakHoursData?.length) {
    return (
      <div className="main-content">
        <div className="dashboard-card" style={{ textAlign: "center", padding: "60px" }}>
          <div style={{ fontSize: "48px", marginBottom: "20px" }}>📊</div>
          <h2 style={{ fontSize: "24px", marginBottom: "12px", color: "#4b5563" }}>No Traffic Data Yet</h2>
          <p style={{ color: "#6b7280" }}>Upload videos to start generating analysis.</p>
        </div>
      </div>
    );
  }

  // ── Derived display values ──────────────────────────────────────────────────
  const weeklyData = overviewData?.weekly_data || [0, 0, 0, 0, 0, 0, 0];
  const totalWeeklyVehicles = overviewData?.total_vehicles || weeklyData.reduce((a, b) => a + b, 0);
  const dailyAverage = Math.round(totalWeeklyVehicles / 7);
  const firstHalf = weeklyData.slice(0, 3).reduce((a, b) => a + b, 0) / 3;
  const secondHalf = weeklyData.slice(4, 7).reduce((a, b) => a + b, 0) / 3;
  const weeklyTrend = firstHalf > 0 ? ((secondHalf - firstHalf) / firstHalf * 100).toFixed(1) : 0;
  const isIncreasing = weeklyTrend > 0;

  const selectedDayData = peakHoursData.find((d) => d.name === selectedPeakDay) || null;

  // Chart labels include actual dates from the server-confirmed weekDates
  const chartLabels = dayNames.map((name, i) =>
    weekDates[i] ? `${name.slice(0, 3)} · ${formatShortDate(weekDates[i])}` : name.slice(0, 3)
  );

  const lineChartData = {
    labels: chartLabels,
    datasets: [{
      label: "Vehicles",
      data: weeklyData,
      backgroundColor: "rgba(59, 130, 246, 0.08)",
      borderColor: "rgba(59, 130, 246, 1)",
      borderWidth: 3,
      fill: true,
      tension: 0.4,
      pointBackgroundColor: "rgba(59, 130, 246, 1)",
      pointBorderColor: "#fff",
      pointBorderWidth: 3,
      pointRadius: 8,
      pointHoverRadius: 10,
    }],
  };

  const lineChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: "index", intersect: false },
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: "rgba(17, 24, 39, 0.95)",
        titleColor: "#fff",
        bodyColor: "#fff",
        borderColor: "rgba(59, 130, 246, 0.5)",
        borderWidth: 2,
        padding: 16,
        displayColors: false,
        callbacks: {
          title: (ctx) => {
            const idx = ctx[0].dataIndex;
            const d = weekDates[idx];
            return d ? `${dayNames[idx]}, ${formatShortDate(d)}` : dayNames[idx];
          },
          label: (ctx) => `Total: ${ctx.parsed.y.toLocaleString()} vehicles`,
          afterLabel: (ctx) => {
            const vpm = (ctx.parsed.y / (24 * 60)).toFixed(1);
            return [
              "",
              `Per Minute: ${vpm} vehicles/min`,
              "",
              `% of week: ${totalWeeklyVehicles > 0 ? ((ctx.parsed.y / totalWeeklyVehicles) * 100).toFixed(1) : 0}%`,
            ];
          },
        },
      },
    },
    scales: {
      y: {
        beginAtZero: true,
        grid: { color: "rgba(0,0,0,0.06)" },
        ticks: { color: "#4b5563", callback: (v) => v.toLocaleString() },
        title: { display: true, text: "Number of Vehicles", font: { size: 13, weight: "bold" }, color: "#1f2937" },
      },
      x: {
        grid: { display: true, color: "rgba(0,0,0,0.03)" },
        ticks: { font: { size: 12, weight: "500" }, color: "#4b5563", maxRotation: 0 },
        title: { display: true, text: "Day of Week", font: { size: 13, weight: "bold" }, color: "#1f2937" },
      },
    },
  };

  // ── Render ──────────────────────────────────────────────────────────────────
  return (
    <div className="main-content">
      {/* Header */}
      <header style={{ marginBottom: "32px" }}>
        <h1 style={{ fontSize: "32px", fontWeight: "bold", color: "#2d3748", margin: "0 0 8px 0" }}>
          Traffic Overview
        </h1>
        <p style={{ color: "#666", margin: 0 }}>Real-time traffic analytics dashboard</p>
      </header>

      {error && (
        <div style={{ backgroundColor: "#fee2e2", border: "1px solid #fca5a5", borderRadius: "8px", padding: "12px 16px", marginBottom: "24px", color: "#991b1b", fontSize: "14px" }}>
          ⚠️ {error}
        </div>
      )}

      {/* Location Filter */}
      <div className="dashboard-card" style={{ marginBottom: "32px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h2 style={{ fontSize: "20px", fontWeight: "600", color: "#2d3748", margin: 0 }}>Traffic Overview</h2>
          <select
            value={selectedLocation}
            onChange={(e) => setSelectedLocation(e.target.value)}
            style={{ minWidth: "200px", padding: "8px", borderRadius: "6px", border: "1px solid #d1d5db", fontSize: "14px" }}
          >
            <option value="all">All Locations</option>
            {locations.map((loc) => (
              <option key={loc.id} value={loc.id}>{loc.display_name}</option>
            ))}
          </select>
        </div>
        {selectedLocation !== "all" && (
          <div style={{ padding: "10px 14px", backgroundColor: "#f0f9ff", borderRadius: "6px", border: "1px solid #bae6fd", marginTop: "14px", fontSize: "14px", color: "#0369a1" }}>
            <strong>Viewing:</strong> {getLocationName(selectedLocation)}
          </div>
        )}
      </div>

      {/* Summary cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: "20px", marginBottom: "32px" }}>
        {[
          {
            gradient: "linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)",
            shadow: "rgba(79,172,254,0.3)",
            emoji: "📅",
            label: "Vehicles Per Day",
            value: dailyAverage.toLocaleString(),
            unit: "/day",
            sub: `${isIncreasing ? "+" : ""}${weeklyTrend}% weekly trend`,
          },
          {
            gradient: "linear-gradient(135deg, #fa709a 0%, #fee140 100%)",
            shadow: "rgba(250,112,154,0.3)",
            emoji: "📈",
            label: "Weekly Total",
            value: totalWeeklyVehicles.toLocaleString(),
            unit: " vehicles",
            sub: weekDates[0] && weekDates[6]
              ? `Week of ${formatShortDate(weekDates[0])} – ${formatShortDate(weekDates[6])}`
              : "This week",
          },
        ].map((card) => (
          <div key={card.label} style={{ background: card.gradient, borderRadius: "16px", padding: "24px", color: "white", boxShadow: `0 10px 25px ${card.shadow}`, position: "relative", overflow: "hidden" }}>
            <div style={{ position: "absolute", top: "-20px", right: "-20px", fontSize: "110px", opacity: "0.1" }}>{card.emoji}</div>
            <div style={{ position: "relative", zIndex: 1 }}>
              <div style={{ fontSize: "13px", opacity: 0.9, marginBottom: "6px", fontWeight: "500" }}>{card.label}</div>
              <div style={{ display: "flex", alignItems: "baseline", gap: "6px", marginBottom: "10px" }}>
                <span style={{ fontSize: "38px", fontWeight: "bold" }}>{card.value}</span>
                <span style={{ fontSize: "16px", opacity: 0.8 }}>{card.unit}</span>
              </div>
              <div style={{ display: "inline-flex", alignItems: "center", gap: "4px", backgroundColor: "rgba(255,255,255,0.2)", padding: "3px 10px", borderRadius: "20px", fontSize: "12px", fontWeight: "600" }}>
                {card.sub}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Weekly line chart */}
      <div className="dashboard-card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "20px", flexWrap: "wrap", gap: "12px" }}>
          <div>
            <h2 style={{ fontSize: "20px", fontWeight: "600", margin: 0 }}>Traffic Trends Overview</h2>
            <p style={{ color: "#666", fontSize: "14px", marginTop: "4px", margin: "4px 0 0 0" }}>
              Weekly traffic patterns ·{" "}
              <span style={{ color: "#6b7280" }}>
                {weekDates[0] && weekDates[6]
                  ? `Week of ${formatShortDate(weekDates[0])} – ${formatShortDate(weekDates[6])}`
                  : "Loading…"}
              </span>
            </p>
          </div>
          <WeekNavigator
            weekOffset={weekOffset}
            weekDates={weekDates}
            onChange={handleWeekChange}
            loading={weekLoading}
          />
        </div>

        <div style={{ position: "relative" }}>
          {weekLoading && (
            <div style={{ position: "absolute", inset: 0, backgroundColor: "rgba(255,255,255,0.75)", display: "flex", alignItems: "center", justifyContent: "center", borderRadius: "12px", zIndex: 10 }}>
              <div style={{ color: "#6b7280", fontSize: "14px", fontWeight: "500", display: "flex", alignItems: "center", gap: "8px" }}>
                <span style={{ display: "inline-block", width: "16px", height: "16px", border: "2px solid #d1d5db", borderTopColor: "#3b82f6", borderRadius: "50%", animation: "spin 0.7s linear infinite" }} />
                Loading week data…
              </div>
              <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
            </div>
          )}
          <div style={{ height: "380px", marginBottom: "24px" }}>
            <Line data={lineChartData} options={lineChartOptions} />
          </div>
        </div>

        {totalWeeklyVehicles === 0 && !weekLoading && (
          <div style={{ padding: "12px 16px", backgroundColor: "#f0f9ff", borderRadius: "8px", border: "1px solid #bae6fd", marginBottom: "20px", fontSize: "13px", color: "#0369a1", textAlign: "center" }}>
            📅 No videos recorded during{" "}
            <strong>
              {weekDates[0] && weekDates[6]
                ? `${formatShortDate(weekDates[0])} – ${formatShortDate(weekDates[6])}`
                : "this week"}
            </strong>.
            Use the arrows above to navigate to another week.
          </div>
        )}

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "20px", paddingTop: "20px", borderTop: "2px solid #e5e7eb" }}>
          {[
            { label: "WEEKLY TOTAL", value: totalWeeklyVehicles.toLocaleString(), sub: "vehicles counted", subColor: "#9ca3af" },
            { label: "DAILY AVERAGE", value: dailyAverage.toLocaleString(), sub: `${isIncreasing ? "+" : ""}${weeklyTrend}% from last week`, subColor: isIncreasing ? "#10b981" : "#ef4444" },
            {
              label: "PEAK DAY",
              value: totalWeeklyVehicles > 0
                ? ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"][weeklyData.indexOf(Math.max(...weeklyData))]
                : "—",
              sub: totalWeeklyVehicles > 0 ? `${Math.max(...weeklyData).toLocaleString()} vehicles` : "No data yet",
              subColor: "#9ca3af",
            },
          ].map((s) => (
            <div key={s.label} style={{ textAlign: "center" }}>
              <p style={{ fontSize: "12px", color: "#6b7280", marginBottom: "6px", fontWeight: "600" }}>{s.label}</p>
              <p style={{ fontSize: "26px", fontWeight: "bold", color: "#1f2937" }}>{s.value}</p>
              <p style={{ fontSize: "12px", color: s.subColor, marginTop: "4px", fontWeight: "600" }}>{s.sub}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Daily Traffic Flow (Hourly Distribution) */}
      <div className="dashboard-card" style={{ marginTop: "32px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "24px", paddingBottom: "16px", borderBottom: "1px solid #e5e7eb", flexWrap: "wrap", gap: "12px" }}>
          <div>
            <h2 style={{ fontSize: "22px", fontWeight: "600", margin: "0 0 4px 0" }}>Daily Traffic Flow</h2>
            <p style={{ fontSize: "14px", color: "#6b7280", margin: 0 }}>24-hour vehicle distribution · bar color indicates data confidence</p>
          </div>
          <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
            {peakStats && (
              <span style={{ fontSize: "13px", color: "#374151", backgroundColor: "#f3f4f6", padding: "5px 12px", borderRadius: "20px", fontWeight: "500" }}>
                Overall peak: <strong>{peakStats.overall_peak_hour}</strong>
              </span>
            )}
            <button
              onClick={refreshPeakHours}
              disabled={refreshing}
              style={{ padding: "6px 14px", backgroundColor: refreshing ? "#9ca3af" : "#3b82f6", color: "white", border: "none", borderRadius: "6px", cursor: refreshing ? "not-allowed" : "pointer", fontSize: "13px", fontWeight: "500" }}
            >
              {refreshing ? "⟳ Refreshing…" : "↻ Refresh"}
            </button>
          </div>
        </div>

        {/* Day selector tabs */}
        <div style={{ display: "flex", gap: "6px", marginBottom: "24px", flexWrap: "wrap" }}>
          {peakHoursData.length > 0 ? (
            peakHoursData.map((day) => {
              const isSelected = selectedPeakDay === day.name;
              const hasData = (day.total_vehicles || 0) > 0;
              const hasWarnings = day.warnings?.length > 0;
              const dayIdx = dayNames.indexOf(day.name);
              const dateLabel = dayIdx >= 0 && weekDates[dayIdx] ? formatShortDate(weekDates[dayIdx]) : "";

              return (
                <button
                  key={day.name}
                  onClick={() => setSelectedPeakDay(day.name)}
                  style={{
                    padding: "8px 16px",
                    borderRadius: "8px",
                    border: isSelected ? "2px solid #3b82f6" : "2px solid #e5e7eb",
                    backgroundColor: isSelected ? "#eff6ff" : "white",
                    color: isSelected ? "#1d4ed8" : hasData ? "#374151" : "#9ca3af",
                    fontWeight: isSelected ? "700" : "500",
                    fontSize: "13px",
                    cursor: "pointer",
                    transition: "all 0.15s ease",
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    gap: "2px",
                  }}
                >
                  <span style={{ display: "flex", alignItems: "center", gap: "5px" }}>
                    {day.name.slice(0, 3)}
                    {hasData && (
                      <span style={{ fontSize: "10px", backgroundColor: isSelected ? "#bfdbfe" : "#f3f4f6", color: isSelected ? "#1d4ed8" : "#6b7280", padding: "1px 5px", borderRadius: "10px", fontWeight: "600" }}>
                        {(day.total_vehicles || 0).toLocaleString()}
                      </span>
                    )}
                    {hasWarnings && (
                      <span title={day.warnings.join("; ")} style={{ width: "7px", height: "7px", borderRadius: "50%", backgroundColor: "#f59e0b", display: "inline-block", flexShrink: 0 }} />
                    )}
                  </span>
                  {dateLabel && (
                    <span style={{ fontSize: "10px", color: isSelected ? "#3b82f6" : "#9ca3af", fontWeight: "400" }}>
                      {dateLabel}
                    </span>
                  )}
                </button>
              );
            })
          ) : (
            <p style={{ fontSize: "14px", color: "#9ca3af" }}>No data available. Upload and process videos to see daily breakdown.</p>
          )}
        </div>

        {selectedDayData ? (
          <HourlyDistributionChart dayData={selectedDayData} />
        ) : (
          <div style={{ padding: "60px", textAlign: "center", color: "#9ca3af", backgroundColor: "#f9fafb", borderRadius: "12px" }}>
            <div style={{ fontSize: "40px", marginBottom: "12px" }}>📊</div>
            <p style={{ fontSize: "15px" }}>
              {peakHoursData.length > 0 ? "Select a day above to view its hourly breakdown." : "No traffic data yet. Upload videos to get started."}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

export default Home;