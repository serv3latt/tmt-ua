// jsPsych and its plugins come from the CDN as classic scripts (index.html)
// and register globals; this module turns them into ordinary imports.
// If the CDN failed or a file did not match its integrity hash, they are
// missing and main.js shows an error instead of starting. ParameterType is
// then an empty object, so that our own plugins, which use it as soon as
// they are imported, do not break the page before that error can be shown.

export const initJsPsych = globalThis.initJsPsych;
export const ParameterType = globalThis.jsPsychModule?.ParameterType ?? {};
export const HtmlButtonResponse = globalThis.jsPsychHtmlButtonResponse;
export const VirtualChinrest = globalThis.jsPsychVirtualChinrest;

export const libsLoaded = Boolean(
  initJsPsych && globalThis.jsPsychModule?.ParameterType && HtmlButtonResponse && VirtualChinrest,
);
