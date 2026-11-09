import { APP_VERSION, RECEIVER_URL } from './config.js';
import { texts } from './texts.uk.js';
import { parseUrl, buildParams, selectBlocks } from './session.js';
import { BLOCKS, isPlaceholder } from './blocks.js';
import { initJsPsych, libsLoaded } from './lib.js';
import { renderDevMenu, createDevBadge, renderDevEnd } from './dev.js';
import { renderEnvCheck } from './dev-env.js';
import { newSessionId, newParticipantCode } from './data/ids.js';
import { deviceInfo } from './data/device.js';
import { createSender } from './data/sender.js';
import { createMonitor } from './data/monitor.js';
import { fullscreenGate } from './tasks/fullscreen.js';
import {
  createFullscreenBanner,
  exitFullscreen,
  fullscreenWanted,
  isFullscreen,
} from './fullscreen.js';

// Entry point: reads the URL, then either shows a dev page or runs the
// session blocks in their fixed order, sending each block's data when the
// block ends.

function showMessage(text) {
  const message = document.createElement('p');
  message.className = 'message';
  message.textContent = text;
  document.body.replaceChildren(message);
}

// Adds what the monitor recorded around a task to the task's own message.
function withEnvironment(message, env) {
  if (!message || !env) return message;
  return {
    ...message,
    summary: { ...message.summary, ...env.summary },
    log: { ...message.log, env: env.log },
  };
}

function start() {
  document.title = texts.common.pageTitle;

  const session = parseUrl(window.location.search);
  if (session.error) return showMessage(texts.errors.badLink);
  if (!libsLoaded) return showMessage(texts.errors.loadFailed);

  const isDev = session.mode === 'dev';
  if (isDev && session.devTool !== null) {
    if (session.devTool === 'env') return renderEnvCheck(session);
    return showMessage(`Unknown dev tool: ${session.devTool}`);
  }
  if (isDev && session.devStart === null && session.devOnly === null) {
    return renderDevMenu(BLOCKS, session);
  }

  // Both can throw only in dev mode: overrides and block choice come from dev links.
  let params, blocks;
  try {
    params = buildParams(session.overrides);
    blocks = selectBlocks(BLOCKS, session);
  } catch (error) {
    return showMessage(error.message);
  }

  // Until every block is built, main mode sends nothing, so the main
  // spreadsheet stays empty until data collection starts.
  const collecting = session.mode !== 'main' || !BLOCKS.some(isPlaceholder);

  const badge = isDev ? createDevBadge(session) : null;
  const ids = { session_id: newSessionId(), participant_code: newParticipantCode() };
  let atEnd = false;
  const sender = createSender({
    url: RECEIVER_URL,
    base: { ...ids, mode: session.mode, app_version: APP_VERSION },
    meta: { session_type: 'first', started_at: new Date().toISOString(), ...deviceInfo() },
    ...params.send,
    onChange: (state) => {
      badge?.update(state);
      if (atEnd && !isDev && state.pending === 0) showMessage(texts.common.sessionEnd);
    },
  });

  const monitor = createMonitor();
  const banner = createFullscreenBanner(
    texts.fullscreen.banner,
    () => monitor.active() !== null && fullscreenWanted() && !isFullscreen(),
  );

  const jsPsych = initJsPsych({
    display_element: 'jspsych-target',
    on_finish: () => {
      exitFullscreen();
      if (isDev) return renderDevEnd(jsPsych, session, badge);
      // The participant may close the tab right after the last screen, so
      // the thank-you text appears only once everything is delivered.
      atEnd = true;
      if (sender.pending() === 0) return showMessage(texts.common.sessionEnd);
      showMessage(texts.data.sending);
      sender.flush().then((done) => done || showMessage(texts.data.offline));
    },
  });
  jsPsych.data.addProperties({ app_version: APP_VERSION, mode: session.mode, session_id: ids.session_id });

  if (isDev) {
    document.body.append(badge.element);
    // Handle for debugging in the browser console and for automated checks.
    window.tmtua = { jsPsych, params, session, sender, ids, monitor };
  }

  const ctx = { jsPsych, params, session, sender, monitor };
  const timeline = blocks.map((b) => {
    const node = {
      timeline: b.build(b, ctx),
      on_timeline_start: () => {
        if (b.isTask) monitor.startBlock(b.id);
        banner.refresh();
      },
      on_timeline_finish: () => {
        const env = b.isTask ? monitor.endBlock() : null;
        banner.refresh();
        if (collecting) sender.send(b.id, withEnvironment(b.message(b, ctx), env));
      },
    };
    return b.isTask ? { timeline: [fullscreenGate(), node] } : node;
  });
  jsPsych.run(timeline);
}

start();
