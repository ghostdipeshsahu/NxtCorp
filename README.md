# NxtCorp

Narrative-based learning game. Students play an **AI Trainee** at a fictional Hyderabad tech company called NxtCorp. They learn to supervise AI: write a prompt precisely enough that the AI produces correct code, and verify it did. Students never write code — they write instructions.

This repo contains the FastAPI backend, the React frontend, the offline question-authoring script, and the deployment configs for Render/Railway + Vercel.

## Layout

```
nxtcorp/
├── backend/           FastAPI + SQLAlchemy + Anthropic
│   ├── agents/        Coach (Priya) + Assessor
│   ├── auth/          bcrypt + JWT
│   ├── core/          Code generator, code executor (subprocess + exec), question loader, progression
│   ├── db/            SQLAlchemy models + engine
│   ├── models/        Pydantic schemas
│   ├── routes/        auth, onboarding, task, story
│   └── services/      run_pipeline (orchestrator), profile builder, story event engine
├── frontend/          React 18 + Vite + Tailwind v3
│   └── src/components/
│       ├── Auth/      Login + register
│       ├── Onboarding/ Welcome → Name → Avatar (5 variants) → Pronouns → Day 1 story
│       ├── Office/    Three-panel office UI (OfficeView, TopBar, Characters)
│       ├── Task/      JIRA-like ticket card, prompt editor, test results
│       ├── Chat/      Slack-like chat with programmatic SVG avatars
│       ├── Profile/   SkillProfile modal (5 skills + badges + level + streak)
│       └── Story/     Story event overlay
├── questions/         Enriched JSON files (p001_detect_capital.json + future)
├── scripts/           Verification harnesses (test_step2..test_step11) + author.py
├── .github/workflows/ CI: backend no-LLM tests + frontend build
├── Procfile           Heroku-style start command
├── render.yaml        Render blueprint (backend + Postgres DB)
├── railway.json       Railway config
├── runtime.txt        Python 3.11
└── frontend/vercel.json  Vercel SPA + rewrite config
```

## Build order (already complete)

1. ✅ Project skeleton + DB models + JWT auth + seed question
2. ✅ Code Executor — subprocess sandbox + per-attempt timeout
3. ✅ Code Generator — literalist system prompt, defensive parsing
4. ✅ Assessor Agent — LLM-judged requirement score + deterministic output score + gap detection
5. ✅ Coach Agent — Priya's voice + 4-level Socratic escalation
6. ✅ FastAPI endpoints — `/api/task/{current,run,respond}` + full loop persistence
7. ✅ React frontend — three-panel office, programmatic SVG avatars
8. ✅ Onboarding flow + Day 1 story (Priya welcome + Arjun intro)
9. ✅ Progression — daily streak, level promotions, Ravi promotion messages, badges
10. ✅ Story events — Act 1 catalog with prereq chains + XP grants
11. ✅ Author script — offline question enrichment with validation + reference verification
12. ✅ GitHub setup + deployment configs (this step)

## Local development

### Backend

Requires Python 3.11+. SQLite is the default local DB.

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux
pip install -r requirements.txt
copy .env.example .env          # Windows  (cp on macOS / Linux)
# edit .env: set ANTHROPIC_API_KEY, JWT_SECRET
```

Run from the **project root** (so `backend.*` imports resolve):

```bash
cd ..
uvicorn backend.main:app --reload --port 8000
```

DB tables auto-create on startup via `init_db()`.

### Frontend

```bash
cd frontend
npm install
npm run dev      # serves on http://localhost:5173, /api proxied to :8000
```

Open `http://localhost:5173`. Register a new account, walk through onboarding, submit a prompt for P001.

### Verification harnesses

Each step has a deterministic test script in `scripts/`. The non-LLM ones run in CI:

```bash
python -m scripts.test_step2      # Code Executor on P001
python -m scripts.test_step9      # progression (streak, level, badges)
python -m scripts.test_step10     # story event engine
python -m scripts.test_step11     # author script (offline scenarios)
```

LLM-touching tests (require credits):

```bash
python -m scripts.test_step3      # Code Generator (literalism: vague fails, precise passes)
python -m scripts.test_step4      # Assessor (gap detection on canned outcomes)
python -m scripts.test_step5      # Coach (full L1..L4 Socratic ladder)
python -m scripts.test_step6      # Full pipeline integration via TestClient
python -m scripts.test_step8      # Onboarding endpoint
python -m scripts.test_step11 --live  # Author live call
```

## Deployment

### Backend → Render (Blueprint)

The repo includes `render.yaml` that provisions:

- A web service running `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
- A Starter-plan Postgres DB with `DATABASE_URL` auto-wired

Steps:

1. Push the repo to GitHub.
2. On Render: **New +** → **Blueprint** → point at your repo.
3. Render will read `render.yaml` and prompt for the `sync: false` env vars:
   - `ANTHROPIC_API_KEY` — your key
   - `ANTHROPIC_BASE_URL` — empty for direct Anthropic, `https://openrouter.ai/api` for OpenRouter
   - `ANTHROPIC_MODEL` — e.g. `claude-sonnet-4-6` or `anthropic/claude-haiku-4.5`
   - `CORS_ORIGINS` — your Vercel URL, e.g. `https://nxtcorp.vercel.app`
