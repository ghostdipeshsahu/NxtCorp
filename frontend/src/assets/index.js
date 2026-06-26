// Asset auto-discovery — Vite's import.meta.glob scans the folders at build
// time and gives us a {path: url} map. Drop new files in scenes/ or
// characters/ and they appear automatically after a dev server restart.
//
// Public helpers:
//   getSceneBackground('cabin') -> url or null
//   getCharacterPortrait('priya', 'happy') -> url or null

const sceneModules = import.meta.glob('./scenes/*.{png,jpg,jpeg,webp,avif,svg}', {
  eager: true,
  import: 'default',
});

const characterModules = import.meta.glob(
  './characters/*.{png,jpg,jpeg,webp,avif,svg}',
  { eager: true, import: 'default' },
);


function stemOf(path) {
  // './scenes/cabin.png' -> 'cabin'
  const m = path.match(/\/([^/]+)\.[^.]+$/);
  return m ? m[1].toLowerCase() : null;
}

// Build {stem: url} indexes.
const SCENE_BG = (() => {
  const out = {};
  for (const [path, url] of Object.entries(sceneModules)) {
    const stem = stemOf(path);
    if (stem) out[stem] = url;
  }
  return out;
})();

const CHAR_PORTRAITS = (() => {
  const out = {};
  for (const [path, url] of Object.entries(characterModules)) {
    const stem = stemOf(path);
    if (stem) out[stem] = url;
  }
  return out;
})();


export function getSceneBackground(name) {
  return SCENE_BG[name.toLowerCase()] || null;
}

export function getCharacterPortrait(character, expression) {
  const c = String(character || '').toLowerCase();
  const e = String(expression || '').toLowerCase();
  // Try character-expression, then plain character.
  if (e && CHAR_PORTRAITS[`${c}-${e}`]) return CHAR_PORTRAITS[`${c}-${e}`];
  return CHAR_PORTRAITS[c] || null;
}

// For debugging / dev panel.
export function listAvailableAssets() {
  return {
    scenes: Object.keys(SCENE_BG),
    characters: Object.keys(CHAR_PORTRAITS),
  };
}
