import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  createArtist,
  deleteArtist,
  getDiscoveryQueue,
  getDiscoverySettings,
  getArtists,
  getHealth,
  getProviders,
  reviewDiscoveryCandidate,
  saveProviderSettings,
  saveDiscoverySettings,
  searchArtists,
} from "./api.js";

const PAGE_SIZE = 50;
const PREFERENCE_KEY = "breakout-radar-discovery-preferences";
const DEFAULT_PREFERENCES = { area: "", genre: "", limit: 10, enabled: true };

function preferencesFromSettings(settings) {
  return {
    area: settings.areas.join(", "),
    genre: settings.genres.join(", "),
    limit: settings.result_limit,
    enabled: settings.enabled,
  };
}

function filterValues(value) {
  return [...new Set(value.split(",").map((item) => item.trim()).filter(Boolean))];
}

const NAV_ITEMS = [
  { id: "discovery", label: "Discovery", icon: "compass" },
  { id: "analyze", label: "Analyze", icon: "chart" },
  { id: "recommend", label: "Recommend", icon: "spark" },
  { id: "settings", label: "Settings", icon: "settings" },
];

const PAGE_CONTENT = {
  discovery: {
    kicker: "ARTIST INTELLIGENCE",
    title: "Discovery",
    description: "Build a trusted artist directory. No generated profiles or estimates.",
  },
  analyze: {
    kicker: "EVIDENCE REVIEW",
    title: "Analyze",
    description: "Review source-backed artist evidence when authorized data becomes available.",
  },
  recommend: {
    kicker: "HUMAN DECISIONS",
    title: "Recommend",
    description: "Recommendations stay unavailable until real, permissioned evidence is connected.",
  },
  settings: {
    kicker: "WORKSPACE CONTROL",
    title: "Settings",
    description: "Review service status, connected sources, and the workspace's data boundaries.",
  },
};

function Icon({ name, size = 18 }) {
  const common = {
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.7,
    strokeLinecap: "round",
    strokeLinejoin: "round",
    "aria-hidden": true,
  };
  const shapes = {
    compass: <><circle cx="12" cy="12" r="9" /><path d="m15.8 8.2-2.5 5.1-5.1 2.5 2.5-5.1 5.1-2.5Z" /></>,
    chart: <><path d="M4 19V5" /><path d="M4 19h16" /><path d="m7 15 4-4 3 2 5-6" /><path d="M16 7h3v3" /></>,
    spark: <><path d="m12 3 1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3Z" /><path d="m19 15 .8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8L19 15Z" /></>,
    settings: <><circle cx="12" cy="12" r="3" /><path d="m19.4 15 .1.1 1.3 1-1.4 2.4-1.5-.6a8 8 0 0 1-1.7 1l-.2 1.6h-2.8L13 19a8 8 0 0 1-2-.5l-1.4.9-2-2 1-1.3a8 8 0 0 1-.7-1.8l-1.6-.4V11l1.5-.4a8 8 0 0 1 .8-1.8l-.9-1.4 2-2 1.3.9a8 8 0 0 1 1.9-.6l.4-1.6h2.8l.4 1.6a8 8 0 0 1 1.8.8l1.4-.9 2 2-.9 1.4a8 8 0 0 1 .6 1.9l1.6.4v2.8l-1.6.4a8 8 0 0 1-.6 1.5Z" transform="translate(-1 -1) scale(.92)" /></>,
    search: <><circle cx="10.8" cy="10.8" r="6.8" /><path d="m16 16 4.5 4.5" /></>,
    plus: <><path d="M12 5v14" /><path d="M5 12h14" /></>,
    arrow: <><path d="M5 12h14" /><path d="m13 6 6 6-6 6" /></>,
    music: <><path d="M9 18V5l12-2v13" /><circle cx="6" cy="18" r="3" /><circle cx="18" cy="16" r="3" /></>,
    people: <><circle cx="9" cy="8" r="3" /><path d="M3 20v-1a6 6 0 0 1 12 0v1" /><path d="M17 5a3 3 0 0 1 0 6" /><path d="M21 20v-1a6 6 0 0 0-3.5-5.5" /></>,
    shield: <><path d="M12 3 20 6v5c0 5-3.4 8.3-8 10-4.6-1.7-8-5-8-10V6l8-3Z" /><path d="m9 12 2 2 4-4" /></>,
    database: <><ellipse cx="12" cy="5" rx="8" ry="3" /><path d="M4 5v7c0 1.7 3.6 3 8 3s8-1.3 8-3V5" /><path d="M4 12v7c0 1.7 3.6 3 8 3" /><path d="M20 12v3" /></>,
  };
  return <svg {...common}>{shapes[name] || shapes.spark}</svg>;
}

