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
  unknown:  { label: 'Unknown',  bg: '#f3f4f6', color: '#6b7280', dot: '#9ca3af', bar: '#9ca3af' },
};

function getCongestionMeta(level) {
  if (!level) return CONGESTION_META.none;
  const key = level.toLowerCase().replace(/\s+/g, '_');
  return CONGESTION_META[key] || CONGESTION_META.unknown;
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

/**
 * Formats a date string from the backend into a readable form.
 * Handles:
 *   "2025-01-15"          → "January 15, 2025"
 *   "Jan 15, 2025"        → "January 15, 2025"
 *   "2025-01-15T00:00:00" → "January 15, 2025"
 */
function formatDate(raw) {
  if (!raw) return '—';
  try {
    // Append time component so Date() doesn't shift by timezone offset
    const iso = raw.includes('T') ? raw : `${raw}T00:00:00`;
    const d = new Date(iso);
    if (isNaN(d.getTime())) return raw; // unparseable — return as-is
    return d.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  } catch {
    return raw;
  }
}

// ── Styles ─────────────────────────────────────────────────────────────────────

const s = {
  page: {
    minHeight: '100vh',
    background: '#f8fafc',
    padding: '32px 36px',
    fontFamily: "'DM Sans', 'Segoe UI', sans-serif",
  },
  header: { marginBottom: '36px' },
  headerTitle: {
    fontSize: '28px', fontWeight: '700', color: '#0f172a',
    margin: '0 0 6px 0', letterSpacing: '-0.5px',
  },
  headerSub: { color: '#64748b', margin: 0, fontSize: '15px' },
  topBar: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    marginBottom: '24px', flexWrap: 'wrap', gap: '12px',
  },
  sectionTitle: { fontSize: '20px', fontWeight: '600', color: '#1e293b', margin: 0 },
  controls: { display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' },
  select: {
    padding: '8px 14px', borderRadius: '8px', border: '1.5px solid #e2e8f0',
    background: '#fff', color: '#334155', fontSize: '14px', fontWeight: '500',
    cursor: 'pointer', outline: 'none',
  },
  refreshBtn: {
    padding: '8px 16px', borderRadius: '8px', border: '1.5px solid #e2e8f0',
    background: '#fff', color: '#334155', fontSize: '14px', fontWeight: '500',
    cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px',
  },
  statsRow: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
    gap: '16px', marginBottom: '28px',
  },
  statCard: {
    background: '#fff', border: '1.5px solid #e2e8f0',
    borderRadius: '12px', padding: '18px 20px',
  },
  statLabel: {
    fontSize: '12px', fontWeight: '600', color: '#94a3b8',
    textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '6px',
  },
  statValue: { fontSize: '26px', fontWeight: '700', color: '#0f172a', lineHeight: 1 },
  statSub:   { fontSize: '12px', color: '#64748b', marginTop: '4px' },
  card: {
    background: '#fff', borderRadius: '14px', border: '1.5px solid #e2e8f0',
    overflow: 'hidden', boxShadow: '0 1px 4px rgba(0,0,0,0.04)',
  },
  cardHeader: {
    padding: '20px 24px 16px', borderBottom: '1px solid #f1f5f9',
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
  },
  cardTitle: { fontSize: '16px', fontWeight: '600', color: '#1e293b', margin: 0 },
  badge:     { fontSize: '12px', padding: '3px 10px', borderRadius: '20px', fontWeight: '600' },
  tableWrap: { overflowX: 'auto' },
  table:     { width: '100%', borderCollapse: 'collapse' },
  th: {
    padding: '12px 20px', textAlign: 'left', fontSize: '12px',
    fontWeight: '600', color: '#64748b', textTransform: 'uppercase',
    letterSpacing: '0.05em', background: '#f8fafc',
    borderBottom: '1px solid #e2e8f0', whiteSpace: 'nowrap',
  },
  td: {
    padding: '16px 20px', fontSize: '14px', color: '#334155',
    borderBottom: '1px solid #f1f5f9', verticalAlign: 'middle',
  },
  roadName: { fontWeight: '600', color: '#0f172a', fontSize: '14px' },
  areaName: { fontSize: '12px', color: '#64748b', marginTop: '2px' },
  congestionBadge: {
    display: 'inline-flex', alignItems: 'center', gap: '6px',
    padding: '4px 12px', borderRadius: '20px',
    fontSize: '12px', fontWeight: '600', whiteSpace: 'nowrap',
  },
  dot:      { width: '7px', height: '7px', borderRadius: '50%', flexShrink: 0 },
  trendCell:{ display: 'inline-flex', alignItems: 'center', gap: '5px', fontSize: '13px', fontWeight: '500' },
  vphBar:   { display: 'flex', flexDirection: 'column', gap: '4px', minWidth: '120px' },
  vphNum:   { fontWeight: '700', color: '#0f172a', fontSize: '14px' },
  barTrack: { height: '4px', borderRadius: '4px', background: '#e2e8f0', overflow: 'hidden' },
  emptyState: { textAlign: 'center', padding: '64px 32px', color: '#94a3b8' },
  banner: (type) => ({
    background: type === 'warn' ? '#fffbeb' : '#f0fdf4',
    border: `1px solid ${type === 'warn' ? '#fde68a' : '#bbf7d0'}`,
    color: type === 'warn' ? '#78350f' : '#14532d',
    padding: '12px 16px', borderRadius: '8px', fontSize: '13px',
    marginBottom: '20px', display: 'flex', gap: '8px', alignItems: 'flex-start',
  }),
  loadBox: {
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    height: '320px', flexDirection: 'column', gap: '14px',
    color: '#64748b', fontSize: '15px',
  },
  spinner: {
    width: '32px', height: '32px',
    border: '3px solid #e2e8f0', borderTop: '3px solid #3b82f6',
    borderRadius: '50%', animation: 'spin 0.8s linear infinite',
  },
};