4. `JWT_SECRET` is `generateValue: true` so Render mints a strong one.
5. Health check on `/api/health`.

### Backend → Railway

```
railway up
```
…with the repo connected. `railway.json` declares the start command and health check path. Add a Postgres plugin, then set the same env vars listed in the Render section.

### Backend → any platform with Procfile

`web: uvicorn backend.main:app --host 0.0.0.0 --port $PORT`

### Frontend → Vercel

1. Import the repo on Vercel, set **Root Directory** to `frontend/`.
2. Vercel auto-detects Vite (`vercel.json` enforces it).
3. Set the env var `VITE_API_BASE` to your backend URL, e.g. `https://nxtcorp-api.onrender.com` (no trailing slash).
4. Deploy.

`vercel.json` includes the SPA rewrite (`/(.*) → /index.html`) so client-side routing works.

## Env vars cheat sheet

**Backend** (`backend/.env` or platform env):

| Var                  | Required | Notes                                                                            |
|----------------------|----------|----------------------------------------------------------------------------------|
| `LLM_API_KEY`        | yes      | `sk-or-v1-...` (OpenRouter) or `sk-...` (direct OpenAI)                          |
| `LLM_BASE_URL`       | no       | Empty = default OpenAI endpoint; `https://openrouter.ai/api/v1` for OpenRouter   |
| `LLM_MODEL`          | yes      | `openai/gpt-4o-mini` via OpenRouter, or `gpt-4o-mini` direct                     |
| `ANTHROPIC_API_KEY`  | legacy   | Fallback slot — read only if `LLM_API_KEY` is unset                              |
| `ANTHROPIC_BASE_URL` | legacy   | Fallback slot — read only if `LLM_BASE_URL` is unset                             |
| `ANTHROPIC_MODEL`    | legacy   | Fallback slot — read only if `LLM_MODEL` is unset                                |
| `DATABASE_URL`       | yes      | `sqlite:///./nxtcorp.db` local; Postgres URL in prod                             |
| `JWT_SECRET`         | yes      | Generate with `python -c "import secrets; print(secrets.token_urlsafe(48))"`     |
| `CORS_ORIGINS`       | no       | Comma-separated; defaults to localhost dev origins                               |
| `SEED_QUESTION_ID`   | no       | Defaults to `p001_detect_capital`                                                |

> ⚠️ **`.env` is read once at process start.** If you change any `LLM_*`
> value, restart `uvicorn` — `--reload` rebuilds Python modules on file
> changes but does **not** re-read `.env`. If you see "AI is temporarily
> unavailable" repeatedly, restart the backend so it picks up fresh env
> values:
>
> ```powershell
> Get-Process python | Where-Object { $_.MainWindowTitle -like '*uvicorn*' } | Stop-Process -Force
> uvicorn backend.main:app --reload --port 8000
> ```
>
> The LLM shim (`backend/core/llm.py`) already retries 502/503/504/429
> and connection errors up to 3 times with a 2 s delay — restart is
> only needed when the upstream is healthy but you changed env values.

**Frontend** (`frontend/.env` or Vercel env):

| Var              | Required | Notes                                                          |
|------------------|----------|----------------------------------------------------------------|
| `VITE_API_BASE`  | prod yes | Backend URL. Empty in dev (vite proxies `/api` to localhost).  |

## Critical rules locked in design (spec §14)

1. Students never see generated code, hidden tests, reference prompt, or reference code.
2. The Coach Agent always writes in Priya's voice and never gives the answer — only Socratic questions (L1–L4 ladder; L4 reveals only after 3 failed attempts).
3. Code is executed via Python `exec()` inside a subprocess sandbox with timeout.
4. Frontend never calls the LLM directly — always through the backend.
5. Code Generator is genuinely literal (vague prompts produce wrong code by design).
6. All LLM responses parsed defensively (strip markdown fences, handle malformed JSON, fall back gracefully).

## Authoring new questions

Edit `scripts/seeds/<question_id>.json` with the minimal seed:

```json
{
  "question_id": "p003_palindrome",
  "title": "Palindrome check",
  "exercise_type": 3,
  "difficulty": "easy",
  "skill_focus": ["edge_case"],
  "function_signature": "def is_palindrome(s: str) -> bool",
  "problem_sketch": "Return True if s reads the same forwards and backwards."
}
```

Then run:

```bash
python -m scripts.author \
  --input scripts/seeds/p003_palindrome.json \
  --output questions/p003_palindrome.json
```

The author validates the output shape and runs `reference_code` against every sample + hidden test before writing. If it fails, no file is written.

## Initial git commit

```bash
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin git@github.com:<you>/nxtcorp.git
git push -u origin main
```
