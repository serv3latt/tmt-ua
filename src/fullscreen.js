// Fullscreen mode (decisions 87, 93). Safari has the standard API only since
// version 16.4 (2023), and older Macs may still run Safari 15, so Safari's
// prefixed API is the fallback.

const root = document.documentElement;
let entered = false; // fullscreen has worked at least once in this session

export const fullscreenSupported = () =>
  Boolean(document.fullscreenEnabled || document.webkitFullscreenEnabled);

export const isFullscreen = () =>
  Boolean(document.fullscreenElement || document.webkitFullscreenElement);

// Once fullscreen has worked, the tasks expect it: leaving it is recorded,
// the banner offers a way back, and the next task waits for it. If it never
// worked, the session goes on in a normal window (decision 93).
export const fullscreenWanted = () => entered;

// Written into the data: 'entered', 'failed' (the browser refused) or
// 'unsupported' (the browser has no fullscreen for pages).
export function fullscreenStatus() {
  if (!fullscreenSupported()) return 'unsupported';
  return entered ? 'entered' : 'failed';
}

// Newer Safari fires both events, so callbacks must not mind a repeat.
export function onFullscreenChange(callback) {
  document.addEventListener('fullscreenchange', callback);
  document.addEventListener('webkitfullscreenchange', callback);
}

function changeOrTimeout(ms) {
  return new Promise((resolve) => {
    const done = () => {
      clearTimeout(timer);
      document.removeEventListener('fullscreenchange', done);
      document.removeEventListener('webkitfullscreenchange', done);
      resolve(isFullscreen());
    };
    const timer = setTimeout(done, ms);
    onFullscreenChange(done);
  });
}

// Must be called straight from a click handler: browsers allow fullscreen
// only as a response to the participant's own action. Resolves to true once
// the page is fullscreen and to false if the browser refused.
export function enterFullscreen() {
  if (isFullscreen()) return Promise.resolve(true);
  let request;
  try {
    request = root.requestFullscreen ? root.requestFullscreen() : root.webkitRequestFullscreen?.();
  } catch {
    return Promise.resolve(false);
  }
  // The prefixed API returns nothing; its result shows in the change event.
  const result = request?.then
    ? request.then(() => isFullscreen(), () => false)
    : changeOrTimeout(1000);
  return result.then((ok) => {
    if (ok) entered = true;
    return ok;
  });
}

export function exitFullscreen() {
  if (!isFullscreen()) return;
  const request = document.exitFullscreen
    ? document.exitFullscreen()
    : document.webkitExitFullscreen?.();
  request?.catch?.(() => {});
}

// A strip at the top of the page that brings fullscreen back with one click
// while a task runs (decision 87). It lies outside the task's area and stops
// its own clicks there, so a task never takes them for answers (in TMT, not
// for a click beside the circles).
export function createFullscreenBanner(label, shouldShow) {
  const banner = document.createElement('div');
  banner.className = 'fs-banner';
  banner.hidden = true;
  const button = document.createElement('button');
  button.type = 'button';
  button.textContent = label;
  banner.append(button);
  for (const type of ['pointerdown', 'pointerup', 'mousedown', 'mouseup', 'click']) {
    banner.addEventListener(type, (event) => event.stopPropagation());
  }
  button.addEventListener('click', () => enterFullscreen());

  const refresh = () => {
    banner.hidden = !shouldShow();
  };
  onFullscreenChange(refresh);
  document.body.append(banner);
  return { element: banner, refresh };
}
