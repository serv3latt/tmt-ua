import { fullscreenWanted, isFullscreen, onFullscreenChange } from '../fullscreen.js';

// Records what happens around each task while it runs (decisions 62, 87,
// 98, 99): leaving the tab or minimising the window, the window losing focus
// to another program, leaving fullscreen, resizing the window, changing the
// page scale, and whether clicks come from a cursor or a finger. The task
// itself goes on; whether to exclude anything is decided in the analysis.
//
// The browser reports a mouse and a touchpad alike ('mouse'), so which one
// the participant uses is asked in the questionnaire.

const SETTLE_MS = 400; // dragging a window edge fires dozens of resize events
const FULLSCREEN_RESIZE_MS = 1500; // a resize this close to a fullscreen change is part of it

// Each interval: [event name when it starts, event name when it ends].
const INTERVALS = {
  hidden: ['hidden', 'visible'], // tab switched or window minimised
  blur: ['blur', 'focus'], // another window or program has the focus
  fs_exit: ['fs_exit', 'fs_enter'], // out of fullscreen while it is expected
};

const round2 = (x) => Math.round(x * 100) / 100;

export function windowSnapshot() {
  return {
    w: window.innerWidth,
    h: window.innerHeight,
    ow: window.outerWidth,
    oh: window.outerHeight,
    dpr: round2(window.devicePixelRatio),
    scale: round2(window.visualViewport?.scale ?? 1),
  };
}

const sameSnapshot = (a, b) => Object.keys(a).every((key) => a[key] === b[key]);

// True when the page scale changed between two snapshots, which breaks sizes
// set in mm by calibration. Zoom (keys or a pinch on a Mac touchpad) and a
// move to a screen of another density change devicePixelRatio; checked by
// hand in Chrome and Safari 26 on a Mac (T0.5). Older Safari kept
// devicePixelRatio under zoom, but there the page area shrinks or grows in
// both directions while the window stays the same. A pinch that only
// magnifies (no reflow) changes the visual viewport's scale.
export function scaleChanged(a, b) {
  if (a.dpr !== b.dpr || a.scale !== b.scale) return true;
  return a.ow === b.ow && a.oh === b.oh && a.w !== b.w && a.h !== b.h;
}

