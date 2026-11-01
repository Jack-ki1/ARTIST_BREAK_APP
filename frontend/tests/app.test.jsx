import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../src/App.jsx";
import { createArtist } from "../src/api.js";

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
  window.sessionStorage.clear();
  window.localStorage.clear();
  window.history.replaceState({}, "", "/");
});

const health = {
  status: "ok",
  database: "connected",
  authentication: "disabled-demo-mode",
  configured_data_providers: ["musicbrainz"],
};
const page = { items: [], total: 0, limit: 50, offset: 0 };
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
  await clickButton("Enter demo workspace");
  await waitForText("Welcome back.");
  await clickButton("Continue to demo workspace");
  await waitForText("Your directory is empty");
}

function mockBackend(fetchMock = vi.fn(async (url) => {
  if (String(url).endsWith("/health")) return response(health);
  if (String(url).endsWith("/providers")) return response(providers);
  if (String(url).includes("/artists?")) return response(page);
  return response({ detail: "Not found" }, 404);
})) {
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("public and artist workspace", () => {
  it("takes visitors through the public homepage and demo sign-in", async () => {
    mockBackend();
    await renderApp();
    expect(document.querySelector("h1").textContent).toContain("Find the");

    await clickButton("Enter demo workspace");
    expect(document.querySelector("h1").textContent).toBe("Welcome back.");
    await clickButton("Continue to demo workspace");
    await waitForText("Your directory is empty");

    expect(window.location.pathname).toBe("/app");
    expect(window.sessionStorage.getItem("breakout-radar-demo-session")).toBe("active");
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
      if (String(url).includes("/discovery/search")) {
        return response({ items: [candidate], count: 1, offset: 0 });
      }
      if (String(url) === "/api/artists" && options?.method === "POST") {
        return response({ id: "saved-artist", name: candidate.name }, 201);
      }
      return response({ detail: "Not found" }, 404);
    }));
    await enterWorkspace();

    const search = document.querySelector('[aria-label="Live MusicBrainz artist discovery"] input');
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
      source_name: "MusicBrainz",
      source_url: candidate.source_url,
    });
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
    await clickButton("Enter demo workspace");
    await clickButton("Continue to demo workspace");
    await waitForText("Failed to fetch");

    expect(document.body.textContent).toContain("Failed to fetch");
    expect(document.body.textContent).not.toContain("No artist records yet");
  });
});
