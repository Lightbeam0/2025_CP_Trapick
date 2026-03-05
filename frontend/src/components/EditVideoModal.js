// src/components/EditVideoModal.js
import React, { useState, useEffect, useRef } from "react";
import axios from "axios";

const API_BASE_URL = process.env.NODE_ENV === "development"
  ? "http://127.0.0.1:8000"
  : "";

// ─── helpers ─────────────────────────────────────────────────────────────────
const fmtDate = (v) => {
  if (!v) return "";
  if (/^\d{4}-\d{2}-\d{2}$/.test(v)) return v;
  try {
    const d = new Date(v);
    if (!isNaN(d)) {
      // Use local timezone (toISOString() gives UTC which can be yesterday in UTC+8)
      return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
    }
  } catch {}
  return "";
};

const fmtTime = (v) => {
  if (!v) return "";
  if (/^\d{1,2}:\d{2}$/.test(v)) return v.padStart(5, "0");
  if (/^\d{1,2}:\d{2}:\d{2}$/.test(v)) return v.slice(0, 5);
  if (v.includes("T")) return v.split("T")[1].slice(0, 5);
  const m = v.match(/(\d{1,2}):(\d{2})/);
  if (m) return `${m[1].padStart(2, "0")}:${m[2]}`;
  return "";
};

const timeToMinutes = (t) => {
  if (!t) return null;
  const [h, m] = t.split(":").map(Number);
  return h * 60 + m;
};

