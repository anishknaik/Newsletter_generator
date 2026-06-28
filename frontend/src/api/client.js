// Thin wrapper around the FastAPI backend, with JWT auth.
// In production set VITE_API_URL to the deployed backend URL (no trailing slash).
const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
const TOKEN_KEY = "nlg_token";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}
function setToken(t) {
  localStorage.setItem(TOKEN_KEY, t);
}
export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

// Central fetch helper: injects the bearer token, parses errors, and signals
// expired sessions so the UI can bounce back to the login screen.
async function api(path, { method = "GET", body, auth = true } = {}) {
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (auth) {
    const t = getToken();
    if (t) headers["Authorization"] = `Bearer ${t}`;
  }

  const res = await fetch(`${BASE_URL}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (res.status === 401 || res.status === 403) {
    clearToken();
    const err = new Error("Your session expired — please log in again.");
    err.status = res.status;
    throw err;
  }
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `Request failed (${res.status})`);
  }
  return res.status === 204 ? null : res.json();
}

// --- Auth ---
export async function register(email, password) {
  const d = await api("/auth/register", {
    method: "POST",
    auth: false,
    body: { email, password },
  });
  setToken(d.access_token);
  return d.user;
}
export async function login(email, password) {
  const d = await api("/auth/login", {
    method: "POST",
    auth: false,
    body: { email, password },
  });
  setToken(d.access_token);
  return d.user;
}
export async function me() {
  return api("/auth/me");
}
export function logout() {
  clearToken();
}

// --- Topics ---
export async function fetchTopics() {
  return (await api("/topics")).topics;
}
export async function addTopic(name) {
  return (await api("/topics", { method: "POST", body: { name } })).topics;
}

// --- Newsletters ---
export async function generateNewsletter(topics, tone, fromDate, toDate, filters) {
  const body = { topics, tone, filters };
  if (fromDate) body.from_date = fromDate;
  if (toDate) body.to_date = toDate;
  return api("/generate", { method: "POST", body });
}
export async function fetchSaved() {
  return api("/newsletters");
}
export async function fetchSavedById(id) {
  return api(`/newsletters/${id}`);
}
export async function deleteSaved(id) {
  return api(`/newsletters/${id}`, { method: "DELETE" });
}

export async function emailNewsletter(id, to) {
  // Omit the body to use the account email; include { to } to override it.
  return api(`/newsletters/${id}/email`, {
    method: "POST",
    body: to ? { to } : undefined,
  });
}

// --- Subscription / scheduling ---
export async function getSubscription() {
  return api("/subscription");
}
export async function putSubscription(sub) {
  return api("/subscription", { method: "PUT", body: sub });
}
export async function sendSubscriptionNow() {
  return api("/subscription/send-now", { method: "POST" });
}

// --- Filter presets ---
export async function fetchPresets() {
  return api("/presets");
}
export async function createPreset(name, filters) {
  return api("/presets", { method: "POST", body: { name, filters } });
}
export async function deletePreset(id) {
  return api(`/presets/${id}`, { method: "DELETE" });
}
