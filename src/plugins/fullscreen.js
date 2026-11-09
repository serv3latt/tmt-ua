import { ParameterType } from '../lib.js';
import { enterFullscreen } from '../fullscreen.js';

// A screen with a text and a button that turns fullscreen on. Browsers allow
// fullscreen only straight from a click, which a plain button screen cannot
// guarantee, hence this small plugin. Data: fullscreen (whether it worked).
export class FullscreenPlugin {
  static info = {
    name: 'tmtua-fullscreen',
    version: '1.0.0',
    parameters: {
      stimulus: { type: ParameterType.HTML_STRING, default: '' },
      button_label: { type: ParameterType.STRING, default: '' },
    },
    data: {
      fullscreen: { type: ParameterType.BOOL },
    },
  };

  constructor(jsPsych) {
    this.jsPsych = jsPsych;
  }

  trial(displayElement, trial) {
    displayElement.innerHTML = `<div class="screen">${trial.stimulus}
      <p><button type="button" class="jspsych-btn">${trial.button_label}</button></p></div>`;
    const button = displayElement.querySelector('button');
    button.addEventListener('click', () => {
      button.disabled = true;
      enterFullscreen().then((ok) => this.jsPsych.finishTrial({ fullscreen: ok }));
    });
  }
}
