import { HtmlButtonResponse } from '../lib.js';
import { texts } from '../texts.uk.js';
import { FullscreenPlugin } from '../plugins/fullscreen.js';
import { holdsTasks } from './calibration.js';
import {
  fullscreenStatus,
  fullscreenSupported,
  fullscreenWanted,
  isFullscreen,
} from '../fullscreen.js';

// Block "fullscreen": turns fullscreen on before the first task. If the
// browser has no fullscreen or refuses it, the participant is asked to
// maximise the window and the session goes on, with the status in the data
// (decision 93). Then the page must hold the task area at the calibrated
// scale: without fullscreen the participant may enlarge the window and check
// again a few times (decision 101); if it still does not fit, or does not
// fit even in fullscreen (the screen is too small), the session ends
// (screen_too_small). Without a calibration (dev links that skip it) there
// is nothing to check.
export function fullscreenScreens(block, ctx) {
  const state = { checks: 0, viewMm: null };
  ctx.fullscreen = state;
  const fits = () =>
    holdsTasks(window.innerWidth, window.innerHeight, ctx.calibration.pxPerMm, ctx.params.screen);

  const enter = {
    timeline: [
      {
        type: FullscreenPlugin,
        stimulus: texts.fullscreen.enter,
        button_label: texts.fullscreen.enterButton,
      },
    ],
    conditional_function: fullscreenSupported,
  };
  const unavailable = {
    timeline: [
      {
        type: HtmlButtonResponse,
        stimulus: `<div class="screen">${texts.fullscreen.unavailable}</div>`,
        choices: [texts.common.next],
      },
    ],
    conditional_function: () => !isFullscreen(),
  };
  const enlargeWindow = {
    timeline: [
      {
        type: HtmlButtonResponse,
        stimulus: `<div class="screen">${texts.screen.windowTooSmall}</div>`,
        choices: [texts.screen.recheck],
        on_finish: () => {
          state.checks += 1;
        },
      },
    ],
    conditional_function: () => ctx.calibration !== null && !isFullscreen() && !fits(),
    loop_function: () => !fits() && state.checks < ctx.params.screen.windowChecks,
  };

  return [
    {
      timeline: [enter, unavailable, enlargeWindow],
      on_timeline_finish: () => {
        if (ctx.calibration === null) return;
        const { pxPerMm } = ctx.calibration;
        state.viewMm = [window.innerWidth / pxPerMm, window.innerHeight / pxPerMm];
        if (!fits()) ctx.end('screen_too_small');
      },
    },
  ];
}

const round1 = (x) => Math.round(x * 10) / 10;

export function fullscreenMessage(block, ctx) {
  const summary = { fullscreen_status: fullscreenStatus() };
  const state = ctx.fullscreen;
  if (state?.viewMm) {
    summary.fullscreen_view_w_mm = round1(state.viewMm[0]);
    summary.fullscreen_view_h_mm = round1(state.viewMm[1]);
    summary.fullscreen_window_checks = state.checks;
  }
  return { summary };
}

// Goes before every task (decision 87): if the participant left fullscreen,
// the next task does not start until it is back. Repeats if the browser
// refused to return.
export function fullscreenGate() {
  return {
    timeline: [
      {
        type: FullscreenPlugin,
        stimulus: texts.fullscreen.gate,
        button_label: texts.fullscreen.gateButton,
      },
    ],
    conditional_function: () => fullscreenWanted() && !isFullscreen(),
    loop_function: () => !isFullscreen(),
  };
}
