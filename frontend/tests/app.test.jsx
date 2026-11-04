import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../src/App.jsx";
import { createArtist, searchArtists } from "../src/api.js";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
let root;
let host;

afterEach(async () => {
  if (root) await act(async () => root.unmount());
  host?.remove();
  root = null;
  host = null;
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  window.localStorage.clear();
  window.history.replaceState({}, "", "/");
});

const health = {
  status: "ok",
  database: "connected",
  authentication: "disabled",
  configured_data_providers: ["musicbrainz"],
};
const page = { items: [], total: 0, limit: 50, offset: 0 };
const discoverySettings = { areas: [], genres: [], result_limit: 10, enabled: true, interval_seconds: 900, updated_at: null };
const discoveryQueue = { items: [], total: 0, limit: 50, offset: 0 };
const providers = [
  { id: "musicbrainz", name: "MusicBrainz", configured: true, description: "Live artist catalog", url: "https://musicbrainz.org" },
  { id: "spotify", name: "Spotify", configured: false, description: "Not integrated", url: "https://spotify.com" },
  { id: "youtube", name: "YouTube", configured: false, description: "Not integrated", url: "https://youtube.com" },
];
const response = (body, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

async function renderApp() {
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  await act(async () => root.render(<App />));
}

async function waitForText(text) {
  for (let attempt = 0; attempt < 30; attempt += 1) {
    if (document.body.textContent.includes(text)) return;
    await act(async () => new Promise((resolve) => setTimeout(resolve, 10)));
  }
  throw new Error(`Timed out waiting for "${text}"`);
}

async function clickButton(text) {
  const button = [...document.querySelectorAll("button")]
    .find((candidate) => candidate.textContent.includes(text));
  if (!button) throw new Error(`Could not find button "${text}"`);
  await act(async () => button.click());
}

async function enterWorkspace() {
  await renderApp();
  await waitForText("Your directory is empty");
}

function mockBackend(fetchMock = vi.fn(async (url) => {
  if (String(url).endsWith("/health")) return response(health);
  if (String(url).endsWith("/providers")) return response(providers);
  if (String(url).includes("/artists?")) return response(page);
  if (String(url).includes("/discovery/settings")) return response(discoverySettings);
  if (String(url).includes("/discovery/queue")) return response(discoveryQueue);
  return response({ detail: "Not found" }, 404);
})) {
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("artist workspace", () => {
  it("opens the workspace directly without a sign-in screen", async () => {
    mockBackend();
    await renderApp();
    await waitForText("Your directory is empty");

    expect(document.body.textContent).not.toContain("Sign in");
    expect(window.location.pathname).toBe("/");
  });

  it("provides exactly four working sections without invented insights", async () => {
    mockBackend();
    await enterWorkspace();

    const navigation = document.querySelector('[aria-label="Main navigation"]');
    expect([...navigation.querySelectorAll("button")].map((button) => button.querySelector("span").textContent))
      .toEqual(["Discovery", "Analyze", "Recommend", "Settings"]);

    await act(async () => navigation.querySelectorAll("button")[1].click());
    expect(document.querySelector("h1").textContent).toBe("Analyze");
    expect(document.body.textContent).toContain("No audience histories, audio measurements, or source observations are available");

    await act(async () => navigation.querySelectorAll("button")[2].click());
    expect(document.querySelector("h1").textContent).toBe("Recommend");
    expect(document.body.textContent).toContain("No recommendations available");
    expect(document.body.textContent).not.toContain("82.4%");
  });

  it("searches live catalog data and saves only an explicitly selected artist", async () => {
    const candidate = {
      id: "musicbrainz-id",
      external_id: "musicbrainz-id",
      provider_id: "musicbrainz",
      name: "Catalog Artist",
      country: "KE",
      area: "Nairobi",
      type: "Person",
      disambiguation: null,
      tags: ["alternative"],
      source_url: "https://musicbrainz.org/artist/musicbrainz-id",
    };
    const fetchMock = mockBackend(vi.fn(async (url, options) => {
      if (String(url).endsWith("/health")) return response(health);
      if (String(url).endsWith("/providers")) return response(providers);
      if (String(url).includes("/artists?")) return response(page);
      if (String(url).includes("/discovery/settings")) return response(discoverySettings);
      if (String(url).includes("/discovery/queue")) return response(discoveryQueue);
      if (String(url).includes("/discovery/search")) {
        return response({ items: [candidate], count: 1, offset: 0 });
      }
      if (String(url) === "/api/artists" && options?.method === "POST") {
        return response({ id: "saved-artist", name: candidate.name }, 201);
      }
      return response({ detail: "Not found" }, 404);
    }));
    await enterWorkspace();

    const search = document.querySelector('[aria-label="Live artist discovery"] input');
    await act(async () => {
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set.call(search, "Catalog Artist");
      search.dispatchEvent(new Event("input", { bubbles: true }));
    });
    await clickButton("Search catalog");
    await waitForText("Catalog Artist");

    expect(fetchMock.mock.calls.some(([url]) =>
      String(url).includes("/discovery/search?") &&
      String(url).includes("query=Catalog+Artist"),
    )).toBe(true);
    await clickButton("Add to directory");
    await waitForText("In directory");

    const saveCall = fetchMock.mock.calls.find(([url, options]) =>
      String(url) === "/api/artists" && options?.method === "POST",
    );
    expect(JSON.parse(saveCall[1].body)).toMatchObject({
      name: "Catalog Artist",
      source_name: "musicbrainz",
      source_url: candidate.source_url,
    });
  });

  it("saves recurring discovery settings to the backend", async () => {
    const fetchMock = mockBackend(vi.fn(async (url, options) => {
      if (String(url).endsWith("/health")) return response(health);
      if (String(url).endsWith("/providers")) return response(providers);
      if (String(url).includes("/artists?")) return response(page);
      if (String(url).includes("/discovery/queue")) return response(discoveryQueue);
      if (String(url).includes("/discovery/settings") && options?.method === "PUT") {
        return response({
          areas: ["Kenya", "Ghana"],
          genres: ["Afrobeats", "Alternative R&B"],
          result_limit: 5,
          enabled: true,
          interval_seconds: 900,
          updated_at: "2026-11-02T00:00:00Z",
        });
      }
      if (String(url).includes("/discovery/settings")) return response(discoverySettings);
      return response({ detail: "Not found" }, 404);
    }));
    await enterWorkspace();
    const navigation = document.querySelector('[aria-label="Main navigation"]');
    await act(async () => navigation.querySelectorAll("button")[3].click());

    const fields = document.querySelectorAll(".preferences-form textarea");
    await act(async () => {
      Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value").set.call(fields[0], "Kenya, Ghana");
      fields[0].dispatchEvent(new Event("input", { bubbles: true }));
      Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value").set.call(fields[1], "Afrobeats, Alternative R&B");
      fields[1].dispatchEvent(new Event("input", { bubbles: true }));
    });
    await clickButton("Save settings");
    await waitForText("Scheduled searches run every 15 minutes");

    const saveCall = fetchMock.mock.calls.find(([url, options]) =>
      String(url).includes("/discovery/settings") && options?.method === "PUT",
    );
    expect(JSON.parse(saveCall[1].body)).toEqual({
      areas: ["Kenya", "Ghana"],
      genres: ["Afrobeats", "Alternative R&B"],
      result_limit: 10,
      enabled: true,
    });
  });

  it("lets a scout select providers and submit API credentials without reading saved secrets", async () => {
    const configuredProviders = [
      {
        id: "musicbrainz",
        name: "MusicBrainz",
        status: "available",
        configured: true,
        enabled: true,
        description: "Open artist catalog",
        access_note: "No API key.",
        url: "https://musicbrainz.org",
        fields: [],
        configured_fields: [],
      },
      {
        id: "spotify",
        name: "Spotify",
        status: "needs_credentials",
        configured: false,
        enabled: false,
        description: "Search Spotify",
        access_note: "Developer application required.",
        url: "https://developer.spotify.com",
        fields: [
          { key: "client_id", label: "Client ID", secret: false },
          { key: "client_secret", label: "Client secret", secret: true },
        ],
        configured_fields: [],
      },
    ];
    let updatedPayload;
    const fetchMock = mockBackend(vi.fn(async (url, options) => {
      if (String(url).endsWith("/health")) return response(health);
      if (String(url).endsWith("/providers") && options?.method === "PUT") {
        updatedPayload = JSON.parse(options.body);
        return response(configuredProviders.map((provider) => ({
          ...provider,
          enabled: updatedPayload.enabled_provider_ids.includes(provider.id),
          configured: provider.id === "spotify",
          status: provider.id === "spotify" ? "available" : "available",
          configured_fields: provider.id === "spotify" ? ["client_id", "client_secret"] : [],
        })));
      }
      if (String(url).endsWith("/providers")) return response(configuredProviders);
      if (String(url).includes("/artists?")) return response(page);
      if (String(url).includes("/discovery/settings")) return response(discoverySettings);
      if (String(url).includes("/discovery/queue")) return response(discoveryQueue);
      return response({ detail: "Not found" }, 404);
    }));
    await enterWorkspace();
    const navigation = document.querySelector('[aria-label="Main navigation"]');
    await act(async () => navigation.querySelectorAll("button")[3].click());

    const spotifyCard = [...document.querySelectorAll(".provider-card")]
      .find((card) => card.textContent.includes("Spotify"));
    const checkbox = spotifyCard.querySelector(".provider-enable input");
    const credentialInputs = spotifyCard.querySelectorAll(".provider-credentials input:not([type=checkbox])");
    await act(async () => {
      checkbox.click();
      for (const [input, value] of [[credentialInputs[0], "client-id"], [credentialInputs[1], "client-secret"]]) {
        Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set.call(input, value);
        input.dispatchEvent(new Event("input", { bubbles: true }));
      }
    });
    await clickButton("Save provider settings");
    await waitForText("Credentials are stored encrypted by the backend");

    expect(updatedPayload).toEqual({
      enabled_provider_ids: ["musicbrainz", "spotify"],
      credential_updates: {
        spotify: { client_id: "client-id", client_secret: "client-secret" },
      },
      clear_credentials: [],
    });
    expect(fetchMock.mock.calls.some(([, options]) =>
      options?.method === "GET" && options?.headers?.Authorization,
    )).toBe(false);
  });


  it("sends multiple regions and genres in one discovery request", async () => {
    const fetchMock = vi.fn(async () => response({ items: [], count: 0, offset: 0, errors: [] }));
    vi.stubGlobal("fetch", fetchMock);

    await searchArtists({
      query: "new act",
      areas: ["Kenya", "Ghana"],
      genres: ["Afrobeats", "Alternative R&B"],
      limit: 5,
      offset: 0,
    });

    const [url] = fetchMock.mock.calls[0];
    const params = new URL(url, "http://localhost").searchParams;
    expect(params.get("query")).toBe("new act");
    expect(params.getAll("area")).toEqual(["Kenya", "Ghana"]);
    expect(params.getAll("genre")).toEqual(["Afrobeats", "Alternative R&B"]);
    expect(params.get("limit")).toBe("5");
  });

  it("sends only submitted identity fields to the backend", async () => {
    const fetchMock = vi.fn(async () => response({ id: "created-record", name: "Artist Entered By User" }, 201));
    vi.stubGlobal("fetch", fetchMock);

    await createArtist({
      name: "Artist Entered By User",
      country: null,
      city: null,
      genre: null,
      source_name: null,
      source_url: null,
    });

    expect(fetchMock).toHaveBeenCalledWith("/api/artists", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: "Artist Entered By User",
        country: null,
        city: null,
        genre: null,
        source_name: null,
        source_url: null,
      }),
    });
  });

  it("shows backend failures instead of substituting fallback data", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => {
      throw new TypeError("Failed to fetch");
    }));
    await renderApp();
    await waitForText("Failed to fetch");

    expect(document.body.textContent).toContain("Failed to fetch");
    expect(document.body.textContent).not.toContain("No artist records yet");
  });
});
