import { HtmlButtonResponse } from '../lib.js';
import { texts } from '../texts.uk.js';
import { deviceInfo, deviceRejection } from '../data/device.js';

// Block "device_check": phones and tablets are turned away on the first
// screen, which then stays for good, without a button. Nothing is recorded
// about them: the person has not consented yet (decision 97). An accepted
// device is described by the device fields of the session's first message.
export function deviceCheck() {
  return [
    {
      timeline: [
        {
          type: HtmlButtonResponse,
          stimulus: `<div class="screen">${texts.device.rejected}</div>`,
          choices: [],
        },
      ],
      conditional_function: () => deviceRejection(deviceInfo()) !== null,
    },
  ];
}

export const deviceCheckMessage = () => null;
