import { MODES, PARAMS } from './config.js';

// Reads the page URL. Returns { mode, devStart, devOnly, devTool, overrides },
// or { error } when the link is malformed. Unknown modes are rejected rather
// than treated as main, so a mistyped pilot link never writes into the main
// data.
export function parseUrl(search) {
  const query = new URLSearchParams(search);
  const mode = query.get('mode') ?? 'main';
  if (!MODES.includes(mode)) return { error: 'bad_mode' };

  const session = { mode, devStart: null, devOnly: null, devTool: null, overrides: {} };
  if (mode !== 'dev') return session;

  session.devStart = query.get('start');
  session.devOnly = query.get('only');
  session.devTool = query.get('tool');
  for (const [key, value] of query) {
    if (key.startsWith('set.')) session.overrides[key.slice('set.'.length)] = value;
  }
  return session;
}

// Returns a copy of the parameters with dev overrides applied. Only existing
// numeric parameters can be overridden, so a typo in the URL fails loudly
// instead of being silently ignored.
export function buildParams(overrides, base = PARAMS) {
  const params = structuredClone(base);
  for (const [path, raw] of Object.entries(overrides)) {
    const keys = path.split('.');
    const last = keys.pop();
    const parent = keys.reduce((obj, key) => obj?.[key], params);
    const value = Number(raw);
    if (typeof parent?.[last] !== 'number' || raw === '' || !Number.isFinite(value)) {
      throw new Error(`Unknown or non-numeric parameter: set.${path}=${raw}`);
    }
    parent[last] = value;
  }
  return params;
}

// Picks the blocks to run: all of them, or in dev mode one block (only=)
// or everything from a given block on (start=).
export function selectBlocks(blocks, session) {
  const id = session.devOnly ?? session.devStart;
  if (id === null) return blocks;
  const index = blocks.findIndex((block) => block.id === id);
  if (index === -1) throw new Error(`Unknown block: ${id}`);
  return session.devOnly ? [blocks[index]] : blocks.slice(index);
}
