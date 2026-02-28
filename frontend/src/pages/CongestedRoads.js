// src/pages/CongestedRoads.js
import React, { useState, useEffect, useCallback } from "react";
import axios from "axios";

const API_BASE_URL = process.env.NODE_ENV === 'development'
  ? 'http://127.0.0.1:8000'
  : '';

// ── Helpers ────────────────────────────────────────────────────────────────────

const CONGESTION_META = {
  severe:   { label: 'Severe',   bg: '#fce7f3', color: '#9d174d', dot: '#ec4899', bar: '#ec4899' },
  high:     { label: 'High',     bg: '#fee2e2', color: '#991b1b', dot: '#ef4444', bar: '#ef4444' },
  medium:   { label: 'Medium',   bg: '#fef3c7', color: '#92400e', dot: '#f59e0b', bar: '#f59e0b' },
  low:      { label: 'Low',      bg: '#d1fae5', color: '#065f46', dot: '#10b981', bar: '#10b981' },
  very_low: { label: 'Very Low', bg: '#e0f2fe', color: '#075985', dot: '#38bdf8', bar: '#38bdf8' },
  none:     { label: 'None',     bg: '#f3f4f6', color: '#374151', dot: '#9ca3af', bar: '#9ca3af' },
  Unknown:  { label: 'Unknown',  bg: '#f3f4f6', color: '#6b7280', dot: '#9ca3af', bar: '#9ca3af' },
};

function getCongestionMeta(level) {
  if (!level) return CONGESTION_META.none;
  const key = level.toLowerCase().replace(/\s+/g, '_');
  return CONGESTION_META[key] || CONGESTION_META.Unknown;
}

const TREND_META = {
  increasing:  { icon: '↗', color: '#dc2626', label: 'Rising'  },
  decreasing:  { icon: '↘', color: '#16a34a', label: 'Falling' },
  stable:      { icon: '→', color: '#2563eb', label: 'Stable'  },
  fluctuating: { icon: '↕', color: '#d97706', label: 'Varying' },
};

function getTrendMeta(trend) {
  return TREND_META[trend?.toLowerCase()] || TREND_META.stable;
}

// ── Static fallback data (shown when API has no records yet) ──────────────────

const STATIC_DATA = [
  {
    road: 'Baliwasan Road',
    area: 'Baliwasan Area',
    time: '7:30 - 9:00 AM',
    congestion_level: 'high',
    vehicles_per_hour: 2450,
    trend: 'increasing',
    is_static: true,
  },
  {
    road: 'San Roque Highway',
    area: 'San Roque Area',
    time: '7:45 - 9:15 AM',
    congestion_level: 'high',
    vehicles_per_hour: 1950,
    trend: 'stable',
    is_static: true,
  },
  {
    road: 'Camino Nuevo Street',
    area: 'Camino Nuevo',
    time: '8:00 - 9:30 AM',
    congestion_level: 'medium',
    vehicles_per_hour: 1320,
    trend: 'decreasing',
    is_static: true,
  },
  {
    road: 'Divisoria Boulevard',
    area: 'City Proper',
    time: '5:00 - 6:30 PM',
    congestion_level: 'medium',
    vehicles_per_hour: 1110,
    trend: 'increasing',
    is_static: true,
  },
  {
    road: 'Veterans Avenue',
    area: 'Pettit Barracks',
    time: '7:00 - 8:30 AM',
    congestion_level: 'low',
    vehicles_per_hour: 740,
    trend: 'stable',
    is_static: true,
  },
  {
    road: 'Governor Lim Ave',
    area: 'Tetuan District',
    time: '4:30 - 6:00 PM',
    congestion_level: 'low',
    vehicles_per_hour: 610,
    trend: 'decreasing',
    is_static: true,
  },
];

// ── Styles ─────────────────────────────────────────────────────────────────────

