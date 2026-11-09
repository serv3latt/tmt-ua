import { devUrl } from './dev.js';
import { detectBrowser, detectOs } from './data/device.js';
import { createMonitor, windowSnapshot } from './data/monitor.js';
import {
  enterFullscreen,
  exitFullscreen,
  fullscreenSupported,
  isFullscreen,
  onFullscreenChange,
} from './fullscreen.js';

// Dev page ?mode=dev&tool=env for checks by hand on real devices (T0.5):
// whether keys reach the page in fullscreen (Safari used to block typing
// there; coding needs digits and SART the space bar), how the window and
// scale readings change, and what the monitor would record during a task.
// Nothing is sent anywhere.

const DIGITS = ['1', '2', '3', '4', '5', '6', '7', '8', '9'];

const EVENT_LABELS = {
  hidden: 'вкладку сховано або вікно згорнуто',
  visible: 'вкладка знову видима',
  blur: 'вікно втратило фокус',
  focus: 'фокус повернувся',
  fs_exit: 'вихід із повноекранного режиму',
  fs_enter: 'повернення в повноекранний режим',
  resize: 'зміна розміру вікна',
  zoom: 'зміна масштабу',
};

// The digit a key stands for, by its place on the keyboard (top row or
// numeric keypad), so that any layout works (decision 82); ' ' for space.
function keyOf(event) {
  const match = event.code.match(/^(?:Digit|Numpad)([1-9])$/);
  if (match) return match[1];
  if (event.code === 'Space' || event.key === ' ') return ' ';
  return DIGITS.includes(event.key) ? event.key : null;
}

function describe(event) {
  let text = `${(event.t / 1000).toFixed(1)} с · ${EVENT_LABELS[event.type] ?? event.type}`;
  if (event.type === 'resize' || event.type === 'zoom') {
    text += ` · ${event.w}×${event.h}, вікно ${event.ow}×${event.oh}, dpr ${event.dpr}, масштаб ${event.scale}`;
    if (event.by_fullscreen) text += ' · через повноекранний режим, не рахується';
  }
  if (event.at_start) text += ' · уже на початку';
  return text;
}

export function renderEnvCheck(session) {
  const cells = [...DIGITS, ' ']
    .map((k) => `<span class="env-key" data-key="${k}">${k === ' ' ? 'пробіл' : k}</span>`)
    .join('');
  document.body.innerHTML = `
    <main class="dev-env">
      <h1>Перевірка середовища · dev</h1>
      <p><a href="${devUrl(session)}">До меню</a> · <span class="env-browser"></span></p>

      <h2>1. Клавіші в повноекранному режимі</h2>
      <p>Увімкніть повноекранний режим і натисніть по черзі 1–9 і пробіл. Клітинка
        зеленіє, лише якщо сторінка отримала натискання в повноекранному режимі.</p>
      <p>
        <button type="button" class="env-fs-enter">Увімкнути повноекранний режим</button>
        <button type="button" class="env-fs-exit">Вимкнути</button>
        Зараз: <b class="env-fs-state"></b>
      </p>
      <p class="env-keys">${cells}</p>
      <ol class="env-key-log" reversed></ol>

      <h2>2. Вікно й масштаб зараз</h2>
      <p class="env-window"></p>

      <h2>3. Що записав би монітор під час завдання</h2>
      <p>Спробуйте: перейти на іншу вкладку й назад, клікнути в іншу програму, вийти з
        повноекранного режиму клавішею Esc, змінити масштаб (Cmd або Ctrl і «+», потім
        «0»), змінити розмір вікна.</p>
      <ol class="env-events"></ol>
    </main>`;

  const $ = (selector) => document.querySelector(selector);
  const browser = detectBrowser(navigator.userAgent);
  $('.env-browser').textContent =
    `${browser.name} ${browser.version}, ${detectOs(navigator.userAgent, navigator.maxTouchPoints)}`;

  const showState = () => {
    $('.env-fs-state').textContent = !fullscreenSupported()
      ? 'браузер не підтримує повноекранний режим'
      : isFullscreen()
        ? 'повноекранний режим'
        : 'звичайне вікно';
  };
  showState();
  onFullscreenChange(showState);
  $('.env-fs-enter').addEventListener('click', () => enterFullscreen().then(showState));
  $('.env-fs-exit').addEventListener('click', exitFullscreen);

  document.addEventListener('keydown', (event) => {
    const key = keyOf(event);
    const item = document.createElement('li');
    item.textContent = `key «${event.key}» · code ${event.code} · ${isFullscreen() ? 'повноекранний' : 'звичайне вікно'}`;
    $('.env-key-log').prepend(item);
    if (key === null) return;
    event.preventDefault(); // as in the tasks: no page scroll on space
    if (isFullscreen()) $(`.env-key[data-key="${key}"]`).classList.add('env-key-ok');
  });

  const showWindow = () => {
    const s = windowSnapshot();
    $('.env-window').textContent =
      `сторінка ${s.w}×${s.h} · вікно ${s.ow}×${s.oh} · екран ${screen.width}×${screen.height}` +
      ` · devicePixelRatio ${s.dpr} · масштаб жестом ${s.scale}`;
  };
  showWindow();
  setInterval(showWindow, 500);

  const monitor = createMonitor({
    onEvent: (event) => {
      const item = document.createElement('li');
      item.textContent = describe(event);
      $('.env-events').append(item);
    },
  });
  monitor.startBlock('env');
}
