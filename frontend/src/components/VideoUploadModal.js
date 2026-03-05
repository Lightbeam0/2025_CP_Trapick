// src/components/VideoUploadModal.js
import React, { useState, useEffect, useRef, useCallback } from 'react';
import axios from 'axios';
import { useVideoProgress } from '../hooks/useVideoProgress';

const API_BASE_URL = process.env.NODE_ENV === 'development'
  ? 'http://127.0.0.1:8000'
  : '';

// ─── tiny helpers ────────────────────────────────────────────────────────────
const timeToMinutes = (t) => {
  if (!t) return null;
  const [h, m] = t.split(':').map(Number);
  return h * 60 + m;
};

const minutesToTime = (mins) => {
  const m = ((mins % (24 * 60)) + 24 * 60) % (24 * 60);
  return `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`;
};

const formatDuration = (seconds) => {
  if (!seconds) return '';
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
};

// ─── TimelineBar ─────────────────────────────────────────────────────────────
const TimelineBar = ({ occupiedSlots, proposedStart, proposedEnd, hasConflict }) => {
  const dayMinutes = 24 * 60;

  const toPercent = (mins) => `${(mins / dayMinutes) * 100}%`;

  const hourMarkers = [0, 6, 12, 18, 24];

  return (
    <div style={{ marginTop: 4 }}>
      {/* Hour labels */}
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
        {hourMarkers.map(h => (
          <span key={h} style={{ fontSize: 10, color: '#94a3b8', fontFamily: 'monospace' }}>
            {h === 24 ? '24:00' : `${String(h).padStart(2, '0')}:00`}
          </span>
        ))}
      </div>

      {/* Bar */}
      <div style={{
        position: 'relative',
        height: 28,
        backgroundColor: '#1e293b',
        borderRadius: 6,
        overflow: 'hidden',
        border: '1px solid #334155',
      }}>
        {/* Hour grid lines */}
        {[6, 12, 18].map(h => (
          <div key={h} style={{
            position: 'absolute',
            left: toPercent(h * 60),
            top: 0, bottom: 0,
            width: 1,
            backgroundColor: '#334155',
          }} />
        ))}

        {/* Occupied slots */}
        {occupiedSlots.map((slot, i) => {
          const s = timeToMinutes(slot.start_time);
          const e = timeToMinutes(slot.end_time);
          if (s === null || e === null) return null;
          const end = e < s ? e + dayMinutes : e;
          return (
            <div key={i} title={`${slot.title || slot.filename}\n${slot.start_time}–${slot.end_time}`}
              style={{
                position: 'absolute',
                left: toPercent(s),
                width: toPercent(end - s),
                top: 4, bottom: 4,
                backgroundColor: '#3b82f6',
                borderRadius: 3,
                opacity: 0.85,
              }}
            />
          );
        })}

        {/* Proposed slot */}
        {proposedStart !== null && proposedEnd !== null && (
          <div style={{
            position: 'absolute',
            left: toPercent(proposedStart),
            width: toPercent(Math.max(1, proposedEnd - proposedStart)),
            top: 2, bottom: 2,
            backgroundColor: hasConflict ? '#ef4444' : '#22c55e',
            borderRadius: 3,
            border: `2px solid ${hasConflict ? '#fca5a5' : '#86efac'}`,
            zIndex: 2,
            transition: 'all 0.2s',
          }} />
        )}
      </div>

      {/* Legend */}
      <div style={{ display: 'flex', gap: 12, marginTop: 6 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <div style={{ width: 10, height: 10, borderRadius: 2, backgroundColor: '#3b82f6' }} />
          <span style={{ fontSize: 10, color: '#94a3b8' }}>Occupied</span>
        </div>
        {proposedStart !== null && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <div style={{ width: 10, height: 10, borderRadius: 2, backgroundColor: hasConflict ? '#ef4444' : '#22c55e' }} />
            <span style={{ fontSize: 10, color: '#94a3b8' }}>
              {hasConflict ? 'Conflict' : 'Your upload'}
            </span>
          </div>
        )}
      </div>
    </div>
  );
};

// ─── ConflictBanner ───────────────────────────────────────────────────────────
const ConflictBanner = ({ conflicts }) => (
  <div style={{
    backgroundColor: '#1c0a0a',
    border: '1px solid #7f1d1d',
    borderLeft: '3px solid #ef4444',
    borderRadius: 6,
    padding: '10px 14px',
    marginBottom: 12,
  }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
      <span style={{ fontSize: 14 }}>⛔</span>
      <span style={{ color: '#fca5a5', fontWeight: 600, fontSize: 13 }}>
        Time slot conflict detected
      </span>
    </div>
    {conflicts.map((c, i) => (
      <div key={i} style={{
        fontSize: 12, color: '#fca5a5', opacity: 0.85,
        paddingLeft: 20, marginTop: 2,
      }}>
        • <strong>{c.filename}</strong> — {c.start_time}–{c.end_time}
        {' '}({c.overlap_minutes} min overlap)
      </div>
    ))}
    <div style={{ fontSize: 11, color: '#f87171', opacity: 0.6, marginTop: 6, paddingLeft: 20 }}>
      Choose a different start time or date.
    </div>
  </div>
);

// ─── main modal ──────────────────────────────────────────────────────────────
const VideoUploadModal = ({ isOpen, onClose, onUpload }) => {
  const { updateVideoProgress } = useVideoProgress();

  const [formData, setFormData] = useState({
    file: null,
    title: '',
    locationId: '',
    videoDate: '',
    startTime: '',
    endTime: '',
  });

  const [uploading, setUploading]           = useState(false);
  const [currentProgress, setCurrentProgress] = useState(0);
  const [progressMessage, setProgressMessage] = useState('');
  const [isProcessing, setIsProcessing]     = useState(false);
  const [locations, setLocations]           = useState([]);
  const [loadingLocations, setLoadingLocations] = useState(false);
  const [uploadSuccess, setUploadSuccess]   = useState(false);
  const [successMessage, setSuccessMessage] = useState('');
  const [error, setError]                   = useState('');

  // time-slot / conflict state
  const [occupiedSlots, setOccupiedSlots]   = useState([]);
  const [loadingSlots, setLoadingSlots]     = useState(false);
  const [conflicts, setConflicts]           = useState([]);
  const [checkingConflict, setCheckingConflict] = useState(false);
  const [detectedDuration, setDetectedDuration] = useState(null); // seconds
  const [autoEndTime, setAutoEndTime]       = useState(false);

  const conflictDebounce = useRef(null);
  const fileInputRef = useRef(null);

  const updateField = (field, value) =>
    setFormData(prev => ({ ...prev, [field]: value }));

  // ── reset on open ─────────────────────────────────────────────────────────
  useEffect(() => {
    if (isOpen) {
      fetchLocations();
      resetAll();
    }
  }, [isOpen]);

  const resetAll = () => {
    setFormData({ file: null, title: '', locationId: '', videoDate: '', startTime: '', endTime: '' });
    setUploadSuccess(false);
    setSuccessMessage('');
    setError('');
    setOccupiedSlots([]);
    setConflicts([]);
    setDetectedDuration(null);
    setAutoEndTime(false);
    setCurrentProgress(0);
    setProgressMessage('');
    setIsProcessing(false);
    setUploading(false);
  };

  const fetchLocations = async () => {
    try {
      setLoadingLocations(true);
      const res = await axios.get(`${API_BASE_URL}/api/locations/`);
      setLocations(res.data);
    } catch {
      setError('Failed to load locations.');
    } finally {
      setLoadingLocations(false);
    }
  };

  // ── fetch occupied slots when location + date change ──────────────────────
  useEffect(() => {
    if (formData.locationId && formData.videoDate) {
      fetchOccupiedSlots();
    } else {
      setOccupiedSlots([]);
    }
  }, [formData.locationId, formData.videoDate]);

  const fetchOccupiedSlots = async () => {
    try {
      setLoadingSlots(true);
      const res = await axios.get(`${API_BASE_URL}/api/videos/time-slots/`, {
        params: { location_id: formData.locationId, video_date: formData.videoDate },
      });
      setOccupiedSlots(res.data.occupied_slots || []);
    } catch {
      setOccupiedSlots([]);
    } finally {
      setLoadingSlots(false);
    }
  };

  // ── auto-fill end time when start changes and we know duration ────────────
  useEffect(() => {
    if (formData.startTime && detectedDuration) {
      const startMins = timeToMinutes(formData.startTime);
      const endMins   = startMins + Math.ceil(detectedDuration / 60);
      const computed  = minutesToTime(endMins);
      updateField('endTime', computed);
      setAutoEndTime(true);
    }
  }, [formData.startTime, detectedDuration]);

  // ── debounced conflict check whenever start/end/location/date change ──────
  useEffect(() => {
    clearTimeout(conflictDebounce.current);
    if (!formData.startTime || !formData.endTime || !formData.locationId || !formData.videoDate) {
      setConflicts([]);
      return;
    }
    conflictDebounce.current = setTimeout(checkConflict, 400);
  }, [formData.startTime, formData.endTime, formData.locationId, formData.videoDate]);

  const checkConflict = async () => {
    try {
      setCheckingConflict(true);
      const res = await axios.get(`${API_BASE_URL}/api/videos/check-conflict/`, {
        params: {
          location_id:  formData.locationId,
          video_date:   formData.videoDate,
          start_time:   formData.startTime,
          end_time:     formData.endTime,
        },
      });
      setConflicts(res.data.has_conflict ? res.data.conflicts : []);
    } catch {
      setConflicts([]);
    } finally {
      setCheckingConflict(false);
    }
  };

  // ── file selection — extract duration via browser Video API ───────────────
  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const validTypes = ['video/mp4', 'video/avi', 'video/mov', 'video/webm', 'video/quicktime'];
    if (!validTypes.includes(file.type)) {
      setError('Please select a valid video file (MP4, AVI, MOV, WebM)');
      return;
    }
    if (file.size > 2 * 1024 * 1024 * 1024) {
      setError(`File too large (${(file.size / 1e9).toFixed(2)} GB). Max is 2 GB.`);
      return;
    }

    setError('');
    setDetectedDuration(null);
    setAutoEndTime(false);

    // auto-fill title
    const cleanName = file.name.replace(/\.[^/.]+$/, '');
    setFormData(prev => ({ ...prev, file, title: prev.title || cleanName }));

    // auto-fill date from filename
    const dateMatch = file.name.match(/(\d{4}[-_]\d{2}[-_]\d{2})/);
    if (dateMatch && !formData.videoDate) {
      updateField('videoDate', dateMatch[0].replace(/_/g, '-'));
    }

    // detect duration via browser
    const url = URL.createObjectURL(file);
    const vid = document.createElement('video');
    vid.preload = 'metadata';
    vid.onloadedmetadata = () => {
      URL.revokeObjectURL(url);
      if (vid.duration && isFinite(vid.duration)) {
        setDetectedDuration(Math.round(vid.duration));
      }
    };
    vid.onerror = () => URL.revokeObjectURL(url);
    vid.src = url;
  };

  // ── upload ────────────────────────────────────────────────────────────────
  const handleUpload = async () => {
    if (!formData.file)       return setError('Please select a video file.');
    if (!formData.videoDate)  return setError('Please specify the recording date.');
    if (!formData.locationId) return setError('Please select a location.');
    if (conflicts.length > 0) return setError('Resolve time slot conflicts before uploading.');

    setError('');
    setUploading(true);
    setIsProcessing(true);
    setCurrentProgress(0);
    setProgressMessage('Starting upload…');

    const fd = new FormData();
    fd.append('video', formData.file);
    fd.append('title', formData.title);
    fd.append('video_date', formData.videoDate);
    fd.append('location_id', formData.locationId);
    if (formData.startTime) fd.append('start_time', formData.startTime);
    if (formData.endTime)   fd.append('end_time', formData.endTime);

    try {
      const res = await axios.post(`${API_BASE_URL}/api/upload/video/`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 0,
        onUploadProgress: (evt) => {
          if (evt.total) {
            const pct = Math.round((evt.loaded * 100) / evt.total);
            setCurrentProgress(pct);
            setProgressMessage(`Uploading… ${pct}%`);
          }
        },
      });

      const videoId = res.data.video_id || res.data.upload_id || res.data.id;
      if (!videoId) {
        setError('Upload succeeded but no video ID returned. Please refresh.');
        setUploading(false);
        setIsProcessing(false);
        return;
      }

      const selectedLocation = locations.find(l => String(l.id) === String(formData.locationId));

      updateVideoProgress(videoId, {
        progress: 5,
        message: 'Upload complete, starting processing…',
        status: 'processing',
        filename: formData.file.name,
        video_info: {
          filename: formData.file.name,
          location_name: selectedLocation?.display_name || '',
          group_date: formData.videoDate,
          total_vehicles: 'Processing…',
        },
      });

      if (onUpload) {
        onUpload({
          id: videoId, video_id: videoId, upload_id: videoId,
          task_id: res.data.task_id, status: 'uploaded',
          filename: formData.file.name,
        });
      }

      setUploadSuccess(true);
      setSuccessMessage(res.data.message || 'Video uploaded and processing started!');
      setTimeout(handleClose, 2000);

    } catch (err) {
      // ── 409 conflict from server (double-safety net) ──────────────────────
      if (err.response?.status === 409) {
        const data = err.response.data;
        setConflicts(data.conflicts || []);
        setError(data.detail || 'Time slot conflict detected.');
      } else {
        setError(err.response?.data?.error || err.message || 'Upload failed.');
      }
      setUploading(false);
      setIsProcessing(false);
      setProgressMessage('Upload failed.');
    }
  };

  const handleClose = () => {
    resetAll();
    onClose();
  };

  if (!isOpen) return null;

  // derived values for the timeline
  const proposedStart = timeToMinutes(formData.startTime);
  const proposedEnd   = timeToMinutes(formData.endTime);
  const hasConflict   = conflicts.length > 0;
  const showTimeline  = !!(formData.locationId && formData.videoDate);

  // ─── render ──────────────────────────────────────────────────────────────
  return (
    <>
      <style>{`
        .vum-overlay {
          position: fixed; inset: 0; z-index: 1000;
          background: rgba(0,0,0,0.75);
          backdrop-filter: blur(4px);
          display: flex; align-items: center; justify-content: center;
          padding: 16px;
          animation: vum-fadein 0.15s ease;
        }
        @keyframes vum-fadein { from { opacity:0 } to { opacity:1 } }

        .vum-modal {
          background: #0f172a;
          border: 1px solid #1e293b;
          border-radius: 12px;
          width: 100%; max-width: 540px;
          max-height: 90vh; overflow-y: auto;
          padding: 24px;
          color: #e2e8f0;
          font-family: 'DM Sans', ui-sans-serif, system-ui, sans-serif;
          animation: vum-slidein 0.2s ease;
          scrollbar-width: thin;
          scrollbar-color: #334155 transparent;
        }
        @keyframes vum-slidein { from { transform:translateY(12px); opacity:0 } to { transform:translateY(0); opacity:1 } }

        .vum-label {
          display: block; font-size: 12px; font-weight: 600;
          letter-spacing: 0.06em; text-transform: uppercase;
          color: #64748b; margin-bottom: 6px;
        }
        .vum-input {
          width: 100%; box-sizing: border-box;
          background: #1e293b; border: 1px solid #334155;
          border-radius: 6px; color: #e2e8f0;
          padding: 9px 12px; font-size: 14px;
          outline: none; transition: border-color 0.15s;
          font-family: inherit;
        }
        .vum-input:focus { border-color: #3b82f6; }
        .vum-input:disabled { opacity: 0.45; cursor: not-allowed; }
        .vum-input option { background: #1e293b; }

        .vum-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
        .vum-group { margin-bottom: 14px; }

        .vum-btn {
          border: none; border-radius: 7px;
          padding: 10px 20px; font-size: 14px; font-weight: 600;
          cursor: pointer; transition: all 0.15s; font-family: inherit;
        }
        .vum-btn-primary {
          background: #3b82f6; color: #fff;
        }
        .vum-btn-primary:hover:not(:disabled) { background: #2563eb; }
        .vum-btn-primary:disabled { background: #1e3a5f; color: #475569; cursor: not-allowed; }
        .vum-btn-secondary {
          background: #1e293b; color: #94a3b8;
          border: 1px solid #334155;
        }
        .vum-btn-secondary:hover:not(:disabled) { background: #273549; }

        .vum-file-drop {
          border: 2px dashed #334155; border-radius: 8px;
          padding: 20px; text-align: center; cursor: pointer;
          transition: border-color 0.15s;
          background: #1e293b;
        }
        .vum-file-drop:hover { border-color: #3b82f6; }

        .vum-pill {
          display: inline-flex; align-items: center; gap: 4px;
          font-size: 11px; padding: 2px 8px; border-radius: 10px;
          background: #1e3a5f; color: #60a5fa;
          margin-left: 6px; vertical-align: middle;
        }
        .vum-divider {
          border: none; border-top: 1px solid #1e293b;
          margin: 16px 0;
        }
        .vum-success {
          background: #052e16; border: 1px solid #166534;
          border-radius: 8px; padding: 14px 16px;
          display: flex; align-items: center; gap: 10px;
          color: #86efac; font-weight: 600;
        }
        .vum-spinner {
          width: 14px; height: 14px;
          border: 2px solid rgba(255,255,255,0.2);
          border-top-color: #fff;
          border-radius: 50%;
          animation: spin 0.7s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg) } }

        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&display=swap');
      `}</style>

      <div className="vum-overlay" onClick={handleClose}>
        <div className="vum-modal" onClick={e => e.stopPropagation()}>

          {/* Header */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
            <div>
              <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: '#f1f5f9' }}>
                Upload Traffic Video
              </h2>
              <p style={{ margin: '3px 0 0', fontSize: 12, color: '#64748b' }}>
                Slots are checked in real time
              </p>
            </div>
            <button onClick={handleClose} style={{
              background: '#1e293b', border: '1px solid #334155',
              borderRadius: 6, color: '#94a3b8', width: 32, height: 32,
              fontSize: 18, cursor: 'pointer', display: 'flex',
              alignItems: 'center', justifyContent: 'center',
            }}>×</button>
          </div>

          {/* Success */}
          {uploadSuccess && (
            <div className="vum-success">
              <span style={{ fontSize: 20 }}>✅</span>
              <span>{successMessage}</span>
            </div>
          )}

          {/* Progress */}
          {(uploading || isProcessing) && !uploadSuccess && (
            <div style={{ marginBottom: 16 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6, fontSize: 12, color: '#94a3b8' }}>
                <span>{progressMessage}</span>
                <span>{currentProgress}%</span>
              </div>
              <div style={{ height: 6, backgroundColor: '#1e293b', borderRadius: 3, overflow: 'hidden' }}>
                <div style={{
                  height: '100%', borderRadius: 3,
                  backgroundColor: '#3b82f6',
                  width: `${currentProgress}%`,
                  transition: 'width 0.3s',
                }} />
              </div>
            </div>
          )}

          {/* Error banner */}
          {error && !uploadSuccess && (
            <div style={{
              background: '#1c0a0a', border: '1px solid #7f1d1d',
              borderLeft: '3px solid #ef4444',
              borderRadius: 6, padding: '10px 14px',
              color: '#fca5a5', fontSize: 13, marginBottom: 14,
            }}>
              {error}
            </div>
          )}

          {!uploadSuccess && (
            <>
              {/* ── File drop zone ── */}
              <div className="vum-group">
                <label className="vum-label">Video File *</label>
                <div className="vum-file-drop" onClick={() => fileInputRef.current?.click()}>
                  <input ref={fileInputRef} type="file" accept="video/*"
                    onChange={handleFileChange} style={{ display: 'none' }}
                    disabled={uploading || isProcessing} />
                  {formData.file ? (
                    <div>
                      <div style={{ fontSize: 13, color: '#e2e8f0', fontWeight: 600, marginBottom: 4 }}>
                        📹 {formData.file.name}
                      </div>
                      <div style={{ fontSize: 12, color: '#64748b' }}>
                        {(formData.file.size / 1024 / 1024).toFixed(1)} MB
                        {detectedDuration && (
                          <span className="vum-pill">
                            ⏱ {formatDuration(detectedDuration)}
                          </span>
                        )}
                      </div>
                    </div>
                  ) : (
                    <div>
                      <div style={{ fontSize: 28, marginBottom: 6 }}>📂</div>
                      <div style={{ fontSize: 13, color: '#94a3b8' }}>
                        Click to select a video file
                      </div>
                      <div style={{ fontSize: 11, color: '#475569', marginTop: 4 }}>
                        MP4, AVI, MOV, WebM — max 2 GB
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* ── Title ── */}
              <div className="vum-group">
                <label className="vum-label">Title</label>
                <input className="vum-input" type="text" value={formData.title}
                  onChange={e => updateField('title', e.target.value)}
                  placeholder="Auto-filled from filename"
                  disabled={uploading || isProcessing} />
              </div>

              <hr className="vum-divider" />

              {/* ── Location + Date ── */}
              <div className="vum-row">
                <div className="vum-group">
                  <label className="vum-label">Location *</label>
                  <select className="vum-input" value={formData.locationId}
                    onChange={e => updateField('locationId', e.target.value)}
                    disabled={uploading || isProcessing || loadingLocations}>
                    <option value="">Select…</option>
                    {loadingLocations
                      ? <option disabled>Loading…</option>
                      : locations.map(l => (
                          <option key={l.id} value={l.id}>{l.display_name}</option>
                        ))
                    }
                  </select>
                </div>
                <div className="vum-group">
                  <label className="vum-label">Recording Date *</label>
                  <input className="vum-input" type="date" value={formData.videoDate}
                    onChange={e => updateField('videoDate', e.target.value)}
                    disabled={uploading || isProcessing} />
                </div>
              </div>

              {/* ── Timeline ── */}
              {showTimeline && (
                <div style={{
                  background: '#0f172a', border: '1px solid #1e293b',
                  borderRadius: 8, padding: '12px 14px', marginBottom: 14,
                }}>
                  <div style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    marginBottom: 8,
                  }}>
                    <span style={{ fontSize: 11, fontWeight: 600, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                      Day Coverage
                    </span>
                    {loadingSlots && (
                      <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                        <div className="vum-spinner" />
                        <span style={{ fontSize: 11, color: '#64748b' }}>Loading…</span>
                      </div>
                    )}
                    {!loadingSlots && (
                      <span style={{ fontSize: 11, color: '#475569' }}>
                        {occupiedSlots.length} slot{occupiedSlots.length !== 1 ? 's' : ''} occupied
                      </span>
                    )}
                  </div>
                  <TimelineBar
                    occupiedSlots={occupiedSlots}
                    proposedStart={proposedStart}
                    proposedEnd={proposedEnd}
                    hasConflict={hasConflict}
                  />

                  {/* Occupied slot list */}
                  {!loadingSlots && occupiedSlots.length > 0 && (
                    <div style={{ marginTop: 10 }}>
                      <div style={{ fontSize: 10, fontWeight: 600, color: '#475569', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 5 }}>
                        Taken Slots
                      </div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                        {occupiedSlots.map((slot, i) => {
                          const isConflicting = conflicts.some(c => c.video_id === slot.video_id);
                          return (
                            <div key={i} style={{
                              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                              background: isConflicting ? '#1c0a0a' : '#0c1a2e',
                              border: `1px solid ${isConflicting ? '#7f1d1d' : '#1e3a5f'}`,
                              borderLeft: `3px solid ${isConflicting ? '#ef4444' : '#3b82f6'}`,
                              borderRadius: 5, padding: '5px 10px',
                            }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
                                <span style={{ fontSize: 13 }}>{isConflicting ? '⛔' : '🎬'}</span>
                                <span style={{
                                  fontSize: 12, color: isConflicting ? '#fca5a5' : '#93c5fd',
                                  fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                                  maxWidth: 180,
                                }}>
                                  {slot.title || slot.filename}
                                </span>
                              </div>
                              <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
                                <span style={{
                                  fontSize: 12, fontFamily: 'monospace',
                                  color: isConflicting ? '#fca5a5' : '#60a5fa',
                                  fontWeight: 600,
                                }}>
                                  {slot.start_time} – {slot.end_time}
                                </span>
                                <span style={{
                                  fontSize: 10, padding: '1px 6px', borderRadius: 8,
                                  background: slot.status === 'completed' ? '#052e16' : '#1c1400',
                                  color: slot.status === 'completed' ? '#86efac' : '#fbbf24',
                                  border: `1px solid ${slot.status === 'completed' ? '#166534' : '#78350f'}`,
                                }}>
                                  {slot.status}
                                </span>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {!loadingSlots && occupiedSlots.length === 0 && (
                    <div style={{ marginTop: 8, fontSize: 12, color: '#334155', textAlign: 'center' }}>
                      No videos recorded on this date yet
                    </div>
                  )}
                </div>
              )}

              {/* ── Conflict details ── */}
              {hasConflict && <ConflictBanner conflicts={conflicts} />}

              {/* ── Start / End time ── */}
              <div className="vum-row">
                <div className="vum-group">
                  <label className="vum-label">Start Time</label>
                  <input className="vum-input" type="time" value={formData.startTime}
                    onChange={e => { setAutoEndTime(false); updateField('startTime', e.target.value); }}
                    disabled={uploading || isProcessing} />
                </div>
                <div className="vum-group">
                  <label className="vum-label">
                    End Time
                    {autoEndTime && detectedDuration && (
                      <span className="vum-pill">Auto ✨</span>
                    )}
                  </label>
                  <input className="vum-input" type="time" value={formData.endTime}
                    onChange={e => { setAutoEndTime(false); updateField('endTime', e.target.value); }}
                    disabled={uploading || isProcessing}
                    style={autoEndTime ? { borderColor: '#22c55e' } : {}} />
                </div>
              </div>

              {/* Hint when no start time */}
              {formData.file && detectedDuration && !formData.startTime && (
                <div style={{
                  fontSize: 12, color: '#94a3b8', marginTop: -6, marginBottom: 14,
                  paddingLeft: 2,
                }}>
                  💡 Set a start time and end time will be auto-filled ({formatDuration(detectedDuration)})
                </div>
              )}

              {/* Conflict checking indicator */}
              {checkingConflict && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: '#64748b', marginBottom: 10 }}>
                  <div className="vum-spinner" />
                  Checking slot availability…
                </div>
              )}

              <hr className="vum-divider" />

              {/* ── Actions ── */}
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
                <button className="vum-btn vum-btn-secondary" onClick={handleClose}
                  disabled={uploading || isProcessing}>
                  Cancel
                </button>
                <button className="vum-btn vum-btn-primary" onClick={handleUpload}
                  disabled={
                    !formData.file || uploading || isProcessing ||
                    !formData.locationId || hasConflict || checkingConflict
                  }>
                  {uploading || isProcessing ? (
                    <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <div className="vum-spinner" />
                      {isProcessing ? 'Processing…' : 'Uploading…'}
                    </span>
                  ) : 'Upload Video'}
                </button>
              </div>
            </>
          )}

          {uploadSuccess && (
            <p style={{ textAlign: 'center', fontSize: 12, color: '#475569', marginTop: 16 }}>
              Closing automatically…
            </p>
          )}
        </div>
      </div>
    </>
  );
};

export default VideoUploadModal;