const minutesToTime = (mins) => {
  const m = ((mins % (24 * 60)) + 24 * 60) % (24 * 60);
  return `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
};

const formatDuration = (seconds) => {
  if (!seconds) return "";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.round(seconds % 60);
  if (h > 0) return `${h}h ${m}m ${s}s`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
};

// Browser-native duration extraction — no upload, reads metadata only
const detectVideoDuration = (file) =>
  new Promise((resolve) => {
    const url = URL.createObjectURL(file);
    const vid = document.createElement("video");
    vid.preload = "metadata";
    vid.onloadedmetadata = () => {
      URL.revokeObjectURL(url);
      resolve(isFinite(vid.duration) && vid.duration > 0 ? Math.round(vid.duration) : null);
    };
    vid.onerror = () => { URL.revokeObjectURL(url); resolve(null); };
    vid.src = url;
  });

// ─── ConflictBanner ──────────────────────────────────────────────────────────
const ConflictBanner = ({ conflicts }) => (
  <div style={{
    background: "#1c0a0a", border: "1px solid #7f1d1d",
    borderLeft: "3px solid #ef4444", borderRadius: 6,
    padding: "10px 14px", marginBottom: 14,
  }}>
    <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
      <span>⛔</span>
      <span style={{ color: "#fca5a5", fontWeight: 600, fontSize: 13 }}>
        Time slot conflict
      </span>
    </div>
    {conflicts.map((c, i) => (
      <div key={i} style={{ fontSize: 12, color: "#fca5a5", opacity: 0.85, paddingLeft: 20, marginTop: 2 }}>
        • <strong>{c.filename}</strong> — {c.start_time}–{c.end_time}
        {" "}({c.overlap_minutes} min overlap)
      </div>
    ))}
    <div style={{ fontSize: 11, color: "#f87171", opacity: 0.6, marginTop: 6, paddingLeft: 20 }}>
      Choose a different time range.
    </div>
  </div>
);

// ─── main component ───────────────────────────────────────────────────────────
function EditVideoModal({ isOpen, onClose, video, onVideoUpdated, locations = [] }) {
  const [loading, setLoading]         = useState(false);
  const [error, setError]             = useState(null);
  const [success, setSuccess]         = useState(null);
  const [conflicts, setConflicts]     = useState([]);
  const [checking, setChecking]       = useState(false);
  const conflictTimer                 = useRef(null);

  // duration
  const [duration, setDuration]             = useState(null);   // seconds
  const [detecting, setDetecting]           = useState(false);
  const [autoEndApplied, setAutoEndApplied] = useState(false);
  const [durationSource, setDurationSource] = useState(null);   // "db" | "detected"
  const fileInputRef                        = useRef(null);

  const [form, setForm] = useState({
    title: "", video_date: "", video_start_time: "", video_end_time: "",
  });

  // ── Init from video prop ──────────────────────────────────────────────────
  useEffect(() => {
    if (!video) return;
    setForm({
      title:            video.title || video.filename || "",
      video_date:       fmtDate(video.video_date),
      video_start_time: fmtTime(video.video_start_time || video.start_time),
      video_end_time:   fmtTime(video.video_end_time   || video.end_time),
    });
    setError(null);
    setSuccess(null);
    setConflicts([]);
    setAutoEndApplied(false);

    if (video.duration_seconds > 0) {
      // List payload already has it
      setDuration(Math.round(video.duration_seconds));
      setDurationSource("db");
    } else {
      // List API omitted it — silently fetch from server
      setDuration(null);
      setDurationSource(null);
      fetchDurationFromServer(video.id);
    }
  }, [video]);

  // Fetch duration_seconds from server if the list payload didn't include it
  const fetchDurationFromServer = async (videoId) => {
    try {
      const res = await axios.get(`${API_BASE_URL}/api/videos/${videoId}/manage/`);
      const d = res.data?.video?.duration_seconds || res.data?.duration_seconds;
      if (d > 0) {
        setDuration(Math.round(d));
        setDurationSource("db");
      }
    } catch {
      // silently ignore — file picker fallback still available
    }
  };

  const set = (field, value) => setForm(prev => ({ ...prev, [field]: value }));

  // ── Auto-compute end time when start or duration changes ─────────────────
  // Always recalculate end time whenever start time changes (if we know duration).
  // This is the core behaviour: change start → end shifts by the same duration.
  useEffect(() => {
    if (!form.video_start_time || !duration) return;
    const startMins = timeToMinutes(form.video_start_time);
    if (startMins === null) return;
    const computed = minutesToTime(startMins + Math.ceil(duration / 60));
    setForm(prev => ({ ...prev, video_end_time: computed }));
    setAutoEndApplied(true);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [form.video_start_time, duration]);

  // ── File picker — detect duration from video file metadata ───────────────
  const handleFileSelect = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setDetecting(true);
    try {
      const detected = await detectVideoDuration(file);
      if (detected) {
        setDuration(detected);
        setDurationSource("detected");
        setAutoEndApplied(false); // let the effect re-trigger

        // If start time already set, immediately compute end
        if (form.video_start_time) {
          const startMins = timeToMinutes(form.video_start_time);
          const computed  = minutesToTime(startMins + Math.ceil(detected / 60));
          setForm(prev => ({ ...prev, video_end_time: computed }));
          setAutoEndApplied(true);
        }
      } else {
        setError("Could not detect duration from this file.");
      }
    } finally {
      setDetecting(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  // ── Conflict check ────────────────────────────────────────────────────────
  useEffect(() => {
    clearTimeout(conflictTimer.current);
    if (!form.video_start_time || !form.video_end_time || !form.video_date || !video) {
      setConflicts([]); return;
    }
    const locationId = video.location?.id;
    if (!locationId) { setConflicts([]); return; }

    conflictTimer.current = setTimeout(async () => {
      try {
        setChecking(true);
        const res = await axios.get(`${API_BASE_URL}/api/videos/check-conflict/`, {
          params: {
            location_id:      locationId,
            video_date:       form.video_date,
            start_time:       form.video_start_time,
            end_time:         form.video_end_time,
            exclude_video_id: String(video.id),
          },
        });
        setConflicts(res.data.has_conflict ? res.data.conflicts : []);
      } catch { setConflicts([]); }
      finally  { setChecking(false); }
    }, 450);
  }, [form.video_start_time, form.video_end_time, form.video_date, video]);

  // ── Submit ────────────────────────────────────────────────────────────────
  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!video?.id)           return setError("No video selected.");
    if (conflicts.length > 0) return setError("Resolve conflicts first.");

    setLoading(true); setError(null); setSuccess(null);

    const payload = {};
    if (form.title !== (video.title || video.filename || ""))
      payload.title = form.title;
    if (form.video_date !== fmtDate(video.video_date))
      payload.video_date = form.video_date;
    if (form.video_start_time !== fmtTime(video.video_start_time || video.start_time || ""))
      payload.video_start_time = form.video_start_time;
    if (form.video_end_time !== fmtTime(video.video_end_time || video.end_time || ""))
      payload.video_end_time = form.video_end_time;

    if (Object.keys(payload).length === 0) {
      setSuccess("No changes detected."); setTimeout(onClose, 1500);
      setLoading(false); return;
    }

    try {
      const res = await axios.put(
        `${API_BASE_URL}/api/videos/${video.id}/manage/`,
        payload,
        { headers: { "Content-Type": "application/json" } }
      );
      const updatedVideo = res.data.video;
      setSuccess("Video updated successfully!");
      if (updatedVideo) {
        setForm({
          title:            updatedVideo.title || "",
          video_date:       fmtDate(updatedVideo.video_date),
          video_start_time: fmtTime(updatedVideo.video_start_time),
          video_end_time:   fmtTime(updatedVideo.video_end_time),
        });
      }
      setTimeout(() => onVideoUpdated({ ...updatedVideo, _updatedGroup: res.data.group }), 1200);
    } catch (err) {
      if (err.response?.status === 409) {
        setConflicts(err.response.data.conflicts || []);
        setError(err.response.data.detail || "Time slot conflict detected.");
      } else {
        setError(err.response?.data?.error || err.message || "Failed to update video.");
      }
    } finally { setLoading(false); }
  };

  // ── Delete ────────────────────────────────────────────────────────────────
  const handleDelete = async () => {
    if (!video?.id) return;
    if (!window.confirm(`Delete "${video.title || video.filename}"? Cannot be undone.`)) return;
    setLoading(true); setError(null);
    try {
      await axios.delete(`${API_BASE_URL}/api/videos/${video.id}/delete/`);
      onVideoUpdated({ ...video, _deleted: true });
    } catch (err) {
      setError(err.response?.data?.error || err.message || "Failed to delete.");
      setLoading(false);
    }
  };

  const handleClose = () => { if (!loading) onClose(); };

  if (!isOpen || !video) return null;

  const canSave     = !loading && !checking && conflicts.length === 0;
  const hasDbDuration = video.duration_seconds > 0;

  const inputStyle = {
    width: "100%", boxSizing: "border-box", padding: "9px 12px",
    background: "#1e293b", border: "1px solid #334155",
    borderRadius: 6, color: "#e2e8f0", fontSize: 14,
    fontFamily: "inherit", outline: "none", transition: "border-color .15s",
  };
  const labelStyle = {
    display: "block", fontSize: 11, fontWeight: 600,
    letterSpacing: ".06em", textTransform: "uppercase",
    color: "#64748b", marginBottom: 5,
  };

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&display=swap');
        .evm-overlay{position:fixed;inset:0;z-index:1100;background:rgba(0,0,0,.75);backdrop-filter:blur(4px);display:flex;align-items:center;justify-content:center;padding:16px;animation:evm-in .15s ease;}
        @keyframes evm-in{from{opacity:0}to{opacity:1}}
        .evm-modal{background:#0f172a;border:1px solid #1e293b;border-radius:12px;width:100%;max-width:500px;max-height:90vh;overflow-y:auto;padding:24px;color:#e2e8f0;font-family:'DM Sans',ui-sans-serif,system-ui,sans-serif;animation:evm-slide .2s ease;scrollbar-width:thin;scrollbar-color:#334155 transparent;}
        @keyframes evm-slide{from{transform:translateY(10px);opacity:0}to{transform:translateY(0);opacity:1}}
        .evm-input:focus{border-color:#3b82f6!important;box-shadow:0 0 0 3px rgba(59,130,246,.15);}
        .evm-input:disabled{opacity:.45;cursor:not-allowed;}
        .evm-input-auto{border-color:#22c55e!important;}
        .evm-spinner{width:13px;height:13px;border-radius:50%;border:2px solid rgba(255,255,255,.2);border-top-color:#fff;animation:spin .7s linear infinite;display:inline-block;}
        @keyframes spin{to{transform:rotate(360deg)}}
        .pill{display:inline-flex;align-items:center;gap:3px;font-size:10px;padding:2px 7px;border-radius:10px;font-weight:600;letter-spacing:.03em;margin-left:6px;vertical-align:middle;}
        .pill-green{background:#052e16;color:#86efac;border:1px solid #166534;}
        .pill-blue{background:#0c1a2e;color:#60a5fa;border:1px solid #1e3a5f;}
        .pill-amber{background:#1c1400;color:#fbbf24;border:1px solid #78350f;}
        .detect-btn{margin-top:8px;width:100%;background:#1e293b;border:1px dashed #334155;border-radius:6px;padding:9px 12px;color:#64748b;font-size:12px;font-family:inherit;cursor:pointer;transition:all .15s;display:flex;align-items:center;gap:8px;}
        .detect-btn:hover:not(:disabled){border-color:#3b82f6;color:#93c5fd;background:#0c1a2e;}
        .detect-btn:disabled{cursor:not-allowed;opacity:.5;}
        input[type=date]::-webkit-calendar-picker-indicator,input[type=time]::-webkit-calendar-picker-indicator{filter:invert(.5);cursor:pointer;}
      `}</style>

      <div className="evm-overlay" onClick={handleClose}>
        <div className="evm-modal" onClick={e => e.stopPropagation()}>

          {/* Header */}
          <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", marginBottom:20 }}>
            <div>
              <h2 style={{ margin:0, fontSize:20, fontWeight:700, color:"#f1f5f9" }}>Edit Video</h2>
              <p style={{ margin:"3px 0 0", fontSize:12, color:"#64748b" }}>
                Changes update grouping &amp; statistics immediately
              </p>
            </div>
            <button onClick={handleClose} disabled={loading} style={{
              background:"#1e293b", border:"1px solid #334155", borderRadius:6,
              color:"#94a3b8", width:32, height:32, fontSize:18, cursor:"pointer",
              display:"flex", alignItems:"center", justifyContent:"center",
            }}>×</button>
          </div>

          {/* File info */}
          <div style={{
            background:"#1e293b", border:"1px solid #334155", borderRadius:8,
            padding:"10px 14px", marginBottom:16, fontSize:13, wordBreak:"break-all",
          }}>
            <span style={{ color:"#64748b", fontSize:11 }}>File: </span>
            <span style={{ color:"#e2e8f0", fontWeight:500 }}>{video.filename}</span>
            {video.processing_status && (
              <span style={{
                marginLeft:8, fontSize:10, padding:"2px 8px", borderRadius:10,
                textTransform:"uppercase",
                background: video.processing_status === "completed" ? "#052e16" : "#1c1917",
                color:      video.processing_status === "completed" ? "#86efac" : "#a8a29e",
                border:     `1px solid ${video.processing_status === "completed" ? "#166534" : "#44403c"}`,
              }}>{video.processing_status}</span>
            )}
          </div>

          {/* Alerts */}
          {success && (
            <div style={{ background:"#052e16", border:"1px solid #166534", borderRadius:6, padding:"10px 14px", color:"#86efac", fontSize:13, marginBottom:14, display:"flex", alignItems:"center", gap:8 }}>
              <span>✅</span> {success}
            </div>
          )}
          {error && !success && (
            <div style={{ background:"#1c0a0a", border:"1px solid #7f1d1d", borderLeft:"3px solid #ef4444", borderRadius:6, padding:"10px 14px", color:"#fca5a5", fontSize:13, marginBottom:14 }}>
              {error}
            </div>
          )}
          {conflicts.length > 0 && <ConflictBanner conflicts={conflicts} />}
          {checking && (
            <div style={{ display:"flex", alignItems:"center", gap:6, fontSize:12, color:"#64748b", marginBottom:10 }}>
              <span className="evm-spinner" /> Checking slot availability…
            </div>
          )}

          <form onSubmit={handleSubmit}>

            {/* Title */}
            <div style={{ marginBottom:14 }}>
              <label style={labelStyle}>Title</label>
              <input className="evm-input" style={inputStyle} type="text"
                value={form.title} onChange={e => set("title", e.target.value)}
                placeholder="Descriptive title" disabled={loading} />
            </div>

            {/* Date */}
            <div style={{ marginBottom:14 }}>
              <label style={labelStyle}>Recording Date</label>
              <input className="evm-input" style={inputStyle} type="date"
                value={form.video_date} onChange={e => set("video_date", e.target.value)}
                disabled={loading} />
              <div style={{ fontSize:11, color:"#475569", marginTop:4 }}>
                Changing the date moves this video to a different day group.
              </div>
            </div>

            {/* ── Duration card ── */}
            <div style={{
              background:"#0a111e", border:"1px solid #1e293b",
              borderRadius:8, padding:"12px 14px", marginBottom:14,
            }}>
              {/* Title row */}
              <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", marginBottom:10 }}>
                <span style={{ fontSize:11, fontWeight:600, color:"#64748b", textTransform:"uppercase", letterSpacing:".06em" }}>
                  Video Duration
                </span>

                {duration ? (
                  <span>
                    <span className="pill pill-green">⏱ {formatDuration(duration)}</span>
                    {durationSource === "db"
                      ? <span className="pill pill-blue">from DB</span>
                      : <span className="pill pill-amber">detected</span>
                    }
                  </span>
                ) : (
                  <span style={{ fontSize:12, color:"#475569" }}>Not available</span>
                )}
              </div>

              {/* What end time will look like */}
              {duration && form.video_start_time && (
                <div style={{
                  background:"#0f172a", borderRadius:6, padding:"7px 10px",
                  fontSize:12, color:"#94a3b8", marginBottom:10,
                  display:"flex", alignItems:"center", gap:6,
                }}>
                  <span>🧮</span>
                  <span>
                    {form.video_start_time} + {formatDuration(duration)} =&nbsp;
                    <strong style={{ color:"#22c55e" }}>
                      {minutesToTime(timeToMinutes(form.video_start_time) + Math.ceil(duration / 60))}
                    </strong>
                  </span>
                </div>
              )}

              {/* File picker — hidden input + styled button */}
              <input
                ref={fileInputRef}
                type="file"
                accept="video/*"
                style={{ display:"none" }}
                onChange={handleFileSelect}
                disabled={detecting || loading}
              />
              <button
                type="button"
                className="detect-btn"
                onClick={() => fileInputRef.current?.click()}
                disabled={detecting || loading}
              >
                {detecting ? (
                  <><span className="evm-spinner" /> Detecting duration…</>
                ) : hasDbDuration ? (
                  <><span>🔄</span><span>Re-select file to override duration</span></>
                ) : (
                  <>
                    <span style={{ fontSize:16 }}>📂</span>
                    <span>
                      Select the video file to detect duration
                      <span style={{ display:"block", fontSize:10, color:"#475569", marginTop:1 }}>
                        Reads metadata locally — nothing is uploaded
                      </span>
                    </span>
                  </>
                )}
              </button>
            </div>

            {/* ── Start / End time ── */}
            <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:12, marginBottom:6 }}>
              <div>
                <label style={labelStyle}>Start Time</label>
                <input
                  className="evm-input"
                  style={inputStyle}
                  type="time"
                  value={form.video_start_time}
                  onChange={e => {
                    set("video_start_time", e.target.value);
                  }}
                  disabled={loading}
                />
              </div>
              <div>
                <label style={labelStyle}>
                  End Time
                  {autoEndApplied && duration && (
                    <span className="pill pill-green">Auto ✨</span>
                  )}
                </label>
                <input
                  className={`evm-input${autoEndApplied ? " evm-input-auto" : ""}`}
                  style={{
                    ...inputStyle,
                    ...(autoEndApplied ? { borderColor:"#22c55e" } : {}),
                  }}
                  type="time"
                  value={form.video_end_time}
                  onChange={e => {
                    setAutoEndApplied(false);
                    set("video_end_time", e.target.value);
                  }}
                  disabled={loading}
                />
              </div>
            </div>

            {/* Contextual hints */}
            {duration && !form.video_start_time && (
              <div style={{ fontSize:11, color:"#94a3b8", marginBottom:12, paddingLeft:2 }}>
                💡 Set a start time — end time will be calculated automatically ({formatDuration(duration)})
              </div>
            )}
            {!duration && form.video_start_time && !form.video_end_time && (
              <div style={{ fontSize:11, color:"#94a3b8", marginBottom:12, paddingLeft:2 }}>
                💡 Select the video file above to auto-detect duration and fill end time
              </div>
            )}

            {/* Location read-only */}
            {video.location && (
              <div style={{
                background:"#0c1a2e", border:"1px solid #1e3a5f",
                borderRadius:6, padding:"10px 14px", margin:"14px 0",
              }}>
                <div style={{ fontSize:11, color:"#3b82f6", marginBottom:3 }}>Location (read-only)</div>
                <div style={{ fontSize:14, fontWeight:600, color:"#60a5fa" }}>
                  {video.location.display_name || video.location.name}
                </div>
                <div style={{ fontSize:11, color:"#1d4ed8", marginTop:3 }}>
                  Re-process the video to change its location.
                </div>
              </div>
            )}

            <div style={{ borderTop:"1px solid #1e293b", margin:"20px 0 16px" }} />

            {/* Actions */}
            <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center" }}>
              <button type="button" onClick={handleDelete} disabled={loading}
                style={{
                  padding:"9px 18px", borderRadius:6, fontSize:14, fontWeight:600,
                  background:"transparent", border:"1px solid #7f1d1d",
                  color:"#f87171", cursor:loading ? "not-allowed" : "pointer",
                  opacity: loading ? 0.5 : 1,
                }}>
                Delete
              </button>
              <div style={{ display:"flex", gap:10 }}>
                <button type="button" onClick={handleClose} disabled={loading}
                  style={{
                    padding:"9px 18px", borderRadius:6, fontSize:14, fontWeight:600,
                    background:"#1e293b", border:"1px solid #334155",
                    color:"#94a3b8", cursor:loading ? "not-allowed" : "pointer",
                  }}>
                  Cancel
                </button>
                <button type="submit" disabled={!canSave}
                  style={{
                    padding:"9px 18px", borderRadius:6, fontSize:14, fontWeight:600,
                    background: canSave ? "#3b82f6" : "#1e3a5f",
                    color:      canSave ? "#fff"    : "#475569",
                    border:"none", cursor: canSave ? "pointer" : "not-allowed",
                    display:"flex", alignItems:"center", gap:8, transition:"background .15s",
                  }}>
                  {loading && <span className="evm-spinner" />}
                  {loading ? "Saving…" : "Save Changes"}
                </button>
              </div>
            </div>
          </form>
        </div>
      </div>
    </>
  );
}

export default EditVideoModal;