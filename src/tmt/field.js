// Draws a TMT field as SVG in real millimetres. Used by the options page
// (dev-tmt.js, T1.1) and later by the TMT plugin (T1.2).
//
// Layout coordinates are in field units (tools/tmt_layouts.py): 1 unit is
// 1/100 of the height of the full field, origin in the field centre. The SVG
// user unit is 1 mm, and the SVG is sized in CSS px from the calibration, so
// everything inside is set in mm.

const SVG_NS = 'http://www.w3.org/2000/svg';

function el(name, attrs = {}, text = null) {
  const node = document.createElementNS(SVG_NS, name);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
  if (text !== null) node.textContent = text;
  return node;
}

const mm = (x) => Number(x.toFixed(3));

// Text whose capital letters are exactly `heightMm` tall and centred on
// (x, y). font.cap is the height of a capital as a share of the font size
// (src/fonts/fonts.json), so the result does not depend on how a browser
// aligns text vertically.
export function label(text, x, y, heightMm, font, attrs = {}) {
  return el(
    'text',
    {
      x: mm(x),
      y: mm(y + heightMm / 2),
      'font-size': mm(heightMm / font.cap),
      'font-family': `'${font.family}'`,
      'font-weight': font.weight,
      'text-anchor': 'middle',
      ...attrs,
    },
    text,
  );
}

// options: {
//   layout      one layout from the layouts file ({ points, labels, label_sides })
//   fieldMm     { w, h } of the full field in mm; the unit is h / 100
//   areaUnits   { w, h } of this layout's own area in units (smaller for practice)
//   circleMm    circle diameter
//   letterMm    height of capital letters and digits in the circles
//   font        { family, weight, cap }
//   pxPerMm     from the calibration
//   style       { circleStrokeMm, lineMm, crossMm, wordMm }
//   labelBox    rules.label_box from the layouts file, for the words
//   show        { path, border, cross, words }
//   words       { start, end }
// }
export function renderField(options) {
  const { layout, fieldMm, areaUnits, circleMm, letterMm, font, pxPerMm, style, show = {} } = options;
  const unit = fieldMm.h / 100;
  const svg = el('svg', {
    class: 'tmt-field',
    width: mm(fieldMm.w * pxPerMm),
    height: mm(fieldMm.h * pxPerMm),
    viewBox: `${-fieldMm.w / 2} ${-fieldMm.h / 2} ${fieldMm.w} ${fieldMm.h}`,
  });
  svg.dataset.layout = layout.id;

  if (show.border) {
    const frame = { fill: 'none', stroke: '#9aa', 'stroke-width': 0.25, 'stroke-dasharray': '2 2' };
    svg.append(el('rect', { x: -fieldMm.w / 2, y: -fieldMm.h / 2, width: fieldMm.w, height: fieldMm.h, ...frame }));
    if (areaUnits.w * unit < fieldMm.w) {
      const w = areaUnits.w * unit;
      const h = areaUnits.h * unit;
      svg.append(el('rect', { x: mm(-w / 2), y: mm(-h / 2), width: mm(w), height: mm(h), ...frame }));
    }
  }

  const points = layout.points.map(([x, y]) => [x * unit, y * unit]);
  if (show.path) {
    svg.append(
      el('polyline', {
        class: 'tmt-path',
        points: points.map(([x, y]) => `${mm(x)},${mm(y)}`).join(' '),
        fill: 'none',
        stroke: '#000',
        'stroke-width': style.lineMm,
        'stroke-linejoin': 'round',
      }),
    );
  }

  points.forEach(([x, y], index) => {
    const group = el('g', { class: 'tmt-circle' });
    group.dataset.index = index;
    group.dataset.label = layout.labels[index];
    group.append(
      el('circle', {
        cx: mm(x),
        cy: mm(y),
        r: mm((circleMm - style.circleStrokeMm) / 2), // the outline stays inside the diameter
        fill: '#fff',
        stroke: '#000',
        'stroke-width': style.circleStrokeMm,
      }),
      label(layout.labels[index], x, y, letterMm, font),
    );
    svg.append(group);
  });

  if (show.words) {
    const box = options.labelBox;
    for (const [index, key] of [[0, 'start'], [points.length - 1, 'end']]) {
      const side = layout.label_sides[key];
      const centre = (box.offset + box.h / 2) * unit * (side === 'above' ? -1 : 1);
      const [x, y] = points[index];
      svg.append(label(options.words[key], x, y + centre, style.wordMm, font, { class: 'tmt-word' }));
    }
  }

  if (show.cross) {
    const arm = style.crossMm / 2;
    svg.append(
      el('path', {
        class: 'tmt-cross',
        d: `M${-arm} 0H${arm}M0 ${-arm}V${arm}`,
        stroke: '#000',
        'stroke-width': style.lineMm,
      }),
    );
  }
  return svg;
}

// Length of the correct path in mm on a field of this height.
export function pathLengthMm(layout, fieldMm) {
  const unit = fieldMm.h / 100;
  let total = 0;
  for (let i = 1; i < layout.points.length; i += 1) {
    const [x0, y0] = layout.points[i - 1];
    const [x1, y1] = layout.points[i];
    total += Math.hypot(x1 - x0, y1 - y0) * unit;
  }
  return total;
}

// Smallest gap between the edges of two circles, in mm.
export function minGapMm(layout, fieldMm, circleMm) {
  const unit = fieldMm.h / 100;
  let smallest = Infinity;
  for (let i = 0; i < layout.points.length; i += 1) {
    for (let j = i + 1; j < layout.points.length; j += 1) {
      const [x0, y0] = layout.points[i];
      const [x1, y1] = layout.points[j];
      smallest = Math.min(smallest, Math.hypot(x1 - x0, y1 - y0) * unit);
    }
  }
  return smallest - circleMm;
}
