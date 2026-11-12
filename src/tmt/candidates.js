// Options the author chooses from in T1.1 (open question B3): field size,
// circle diameter, letter height, font, and the layout of each part. Shown
// on the dev page ?mode=dev&tool=tmt (dev-tmt.js). When the choice is made,
// the chosen values move to PARAMS.tmt in config.js and this file goes away.

export const LAYOUTS_URL = 'stimuli/tmt-layout-candidates.json';
export const FONTS_URL = 'src/fonts/fonts.json';
export const FONTS_DIR = 'src/fonts/';

// The field keeps the 16:10 proportion the layouts are generated for.
export const FIELDS_MM = [
  { w: 224, h: 140 },
  { w: 240, h: 150 },
  { w: 256, h: 160 },
];
export const CIRCLES_MM = [10, 11, 12];
export const LETTERS_MM = [4, 4.5, 5];

// Fonts offered; the files and their metrics are in src/fonts/fonts.json.
export const FONT_IDS = ['inter', 'montserrat', 'arsenal'];

export const PARTS = [
  { id: 'a', label: 'A' },
  { id: 'b', label: 'B' },
  { id: 'practice_a', label: 'Пробна A' },
  { id: 'practice_b', label: 'Пробна B' },
];

export const DEFAULT_CHOICE = {
  part: 'a',
  layout: { a: 1, b: 1, practice_a: 1, practice_b: 1 },
  field: 1,
  circle: 1,
  letter: 1,
  font: 'inter',
  show: { path: false, border: true, cross: false, words: false },
};

// Not offered as options: drawing details.
export const STYLE = {
  circleStrokeMm: 0.4,
  lineMm: 0.5,
  crossMm: 8,
  wordMm: 3,
};

export const WORDS = { start: 'Початок', end: 'Кінець' };

// What to look at when choosing the font, in two lines per font: the pairs
// named in decision 121, then other look-alikes and the widest labels.
export const SPECIMEN = [
  [['З', '3'], ['Г', 'Ґ'], ['Е', 'Є'], ['И', 'І']],
  [['І', '1'], ['В', '8', '13'], ['Б', '6'], ['10', '12', '25']],
];