// onEvent(event) is called for every recorded event (used by the dev page).
export function createMonitor({ onEvent } = {}) {
  const now = () => performance.now();
  const state = {
    hidden: document.visibilityState === 'hidden',
    blur: !document.hasFocus(),
    fs_exit: false,
  };
  let block = null;
  let settled = windowSnapshot();
  let settleTimer = null;
  let lastFullscreenChange = -Infinity;
  let lastResize = null; // { t, event } of the last plain resize
  let baseline = null; // scale at calibration: { dpr, scale }

  function record(t, event) {
    event = { t: Math.round(t - block.t0), ...event };
    block.events.push(event);
    onEvent?.(event);
    return event;
  }

  function setState(kind, on) {
    if (state[kind] === on) return;
    state[kind] = on;
    if (!block) return;
    const t = now();
    const interval = block.intervals[kind];
    if (on) {
      interval.n += 1;
      interval.since = t;
    } else if (interval.since !== null) {
      interval.ms += t - interval.since;
      interval.since = null;
    }
    record(t, { type: INTERVALS[kind][on ? 0 : 1] });
  }

  function settle() {
    clearTimeout(settleTimer);
    settleTimer = null;
    const prev = settled;
    settled = windowSnapshot();
    if (!block || sameSnapshot(prev, settled)) return;
    const t = now();
    const zoom = scaleChanged(prev, settled);
    const byFullscreen = !zoom && t - lastFullscreenChange < FULLSCREEN_RESIZE_MS + SETTLE_MS;
    if (zoom) block.zoom += 1;
    else if (!byFullscreen) block.resize += 1;
    const event = record(t, { type: zoom ? 'zoom' : 'resize', ...settled, ...(byFullscreen && { by_fullscreen: true }) });
    lastResize = zoom || byFullscreen ? null : { t, event, block };
  }

  function scheduleSettle() {
    clearTimeout(settleTimer);
    settleTimer = setTimeout(settle, SETTLE_MS);
  }

  function fullscreenChanged() {
    const t = now();
    lastFullscreenChange = t;
    // The window can settle before the browser reports the change itself.
    if (lastResize?.block === block && block && t - lastResize.t < FULLSCREEN_RESIZE_MS) {
      block.resize -= 1;
      lastResize.event.by_fullscreen = true;
      lastResize = null;
    }
    setState('fs_exit', fullscreenWanted() && !isFullscreen());
  }

  document.addEventListener('visibilitychange', () =>
    setState('hidden', document.visibilityState === 'hidden'),
  );
  window.addEventListener('blur', () => setState('blur', true));
  window.addEventListener('focus', () => setState('blur', false));
  onFullscreenChange(fullscreenChanged);
  window.addEventListener('resize', scheduleSettle);
  window.visualViewport?.addEventListener('resize', scheduleSettle);
  window.addEventListener(
    'pointerdown',
    (event) => {
      if (!block) return;
      const type = event.pointerType || 'unknown';
      block.pointer[type] = (block.pointer[type] ?? 0) + 1;
    },
    true,
  );

  // Remembers the scale the calibration was made at (T0.6).
  function setBaseline() {
    const { dpr, scale } = windowSnapshot();
    baseline = { dpr, scale };
  }

  // Something already going on when the task starts (e.g. the previous task
  // ran out of time while the tab was hidden) counts as one exit from the
  // start of this task. Likewise a task that starts at another scale than
  // the calibration was made at counts one zoom: the scale may have changed
  // between tasks, where nothing is watched.
  function startBlock(id) {
    // Asked directly: the change event can come after the gate has already
    // seen fullscreen return and let the task start.
    state.fs_exit = fullscreenWanted() && !isFullscreen();
    const t0 = now();
    block = {
      id,
      t0,
      startedAt: new Date().toISOString(),
      window: windowSnapshot(),
      events: [],
      intervals: {},
      resize: 0,
      zoom: 0,
      pointer: {},
    };
    for (const kind of Object.keys(INTERVALS)) {
      block.intervals[kind] = { n: 0, ms: 0, since: null };
      if (state[kind]) {
        block.intervals[kind] = { n: 1, ms: 0, since: t0 };
        record(t0, { type: INTERVALS[kind][0], at_start: true });
      }
    }
    const current = windowSnapshot();
    if (baseline && (current.dpr !== baseline.dpr || current.scale !== baseline.scale)) {
      block.zoom += 1;
      record(t0, { type: 'zoom', ...current, at_start: true, since_calibration: true });
    }
  }

  // Returns { summary, log } for the task, with column names prefixed by its id.
  function endBlock() {
    if (!block) return null;
    if (settleTimer) settle();
    const t = now();
    const done = block;
    block = null;
    const p = `${done.id}_`;
    const summary = {};
    for (const [kind, interval] of Object.entries(done.intervals)) {
      if (interval.since !== null) interval.ms += t - interval.since;
      summary[`${p}${kind}_n`] = interval.n;
      summary[`${p}${kind}_ms`] = Math.round(interval.ms);
    }
    summary[`${p}resize_n`] = done.resize;
    summary[`${p}zoom_n`] = done.zoom;
    summary[`${p}touch_n`] = Object.entries(done.pointer)
      .filter(([type]) => type !== 'mouse')
      .reduce((sum, [, n]) => sum + n, 0);
    const log = {
      started_at: done.startedAt,
      duration_ms: Math.round(t - done.t0),
      window_at_start: done.window,
      pointer: done.pointer,
      events: done.events,
    };
    return { summary, log };
  }

  return { setBaseline, startBlock, endBlock, active: () => block?.id ?? null };
}
