import { devUrl } from './dev.js';
import { devScale } from './scale.js';
import { enterFullscreen, exitFullscreen, fullscreenSupported, isFullscreen, onFullscreenChange } from './fullscreen.js';
import { renderField, label, pathLengthMm, minGapMm } from './tmt/field.js';
import {
  LAYOUTS_URL,
  FONTS_URL,
  FONTS_DIR,
  FIELDS_MM,
  CIRCLES_MM,
  LETTERS_MM,
  FONT_IDS,
  PARTS,
  DEFAULT_CHOICE,
  STYLE,
  WORDS,
  SPECIMEN,
} from './tmt/candidates.js';

// Dev page ?mode=dev&tool=tmt (T1.1): the author looks at the candidate
// layouts, sizes and fonts of the TMT in their real size on his own screen
// and picks. Sizes are in mm through the last calibration made in dev mode
// in this browser (scale.js); without one they are only approximate, and the
// page says so. Nothing is sent anywhere.
//
// "Try it" lets him click through a layout to feel the sizes under a mouse or
// a touchpad: start on the cross, a right click draws the line, a wrong
// circle turns red until the next right one (decisions 59, 63). It is a
// rough preview of the behaviour, not the TMT plugin (T1.2), and records
// nothing.

const CHOICE_KEY = 'tmtua.dev.tmtChoice';
const SVG_NS = 'http://www.w3.org/2000/svg';

const num = (x, digits = 1) => x.toFixed(digits).replace('.', ',');

function loadChoice() {
  const choice = structuredClone(DEFAULT_CHOICE);
  try {
    const saved = JSON.parse(localStorage.getItem(CHOICE_KEY)) ?? {};
    for (const key of ['part', 'field', 'circle', 'letter', 'font']) {
      if (key in saved) choice[key] = saved[key];
    }
    Object.assign(choice.layout, saved.layout);
    Object.assign(choice.show, saved.show);
  } catch {
    // keep the defaults
  }
  return choice;
}

function saveChoice(choice) {
  try {
    localStorage.setItem(CHOICE_KEY, JSON.stringify(choice));
  } catch {
    // the choice then lives until the page is closed
  }
}

async function loadFonts() {
  const { fonts } = await (await fetch(FONTS_URL)).json();
  const offered = FONT_IDS.map((id) => fonts.find((font) => font.id === id));
  await Promise.all(
    offered.map(async (font) => {
      const face = new FontFace(font.family, `url(${FONTS_DIR}${font.file})`, { weight: String(font.weight) });
      document.fonts.add(await face.load());
    }),
  );
  return offered;
}

// A row of buttons of which one is on.
function group(title, name, items, current) {
  const buttons = items
    .map(
      ([value, text]) =>
        `<button type="button" data-set="${name}" data-value="${value}"${
          String(value) === String(current) ? ' class="on"' : ''
        }>${text}</button>`,
    )
    .join('');
  return `<span class="tmt-group"><b>${title}</b>${buttons}</span>`;
}

// Circles with the look-alike pairs, one row per font, in the chosen size.
function renderSpecimen(fonts, circleMm, letterMm, pxPerMm) {
  const step = circleMm + 3;
  const gap = 7;
  const lineWidth = (line) => line.reduce((sum, set) => sum + set.length * step + gap, 0);
  const width = 34 + Math.max(...SPECIMEN.map(lineWidth));
  const lineHeight = circleMm + 4;
  const rowHeight = SPECIMEN.length * lineHeight + 8;
  const height = fonts.length * rowHeight;
  const svg = document.createElementNS(SVG_NS, 'svg');
  svg.setAttribute('class', 'tmt-field tmt-specimen');
  svg.setAttribute('width', width * pxPerMm);
  svg.setAttribute('height', height * pxPerMm);
  svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
  fonts.forEach((font, row) => {
    const top = rowHeight * row + 4;
    svg.append(label(font.label, 16, top + (SPECIMEN.length * lineHeight) / 2, 3, font));
    SPECIMEN.forEach((line, lineIndex) => {
      const y = top + lineHeight * lineIndex + lineHeight / 2;
      let x = 34 + circleMm / 2;
      for (const set of line) {
        for (const text of set) {
          const circle = document.createElementNS(SVG_NS, 'circle');
          circle.setAttribute('cx', x);
          circle.setAttribute('cy', y);
          circle.setAttribute('r', (circleMm - STYLE.circleStrokeMm) / 2);
          circle.setAttribute('fill', '#fff');
          circle.setAttribute('stroke', '#000');
          circle.setAttribute('stroke-width', STYLE.circleStrokeMm);
          const group = document.createElementNS(SVG_NS, 'g');
          group.setAttribute('class', 'tmt-circle');
          group.append(circle, label(text, x, y, letterMm, font));
          svg.append(group);
          x += step;
        }
        x += gap;
      }
    });
  });
  return svg;
}

