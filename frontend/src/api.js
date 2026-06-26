// Tiny fetch wrapper around the FastAPI backend.
// JWT lives in localStorage so a page refresh keeps the session.

// In dev, Vite proxies /api -> http://localhost:8000 (see vite.config.js).
// In prod (Vercel), set VITE_API_BASE to the backend URL, e.g.
// "https://nxtcorp-api.onrender.com". Empty string keeps paths same-origin.
const API_BASE = (import.meta.env.VITE_API_BASE || '').replace(/\/$/, '');

const TOKEN_KEY = 'nxtcorp.token';

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

async function request(path, { method = 'GET', body, auth = true } = {}) {
  const headers = { 'Content-Type': 'application/json' };
  if (auth) {
    const token = getToken();
    if (token) headers.Authorization = `Bearer ${token}`;
  }
  const url = `${API_BASE}${path}`;

  let res;
  try {
    res = await fetch(url, {
      method,
      headers,
      body: body == null ? undefined : JSON.stringify(body),
    });
  } catch (netErr) {
    // BUG 1 fix: never swallow the network error. Log the full context to
    // the browser console so the cause (backend down, CORS, proxy off,
    // mixed-content, DNS) is visible. Re-throw with a clearer message.
    // eslint-disable-next-line no-console
    console.error('[api] fetch failed', {
      url,
      method,
      message: netErr?.message,
      name: netErr?.name,
      error: netErr,
    });
    const err = new Error(
      `Network call to ${method} ${url} failed: ${netErr?.message || netErr}. ` +
        `Is the backend running at ${API_BASE || 'http://localhost:8000'}?`,
    );
    err.cause = netErr;
    err.isNetwork = true;
    throw err;
  }

  if (res.status === 204) return null;

  let payload = null;
  try {
    payload = await res.json();
  } catch (_) {
    // body wasn't JSON — that's fine for 4xx
  }

  if (!res.ok) {
    const detail = payload && payload.detail ? payload.detail : res.statusText;
    const err = new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
    err.status = res.status;
    err.payload = payload;
    // eslint-disable-next-line no-console
    console.error('[api] HTTP error', { url, method, status: res.status, detail, payload });
    throw err;
  }
  return payload;
}

// ---------- Auth ----------

export async function register({ username, password, display_name, avatar_id, pronouns }) {
  const data = await request('/api/auth/register', {
    method: 'POST',
    auth: false,
    body: { username, password, display_name, avatar_id, pronouns },
  });
  setToken(data.access_token);
  return data;
}

export async function login({ username, password }) {
  const data = await request('/api/auth/login', {
    method: 'POST',
    auth: false,
    body: { username, password },
  });
  setToken(data.access_token);
  return data;
}

export function logout() {
  clearToken();
}

// ---------- Player ----------

export function getProfile() {
  return request('/api/player/profile');
}

// ---------- Onboarding ----------

export function completeOnboarding({ display_name, avatar_id, pronouns, job_role }) {
  return request('/api/onboarding/complete', {
    method: 'POST',
    body: { display_name, avatar_id, pronouns, job_role },
  });
}

// ---------- Story ----------

export function getStoryCurrent() {
  return request('/api/story/current');
}

export function advanceStory({ event_key, skipped = false }) {
  return request('/api/story/advance', {
    method: 'POST',
    body: { event_key, skipped },
  });
}

// ---------- Task ----------

export function getCurrentTask() {
  return request('/api/task/current');
}

export function runAttempt(payload) {
  // payload = { attempt_number, plus exactly ONE of:
  //   student_prompt   (Type 3, 5)
  //   subtasks         (Type 1, list of strings)
  //   identified_gaps  (Type 2, list of strings)
  //   test_cases       (Type 4, list of {input, expected}) }
  return request('/api/task/run', { method: 'POST', body: payload });
}

export function respondToCoach({ student_response }) {
  return request('/api/task/respond', {
    method: 'POST',
    body: { student_response },
  });
}

export function getCoffeeHint() {
  return request('/api/task/hint', { method: 'POST' });
}

// v5: mark the Meeting Room as completed for the current question. Backend
// persists the flag so the meeting never replays on the same ticket.
export function markMeetingComplete() {
  return request('/api/task/meeting/complete', { method: 'POST' });
}

// v3: multi-turn Arjun coffee-corner conversation.
// round: 0 → opener (no choice needed), 1 → reply to R1 pick, 2 → hint.
export function postCoffeeTurn({ round, choice = null }) {
  return request('/api/coffee/turn', {
    method: 'POST',
    body: { round, choice },
  });
}
