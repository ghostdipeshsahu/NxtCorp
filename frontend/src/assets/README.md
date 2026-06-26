# Asset drop folder

Drop PNG / JPG / WEBP files here and they get picked up automatically by Vite
(`import.meta.glob`). No code changes needed — restart the dev server after
adding new files.

## Scene backgrounds (`scenes/`)

Full-bleed background art for each scene. 16:9 or similar, ~1024×768 works
well. The scene UI (text labels, buttons) renders ON TOP of these images.

| Filename                  | Used by      | What it should show                                |
|---------------------------|--------------|----------------------------------------------------|
| `scenes/cabin.{png,jpg,webp}`   | CabinScene   | Manager's cabin: warm lamp, wooden desk, window, awards, plants |
| `scenes/desk.{png,jpg,webp}`    | DeskScene    | Open-plan office desk at night: monitor, lamp, mug |
| `scenes/coffee.{png,jpg,webp}`  | CoffeeScene  | Office pantry: coffee machine, warm tones          |

If a file is missing, the scene falls back to its built-in CSS rendering.

## Character portraits (`characters/`)

Full-body or chest-up illustrations to display in scenes (NOT the small chat
avatars — those keep using the existing SVG). Transparent background.

| Filename                              | Used by                | Notes                          |
|---------------------------------------|------------------------|--------------------------------|
| `characters/priya.{png,webp}`         | CabinScene             | Sits behind her desk           |
| `characters/arjun.{png,webp}`         | CoffeeScene            | Leans in at the coffee machine |
| `characters/zara.{png,webp}`          | (future scenes)        | QA — sharp focused             |
| `characters/ravi.{png,webp}`          | PromotionCinematic     | CTO — distinguished            |

Optional per-expression variants take the form `{char}-{expr}.{ext}`:
e.g. `priya-happy.png`, `priya-thinking.png`, `priya-concerned.png`,
`priya-excited.png`. Code picks the closest match — exact expression match
first, then the bare `{char}.png`, then the SVG fallback.

## Where to source

- itch.io free packs: search "anime visual novel backgrounds", "office bg"
- OpenGameArt
- Pixabay / Unsplash (CC0 photos can work for backgrounds with a heavy
  filter; less so for characters)

## Format tips

- PNG/WEBP with alpha for character portraits (so the background shows through)
- JPG/WEBP for backgrounds is fine (smaller file)
- Filename is lowercase, hyphens not spaces.
