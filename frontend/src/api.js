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
      // Use the HTTP status when the server does not return a JSON error.
    }
    throw new Error(message);
  }

  if (response.status === 204) return null;
  return response.json();
}

export const getHealth = () => request("/health");
export const getProviders = () => request("/providers");
export const saveProviderSettings = (settings) =>
  request("/providers", { method: "PUT", body: JSON.stringify(settings) });
export const getDiscoverySettings = () => request("/discovery/settings");
export const saveDiscoverySettings = (settings) =>
  request("/discovery/settings", { method: "PUT", body: JSON.stringify(settings) });
export const getDiscoveryQueue = ({ status = "pending", limit = 50, offset = 0 } = {}) =>
  request(`/discovery/queue?status=${encodeURIComponent(status)}&limit=${limit}&offset=${offset}`);
export const reviewDiscoveryCandidate = (id, status) =>
  request(`/discovery/queue/${encodeURIComponent(id)}`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
export const getArtists = ({ limit = 50, offset = 0 } = {}) =>
  request(`/artists?limit=${limit}&offset=${offset}`);
export const createArtist = (artist) =>
  request("/artists", { method: "POST", body: JSON.stringify(artist) });
export const deleteArtist = (id) =>
  request(`/artists/${encodeURIComponent(id)}`, { method: "DELETE" });
export const searchArtists = ({
  query = "",
  area = "",
  genre = "",
  areas,
  genres,
  limit = 10,
  offset = 0,
}) => {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (query.trim()) params.set("query", query.trim());

  const areaFilters = Array.isArray(areas) ? areas : (area.trim() ? [area.trim()] : []);
  const genreFilters = Array.isArray(genres) ? genres : (genre.trim() ? [genre.trim()] : []);
  for (const value of areaFilters) {
    if (typeof value === "string" && value.trim()) params.append("area", value.trim());
  }
  for (const value of genreFilters) {
    if (typeof value === "string" && value.trim()) params.append("genre", value.trim());
  }
  return request(`/discovery/search?${params}`);
};
