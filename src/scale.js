// How many CSS pixels make 1 mm for the tasks. In a session this comes from
// the calibration block. Dev links that skip that block (?only=tmt_a, the
// TMT options page) use the last calibration made in dev mode in this
// browser, and without one a fallback value, so that a task can be opened on
// its own. Main and pilot sessions always calibrate, never use either.

// CSS reference pixel: 96 px per inch. True only on a ~96 dpi screen at
// 100 % zoom; on a 13" MacBook Air the real value is about 5.06.
export const FALLBACK_PX_PER_MM = 96 / 25.4;

const KEY = 'tmtua.dev.calibration';

// Remembers a calibration made in dev mode. Storage may be unavailable
// (private window): then dev links simply fall back.
export function saveDevCalibration(calibration) {
  try {
    localStorage.setItem(
      KEY,
      JSON.stringify({
        pxPerMm: calibration.pxPerMm,
        dpr: calibration.dpr,
        suspect: calibration.suspect,
        savedAt: new Date().toISOString(),
      }),
    );
  } catch {
    // nothing to do
  }
}

export function loadDevCalibration() {
  try {
    const saved = JSON.parse(localStorage.getItem(KEY));
    return saved && Number.isFinite(saved.pxPerMm) && saved.pxPerMm > 0 ? saved : null;
  } catch {
    return null;
  }
}

// { pxPerMm, source, dpr, savedAt }: source is 'calibration' (this session),
// 'dev_saved' or 'fallback'. dpr is the devicePixelRatio the value is valid
// for (null for the fallback): a later zoom makes it wrong.
export function devScale() {
  const saved = loadDevCalibration();
  if (saved) return { pxPerMm: saved.pxPerMm, source: 'dev_saved', dpr: saved.dpr, savedAt: saved.savedAt };
  return { pxPerMm: FALLBACK_PX_PER_MM, source: 'fallback', dpr: null, savedAt: null };
}

export function taskScale(ctx) {
  if (ctx.calibration) {
    return { pxPerMm: ctx.calibration.pxPerMm, source: 'calibration', dpr: ctx.calibration.dpr, savedAt: null };
  }
  if (ctx.session.mode !== 'dev') throw new Error('A task started before the screen calibration');
  return devScale();
}