const styles = {
  page: {
    minHeight: '100vh',
    background: '#f8fafc',
    padding: '32px 36px',
    fontFamily: "'DM Sans', 'Segoe UI', sans-serif",
  },
  header: {
    marginBottom: '36px',
  },
  headerTitle: {
    fontSize: '28px',
    fontWeight: '700',
    color: '#0f172a',
    margin: '0 0 6px 0',
    letterSpacing: '-0.5px',
  },
  headerSub: {
    color: '#64748b',
    margin: 0,
    fontSize: '15px',
  },
  topBar: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '24px',
    flexWrap: 'wrap',
    gap: '12px',
  },
  sectionTitle: {
    fontSize: '20px',
    fontWeight: '600',
    color: '#1e293b',
    margin: 0,
  },
  controls: {
    display: 'flex',
    gap: '10px',
    alignItems: 'center',
    flexWrap: 'wrap',
  },
  select: {
    padding: '8px 14px',
    borderRadius: '8px',
    border: '1.5px solid #e2e8f0',
    background: '#fff',
    color: '#334155',
    fontSize: '14px',
    fontWeight: '500',
    cursor: 'pointer',
    outline: 'none',
  },
  refreshBtn: {
    padding: '8px 16px',
    borderRadius: '8px',
    border: '1.5px solid #e2e8f0',
    background: '#fff',
    color: '#334155',
    fontSize: '14px',
    fontWeight: '500',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    transition: 'background 0.15s',
  },
  statsRow: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
    gap: '16px',
    marginBottom: '28px',
  },
  statCard: {
    background: '#fff',
    border: '1.5px solid #e2e8f0',
    borderRadius: '12px',
    padding: '18px 20px',
  },
  statLabel: {
    fontSize: '12px',
    fontWeight: '600',
    color: '#94a3b8',
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
    marginBottom: '6px',
  },
  statValue: {
    fontSize: '26px',
    fontWeight: '700',
    color: '#0f172a',
    lineHeight: 1,
  },
  statSub: {
    fontSize: '12px',
    color: '#64748b',
    marginTop: '4px',
  },
  card: {
    background: '#fff',
    borderRadius: '14px',
    border: '1.5px solid #e2e8f0',
    overflow: 'hidden',
    boxShadow: '0 1px 4px rgba(0,0,0,0.04)',
  },
  cardHeader: {
    padding: '20px 24px 16px',
    borderBottom: '1px solid #f1f5f9',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  cardTitle: {
    fontSize: '16px',
    fontWeight: '600',
    color: '#1e293b',
    margin: 0,
  },
  badge: {
    fontSize: '12px',
    padding: '3px 10px',
    borderRadius: '20px',
    fontWeight: '600',
  },
  tableWrap: {
    overflowX: 'auto',
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse',
  },
  th: {
    padding: '12px 20px',
    textAlign: 'left',
    fontSize: '12px',
    fontWeight: '600',
    color: '#64748b',
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
    background: '#f8fafc',
    borderBottom: '1px solid #e2e8f0',
    whiteSpace: 'nowrap',
  },
  td: {
    padding: '16px 20px',
    fontSize: '14px',
    color: '#334155',
    borderBottom: '1px solid #f1f5f9',
    verticalAlign: 'middle',
  },
  roadName: {
    fontWeight: '600',
    color: '#0f172a',
    fontSize: '14px',
  },
  areaName: {
    fontSize: '12px',
    color: '#64748b',
    marginTop: '2px',
  },
  congestionBadge: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '6px',
    padding: '4px 12px',
    borderRadius: '20px',
    fontSize: '12px',
    fontWeight: '600',
    whiteSpace: 'nowrap',
  },
  dot: {
    width: '7px',
    height: '7px',
    borderRadius: '50%',
    flexShrink: 0,
  },
  trendCell: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '5px',
    fontSize: '13px',
    fontWeight: '500',
  },
  vphBar: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
    minWidth: '120px',
  },
  vphNum: {
    fontWeight: '700',
    color: '#0f172a',
    fontSize: '14px',
  },
  barTrack: {
    height: '4px',
    borderRadius: '4px',
    background: '#e2e8f0',
    overflow: 'hidden',
  },
  emptyState: {
    textAlign: 'center',
    padding: '64px 32px',
    color: '#94a3b8',
  },
  banner: (color) => ({
    background: color === 'warn' ? '#fffbeb' : '#f0fdf4',
    border: `1px solid ${color === 'warn' ? '#fde68a' : '#bbf7d0'}`,
    color: color === 'warn' ? '#78350f' : '#14532d',
    padding: '12px 16px',
    borderRadius: '8px',
    fontSize: '13px',
    marginBottom: '20px',
    display: 'flex',
    gap: '8px',
    alignItems: 'flex-start',
  }),
  loadBox: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    height: '320px',
    flexDirection: 'column',
    gap: '14px',
    color: '#64748b',
    fontSize: '15px',
  },
  spinner: {
    width: '32px',
    height: '32px',
    border: '3px solid #e2e8f0',
    borderTop: '3px solid #3b82f6',
    borderRadius: '50%',
    animation: 'spin 0.8s linear infinite',
  },
};

