// src/components/SmoothProgressBar.js
// Drop-in replacement for the inline progress bars in Sidebar.js
import React, { useState, useEffect, useRef } from 'react';

/**
 * Renders a single animated progress bar that:
 *  - Smoothly interpolates toward the target value (no jumps)
 *  - Pulses gently while processing
 *  - Flashes green on completion
 *  - Uses CSS transitions as the primary animation driver
 */
function SmoothProgressBar({ progress = 0, status = 'processing', message = '' }) {
  // displayProgress tracks the visually rendered value (interpolated)
  const [displayProgress, setDisplayProgress] = useState(() => Math.max(0, progress - 5));
  const animFrameRef = useRef(null);
  const targetRef = useRef(progress);

  // Update target whenever the prop changes
  useEffect(() => {
    targetRef.current = progress;
  }, [progress]);

  // Smooth animation loop: ease toward targetRef.current
  useEffect(() => {
    const SPEED = 0.08; // fraction to close per frame (lower = smoother/slower)
    const MIN_STEP = 0.15; // minimum movement per frame (prevents stalling)
    const SNAP_THRESHOLD = 0.1; // snap when this close

    const tick = () => {
      setDisplayProgress(prev => {
        const target = targetRef.current;
        const diff = target - prev;

        if (Math.abs(diff) <= SNAP_THRESHOLD) return target;

        const step = Math.max(Math.abs(diff) * SPEED, MIN_STEP);
        return diff > 0
          ? Math.min(target, prev + step)
          : Math.max(target, prev - step);
      });
      animFrameRef.current = requestAnimationFrame(tick);
    };

    animFrameRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(animFrameRef.current);
  }, []); // intentionally run once; target is tracked via ref

  const isCompleted = status === 'completed';
  const isFailed = status === 'failed';
  const isProcessing = status === 'processing';

  const barColor = isCompleted
    ? '#10b981'   // emerald
    : isFailed
    ? '#ef4444'   // red
    : '#3b82f6';  // blue

  const barBg = isCompleted
    ? 'rgba(16,185,129,0.12)'
    : isFailed
    ? 'rgba(239,68,68,0.10)'
    : 'rgba(59,130,246,0.10)';

  const clampedDisplay = Math.max(0, Math.min(100, displayProgress));

  return (
    <div style={styles.wrapper}>
      {/* Track */}
      <div style={{ ...styles.track, background: barBg }}>

        {/* Filled portion */}
        <div
          style={{
            ...styles.fill,
            width: `${clampedDisplay}%`,
            background: barColor,
            boxShadow: isProcessing && clampedDisplay > 0
              ? `0 0 6px 1px ${barColor}66`
              : 'none',
          }}
        >
          {/* Shimmer overlay (processing only) */}
          {isProcessing && (
            <div style={styles.shimmer} />
          )}
        </div>
      </div>

      {/* Labels row */}
      <div style={styles.labels}>
        <span style={{ ...styles.messageText, color: isFailed ? '#ef4444' : undefined }}>
          {isFailed
            ? '✗ Failed'
            : isCompleted
            ? '✓ Complete'
            : (message || 'Processing...')}
        </span>
        <span style={{ ...styles.percentText, color: barColor }}>
          {Math.round(clampedDisplay)}%
        </span>
      </div>
    </div>
  );
}

// ── Styles ──────────────────────────────────────────────────────────────────

const styles = {
  wrapper: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
    width: '100%',
  },
  track: {
    position: 'relative',
    height: '6px',
    borderRadius: '99px',
    overflow: 'hidden',
  },
  fill: {
    position: 'absolute',
    top: 0,
    left: 0,
    height: '100%',
    borderRadius: '99px',
    transition: 'background 0.4s ease',
    overflow: 'hidden',
    // CSS transition for any width changes not caught by rAF
    willChange: 'width',
  },
  shimmer: {
    position: 'absolute',
    top: 0,
    left: '-100%',
    width: '60%',
    height: '100%',
    background: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.35), transparent)',
    animation: 'shimmerSlide 1.6s ease-in-out infinite',
  },
  labels: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  messageText: {
    fontSize: '10px',
    color: 'rgba(255,255,255,0.55)',
    flex: 1,
    minWidth: 0,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
    marginRight: '6px',
  },
  percentText: {
    fontSize: '10px',
    fontWeight: '600',
    flexShrink: 0,
    fontVariantNumeric: 'tabular-nums',
  },
};

// Inject keyframes once
if (typeof document !== 'undefined') {
  const KEYFRAME_ID = '__smooth_progress_shimmer__';
  if (!document.getElementById(KEYFRAME_ID)) {
    const style = document.createElement('style');
    style.id = KEYFRAME_ID;
    style.textContent = `
      @keyframes shimmerSlide {
        0%   { left: -60%; }
        100% { left: 110%; }
      }
    `;
    document.head.appendChild(style);
  }
}

export default SmoothProgressBar;