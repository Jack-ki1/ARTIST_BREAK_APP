async function request(path, options = {}) {
  const response = await fetch(`/api${path}`, {
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...options.headers,
    },
  });
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") message = body.detail;
    } catch {
      // Keep the HTTP status when the server does not return JSON.
    }
    throw new Error(message);
  }
  if (response.status === 204) return null;
  return response.json();
}

const json = (method, value) => ({ method, body: JSON.stringify(value) });

export const getHealth = () => request("/health");
export const getDashboard = () => request("/dashboard");
export const getSources = () => request("/sources");
export const saveSources = (payload) => request("/sources", json("PUT", payload));
export const getSettings = () => request("/settings");
export const saveSettings = (config) => request("/settings", json("PUT", { config }));
export const getCandidates = (params = {}) => {
  const query = new URLSearchParams();
  if (params.q) query.set("q", params.q);
  if (params.limit) query.set("limit", String(params.limit));
  return request(`/discovery/candidates?${query.toString()}`);
};
export const runDiscovery = (filters) => request("/discovery/run", json("POST", filters));
export const reviewCandidate = (id, action, note = "") =>
  request(`/discovery/candidates/${encodeURIComponent(id)}/review`, json("POST", { action, note }));
export const getArtists = (params = {}) => {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && String(value).trim()) query.set(key, String(value));
  }
  return request(`/artists?${query.toString()}`);
};
export const createArtist = (artist) => request("/artists", json("POST", artist));
export const getArtist = (id) => request(`/artists/${encodeURIComponent(id)}`);
export const collectEvidence = (id) => request(`/artists/${encodeURIComponent(id)}/collect-evidence`, { method: "POST" });
export const saveReview = (id, review) => request(`/artists/${encodeURIComponent(id)}/reviews`, json("POST", review));
export const saveDecision = (id, decision) => request(`/artists/${encodeURIComponent(id)}/decisions`, json("POST", decision));
export const getRecommendations = () => request("/recommendations");
export const getRuns = () => request("/runs");
export const getAlerts = () => request("/alerts");
export const markAlertRead = (id) => request(`/alerts/${encodeURIComponent(id)}/read`, { method: "PATCH" });

export const getAutomationStatus = () => request("/automation/status");