// ── Component ──────────────────────────────────────────────────────────────────

export default function CongestedRoads() {
  const [timeFilter, setTimeFilter] = useState('all');
  const [levelFilter, setLevelFilter] = useState('all');
  const [liveData, setLiveData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [apiError, setApiError] = useState(null);
  const [usingStatic, setUsingStatic] = useState(false);
  const [lastFetched, setLastFetched] = useState(null);

  // ── Fetch ────────────────────────────────────────────────────────────────────

  const fetchData = useCallback(async () => {
    setLoading(true);
    setApiError(null);
    try {
      // Primary: real congestion endpoint
      const res = await axios.get(`${API_BASE_URL}/api/congestion/`);
      let rows = res.data;

      if (Array.isArray(rows) && rows.length > 0) {
        // Normalise field names (API returns snake_case keys)
        const normalised = rows.map(item => ({
          road: item.road || item.road_name || 'Unknown Road',
          area: item.area || item.location || 'Unknown Area',
          time: item.time || item.peak_time || '—',
          congestion_level: (item.congestion_level || item.congestionLevel || 'Unknown').toLowerCase(),
          vehicles_per_hour: item.vehicles_per_hour || item.vehiclesPerHour || 0,
          trend: item.trend || 'stable',
          is_static: false,
        }));
        setLiveData(normalised);
        setUsingStatic(false);
      } else {
        // API returned empty — try to build from TrafficAnalysis overview
        const overviewRes = await axios.get(`${API_BASE_URL}/api/analyze/`);
        const overview = overviewRes.data;

        // Build synthetic rows from peak_hours_data if present
        const areas = overview?.peak_hours_data || overview?.areas || [];
        if (areas.length > 0) {
          const synthesised = areas.map(area => ({
            road: `${area.name || 'Unknown'} Road`,
            area: area.name || 'Unknown Area',
            time: area.morning_peak || '—',
            congestion_level: area.morning_volume > 1000 ? 'high' : area.morning_volume > 500 ? 'medium' : 'low',
            vehicles_per_hour: area.morning_volume || 0,
            trend: 'stable',
            is_static: false,
          }));
          setLiveData(synthesised);
          setUsingStatic(false);
        } else {
          // Fall back to static demo data
          setLiveData(STATIC_DATA);
          setUsingStatic(true);
        }
      }
    } catch (err) {
      console.error('Congestion API error:', err);
      setApiError('Could not reach the server. Showing sample demonstration data.');
      setLiveData(STATIC_DATA);
      setUsingStatic(true);
    } finally {
      setLoading(false);
      setLastFetched(new Date());
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // ── Filtering ────────────────────────────────────────────────────────────────

  const visibleData = liveData.filter(row => {
    if (levelFilter !== 'all' && row.congestion_level !== levelFilter) return false;
    if (timeFilter === 'morning') {
      const t = (row.time || '').toLowerCase();
      return t.includes('am') || t.includes('morning') || t.match(/^[0-9]:/) || t.startsWith('0');
    }
    if (timeFilter === 'evening') {
      const t = (row.time || '').toLowerCase();
      return t.includes('pm') || t.includes('evening') || t.includes('afternoon');
    }
    return true;
  });

  // ── Stats ────────────────────────────────────────────────────────────────────

  const totalRoads   = visibleData.length;
  const highCount    = visibleData.filter(r => ['high', 'severe'].includes(r.congestion_level)).length;
  const mediumCount  = visibleData.filter(r => r.congestion_level === 'medium').length;
  const avgVph       = totalRoads > 0
    ? Math.round(visibleData.reduce((s, r) => s + (r.vehicles_per_hour || 0), 0) / totalRoads)
    : 0;
  const maxVph       = totalRoads > 0
    ? Math.max(...visibleData.map(r => r.vehicles_per_hour || 0))
    : 1;

  // ── Render ───────────────────────────────────────────────────────────────────

  return (
    <>
      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        tr:hover > td { background: #f8fafc !important; }
      `}</style>

      <div style={styles.page}>

        {/* ── Header ── */}
        <header style={styles.header}>
          <h1 style={styles.headerTitle}>Traffic Monitor</h1>
          <p style={styles.headerSub}>Congestion status and peak traffic information from processed videos</p>
        </header>

        {/* ── Banners ── */}
        {apiError && (
          <div style={styles.banner('warn')}>
            <span>⚠️</span>
            <span>{apiError}</span>
          </div>
        )}
        {!apiError && usingStatic && (
          <div style={styles.banner('warn')}>
            <span>ℹ️</span>
            <span>No live traffic analyses found. Process videos to populate real congestion data. The table below shows sample data for demonstration.</span>
          </div>
        )}
        {!usingStatic && !loading && (
          <div style={styles.banner('ok')}>
            <span>✅</span>
            <span>
              Showing live data from {liveData.length} analysed location{liveData.length !== 1 ? 's' : ''}.
              {lastFetched && ` Last updated: ${lastFetched.toLocaleTimeString()}`}
            </span>
          </div>
        )}

        {/* ── Top bar: title + controls ── */}
        <div style={styles.topBar}>
          <h2 style={styles.sectionTitle}>Congested Roads</h2>
          <div style={styles.controls}>
            <select style={styles.select} value={levelFilter} onChange={e => setLevelFilter(e.target.value)}>
              <option value="all">All Levels</option>
              <option value="severe">Severe</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
              <option value="very_low">Very Low</option>
              <option value="none">None</option>
            </select>
            <select style={styles.select} value={timeFilter} onChange={e => setTimeFilter(e.target.value)}>
              <option value="all">All Day</option>
              <option value="morning">Morning</option>
              <option value="evening">Evening / Afternoon</option>
            </select>
            <button
              style={styles.refreshBtn}
              onClick={fetchData}
              title="Refresh data"
            >
              🔄 Refresh
            </button>
          </div>
        </div>

        {/* ── Stat Cards ── */}
        {!loading && (
          <div style={styles.statsRow}>
            <div style={styles.statCard}>
              <div style={styles.statLabel}>Roads Monitored</div>
              <div style={styles.statValue}>{totalRoads}</div>
              <div style={styles.statSub}>{usingStatic ? 'sample entries' : 'from video analyses'}</div>
            </div>
            <div style={styles.statCard}>
              <div style={styles.statLabel}>Highly Congested</div>
              <div style={{ ...styles.statValue, color: highCount > 0 ? '#dc2626' : '#0f172a' }}>{highCount}</div>
              <div style={styles.statSub}>high or severe level</div>
            </div>
            <div style={styles.statCard}>
              <div style={styles.statLabel}>Moderate</div>
              <div style={{ ...styles.statValue, color: mediumCount > 0 ? '#d97706' : '#0f172a' }}>{mediumCount}</div>
              <div style={styles.statSub}>medium level</div>
            </div>
            <div style={styles.statCard}>
              <div style={styles.statLabel}>Avg Vehicles/Hour</div>
              <div style={styles.statValue}>{avgVph.toLocaleString()}</div>
              <div style={styles.statSub}>across visible roads</div>
            </div>
          </div>
        )}

        {/* ── Main Table Card ── */}
        <div style={styles.card}>
          <div style={styles.cardHeader}>
            <h3 style={styles.cardTitle}>Road Congestion Overview</h3>
            {usingStatic ? (
              <span style={{ ...styles.badge, background: '#fef3c7', color: '#92400e' }}>Sample Data</span>
            ) : (
              <span style={{ ...styles.badge, background: '#d1fae5', color: '#065f46' }}>Live Data</span>
            )}
          </div>

          {loading ? (
            <div style={styles.loadBox}>
              <div style={styles.spinner} />
              <span>Loading congestion data…</span>
            </div>
          ) : visibleData.length === 0 ? (
            <div style={styles.emptyState}>
              <div style={{ fontSize: '40px', marginBottom: '12px' }}>🛣️</div>
              <div style={{ fontWeight: '600', color: '#374151', marginBottom: '6px' }}>No roads match your filters</div>
              <div style={{ fontSize: '13px' }}>Try adjusting the congestion level or time-of-day filter.</div>
            </div>
          ) : (
            <div style={styles.tableWrap}>
              <table style={styles.table}>
                <thead>
                  <tr>
                    <th style={styles.th}>Road / Area</th>
                    <th style={styles.th}>Peak Time</th>
                    <th style={styles.th}>Congestion Level</th>
                    <th style={styles.th}>Vehicles / Hour</th>
                    <th style={styles.th}>Trend</th>
                    <th style={styles.th}>Source</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleData.map((row, idx) => {
                    const cMeta = getCongestionMeta(row.congestion_level);
                    const tMeta = getTrendMeta(row.trend);
                    const barPct = maxVph > 0 ? Math.min(100, (row.vehicles_per_hour / maxVph) * 100) : 0;

                    return (
                      <tr key={idx}>
                        <td style={styles.td}>
                          <div style={styles.roadName}>{row.road}</div>
                          <div style={styles.areaName}>{row.area}</div>
                        </td>

                        <td style={styles.td}>
                          <span style={{ fontVariantNumeric: 'tabular-nums' }}>{row.time}</span>
                        </td>

                        <td style={styles.td}>
                          <span style={{
                            ...styles.congestionBadge,
                            background: cMeta.bg,
                            color: cMeta.color,
                          }}>
                            <span style={{ ...styles.dot, background: cMeta.dot }} />
                            {cMeta.label}
                          </span>
                        </td>

                        <td style={styles.td}>
                          <div style={styles.vphBar}>
                            <span style={styles.vphNum}>{(row.vehicles_per_hour || 0).toLocaleString()}</span>
                            <div style={styles.barTrack}>
                              <div style={{
                                height: '100%',
                                width: `${barPct}%`,
                                background: cMeta.bar,
                                borderRadius: '4px',
                                transition: 'width 0.6s ease',
                              }} />
                            </div>
                          </div>
                        </td>

                        <td style={styles.td}>
                          <span style={{ ...styles.trendCell, color: tMeta.color }}>
                            <span style={{ fontSize: '16px' }}>{tMeta.icon}</span>
                            {tMeta.label}
                          </span>
                        </td>

                        <td style={styles.td}>
                          {row.is_static ? (
                            <span style={{ fontSize: '12px', color: '#94a3b8', fontStyle: 'italic' }}>Sample</span>
                          ) : (
                            <span style={{ fontSize: '12px', color: '#22c55e', fontWeight: '600' }}>Live</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

      </div>
    </>
  );
}