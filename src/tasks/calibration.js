import { HtmlButtonResponse, VirtualChinrest } from '../lib.js';
import { texts } from '../texts.uk.js';

// Block "calibration" (decisions 60, 100): the participant resizes a picture
// of a card until it matches a real one (the card part of the virtual
// chinrest, Li et al., 2020), which tells how many CSS pixels make 1 mm on
// this screen at this zoom. All stimulus sizes are then set in mm. A result
// that looks wrong is asked to be redone once, then kept with a mark
// (decision 100). Besides dragging the corner, the arrow keys adjust the card
// precisely (decision 102). Whether the task area fits is checked on the page itself
// after the fullscreen step (tasks/fullscreen.js), not here: Chrome on a Mac
// reports screen.width as at 100 % zoom even when the page is zoomed (seen
// in T0.6), so a check against the screen would be off by the zoom.
// In dev mode a 100 mm square follows, to check the result with a ruler.

// ISO/IEC 7810 ID-1: bank cards, Ukrainian ID cards, driving licences.
export const CARD_MM = { w: 85.6, h: 53.98 };
// Smaller than a real card on any plausible screen, so it has to be enlarged.
export const CARD_START_PX = 250;

const round = (x, digits) => Number(x.toFixed(digits));

// Why a measurement looks wrong, or null: the card was left as it was, or
// the screen width it implies is implausible (decision 100).
export function calibrationProblem(cardPx, screenWidthPx, params) {
  if (cardPx === CARD_START_PX) return 'unchanged';
  const screenMm = screenWidthPx / (cardPx / CARD_MM.w);
  if (screenMm < params.screenWidthMinMm || screenMm > params.screenWidthMaxMm) return 'implausible_screen';
  return null;
}

// Whether an area of w x h CSS px holds the task area at this calibration.
// Used on the page after the fullscreen step.
export function holdsTasks(w, h, pxPerMm, screenParams) {
  return w / pxPerMm >= screenParams.minWidthMm && h / pxPerMm >= screenParams.minHeightMm;
}

// Fine adjustment of the card with the arrow keys (decision 102): 1 px a
// press, 10 px with Shift; holding a key repeats. A drag of the plugin's
// red corner is coarse on a touchpad. The plugin reads the card's width only
// when the participant confirms, so the keys just resize the same element
// its corner does. Counts keys and drags for the log.
function cardControls() {
  const steps = { ArrowRight: 1, ArrowUp: 1, ArrowLeft: -1, ArrowDown: -1 };
  const counts = { keys: 0, drags: 0 };
  const onKey = (event) => {
    const step = steps[event.key];
    const item = document.querySelector('#item');
    if (!step || !item) return;
    event.preventDefault(); // no page scroll
    const width = Math.max(20, parseInt(item.style.width, 10) + step * (event.shiftKey ? 10 : 1));
    item.style.width = `${width}px`;
    item.style.height = `${Math.round(width / (CARD_MM.w / CARD_MM.h))}px`;
    counts.keys += 1;
  };
  const onDrag = () => {
    counts.drags += 1;
  };
  document.addEventListener('keydown', onKey);
  document.querySelector('#jspsych-resize-handle')?.addEventListener('mousedown', onDrag);
  return {
    counts,
    detach: () => document.removeEventListener('keydown', onKey),
  };
}

// Result of the last attempt, kept in ctx.calibration for the later blocks.
// screenWmm/screenHmm are approximate: off by the zoom factor in Chrome on a
// Mac when the page is zoomed; fullscreen_view_*_mm is exact.
function summarize(attempts) {
  const last = attempts.at(-1);
  const pxPerMm = last.card_px / CARD_MM.w;
  return {
    pxPerMm,
    attempts,
    suspect: last.problem !== null,
    dpr: window.devicePixelRatio,
    screenWmm: screen.width / pxPerMm,
    screenHmm: screen.height / pxPerMm,
  };
}

function devSquare(ctx) {
  const c = ctx.calibration;
  const side = c.pxPerMm * 100;
  return `<div class="dev-calibration">
      <div class="dev-square" style="width:${side}px;height:${side}px"></div>
      <p>Контрольний квадрат (лише dev): виміряйте лінійкою, має бути 100 × 100 мм.</p>
      <p class="dev-hint">px/мм ${round(c.pxPerMm, 3)} · картка ${c.attempts.at(-1).card_px} px ·
        екран ${round(c.screenWmm, 1)} × ${round(c.screenHmm, 1)} мм · devicePixelRatio ${c.dpr} ·
        спроб ${c.attempts.length}${c.suspect ? ' · підозріле: ' + c.attempts.at(-1).problem : ''}</p>
    </div>`;
}

export function calibrationScreens(block, ctx) {
  const params = ctx.params.calibration;
  const attempts = [];
  let controls = null;

  const card = {
    type: VirtualChinrest,
    blindspot_reps: 0,
    resize_units: 'none',
    item_path: 'src/img/card.svg',
    item_width_mm: CARD_MM.w,
    item_height_mm: CARD_MM.h,
    item_init_size: CARD_START_PX,
    adjustment_prompt: () =>
      `<div class="screen calibration">${attempts.length ? texts.calibration.retry : ''}${texts.calibration.prompt}</div>`,
    adjustment_button_prompt: texts.calibration.button,
    on_load: () => {
      controls = cardControls();
    },
    on_finish: (data) => {
      controls.detach();
      attempts.push({
        card_px: data.item_width_px,
        rt_ms: data.rt,
        problem: calibrationProblem(data.item_width_px, screen.width, params),
        drags_n: controls.counts.drags,
        keys_n: controls.counts.keys,
      });
    },
  };

  return [
    {
      timeline: [card],
      loop_function: () => attempts.at(-1).problem !== null && attempts.length < params.attempts,
      on_timeline_finish: () => {
        ctx.calibration = summarize(attempts);
        ctx.monitor.setBaseline();
      },
    },
    {
      timeline: [
        {
          type: HtmlButtonResponse,
          stimulus: () => devSquare(ctx),
          choices: [texts.common.next],
        },
      ],
      conditional_function: () => ctx.session.mode === 'dev',
    },
  ];
}

export function calibrationMessage(block, ctx) {
  const c = ctx.calibration;
  if (!c) return null;
  return {
    summary: {
      px_per_mm: round(c.pxPerMm, 4),
      calibration_card_px: c.attempts.at(-1).card_px,
      calibration_attempts: c.attempts.length,
      calibration_suspect: c.suspect ? 1 : 0,
      calibration_dpr: c.dpr,
      screen_w_mm: round(c.screenWmm, 1),
      screen_h_mm: round(c.screenHmm, 1),
    },
    log: {
      attempts: c.attempts,
      card_mm: CARD_MM,
      card_start_px: CARD_START_PX,
      screen_px: [screen.width, screen.height],
    },
  };
}
