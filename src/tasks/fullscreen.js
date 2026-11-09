import { HtmlButtonResponse } from '../lib.js';
import { texts } from '../texts.uk.js';
import { FullscreenPlugin } from '../plugins/fullscreen.js';
import {
  fullscreenStatus,
  fullscreenSupported,
  fullscreenWanted,
  isFullscreen,
} from '../fullscreen.js';

// Block "fullscreen": turns fullscreen on before the first task. If the
// browser has no fullscreen or refuses it, the participant is asked to
// maximise the window and the session goes on, with the status in the data
// (decision 93; whether the task area fits the window is checked with
// calibration, T0.6).
export function fullscreenScreens() {
  return [
    {
      timeline: [
        {
          type: FullscreenPlugin,
          stimulus: texts.fullscreen.enter,
          button_label: texts.fullscreen.enterButton,
        },
      ],
      conditional_function: fullscreenSupported,
    },
    {
      timeline: [
        {
          type: HtmlButtonResponse,
          stimulus: `<div class="screen">${texts.fullscreen.unavailable}</div>`,
          choices: [texts.common.next],
        },
      ],
      conditional_function: () => !isFullscreen(),
    },
  ];
}

export const fullscreenMessage = () => ({ summary: { fullscreen_status: fullscreenStatus() } });

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
