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
export const getArtists = ({ limit = 50, offset = 0 } = {}) =>
  request(`/artists?limit=${limit}&offset=${offset}`);
export const createArtist = (artist) =>
  request("/artists", { method: "POST", body: JSON.stringify(artist) });
export const deleteArtist = (id) =>
  request(`/artists/${encodeURIComponent(id)}`, { method: "DELETE" });
export const searchArtists = ({ query, area, genre, limit = 10, offset = 0 }) => {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (query.trim()) params.set("query", query.trim());
  if (area.trim()) params.set("area", area.trim());
  if (genre.trim()) params.set("genre", genre.trim());
  return request(`/discovery/search?${params}`);
};