// ── Component ──────────────────────────────────────────────────────────────────

export default function CongestedRoads() {
  const [timeFilter,  setTimeFilter]  = useState('all');
  const [levelFilter, setLevelFilter] = useState('all');
  const [sortBy,      setSortBy]      = useState('congestion');
  const [liveData,    setLiveData]    = useState([]);
  const [loading,     setLoading]     = useState(true);
  const [apiError,    setApiError]    = useState(null);
  const [lastFetched, setLastFetched] = useState(null);

  const LEVEL_ORDER = { severe: 0, high: 1, medium: 2, low: 3, very_low: 4, none: 5 };

  // ── Fetch ────────────────────────────────────────────────────────────────────

  const fetchData = useCallback(async () => {
    setLoading(true);
    setApiError(null);
    try {
      const res  = await axios.get(`${API_BASE_URL}/api/congestion/`);
      const rows = res.data;

      if (Array.isArray(rows) && rows.length > 0) {
        const normalised = rows.map(item => ({
          road:              item.road              || item.road_name || 'Unknown Road',
          area:              item.area              || item.location  || 'Unknown Area',
          time:              item.time              || '—',
          video_date:        item.video_date        || '',
          congestion_level:  (item.congestion_level || 'none').toLowerCase(),
          vehicles_per_hour: item.vehicles_per_hour || 0,
          total_vehicles:    item.total_vehicles    || 0,
          trend:             item.trend             || 'stable',
          congestion_index:  item.congestion_index  ?? null,
          analysis_id:       item.analysis_id       || null,
        }));
        setLiveData(normalised);
        setApiError(null);
      } else {
        // No data case - set empty array instead of static data
        setLiveData([]);
        setApiError('No congestion data available. Please upload and process videos first.');
      }
    } catch (err) {
      console.error('Congestion API error:', err);
      setApiError('Could not reach the server. Please check your connection and try again.');
      setLiveData([]); // Set empty array on error
    } finally {
      setLoading(false);
      setLastFetched(new Date());
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  // ── Filter & sort ─────────────────────────────────────────────────────────────

  const visibleData = [...liveData]
    .filter(row => {
      if (levelFilter !== 'all' && row.congestion_level !== levelFilter) return false;
      if (timeFilter === 'morning') return (row.time || '').toLowerCase().includes('am');
      if (timeFilter === 'evening') return (row.time || '').toLowerCase().includes('pm');
      return true;
    })
    .sort((a, b) => {
      if (sortBy === 'congestion')
        return (LEVEL_ORDER[a.congestion_level] ?? 9) - (LEVEL_ORDER[b.congestion_level] ?? 9);
      if (sortBy === 'vph')
        return b.vehicles_per_hour - a.vehicles_per_hour;
      if (sortBy === 'date')
        return (b.video_date || '').localeCompare(a.video_date || '');
      return 0;
    });

  // ── Stats ─────────────────────────────────────────────────────────────────────

  const totalRoads  = visibleData.length;
  const highCount   = visibleData.filter(r => ['high', 'severe'].includes(r.congestion_level)).length;
  const mediumCount = visibleData.filter(r => r.congestion_level === 'medium').length;
  const maxVph      = totalRoads > 0 ? Math.max(...visibleData.map(r => r.vehicles_per_hour || 0)) : 1;
  const avgVph      = totalRoads > 0
    ? Math.round(visibleData.reduce((s, r) => s + (r.vehicles_per_hour || 0), 0) / totalRoads)
    : 0;

  // ── Render ────────────────────────────────────────────────────────────────────

  return (
    <>
      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        tr:hover > td { background: #f8fafc !important; }
      `}</style>

      <div style={s.page}>

        {/* Header */}
        <header style={s.header}>
          <h1 style={s.headerTitle}>Traffic Monitor</h1>
          <p style={s.headerSub}>Congestion levels from processed video analyses</p>
        </header>

        {/* Error Banner */}
        {apiError && (
          <div style={s.banner('warn')}>
            <span>⚠️</span>
            <span>{apiError}</span>
          </div>
        )}

        {/* Success Banner */}
        {!apiError && !loading && liveData.length > 0 && (
          <div style={s.banner('ok')}>
            <span>✅</span>
            <span>
              Showing real congestion levels from {liveData.length} video
              {liveData.length !== 1 ? ' analyses' : ' analysis'}.
              {lastFetched && ` Last refreshed: ${lastFetched.toLocaleTimeString()}`}
            </span>
          </div>
        )}

        {/* Controls */}
        <div style={s.topBar}>
          <h2 style={s.sectionTitle}>Road Congestion Overview</h2>
          <div style={s.controls}>
            <select style={s.select} value={levelFilter} onChange={e => setLevelFilter(e.target.value)}>
              <option value="all">All Levels</option>
              <option value="severe">Severe</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
              <option value="very_low">Very Low</option>
              <option value="none">None</option>
            </select>
            <select style={s.select} value={timeFilter} onChange={e => setTimeFilter(e.target.value)}>
              <option value="all">All Times</option>
              <option value="morning">Morning (AM)</option>
              <option value="evening">Evening / PM</option>
            </select>
            <select style={s.select} value={sortBy} onChange={e => setSortBy(e.target.value)}>
              <option value="congestion">Sort: Congestion</option>
              <option value="vph">Sort: Vehicles / hr</option>
              <option value="date">Sort: Date</option>
            </select>
            <button style={s.refreshBtn} onClick={fetchData} disabled={loading} title="Refresh">
              {loading ? '⟳ Loading...' : '↻ Refresh'}
            </button>
          </div>
        </div>

        {/* Stat Cards - only show if there's data */}
        {!loading && liveData.length > 0 && (
          <div style={s.statsRow}>
            <div style={s.statCard}>
              <div style={s.statLabel}>Analyses Shown</div>
              <div style={s.statValue}>{totalRoads}</div>
              <div style={s.statSub}>from processed videos</div>
            </div>
            <div style={s.statCard}>
              <div style={s.statLabel}>High / Severe</div>
              <div style={{ ...s.statValue, color: highCount > 0 ? '#dc2626' : '#0f172a' }}>
                {highCount}
              </div>
              <div style={s.statSub}>congestion events</div>
            </div>
            <div style={s.statCard}>
              <div style={s.statLabel}>Medium</div>
              <div style={{ ...s.statValue, color: mediumCount > 0 ? '#d97706' : '#0f172a' }}>
                {mediumCount}
              </div>
              <div style={s.statSub}>congestion events</div>
            </div>
            <div style={s.statCard}>
              <div style={s.statLabel}>Avg Vehicles / hr</div>
              <div style={s.statValue}>{avgVph.toLocaleString()}</div>
              <div style={s.statSub}>across visible rows</div>
            </div>
          </div>
        )}

        {/* Main Table */}
        <div style={s.card}>
          <div style={s.cardHeader}>
            <h3 style={s.cardTitle}>Congestion Details</h3>
            {liveData.length > 0 && (
              <span style={{ ...s.badge, background: '#d1fae5', color: '#065f46' }}>Live Data</span>
            )}
          </div>

          {loading ? (
            <div style={s.loadBox}>
              <div style={s.spinner} />
              <span>Loading congestion data…</span>
            </div>
          ) : visibleData.length === 0 ? (
            <div style={s.emptyState}>
              <div style={{ fontSize: '40px', marginBottom: '12px' }}>🛣️</div>
              <div style={{ fontWeight: '600', color: '#374151', marginBottom: '6px' }}>
                {liveData.length === 0 ? 'No congestion data available' : 'No records match your filters'}
              </div>
              <div style={{ fontSize: '13px' }}>
                {liveData.length === 0 
                  ? 'Upload and process videos to see congestion data.'
                  : 'Adjust the congestion level or time filter above.'}
              </div>
            </div>
          ) : (
            <div style={s.tableWrap}>
              <table style={s.table}>
                <thead>
                  <tr>
                    <th style={s.th}>Location</th>
                    <th style={s.th}>Date</th>
                    <th style={s.th}>Time Range</th>
                    <th style={s.th}>Congestion Level</th>
                    <th style={s.th}>Vehicles / Hour</th>
                    <th style={s.th}>Trend</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleData.map((row, idx) => {
                    const cMeta  = getCongestionMeta(row.congestion_level);
                    const tMeta  = getTrendMeta(row.trend);
                    const barPct = maxVph > 0
                      ? Math.min(100, (row.vehicles_per_hour / maxVph) * 100)
                      : 0;

                    return (
                      <tr key={row.analysis_id || idx}>

                        {/* Location */}
                        <td style={s.td}>
                          <div style={s.roadName}>{row.road}</div>
                          <div style={s.areaName}>{row.area}</div>
                        </td>

                        {/* Date — properly formatted */}
                        <td style={s.td}>
                          <span style={{ fontSize: '13px', color: '#475569' }}>
                            {formatDate(row.video_date)}
                          </span>
                        </td>

                        {/* Time range */}
                        <td style={s.td}>
                          <span style={{ fontVariantNumeric: 'tabular-nums', fontSize: '13px' }}>
                            {row.time}
                          </span>
                        </td>

                        {/* Congestion level badge */}
                        <td style={s.td}>
                          <span style={{
                            ...s.congestionBadge,
                            background: cMeta.bg,
                            color:      cMeta.color,
                          }}>
                            <span style={{ ...s.dot, background: cMeta.dot }} />
                            {cMeta.label}
                          </span>
                          {row.congestion_index != null && (
                            <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '3px' }}>
                              Index: {(row.congestion_index * 100).toFixed(0)}%
                            </div>
                          )}
                        </td>

                        {/* Vehicles / hour bar */}
                        <td style={s.td}>
                          <div style={s.vphBar}>
                            <span style={s.vphNum}>
                              {(row.vehicles_per_hour || 0).toLocaleString()}
                            </span>
                            <div style={s.barTrack}>
                              <div style={{
                                height: '100%',
                                width: `${barPct}%`,
                                background: cMeta.bar,
                                borderRadius: '4px',
                                transition: 'width 0.6s ease',
                              }} />
                            </div>
                            {row.total_vehicles > 0 && (
                              <span style={{ fontSize: '11px', color: '#94a3b8' }}>
                                {row.total_vehicles.toLocaleString()} total detected
                              </span>
                            )}
                          </div>
                        </td>

                        {/* Trend */}
                        <td style={s.td}>
                          <span style={{ ...s.trendCell, color: tMeta.color }}>
                            <span style={{ fontSize: '16px' }}>{tMeta.icon}</span>
                            {tMeta.label}
                          </span>
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