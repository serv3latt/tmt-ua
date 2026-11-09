// App-wide settings. APP_VERSION is written into every data row. Once data
// collection starts, any change in the app needs the author's decision and a
// new version number (CLAUDE.md). Decision numbers refer to
// docs/05-history-and-decisions.md in the private research repo.

export const APP_VERSION = '0.2.0';

// Values allowed in the ?mode= URL parameter; no parameter means 'main'.
// pilot and dev write to the pilot copies of the spreadsheets (decision 53).
export const MODES = ['main', 'pilot', 'dev'];

// Google Apps Script web app that stores the data; routes rows by mode
// (receiver/Code.gs). Redeploying a new version keeps this URL.
export const RECEIVER_URL =
  'https://script.google.com/macros/s/AKfycbwMoh04a4S9_JvBzR4s4yWavwa4wUuTVS2WzYtZOCo8RMeg_t2x-I9d_R_ebUjY2NkL4g/exec';

// Task parameters approved by the author. In dev mode any number here can be
// overridden from the URL, e.g. ?mode=dev&set.tmt.timeLimitMs=20000
// (see session.js); main and pilot always use these values.
export const PARAMS = {
  tmt: {
    timeLimitMs: 300_000, // decision 57
    practiceMaxAttempts: 5, // decision 58
    practiceHintAfterAttempts: 2, // decision 58
    trajectoryHz: 30, // decision 61
  },
  coding: {
    durationMs: 90_000, // protocol
    practiceItems: 10, // decision 80
    practiceRepeatAtErrors: 3, // decision 80
  },
  stroop: {
    practiceTrials: 12, // decision 92
    practiceMinCorrect: 9, // decision 92
    mainTrials: 96, // decision 84
    responseLimitMs: 5000, // decision 91
    itiMs: 500, // decision 93
  },
  sart: {
    practiceTrials: 18, // decision 85
    mainTrials: 225, // decision 66
    digitMs: 250, // Robertson et al., 1997
    maskMs: 900, // Robertson et al., 1997
  },
  // Technical, not research parameters: how data delivery waits and retries
  // (data/sender.js). The receiver's first reply after a pause takes ~7 s.
  send: {
    timeoutMs: 30_000,
    retryBaseMs: 2000,
    retryMaxMs: 30_000,
  },
};