export async function renderTmtOptions(session) {
  document.body.innerHTML = '<p class="message">Завантаження…</p>';
  let data, fonts;
  try {
    [data, fonts] = await Promise.all([fetch(LAYOUTS_URL).then((r) => r.json()), loadFonts()]);
  } catch (error) {
    document.body.innerHTML = `<p class="message">Не вдалося завантажити варіанти: ${error.message}</p>`;
    return;
  }

  const choice = loadChoice();
  const scale = devScale();
  let panelHidden = false;
  let trial = null; // while trying a layout: { next, errors, misses, startedAt }
  let trialResult = ''; // shown in the panel after a finished try

  document.body.innerHTML = `
    <main class="dev-tmt">
      <div class="tmt-panel"></div>
      <div class="tmt-stage"></div>
      <button type="button" class="tmt-panel-show" hidden>Показати панель (H)</button>
      <p class="tmt-trial-note" hidden>Клікніть по хрестику, щоб почати, далі — по кружечках по порядку. Esc — скасувати.</p>
    </main>`;
  const panel = document.querySelector('.tmt-panel');
  const stage = document.querySelector('.tmt-stage');
  const showButton = document.querySelector('.tmt-panel-show');
  const trialNote = document.querySelector('.tmt-trial-note');

  const current = () => {
    const fieldMm = FIELDS_MM[choice.field];
    const part = choice.part === 'letters' ? 'b' : choice.part;
    return {
      part,
      fieldMm,
      circleMm: CIRCLES_MM[choice.circle],
      letterMm: LETTERS_MM[choice.letter],
      font: fonts.find((font) => font.id === choice.font) ?? fonts[0],
      layout: data.layouts[part].find((layout) => layout.variant === choice.layout[part]),
    };
  };

  const scaleNote = () => {
    const calibrate = `<a href="${devUrl(session, { only: 'calibration' })}">відкалібрувати</a>`;
    if (scale.source === 'fallback') {
      return `<span class="tmt-warn">Масштаб приблизний: ${num(scale.pxPerMm, 2)} px/мм — у цьому браузері
        калібрування ще не було, розміри на екрані несправжні.</span> Спершу треба ${calibrate}.`;
    }
    const when = new Date(scale.savedAt).toLocaleString('uk-UA', { dateStyle: 'short', timeStyle: 'short' });
    const zoomed =
      scale.dpr !== window.devicePixelRatio
        ? ` <span class="tmt-warn">Масштаб сторінки змінився після калібрування — розміри несправжні.</span>`
        : '';
    return `Масштаб: ${num(scale.pxPerMm, 2)} px/мм, калібрування від ${when} · ${calibrate} ще раз.${zoomed}`;
  };

  const fitNote = (fieldMm) => {
    const pageW = window.innerWidth / scale.pxPerMm;
    const pageH = window.innerHeight / scale.pxPerMm;
    const fits = pageW >= fieldMm.w && pageH >= fieldMm.h;
    return `Сторінка зараз ${num(pageW, 0)} × ${num(pageH, 0)} мм: поле ${fieldMm.w} × ${fieldMm.h} мм ${
      fits ? 'влазить' : '<span class="tmt-warn">не влазить</span>'
    }${isFullscreen() ? '' : ' (не в повноекранному режимі)'}.`;
  };

  const layoutNote = (c) => {
    const lengthOf = (kind) =>
      pathLengthMm(data.layouts[kind].find((l) => l.variant === choice.layout[kind]), c.fieldMm);
    const gap = minGapMm(c.layout, c.fieldMm, c.circleMm);
    const pair = c.part.startsWith('practice') ? ['practice_a', 'practice_b'] : ['a', 'b'];
    const [a, b] = pair.map(lengthOf);
    const tight = gap < c.circleMm ? ' <span class="tmt-warn">(менше за діаметр)</span>' : '';
    return `Розташування ${c.layout.id}: найменший проміжок між кружечками ${num(gap)} мм${tight} ·
      шлях ${num(lengthOf(c.part) / 10, 0)} см · обрані ${pair[0] === 'a' ? 'A і B' : 'пробні A і B'}:
      ${num(a / 10, 0)} і ${num(b / 10, 0)} см, B довша в ${num(b / a, 2)} раза.`;
  };

  const summary = (c) =>
    `A-${choice.layout.a}, B-${choice.layout.b}, пробна A-${choice.layout.practice_a}, ` +
    `пробна B-${choice.layout.practice_b}; поле ${c.fieldMm.w}×${c.fieldMm.h} мм, кружечок ${c.circleMm} мм, ` +
    `літери ${num(c.letterMm)} мм, шрифт ${c.font.label}, підписи «Початок»/«Кінець»: ${choice.show.words ? 'так' : 'ні'}`;

  const drawPanel = (c) => {
    const variants = data.layouts[c.part].map((layout) => [layout.variant, layout.variant]);
    const check = (key, text) =>
      `<label><input type="checkbox" data-show="${key}"${choice.show[key] ? ' checked' : ''}> ${text}</label>`;
    panel.innerHTML = `
      <div class="tmt-row">
        <a href="${devUrl(session)}">← меню</a>
        ${group('Частина', 'part', [...PARTS.map((p) => [p.id, p.label]), ['letters', 'Літери зблизька']], choice.part)}
        ${choice.part === 'letters' ? '' : group('Розташування', 'layout', variants, choice.layout[c.part])}
        ${group('Шрифт', 'font', fonts.map((f) => [f.id, f.label]), choice.font)}
        <button type="button" data-act="fullscreen">${isFullscreen() ? 'Вийти з повноекранного режиму' : 'Повноекранний режим'}</button>
        <button type="button" data-act="hide">Сховати панель (H)</button>
        ${choice.part === 'letters' ? '' : '<button type="button" data-act="try">Спробувати пройти (T)</button>'}
      </div>
      <div class="tmt-row">
        ${group('Поле, мм', 'field', FIELDS_MM.map((f, i) => [i, `${f.w}×${f.h}`]), choice.field)}
        ${group('Кружечок, мм', 'circle', CIRCLES_MM.map((d, i) => [i, d]), choice.circle)}
        ${group('Літери, мм', 'letter', LETTERS_MM.map((h, i) => [i, num(h)]), choice.letter)}
        ${check('path', 'лінії шляху')} ${check('border', 'межа поля')} ${check('cross', 'хрестик')}
        ${check('words', '«Початок» і «Кінець»')}
      </div>
      <div class="tmt-row tmt-notes">
        <span class="tmt-scale">${scaleNote()}</span> <span class="tmt-fit">${fitNote(c.fieldMm)}</span>
        ${choice.part === 'letters' ? '' : `<span class="tmt-layout-note">${layoutNote(c)}</span>`}
      </div>
      <div class="tmt-row tmt-notes">
        <span>Обрано: <b class="tmt-summary">${summary(c)}</b></span>
        <button type="button" data-act="copy">Скопіювати</button>
        <span class="dev-hint">Клавіші: ← → — розташування, ↑ ↓ — частина, H — панель, T — спробувати.</span>
      </div>
      ${trialResult ? `<div class="tmt-row tmt-notes"><span class="tmt-trial-result">${trialResult}</span></div>` : ''}`;
  };

  const fieldView = (c, show) =>
    renderField({
      layout: c.layout,
      fieldMm: c.fieldMm,
      areaUnits: data.fields[c.part],
      circleMm: c.circleMm,
      letterMm: c.letterMm,
      font: c.font,
      pxPerMm: scale.pxPerMm,
      style: STYLE,
      labelBox: data.rules.label_box,
      show,
      words: WORDS,
    });

  // Any redraw ends a try that is under way: the field is drawn anew.
  const draw = () => {
    const c = current();
    trial = null;
    trialNote.hidden = true;
    drawPanel(c);
    panel.hidden = panelHidden;
    showButton.hidden = !panelHidden;
    const view =
      choice.part === 'letters'
        ? renderSpecimen(fonts, c.circleMm, c.letterMm, scale.pxPerMm)
        : fieldView(c, choice.show);
    stage.replaceChildren(view);
    saveChoice(choice);
  };

  const finishTrial = (c) => {
    const seconds = (performance.now() - trial.startedAt) / 1000;
    trialResult =
      `Спроба ${c.layout.id}: ${num(seconds)} с, помилок ${trial.errors}, кліків повз ${trial.misses}. ` +
      'Це чернетка поведінки, не сам тест: нічого не записується.';
    trial = null;
    panelHidden = false;
    drawPanel(c); // the field with its lines stays until the next change
    panel.hidden = false;
    showButton.hidden = true;
  };

  const onTrialClick = (event, view, c) => {
    if (!trial) return;
    const rect = view.getBoundingClientRect();
    const x = (event.clientX - rect.left) / scale.pxPerMm - c.fieldMm.w / 2;
    const y = (event.clientY - rect.top) / scale.pxPerMm - c.fieldMm.h / 2;
    if (trial.next === -1) {
      if (Math.hypot(x, y) > STYLE.crossMm / 2 + 1) return;
      trial.next = 0;
      trial.startedAt = performance.now();
      view.classList.remove('tmt-waiting');
      view.querySelector('.tmt-cross').remove();
      trialNote.hidden = true;
      return;
    }
    const circle = event.target.closest('.tmt-circle');
    if (!circle) {
      trial.misses += 1; // counted apart, not an error (decision 63)
      return;
    }
    const index = Number(circle.dataset.index);
    if (index < trial.next) return; // already connected
    if (index > trial.next) {
      trial.errors += 1;
      circle.classList.add('tmt-wrong');
      return;
    }
    for (const wrong of view.querySelectorAll('.tmt-wrong')) wrong.classList.remove('tmt-wrong');
    if (index > 0) {
      const unit = c.fieldMm.h / 100;
      const [x0, y0] = c.layout.points[index - 1];
      const [x1, y1] = c.layout.points[index];
      const line = document.createElementNS(SVG_NS, 'line');
      for (const [key, value] of Object.entries({ x1: x0 * unit, y1: y0 * unit, x2: x1 * unit, y2: y1 * unit })) {
        line.setAttribute(key, value);
      }
      line.setAttribute('class', 'tmt-trial-line');
      line.setAttribute('stroke', '#000');
      line.setAttribute('stroke-width', STYLE.lineMm);
      view.insertBefore(line, view.querySelector('.tmt-circle'));
    }
    trial.next += 1;
    if (trial.next === c.layout.points.length) finishTrial(c);
  };

  const startTrial = () => {
    if (choice.part === 'letters') return;
    trialResult = '';
    panelHidden = true;
    draw();
    const c = current();
    const view = fieldView(c, { ...choice.show, path: false, cross: true });
    view.classList.add('tmt-waiting');
    view.addEventListener('pointerdown', (event) => onTrialClick(event, view, c));
    stage.replaceChildren(view);
    trial = { next: -1, errors: 0, misses: 0, startedAt: null };
    trialNote.hidden = false;
    showButton.hidden = true; // it lies over the field corner; Esc brings the panel back
  };

  const set = (name, value) => {
    if (name === 'layout') choice.layout[current().part] = Number(value);
    else if (name === 'part' || name === 'font') choice[name] = value;
    else choice[name] = Number(value);
    draw();
  };

  const step = (list, value, by) => list[(list.indexOf(value) + by + list.length) % list.length];

  panel.addEventListener('click', (event) => {
    const button = event.target.closest('button');
    if (!button) return;
    if (button.dataset.set) return set(button.dataset.set, button.dataset.value);
    if (button.dataset.act === 'fullscreen') return isFullscreen() ? exitFullscreen() : enterFullscreen();
    if (button.dataset.act === 'hide') {
      panelHidden = true;
      return draw();
    }
    if (button.dataset.act === 'try') return startTrial();
    if (button.dataset.act === 'copy') {
      navigator.clipboard?.writeText(summary(current())).then(
        () => (button.textContent = 'Скопійовано'),
        () => (button.textContent = 'Не вдалося — виділіть текст'),
      );
    }
  });
  panel.addEventListener('change', (event) => {
    const key = event.target.dataset.show;
    if (!key) return;
    choice.show[key] = event.target.checked;
    draw();
  });
  showButton.addEventListener('click', () => {
    panelHidden = false;
    draw();
  });
  document.addEventListener('keydown', (event) => {
    if (event.metaKey || event.ctrlKey || event.altKey) return;
    if (event.code === 'KeyH') {
      panelHidden = !panelHidden;
      return draw();
    }
    if (event.code === 'KeyT') return startTrial();
    if (event.key === 'Escape' && trial) {
      panelHidden = false;
      return draw();
    }
    const parts = [...PARTS.map((p) => p.id), 'letters'];
    if (event.key === 'ArrowUp' || event.key === 'ArrowDown') {
      event.preventDefault();
      return set('part', step(parts, choice.part, event.key === 'ArrowDown' ? 1 : -1));
    }
    if ((event.key === 'ArrowLeft' || event.key === 'ArrowRight') && choice.part !== 'letters') {
      event.preventDefault();
      const variants = data.layouts[choice.part].map((layout) => layout.variant);
      set('layout', step(variants, choice.layout[choice.part], event.key === 'ArrowRight' ? 1 : -1));
    }
  });
  window.addEventListener('resize', draw);
  if (fullscreenSupported()) onFullscreenChange(draw);

  // Handle for automated checks.
  window.tmtuaOptions = { choice, scale, data, fonts, current };
  draw();
}