function ArtistForm({ onCreated, onCancel }) {
  const [values, setValues] = useState({
    name: "",
    country: "",
    city: "",
    genre: "",
    source_name: "",
    source_url: "",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const update = (event) => {
    setValues((current) => ({ ...current, [event.target.name]: event.target.value }));
  };

  const submit = async (event) => {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      const artist = await createArtist(
        Object.fromEntries(
          Object.entries(values).map(([key, value]) => [key, value.trim() || null]),
        ),
      );
      setValues({ name: "", country: "", city: "", genre: "", source_name: "", source_url: "" });
      onCreated(artist);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <form className="artist-form panel" onSubmit={submit}>
      <div className="form-heading">
        <div>
          <p className="eyebrow">ARTIST IDENTITY</p>
          <h2>Add to your directory</h2>
        </div>
        <span className="form-tag">Identity only · no audience metrics</span>
      </div>
      <label>
        Artist or act name <span aria-hidden="true">*</span>
        <input autoComplete="off" maxLength={120} name="name" onChange={update} placeholder="Enter an artist name" required value={values.name} />
      </label>
      <div className="form-grid">
        <label>Country or territory<input maxLength={120} name="country" onChange={update} value={values.country} /></label>
        <label>City<input maxLength={120} name="city" onChange={update} value={values.city} /></label>
        <label>Genre<input maxLength={120} name="genre" onChange={update} value={values.genre} /></label>
        <label>Source or permission reference<input maxLength={120} name="source_name" onChange={update} value={values.source_name} /></label>
      </div>
      <label>
        Source URL
        <input maxLength={2048} name="source_url" onChange={update} placeholder="https://…" type="url" value={values.source_url} />
      </label>
      {error && <p className="form-error" role="alert">{error}</p>}
      <div className="form-actions">
        <p>Only enter information you are authorized to store.</p>
        <div className="form-action-buttons">
          <button className="button button-secondary" disabled={saving} onClick={onCancel} type="button">Cancel</button>
          <button className="button button-primary" disabled={saving} type="submit">{saving ? "Saving…" : "Save artist"}</button>
        </div>
      </div>
    </form>
  );
}

function SectionHeading({ kicker, title, description, action }) {
  return (
    <div className="section-heading">
      <div>
        <p className="eyebrow">{kicker}</p>
        <h2>{title}</h2>
        {description && <p className="section-description">{description}</p>}
      </div>
      {action}
    </div>
  );
}

function EmptyModule({ icon, title, description, className = "" }) {
  return (
    <article className={`empty-module panel ${className}`}>
      <span className="module-icon"><Icon name={icon} size={17} /></span>
      <div>
        <h3>{title}</h3>
        <p>{description}</p>
      </div>
    </article>
  );
}

function InsightPanel({ icon, title, description, variant = "standard" }) {
  return (
    <article className={`insight-panel panel insight-${variant}`}>
      <SectionHeading kicker="INSIGHT" title={title} />
      {variant === "chart" && (
        <div aria-hidden="true" className="empty-chart">
          <span /><span /><span /><span />
        </div>
      )}
      {variant === "map" && (
        <div aria-hidden="true" className="empty-map">
          <Icon name="compass" size={44} />
        </div>
      )}
      {variant === "pipeline" && (
        <div aria-hidden="true" className="empty-pipeline">
          <span>No pipeline records</span>
        </div>
      )}
      <div className="insight-empty">
        <span className="module-icon"><Icon name={icon} size={16} /></span>
        <p>{description}</p>
      </div>
    </article>
  );
}

function EmptyState({ icon, title, description, action }) {
  return (
    <div className="empty-state">
      <span className="empty-icon"><Icon name={icon} size={22} /></span>
      <h3>{title}</h3>
      <p>{description}</p>
      {action}
    </div>
  );
}

function formatDate(value) {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(new Date(value));
}

export default function App() {
  const [section, setSection] = useState("discovery");
  const [health, setHealth] = useState(null);
  const [providers, setProviders] = useState([]);
  const [selectedProviderIds, setSelectedProviderIds] = useState(["musicbrainz"]);
  const [providerCredentialDraft, setProviderCredentialDraft] = useState({});
  const [credentialsToClear, setCredentialsToClear] = useState([]);
  const [providerSettingsMessage, setProviderSettingsMessage] = useState("");
  const [page, setPage] = useState({ items: [], total: 0, offset: 0 });
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);
  const [query, setQuery] = useState("");
  const [showForm, setShowForm] = useState(false);
  const searchInputRef = useRef(null);
  const [discoveryQuery, setDiscoveryQuery] = useState("");
  const [discoveryResults, setDiscoveryResults] = useState([]);
  const [discoveryCount, setDiscoveryCount] = useState(null);
  const [discoveryLoading, setDiscoveryLoading] = useState(false);
  const [discoveryError, setDiscoveryError] = useState("");
  const [discoveryQueue, setDiscoveryQueue] = useState({ items: [], total: 0, limit: 50, offset: 0 });
  const [savedCandidates, setSavedCandidates] = useState({});
  const [preferences, setPreferences] = useState(DEFAULT_PREFERENCES);
  const [preferenceDraft, setPreferenceDraft] = useState(DEFAULT_PREFERENCES);
  const [preferencesMessage, setPreferencesMessage] = useState("");

  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(PREFERENCE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        const next = {
          area: typeof parsed.area === "string" ? parsed.area : "",
          genre: typeof parsed.genre === "string" ? parsed.genre : "",
          limit: [5, 10, 25].includes(parsed.limit) ? parsed.limit : 10,
          enabled: parsed.enabled !== false,
        };
        setPreferences(next);
        setPreferenceDraft(next);
      }
    } catch {
      setPreferencesMessage("Could not read saved preferences. Save your settings again to replace them.");
    }
  }, []);

  const reload = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [service, artists, connectedProviders, candidateQueue, storedSettings] = await Promise.all([
        getHealth(),
        getArtists({ limit: PAGE_SIZE, offset: 0 }),
        getProviders(),
        getDiscoveryQueue(),
        getDiscoverySettings(),
      ]);
      let discoverySettings = storedSettings;
      if (!storedSettings.updated_at) {
        let legacyPreferences;
        try {
          const saved = window.localStorage.getItem(PREFERENCE_KEY);
          legacyPreferences = saved ? JSON.parse(saved) : null;
        } catch {
          setPreferencesMessage("Could not read the previous browser preferences; configure discovery settings again.");
        }
        if (legacyPreferences) {
          discoverySettings = await saveDiscoverySettings({
            areas: filterValues(typeof legacyPreferences.area === "string" ? legacyPreferences.area : ""),
            genres: filterValues(typeof legacyPreferences.genre === "string" ? legacyPreferences.genre : ""),
            result_limit: [5, 10, 25].includes(legacyPreferences.limit) ? legacyPreferences.limit : 10,
            enabled: legacyPreferences.enabled !== false,
          });
        }
      }
      setHealth(service);
      setPage(artists);
      setProviders(connectedProviders);
      setSelectedProviderIds(
        connectedProviders.filter((provider) => provider.enabled).map((provider) => provider.id),
      );
      setDiscoveryQueue(candidateQueue);
      const nextPreferences = preferencesFromSettings(discoverySettings);
      setPreferences(nextPreferences);
      setPreferenceDraft(nextPreferences);
      window.localStorage.setItem(PREFERENCE_KEY, JSON.stringify(nextPreferences));
    } catch (requestError) {
      setHealth(null);
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    reload();
  }, [reload, refreshKey]);

  const runDiscovery = useCallback(async (event) => {
    event?.preventDefault();
    const areas = filterValues(preferences.area);
    const genres = filterValues(preferences.genre);
    const queryText = discoveryQuery.trim();
    if (!queryText && !areas.length && !genres.length) {
      setDiscoveryError("Enter an artist, or set a region or genre in Settings before searching.");
      return;
    }
    setDiscoveryLoading(true);
    setDiscoveryError("");
    setDiscoveryResults([]);
    setDiscoveryCount(null);
    try {
      const result = await searchArtists({
        query: queryText,
        areas,
        genres,
        limit: preferences.limit,
        offset: 0,
      });
      setDiscoveryResults(result.items || []);
      setDiscoveryCount(result.count ?? (result.items || []).length);
      setDiscoveryError((result.errors || []).join(" · "));
    } catch (requestError) {
      setDiscoveryError(requestError.message);
    } finally {
      setDiscoveryLoading(false);
    }
  }, [discoveryQuery, preferences]);

  useEffect(() => {
    const timer = window.setInterval(async () => {
      try {
        setDiscoveryQueue(await getDiscoveryQueue());
      } catch (requestError) {
        setDiscoveryError(requestError.message);
      }
    }, 30_000);
    return () => window.clearInterval(timer);
  }, []);

  const savePreferences = async (event) => {
    event.preventDefault();
    const next = {
      ...preferenceDraft,
      area: preferenceDraft.area.trim(),
      genre: preferenceDraft.genre.trim(),
      limit: Number(preferenceDraft.limit),
    };
    setPreferencesMessage("Saving discovery settings…");
    try {
      const settings = await saveDiscoverySettings({
        areas: filterValues(next.area),
        genres: filterValues(next.genre),
        result_limit: next.limit,
        enabled: next.enabled,
      });
      const saved = preferencesFromSettings(settings);
      setPreferences(saved);
      setPreferenceDraft(saved);
      try {
        window.localStorage.setItem(PREFERENCE_KEY, JSON.stringify(saved));
      } catch {
        setPreferencesMessage("Settings saved on the backend, but this browser could not cache a local copy.");
        return;
      }
      setPreferencesMessage("Settings saved. Scheduled searches run every 15 minutes when at least one region or genre is configured.");
    } catch (requestError) {
      setPreferencesMessage(`Could not save discovery settings: ${requestError.message}`);
    }
  };

  const reviewCandidate = async (candidate, status) => {
    try {
      await reviewDiscoveryCandidate(candidate.id, status);
      setDiscoveryQueue(await getDiscoveryQueue());
      if (status === "accepted") setRefreshKey((key) => key + 1);
    } catch (requestError) {
      setDiscoveryError(requestError.message);
    }
  };

  const saveProviders = async (event) => {
    event.preventDefault();
    const credentialUpdates = Object.fromEntries(
      Object.entries(providerCredentialDraft)
        .map(([providerId, fields]) => [
          providerId,
          Object.fromEntries(Object.entries(fields).filter(([, value]) => value.trim())),
        ])
        .filter(([, fields]) => Object.keys(fields).length > 0),
    );
    setProviderSettingsMessage("Saving provider selections…");
    try {
      const updatedProviders = await saveProviderSettings({
        enabled_provider_ids: selectedProviderIds,
        credential_updates: credentialUpdates,
        clear_credentials: credentialsToClear,
      });
      setProviders(updatedProviders);
      setSelectedProviderIds(
        updatedProviders.filter((provider) => provider.enabled).map((provider) => provider.id),
      );
      setProviderCredentialDraft({});
      setCredentialsToClear([]);
      setProviderSettingsMessage("Provider selections saved. Credentials are stored encrypted by the backend.");
    } catch (requestError) {
      setProviderSettingsMessage(`Could not save provider settings: ${requestError.message}`);
    }
  };

  const addCandidate = async (candidate) => {
    setDiscoveryError("");
    try {
      await createArtist({
        name: candidate.name,
        country: candidate.country,
        city: candidate.area,
        genre: candidate.tags.slice(0, 3).join(", ") || null,
        source_name: candidate.provider_id,
        source_url: candidate.source_url,
      });
      setSavedCandidates((current) => ({ ...current, [candidate.id]: true }));
      setRefreshKey((key) => key + 1);
    } catch (requestError) {
      setDiscoveryError(requestError.message);
    }
  };

  useEffect(() => {
    const handleSearchShortcut = (event) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLocaleLowerCase() === "k") {
        event.preventDefault();
        searchInputRef.current?.focus();
      }
      if (event.key === "Escape" && document.activeElement === searchInputRef.current) {
        setQuery("");
        searchInputRef.current.blur();
      }
    };
    window.addEventListener("keydown", handleSearchShortcut);
    return () => window.removeEventListener("keydown", handleSearchShortcut);
  }, []);

  const loadMore = async () => {
    setLoadingMore(true);
    setError("");
    try {
      const nextPage = await getArtists({ limit: PAGE_SIZE, offset: page.items.length });
      setPage((current) => ({ ...nextPage, items: [...current.items, ...nextPage.items] }));
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoadingMore(false);
    }
  };

  const removeArtist = async (artist) => {
    if (!window.confirm(`Delete ${artist.name}? This removes its stored identity record.`)) return;
    setError("");
    try {
      await deleteArtist(artist.id);
      setRefreshKey((key) => key + 1);
    } catch (requestError) {
      setError(requestError.message);
    }
  };

  const filteredArtists = useMemo(() => {
    const term = query.trim().toLocaleLowerCase();
    if (!term) return page.items;
    return page.items.filter((artist) =>
      [artist.name, artist.country, artist.city, artist.genre, artist.source_name]
        .some((value) => value?.toLocaleLowerCase().includes(term)),
    );
  }, [page.items, query]);

  const onCreated = () => {
    setShowForm(false);
    setRefreshKey((key) => key + 1);
  };
  const content = PAGE_CONTENT[section];
  const providerCount = health?.configured_data_providers?.length;
  const backendConnected = health?.status === "ok";

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a aria-label="Breakout Radar home" className="brand" href="/">
          <span aria-hidden="true" className="brand-mark"><Icon name="music" size={21} /></span>
          <span className="brand-copy">BREAKOUT <b>RADAR</b><small>A&amp;R INTELLIGENCE</small></span>
        </a>
        <div className="sidebar-divider" />
        <p className="nav-caption">WORKSPACE</p>
        <nav aria-label="Main navigation" className="nav-list">
          {NAV_ITEMS.map((item) => (
            <button
              aria-current={section === item.id ? "page" : undefined}
              className={`nav-link${section === item.id ? " nav-link-active" : ""}`}
              key={item.id}
              onClick={() => {
                setSection(item.id);
                setShowForm(false);
              }}
              type="button"
            >
              <Icon name={item.icon} size={17} />
              <span>{item.label}</span>
              {item.id === "discovery" && <span className="nav-count">{page.total}</span>}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <span className="operator-avatar">A</span>
          <span className="operator-copy"><b>Workspace operator</b><small>Local workspace</small></span>
          <span aria-label={backendConnected ? "API connected" : "API disconnected"} className={`connection-dot${backendConnected ? " is-online" : ""}`} />
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <label className="global-search">
            <Icon name="search" size={17} />
            <input aria-label="Search artist records" onChange={(event) => setQuery(event.target.value)} placeholder="Search artist, city, genre…" ref={searchInputRef} value={query} />
            <span className="search-shortcut">⌘ K</span>
          </label>
          <div className="topbar-meta">
            <span className={`api-status${backendConnected ? " connected" : ""}`}>
              <i />{backendConnected ? "API connected" : "API unavailable"}
            </span>
            <span aria-hidden="true" className="operator-avatar operator-avatar-small">A</span>
          </div>
        </header>

        <div className="workspace">
          <div className={`page-intro${section === "discovery" ? " page-intro-hidden" : ""}`}>
            <div>
              <p className="eyebrow">{content.kicker}</p>
              <h1>{content.title}</h1>
              <p>{content.description}</p>
            </div>
            <div className="intro-meta">
              <span><i className={`connection-dot${backendConnected ? " is-online" : ""}`} />{backendConnected ? "Python API online" : "Waiting for API"}</span>
              <span>{providerCount === undefined ? "PROVIDER STATUS UNKNOWN" : providerCount === 0 ? "NO PROVIDERS CONNECTED" : `${providerCount} PROVIDER${providerCount === 1 ? "" : "S"} CONNECTED`}</span>
            </div>
          </div>

          {section === "discovery" && (
            <>
              <section className="hero-panel panel">
                <div className="hero-copy">
                  <p className="hero-brand"><span className="hero-brand-mark"><Icon name="music" size={14} /></span> BREAKOUT RADAR</p>
                  <h2>Find tomorrow’s stars<br /><em>with real evidence.</em></h2>
                  <p>Discover and develop artists without invented scores. Your directory is built only from identities you add and information you are authorized to use.</p>
                  <button className="button button-primary hero-button" onClick={() => setShowForm(true)} type="button">
                    <Icon name="plus" size={16} /> Add artist
                  </button>
                </div>
                <div aria-hidden="true" className="hero-art">
                  <div className="hero-light hero-light-one" />
                  <div className="hero-light hero-light-two" />
                  <div className="hero-record">
                    <Icon name="music" size={48} />
                  </div>
                  <div className="hero-soundmark"><i /><i /><i /><i /><i /><i /><i /><i /><i /></div>
                  <div className="hero-art-copy">REAL TALENT.<br /><b>REAL OPPORTUNITY.</b></div>
                </div>
              </section>

              <section aria-label="Workspace overview" className="metric-grid">
                <article className="metric-card panel"><span className="metric-icon icon-green"><Icon name="people" /></span><span className="metric-label">Artist records</span><strong>{loading || error ? "—" : page.total}</strong><small>Operator-entered identities</small></article>
                <article className="metric-card panel"><span className="metric-icon icon-blue"><Icon name="database" /></span><span className="metric-label">Live providers</span><strong>{providerCount ?? "—"}</strong><small>{providerCount === undefined ? "Provider status unavailable" : providerCount ? "Configured integrations" : "None configured"}</small></article>
                <article className="metric-card panel"><span className="metric-icon icon-violet"><Icon name="chart" /></span><span className="metric-label">Measurements</span><strong>None</strong><small>No audience history available</small></article>
                <article className="metric-card metric-status panel"><span className="metric-label">Data status</span><strong><i className={`connection-dot${backendConnected ? " is-online" : ""}`} />{backendConnected ? "Database connected" : "API unavailable"}</strong><small>Authentication is not configured</small></article>
                <article className="metric-card panel"><span className="metric-icon icon-coral"><Icon name="chart" /></span><span className="metric-label">Artist rankings</span><strong>Off</strong><small>No validated scoring model</small></article>
                <article className="metric-card panel"><span className="metric-icon icon-lime"><Icon name="spark" /></span><span className="metric-label">Recommendations</span><strong>Off</strong><small>Evidence required first</small></article>
              </section>

              <section className="live-discovery panel" aria-label="Live artist discovery">
                <SectionHeading
                  action={<button className="text-action" onClick={() => setSection("settings")} type="button">Search preferences <Icon name="arrow" size={13} /></button>}
                  description="Search every enabled and configured artist source. Results are source metadata, not breakout rankings."
                  kicker="LIVE CATALOG SEARCH"
                  title="Discover artists"
                />
                <form className="live-search-form" onSubmit={runDiscovery}>
                  <label>
                    Artist or keyword
                    <input
                      autoComplete="off"
                      maxLength={120}
                      onChange={(event) => setDiscoveryQuery(event.target.value)}
                      placeholder="Try an artist name, sound, or scene…"
                      value={discoveryQuery}
                    />
                  </label>
                  <button className="button button-primary" disabled={discoveryLoading} type="submit">
                    <Icon name="search" size={15} />{discoveryLoading ? "Searching…" : "Search catalog"}
                  </button>
                </form>
                <div className="discovery-filter-summary">
                  <span><Icon name="compass" size={14} /> Region: {preferences.area || "Any region"}</span>
                  <span><Icon name="music" size={14} /> Genre: {preferences.genre || "Any genre"}</span>
                  <span>Up to {preferences.limit} results</span>
                </div>
                <p className="source-disclaimer">Catalog matches are identity metadata. They do not indicate popularity, growth, or emerging status.</p>
                {discoveryError && <p className="discovery-error" role="alert">{discoveryError}</p>}
                {discoveryLoading && <p className="loading-state" role="status">Searching enabled providers…</p>}
                {!discoveryLoading && discoveryCount !== null && discoveryResults.length === 0 && !discoveryError && (
                  <EmptyState description="Try a different artist, region, or genre." icon="search" title="No catalog matches" />
                )}
                {!discoveryLoading && discoveryResults.length > 0 && (
                  <>
                    <p className="discovery-result-count">Found {discoveryCount} unique matches across enabled providers.</p>
                    <div className="candidate-list">
                      {discoveryResults.map((candidate) => {
                        const isSaved = savedCandidates[candidate.id] ||
                          page.items.some((artist) => artist.source_url === candidate.source_url);
                        return (
                          <article className="candidate-row" key={candidate.id}>
                            <span className="candidate-avatar"><Icon name="music" size={17} /></span>
                            <div className="candidate-info">
                              <b>{candidate.name}</b>
                              <span>{[candidate.area, candidate.country, candidate.type].filter(Boolean).join(" · ") || "Location not listed"}</span>
                              {candidate.tags.length > 0 && <div className="candidate-tags">{candidate.tags.map((tag) => <span key={tag}>{tag}</span>)}</div>}
                            </div>
                            <div className="candidate-actions">
                              <a href={candidate.source_url} rel="noreferrer" target="_blank">{candidate.provider_id}</a>
                              <a href={`https://open.spotify.com/search/${encodeURIComponent(candidate.name)}`} rel="noreferrer" target="_blank">Spotify search</a>
                              <a href={`https://www.youtube.com/results?search_query=${encodeURIComponent(candidate.name)}`} rel="noreferrer" target="_blank">YouTube search</a>
                              <button
                                className={`button ${isSaved ? "button-saved" : "button-secondary"}`}
                                disabled={Boolean(isSaved)}
                                onClick={() => addCandidate(candidate)}
                                type="button"
                              >{isSaved ? "In directory" : "Add to directory"}</button>
                            </div>
                          </article>
                        );
                      })}
                    </div>
                  </>
                )}
              </section>

              <section className="review-queue panel" aria-label="Autonomous discovery review queue">
                <SectionHeading
                  description={preferences.enabled
                    ? "The backend checks every 15 minutes, including when this browser is closed. New catalog matches wait here for your review."
                    : "Automatic discovery is paused. Enable it in Settings to resume scheduled searches."}
                  kicker="AUTONOMOUS DISCOVERY"
                  title={`Candidate review queue · ${discoveryQueue.total}`}
                />
                {discoveryQueue.items.length === 0 ? (
                  <EmptyState
                    description={preferences.enabled
                      ? "No candidates are waiting. Enable a ready provider and set at least one region or genre in Settings; the backend will search and queue catalog matches."
                      : "Enable scheduled discovery and configure at least one region or genre to start collecting candidates."}
                    icon="database"
                    title="Queue is clear"
                  />
                ) : (
                  <div className="candidate-list">
                    {discoveryQueue.items.map((candidate) => (
                      <article className="candidate-row" key={candidate.id}>
                        <span className="candidate-avatar"><Icon name="music" size={17} /></span>
                        <div className="candidate-info">
                          <b>{candidate.name}</b>
                          <span>{[candidate.area, candidate.country, candidate.artist_type].filter(Boolean).join(" · ") || "Location not listed"}</span>
                          {candidate.tags.length > 0 && <div className="candidate-tags">{candidate.tags.map((tag) => <span key={tag}>{tag}</span>)}</div>}
                          <a href={candidate.source_url} rel="noreferrer" target="_blank">{candidate.provider_id} source</a>
                        </div>
                        <div className="candidate-actions">
                          <button className="button button-primary" onClick={() => reviewCandidate(candidate, "accepted")} type="button">Add to directory</button>
                          <button className="button button-secondary" onClick={() => reviewCandidate(candidate, "dismissed")} type="button">Dismiss</button>
                        </div>
                      </article>
                    ))}
                  </div>
                )}
              </section>

              {error && (
                <div className="error-panel" role="alert">
                  <div><strong>Could not load artist records.</strong><p>{error}</p></div>
                  <button className="button button-secondary" onClick={reload} type="button">Retry</button>
                </div>
              )}
              {showForm && <ArtistForm onCancel={() => setShowForm(false)} onCreated={onCreated} />}

              <section className="main-grid">
                <article className="directory-panel panel">
                  <SectionHeading
                    action={<button className="text-action" disabled={loading} onClick={reload} type="button">{loading ? "Loading…" : "Refresh"} <Icon name="arrow" size={14} /></button>}
                    description="Only artist identities saved to this workspace appear here."
                    kicker="DISCOVERY"
                    title="Artist directory"
                  />
                  {loading && <p className="loading-state" role="status">Connecting to the Python API…</p>}
                  {!loading && !error && (
                    <div className="table-wrap">
                      <table>
                        <thead><tr><th scope="col">Artist</th><th scope="col">Location</th><th scope="col">Genre</th><th scope="col">Source</th><th scope="col">Added</th><th scope="col"><span className="visually-hidden">Actions</span></th></tr></thead>
                        <tbody>{filteredArtists.map((artist) => (
                          <tr key={artist.id}>
                            <td><span className="artist-initial"><Icon name="music" size={15} /></span><b className="artist-name">{artist.name}</b></td>
                            <td>{[artist.city, artist.country].filter(Boolean).join(", ") || "—"}</td>
                            <td>{artist.genre || "—"}</td>
                            <td>{artist.source_url ? <a href={artist.source_url} rel="noreferrer" target="_blank">{artist.source_name || "Source"}</a> : artist.source_name || "—"}</td>
                            <td>{formatDate(artist.created_at)}</td>
                            <td><button aria-label={`Delete ${artist.name}`} className="delete-button" onClick={() => removeArtist(artist)} type="button">Delete</button></td>
                          </tr>
                        ))}
                        {filteredArtists.length === 0 && (
                          <tr><td className="empty-table-cell" colSpan="6">
                            <EmptyState
                              action={page.items.length < page.total
                                ? <button className="button button-secondary" disabled={loadingMore} onClick={loadMore} type="button">{loadingMore ? "Loading…" : "Load more records"}</button>
                                : !showForm && <button className="button button-secondary" onClick={() => setShowForm(true)} type="button"><Icon name="plus" size={14} /> Add first artist</button>}
                              description={page.items.length === 0
                                ? "No artists have been added yet. Create a real identity record to get started."
                                : `No matches in the ${page.items.length} loaded records${page.items.length < page.total ? ` of ${page.total}` : ""}.`}
                              icon={page.items.length === 0 ? "people" : "search"}
                              title={page.items.length === 0 ? "Your directory is empty" : "No matches"}
                            />
                          </td></tr>
                        )}
                        </tbody>
                      </table>
                      {filteredArtists.length > 0 && <p className="table-caption">Showing {filteredArtists.length} of {page.items.length} loaded identities. No performance metrics are available.</p>}
                      {page.items.length < page.total && <button className="button button-secondary load-more" disabled={loadingMore} onClick={loadMore} type="button">{loadingMore ? "Loading…" : `Load more records (${page.total - page.items.length} remaining)`}</button>}
                    </div>
                  )}
                </article>

                <aside className="side-stack">
                  <article className="movers-panel panel">
                    <SectionHeading action={<button className="text-action" onClick={() => setSection("analyze")} type="button">View all <Icon name="arrow" size={13} /></button>} kicker="MARKET MOVERS" title="Regional activity" />
                    <EmptyState description="Market movement requires verified, permissioned audience data. Nothing is ranked until those observations exist." icon="compass" title="No regional data yet" />
                  </article>
                  <article className="integration-panel panel">
                    <SectionHeading kicker="DATA CONNECTIONS" title="Live sources" />
                    <div className="integration-empty">
                      <span className="source-icon"><Icon name="database" size={19} /></span>
                      <div>
                        <b>{providerCount === undefined ? "Provider status unavailable" : providerCount ? `${providerCount} sources connected` : "No sources connected"}</b>
                        <p>{providerCount === undefined ? "Reconnect to the Python API to check source status." : "Authorized providers supply the evidence behind every insight."}</p>
                      </div>
                    </div>
                    <div className="integration-foot"><span>{providerCount === undefined ? "Status unknown" : `${providerCount} active providers`}</span><button className="text-action" onClick={() => setSection("settings")} type="button">Manage <Icon name="arrow" size={13} /></button></div>
                  </article>
                </aside>
              </section>

              <section aria-label="Signals detected" className="signals-section">
                <SectionHeading action={<span className="section-status">SOURCE-VERIFIED ONLY</span>} kicker="LIVE SIGNALS" title="Signals detected" />
                <div className="signal-grid">
                  <EmptyModule description="No verified activity across connected sources." icon="compass" title="Regional trends" />
                  <EmptyModule description="No authorized creator-content observations." icon="music" title="UGC signals" />
                  <EmptyModule description="No audience growth pattern is available to review." icon="chart" title="Growth alerts" />
                  <EmptyModule description="New movement appears when real source data is connected." icon="spark" title="Emerging trends" />
                </div>
              </section>

              <section aria-label="Artist intelligence dashboard" className="insight-grid">
                <InsightPanel description="Artist rankings need verified performance data and a validated scoring method." icon="people" title="Artist potential" />
                <InsightPanel description="Connect a permissioned source to view real audience change over time." icon="chart" title="Audience intelligence" variant="chart" />
                <InsightPanel description="UGC activity and platform breakdowns are unavailable without a connected source." icon="music" title="UGC intelligence" />
                <InsightPanel description="No growth history is available to evaluate organic or suspicious activity." icon="shield" title="Growth integrity" variant="chart" />
                <InsightPanel description="Artist profiles show only identities and source details entered in this workspace." icon="people" title="Artist intelligence" />
                <InsightPanel description="Regional expansion requires verified location and audience observations." icon="compass" title="Geographic expansion" variant="map" />
                <InsightPanel description="The directory stores identities only; there are no A&R pipeline decisions yet." icon="arrow" title="A&R pipeline" variant="pipeline" />
                <InsightPanel description="No artist evidence is available for an assistant to summarize." icon="spark" title="A&R copilot" />
              </section>
            </>
          )}

          {section === "analyze" && (
            <>
              <section className="analysis-banner panel">
                <span className="large-module-icon"><Icon name="chart" size={26} /></span>
                <div><p className="eyebrow">MEASURED DATA ONLY</p><h2>Analysis starts with evidence.</h2><p>No audience histories, audio measurements, or source observations are available in this workspace.</p></div>
              </section>
              <section className="module-grid analysis-modules">
                <EmptyModule description="No authorized platform history connected." icon="chart" title="Audience growth" />
                <EmptyModule description="Engagement measurements are not available." icon="people" title="Audience composition" />
                <EmptyModule description="Audio traits are not measured by this application." icon="music" title="Audio analysis" />
                <EmptyModule description="A human review requires a real artist record and listening session." icon="shield" title="Artist review" />
              </section>
            </>
          )}

          {section === "recommend" && (
            <section className="recommend-empty panel">
              <EmptyState
                description="This workspace has no measured data or validated decision model. Recommendations are disabled rather than guessed."
                icon="spark"
                title="No recommendations available"
              />
              <div className="recommend-requirements">
                <span><Icon name="shield" size={16} /> Authorized source data</span>
                <span><Icon name="chart" size={16} /> Verified outcome evidence</span>
                <span><Icon name="people" size={16} /> Human A&amp;R review</span>
              </div>
            </section>
          )}

          {section === "settings" && (
            <>
              <section className="settings-grid">
                <article className="settings-panel panel">
                  <SectionHeading kicker="PERSONALIZE DISCOVERY" title="Search preferences" description="These server-side settings control the background discovery schedule." />
                  <form className="preferences-form" onSubmit={savePreferences}>
                    <label>
                      Countries or regions
                      <textarea maxLength={1400} onChange={(event) => setPreferenceDraft((current) => ({ ...current, area: event.target.value }))} placeholder="For example, Kenya, Ghana" rows={2} value={preferenceDraft.area} />
                    </label>
                    <label>
                      Genres or scenes
                      <textarea maxLength={1400} onChange={(event) => setPreferenceDraft((current) => ({ ...current, genre: event.target.value }))} placeholder="For example, alternative R&B, Afrobeats" rows={2} value={preferenceDraft.genre} />
                    </label>
                    <label>
                      Results per search
                      <select onChange={(event) => setPreferenceDraft((current) => ({ ...current, limit: Number(event.target.value) }))} value={preferenceDraft.limit}>
                        <option value="5">5 results</option>
                        <option value="10">10 results</option>
                        <option value="25">25 results</option>
                      </select>
                    </label>
                    <label className="preference-toggle">
                      <span><b>Enable recurring discovery</b><small>The backend searches every configured region/genre combination every 15 minutes and stores new identities in the review queue.</small></span>
                      <input checked={preferenceDraft.enabled} onChange={(event) => setPreferenceDraft((current) => ({ ...current, enabled: event.target.checked }))} type="checkbox" />
                    </label>
                    <div className="preferences-actions">
                      <button className="button button-primary" type="submit">Save settings</button>
                      {preferencesMessage && <span aria-live="polite" role="status">{preferencesMessage}</span>}
                    </div>
                  </form>
                  {preferences.enabled && !preferences.area.trim() && !preferences.genre.trim() && (
                    <p className="settings-note" role="status">
                      Scheduled discovery is enabled but has no search filters. Add at least one region or genre to start collecting candidates.
                    </p>
                  )}
                </article>
                <article className="settings-panel panel">
                  <SectionHeading kicker="SERVICE" title="Backend connection" />
                  <div className="settings-row"><span><Icon name="database" /> API health</span><b className={backendConnected ? "value-positive" : "value-warning"}>{backendConnected ? "Connected" : "Unavailable"}</b></div>
                  <div className="settings-row"><span><Icon name="database" /> Database</span><b>{health?.database || "Unknown"}</b></div>
                  <div className="settings-row"><span><Icon name="shield" /> Authentication</span><b>Not configured</b></div>
                  <div className="settings-row"><span><Icon name="people" /> Artist identities</span><b>{loading || error ? "Unknown" : page.total}</b></div>
                </article>
              </section>
              <section className="provider-settings panel">
                <SectionHeading
                  description="Choose which sources power manual and scheduled search. Provider keys are sent only to this backend and never returned to the browser."
                  kicker="SOURCE CONFIGURATION"
                  title={`Data providers · ${providers.length}`}
                />
                <form onSubmit={saveProviders}>
                  <div className="provider-grid">
                    {providers.map((provider) => {
                      const configuredFields = provider.configured_fields || [];
                      return (
                        <article className="provider-card" key={provider.id}>
                          <label className="provider-enable">
                            <input
                              checked={selectedProviderIds.includes(provider.id)}
                              onChange={(event) => setSelectedProviderIds((current) =>
                                event.target.checked
                                  ? [...new Set([...current, provider.id])]
                                  : current.filter((id) => id !== provider.id))}
                              type="checkbox"
                            />
                            <span className={`provider-icon provider-${provider.id}`}><Icon name={provider.id === "musicbrainz" ? "music" : "database"} size={18} /></span>
                            <span className="provider-copy">
                              <span className="provider-name-row">
                                <b>{provider.name}</b>
                                <span className={`provider-state${provider.status === "available" ? " is-configured" : ""}`}>
                                  {provider.status === "available" ? "Ready" : provider.status === "needs_credentials" ? "Needs credentials" : "Disabled"}
                                </span>
                              </span>
                              <span className="provider-description">{provider.description}</span>
                              <span className="provider-access-note">{provider.access_note}</span>
                              <a href={provider.url} rel="noreferrer" target="_blank">Provider docs <Icon name="arrow" size={12} /></a>
                            </span>
                          </label>
                          {(provider.fields || []).length > 0 && (
                            <div className="provider-credentials">
                              {provider.fields.map((field) => {
                                const credentialId = `${provider.id}.${field.key}`;
                                const isConfigured = configuredFields.includes(field.key) &&
                                  !credentialsToClear.includes(credentialId);
                                return (
                                  <label key={field.key}>
                                    {field.label}
                                    <input
                                      autoComplete="new-password"
                                      onChange={(event) => setProviderCredentialDraft((current) => ({
                                        ...current,
                                        [provider.id]: {
                                          ...current[provider.id],
                                          [field.key]: event.target.value,
                                        },
                                      }))}
                                      disabled={credentialsToClear.includes(credentialId)}
                                      placeholder={isConfigured ? "Saved · enter to replace" : "Not configured"}
                                      type={field.secret ? "password" : "text"}
                                      value={providerCredentialDraft[provider.id]?.[field.key] || ""}
                                    />
                                    {isConfigured && (
                                      <span className="credential-clear">
                                        <input
                                          checked={credentialsToClear.includes(credentialId)}
                                          onChange={(event) => setCredentialsToClear((current) =>
                                            event.target.checked
                                              ? [...current, credentialId]
                                              : current.filter((value) => value !== credentialId))}
                                          type="checkbox"
                                        />
                                        Remove saved value
                                      </span>
                                    )}
                                  </label>
                                );
                              })}
                            </div>
                          )}
                        </article>
                      );
                    })}
                  </div>
                  <div className="preferences-actions provider-save">
                    <button className="button button-primary" type="submit">Save provider settings</button>
                    {providerSettingsMessage && <span aria-live="polite" role="status">{providerSettingsMessage}</span>}
                  </div>
                </form>
                <p className="settings-note">Credentials are encrypted in the backend database with PROVIDER_SECRETS_KEY. Authentication is not configured, so keep the API bound to localhost and do not expose it to untrusted networks. Paid plans, app approval, and provider terms may still be required.</p>
              </section>
            </>
          )}

          <footer className="footer">
            <span className="footer-brand"><Icon name="music" size={17} /> BREAKOUT RADAR</span>
            <span>Better data. Better decisions.</span>
            <span>Unauthenticated · keep access local</span>
          </footer>
        </div>
      </main>
    </div>
  );
}
