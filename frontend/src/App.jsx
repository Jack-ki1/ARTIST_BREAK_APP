import { useEffect, useMemo, useState } from "react";
import {
  getHealth, getDashboard, getSources, saveSources, getSettings, saveSettings,
  getCandidates, runDiscovery, reviewCandidate, getArtists, getArtist,
  collectEvidence, saveReview, saveDecision, getRecommendations, getRuns, getAutomationStatus,
} from "./api.js";

const NAV = [
  { id: "discovery", label: "Discovery", short: "Find emerging artists", icon: "radar" },
  { id: "analyse", label: "Analyse", short: "Understand the evidence", icon: "wave" },
  { id: "recommendations", label: "Recommendations", short: "Make A&R decisions", icon: "trophy" },
  { id: "settings", label: "Settings", short: "Configure the intelligence", icon: "sliders" },
];

const DEFAULT_WEIGHTS = {
  discovery_weights: { momentum: 30, independent_breadth: 25, release_activity: 15, live_activity: 10, search_interest: 10, catalogue_headroom: 10 },
  artistic_weights: { songwriting: 2, vocals: 2, melody: 1.5, production: 1, originality: 1.5, performance: 1, identity: 1 },
};

const SCORE_LABELS = [
  ["songwriting", "Songwriting", "Hooks, structure, lyric craft and emotional clarity"],
  ["vocals", "Vocals", "Tone, range, control, delivery and character"],
  ["melody", "Melody", "Memorability, phrasing, harmony and melodic identity"],
  ["production", "Production", "Arrangement, sound design, mix and technical execution"],
  ["originality", "Originality", "Distinctiveness, risk-taking and artistic point of view"],
  ["performance", "Performance", "Stage potential, energy and audience connection"],
  ["identity", "Artist identity", "Coherent creative world, positioning and visual language"],
];

const money = (value) => new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 }).format(Number(value || 0));
const dateLabel = (value) => {
  if (!value) return "Not recorded";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
};
const timeAgo = (value) => {
  if (!value) return "No activity yet";
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 1000));
  if (seconds < 60) return "Just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
};
const clamp = (value, min = 0, max = 100) => Math.max(min, Math.min(max, Number(value) || 0));

function Icon({ name, size = 18 }) {
  const paths = {
    radar: <><circle cx="12" cy="12" r="9"/><path d="M12 3v9l6.4 6.4M12 12l6-4M3 12h9"/></>,
    wave: <><path d="M2 12h3l3-8 4 16 4-12 3 4h3"/></>,
    trophy: <><path d="M8 21h8M12 17v4M7 4h10v5a5 5 0 0 1-10 0V4Z"/><path d="M7 6H4v2a4 4 0 0 0 4 4M17 6h3v2a4 4 0 0 1-4 4"/></>,
    sliders: <><path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3"/><path d="M2 14h4M10 8h4M18 16h4"/></>,
    search: <><circle cx="10.8" cy="10.8" r="6.8"/><path d="m16 16 5 5"/></>,
    plus: <><path d="M12 5v14M5 12h14"/></>,
    arrow: <><path d="M5 12h14M13 6l6 6-6 6"/></>,
    refresh: <><path d="M20 7v5h-5M4 17v-5h5"/><path d="M6.1 9A7 7 0 0 1 18.4 7L20 12M4 12l1.6 5a7 7 0 0 0 12.3-2"/></>,
    check: <path d="m5 12 4 4L19 6"/>,
    x: <path d="m6 6 12 12M18 6 6 18"/>,
    globe: <><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a15 15 0 0 1 0 18M12 3a15 15 0 0 0 0 18"/></>,
    music: <><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></>,
    chart: <><path d="M4 19V5M4 19h17"/><path d="m7 15 4-4 3 2 5-7"/></>,
    users: <><circle cx="9" cy="8" r="3"/><path d="M2 20a7 7 0 0 1 14 0M17 5a3 3 0 0 1 0 6M18 14a6 6 0 0 1 4 6"/></>,
    pulse: <><path d="M2 12h4l3-8 5 16 3-8h5"/></>,
    external: <><path d="M14 3h7v7M10 14 21 3"/><path d="M19 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h6"/></>,
    chevron: <path d="m7 10 5 5 5-5"/>,
    filter: <><path d="M4 5h16l-6 7v6l-4 2v-8L4 5Z"/></>,
    shield: <><path d="M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11Z"/><path d="m9 12 2 2 4-4"/></>,
    bolt: <path d="m13 2-3 9h7l-5 11 1-9H6l7-11Z"/>,
    database: <><ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/></>,
    menu: <><path d="M4 6h16M4 12h16M4 18h16"/></>,
    sun: <><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4m11.4 11.4 1.4 1.4M2 12h2m16 0h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></>,
    moon: <path d="M20.8 14A8.5 8.5 0 0 1 10 3.2 8.8 8.8 0 1 0 20.8 14Z"/>,
    pin: <><path d="M20 10c0 5-8 11-8 11S4 15 4 10a8 8 0 1 1 16 0Z"/><circle cx="12" cy="10" r="2.4"/></>,
    note: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"/><path d="M14 2v6h6M8 13h8M8 17h8"/></>,
    lock: <><rect x="4" y="10" width="16" height="11" rx="2"/><path d="M8 10V7a4 4 0 1 1 8 0v3"/></>,
    star: <path d="m12 2 3 6.5 7 .8-5.2 4.8 1.4 7L12 17.5l-6.2 3.6 1.4-7L2 9.3l7-.8L12 2Z"/>,
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name] || paths.star}</svg>;
}

function Badge({ children, tone = "neutral" }) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}
function Panel({ title, sub, action, children, className = "" }) {
  return <section className={`panel ${className}`}>
    {(title || action) && <header className="panel-head"><div>{title && <h2>{title}</h2>}{sub && <p>{sub}</p>}</div>{action}</header>}
    {children}
  </section>;
}
function Kpi({ icon, value, label, delta, tone = "lime" }) {
  return <div className="kpi-card">
    <div className={`kpi-icon tone-${tone}`}><Icon name={icon}/></div>
    <div className="kpi-value">{value}</div>
    <div className="kpi-label">{label}</div>
    {delta && <div className="kpi-delta">{delta}</div>}
  </div>;
}
function Score({ value, label, tone = "lime" }) {
  const score = value == null ? null : clamp(value);
  return <div className={`score-ring score-${tone}`} style={{ "--score": score || 0 }}>
    <span>{score == null ? "—" : Math.round(score)}</span>
    {label && <small>{label}</small>}
  </div>;
}
function Empty({ title, body, action }) {
  return <div className="empty-state"><div className="empty-mark"><Icon name="radar" size={23}/></div><strong>{title}</strong><p>{body}</p>{action}</div>;
}
function Notice({ tone = "info", children }) {
  return <div className={`notice notice-${tone}`}>{children}</div>;
}
function SourceDots({ ids = [] }) {
  return <div className="source-dots">{ids.slice(0, 5).map((id) => <span title={id} key={id}>{id.slice(0, 2).toUpperCase()}</span>)}{ids.length > 5 && <em>+{ids.length - 5}</em>}</div>;
}
function Progress({ value }) {
  return <div className="progress-track"><span style={{ width: `${clamp(value)}%` }}/></div>;
}
function fmtMetric(value, metric = "") {
  if (value == null) return "—";
  return `${money(value)}${metric.includes("growth") ? "%" : ""}`;
}
function candidateSources(item, sources) {
  return (item.source_ids || []).map((id) => sources.find((source) => source.id === id)?.name || id);
}

function DiscoverySection({ dashboard, candidates, artists, sources, loading, running, filters, setFilters, onRun, onReview, selectedArtist, setSelectedArtist }) {
  const [artistQuery, setArtistQuery] = useState("");
  const ready = dashboard?.overview?.sources_ready || 0;
  const totals = dashboard?.overview || {};
  const filteredArtists = artists.filter((artist) => !artistQuery || artist.name.toLowerCase().includes(artistQuery.toLowerCase()));
  const run = dashboard?.recent_runs?.[0];
  return <div className="page-stack">
    <section className="hero-panel">
      <div className="hero-copy">
        <div className="eyebrow"><span className="live-pulse"/> A&R INTELLIGENCE / AFRICA-FIRST</div>
        <h1>Find the next <span>movement.</span></h1>
        <p>Surface independent artists early, corroborate identities across sources, and understand the evidence behind their momentum.</p>
        <div className="hero-meta"><span><Icon name="globe" size={14}/> Africa-wide discovery</span><span><Icon name="database" size={14}/> {ready} ready data sources</span><span><Icon name="shield" size={14}/> Evidence-first ranking</span></div>
      </div>
      <div className="hero-orbit">
        <div className="orbit orbit-one"/><div className="orbit orbit-two"/><div className="orbit-core"><Icon name="radar" size={42}/><small>RADAR<br/>ACTIVE</small></div>
        <span className="orbit-node node-a"/><span className="orbit-node node-b"/><span className="orbit-node node-c"/>
      </div>
    </section>

    <div className="kpi-grid">
      <Kpi icon="users" value={money(totals.artists_tracked)} label="Artists in the directory" tone="lime"/>
      <Kpi icon="radar" value={money(totals.pending_candidates)} label="Emerging candidates" tone="cyan"/>
      <Kpi icon="wave" value={money(totals.artistic_reviews)} label="Artistic reviews completed" tone="violet"/>
      <Kpi icon="database" value={`${ready}/${totals.sources_total || sources.length || 73}`} label="Sources ready to query" tone="amber"/>
    </div>

    <Panel title="Run a discovery scan" sub="Search configured catalogues in parallel. Source-specific limits and permissions are respected." className="scan-panel">
      <div className="scan-controls">
        <label className="field field-grow"><span>Artist, scene or discovery query</span><div className="input-icon"><Icon name="search" size={16}/><input value={filters.query} onChange={(event) => setFilters({ ...filters, query: event.target.value })} placeholder="e.g. Nairobi alternative R&B, new Bongo Flava…"/></div></label>
        <label className="field"><span>Country / market</span><select value={filters.country} onChange={(event) => setFilters({ ...filters, country: event.target.value })}><option value="">All markets</option>{["Kenya","Tanzania","Uganda","Rwanda","Nigeria","Ghana","South Africa","Zambia","Ethiopia","Senegal","Côte d’Ivoire","Cameroon"].map((country) => <option key={country}>{country}</option>)}</select></label>
        <label className="field"><span>Genre</span><input value={filters.genre} onChange={(event) => setFilters({ ...filters, genre: event.target.value })} placeholder="Afrobeats, Gengetone…"/></label>
        <button className="btn btn-primary scan-button" onClick={() => onRun()} disabled={running}><Icon name="bolt" size={17}/>{running ? "Scanning sources…" : "Run discovery"}</button>
      </div>
      <div className="scan-foot"><span><Icon name="shield" size={13}/> Search fan-out is capped; results are queued for human review.</span><span>{run ? `Last run ${timeAgo(run.started_at)}` : "No discovery run recorded yet"}</span></div>
      {running && <div className="scan-loading"><span/><span/><span/><span/><span/><small>Querying selected source adapters</small></div>}
    </Panel>

    <div className="content-grid discovery-grid">
      <Panel title="Emerging artist candidates" sub={`${candidates.length} grouped identities awaiting your review`} action={<Badge tone="cyan">REVIEW QUEUE</Badge>}>
        {loading ? <div className="skeleton-list"><span/><span/><span/></div> : candidates.length === 0 ? <Empty title="Your discovery queue is clear" body="Run a scan to find emerging artists. New identities are held here until your team accepts them."/> :
          <div className="candidate-list">{candidates.map((item) => <article className="candidate-row" key={item.group_key}>
            <div className="artist-avatar">{item.image_url ? <img src={item.image_url} alt=""/> : <span>{item.name.slice(0,2).toUpperCase()}</span>}</div>
            <div className="candidate-main"><div className="candidate-title">{item.name}<Badge tone={item.source_count > 1 ? "success" : "neutral"}>{item.source_count} source{item.source_count === 1 ? "" : "s"}</Badge><Badge tone={item.corroborated ? "success" : "warning"}>{item.corroborated ? "Corroborated" : "Provisional"}</Badge></div>
              <div className="candidate-sub">{[item.city, item.country, ...(item.genres || []).slice(0,2)].filter(Boolean).join(" · ") || "Location / genre not yet verified"}</div>
              <div className="candidate-signals"><SourceDots ids={item.source_ids}/><span>{item.signal_summary?.[0] || "Source-backed identity match"}</span></div>
            </div>
            <div className="candidate-score"><Score value={item.discovery_score} label="INDEX"/><small>{item.confidence}% confidence</small></div>
            <div className="candidate-actions"><button className="btn btn-soft" onClick={() => onReview(item, "accept")}>Accept</button><button className="icon-btn" aria-label={`Dismiss ${item.name}`} onClick={() => onReview(item, "dismiss")}><Icon name="x"/></button></div>
          </article>)}</div>}
      </Panel>

      <Panel title="Discovery activity" sub="Latest collection runs and provider responses">
        {(dashboard?.recent_runs || []).length === 0 ? <Empty title="No activity yet" body="Your first source scan will appear here."/> :
          <div className="activity-list">{dashboard.recent_runs.slice(0,6).map((run) => <div className="activity-row" key={run.id}>
            <div className={`activity-icon ${run.status === "completed" ? "activity-success" : "activity-warn"}`}><Icon name={run.status === "completed" ? "check" : "pulse"} size={15}/></div>
            <div className="activity-copy"><strong>{run.query || "Scheduled discovery"}</strong><span>{run.candidates_found} candidates · {run.sources_attempted?.length || 0} sources · {timeAgo(run.started_at)}</span></div>
            <Badge tone={run.status === "completed" ? "success" : "warning"}>{run.status}</Badge>
          </div>)}</div>}
        <div className="source-readiness"><div><span>Source readiness</span><strong>{ready} / {sources.length || 73}</strong></div><Progress value={sources.length ? ready / sources.length * 100 : 0}/><small>Public, credentialed and approved integrations are shown separately.</small></div>
      </Panel>
    </div>

    <Panel title="Artist directory" sub="Accepted artists, ordered by the latest evidence-backed index." action={<div className="table-tools"><div className="input-icon compact"><Icon name="search" size={14}/><input value={artistQuery} onChange={(event) => setArtistQuery(event.target.value)} placeholder="Filter artists…"/></div><span>{filteredArtists.length} / {artists.length}</span></div>}>
      {filteredArtists.length === 0 ? <Empty title="No accepted artists yet" body="Accept a candidate from the discovery queue to create the artist's permanent profile."/> :
        <div className="table-wrap"><table className="data-table"><thead><tr><th>ARTIST</th><th>MARKET</th><th>GENRES</th><th>DISCOVERY</th><th>ARTISTIC</th><th>STAGE</th><th/></tr></thead><tbody>
          {filteredArtists.map((artist) => <tr key={artist.id} onClick={() => setSelectedArtist(artist.id)} className={selectedArtist === artist.id ? "row-selected" : ""}>
            <td><div className="table-artist"><div className="mini-avatar">{artist.image_url ? <img src={artist.image_url} alt=""/> : artist.name.slice(0,2).toUpperCase()}</div><div><strong>{artist.name}</strong><small>{artist.primary_source || "Manual profile"}</small></div></div></td>
            <td>{artist.country || "Unverified"}</td><td>{(artist.genres || []).slice(0,2).join(", ") || "—"}</td>
            <td><span className="score-text">{artist.discovery_score == null ? "—" : Math.round(artist.discovery_score)}</span><small className="muted-inline">{Math.round(artist.discovery_confidence || 0)}% coverage</small></td>
            <td>{artist.artistic_score == null ? <Badge>Not reviewed</Badge> : Math.round(artist.artistic_score)}</td>
            <td><Badge tone={artist.recommendation_tier === "pursue" ? "success" : artist.recommendation_tier === "meet" ? "cyan" : "neutral"}>{artist.recommendation_tier || "hold"}</Badge></td>
            <td><button className="icon-btn" aria-label={`Open ${artist.name}`} onClick={(event) => { event.stopPropagation(); setSelectedArtist(artist.id); }}><Icon name="arrow" size={16}/></button></td>
          </tr>)}
        </tbody></table></div>}
    </Panel>
  </div>;
}

function ObservationTimeline({ observations = [] }) {
  const groups = new Map();
  for (const item of observations) {
    const key = `${item.source_id} · ${item.metric}`;
    const rows = groups.get(key) || [];
    rows.push(item);
    groups.set(key, rows);
  }
  const entry = [...groups.entries()]
    .map(([label, rows]) => [label, rows.sort((a,b) => new Date(a.observed_at) - new Date(b.observed_at))])
    .filter(([, rows]) => rows.length > 1)
    .sort((a,b) => b[1].length - a[1].length)[0];
  if (!entry) return null;
  const [label, rows] = entry;
  const values = rows.map((row) => Number(row.value));
  const min = Math.min(...values);
  const max = Math.max(...values);
  const spread = Math.max(1, max - min);
  const points = values.map((value,index) => {
    const x = 18 + (index / Math.max(1, values.length - 1)) * 464;
    const y = 92 - ((value - min) / spread) * 68;
    return `${x},${y}`;
  }).join(" ");
  return <div className="timeline-chart">
    <div><span>History · {label}</span><small>{rows.length} observations · values remain source-specific</small></div>
    <svg viewBox="0 0 500 112" role="img" aria-label={`Time series for ${label}`}>
      <path d="M18 24H482M18 58H482M18 92H482" stroke="var(--border)" strokeDasharray="3 5" fill="none"/>
      <polyline points={points} fill="none" stroke="var(--lime)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
      {points.split(" ").map((point,index) => { const [cx,cy] = point.split(","); return <circle key={index} cx={cx} cy={cy} r="3.2" fill="var(--panel)" stroke="var(--lime)" strokeWidth="2"/>; })}
    </svg>
    <div><span>{fmtMetric(values[0],label)}</span><span>{fmtMetric(values[values.length-1],label)}</span></div>
  </div>;
}

function AnalyseSection({ artists, selectedArtist, setSelectedArtist, artistDetail, reloadDetail, busy, notify }) {
  const [scores, setScores] = useState(Object.fromEntries(SCORE_LABELS.map(([key]) => [key, 5])));
  const [reviewer, setReviewer] = useState("A&R Team");
  const [trackTitle, setTrackTitle] = useState("");
  const [trackUrl, setTrackUrl] = useState("");
  const [notes, setNotes] = useState("");
  const [strengths, setStrengths] = useState("");
  const [risks, setRisks] = useState("");
  const [collecting, setCollecting] = useState(false);
  useEffect(() => {
    if (artistDetail?.reviews?.length) {
      const review = artistDetail.reviews[0];
      setScores({ ...Object.fromEntries(SCORE_LABELS.map(([key]) => [key, 5])), ...(review.scores || {}) });
      setTrackTitle(review.track_title || "");
      setTrackUrl(review.track_url || "");
      setNotes(review.notes || "");
      setStrengths((review.strengths || []).join("\n"));
      setRisks((review.risks || []).join("\n"));
    } else {
      setScores(Object.fromEntries(SCORE_LABELS.map(([key]) => [key, 5])));
      setTrackTitle(""); setTrackUrl(""); setNotes(""); setStrengths(""); setRisks("");
    }
  }, [artistDetail?.id]);
  const selected = artistDetail;
  const observations = selected?.observations || [];
  const latestMetrics = useMemo(() => {
    const map = new Map();
    observations.forEach((item) => {
      const key = `${item.source_id}:${item.metric}`;
      if (!map.has(key) || new Date(item.observed_at) > new Date(map.get(key).observed_at)) map.set(key, item);
    });
    return [...map.values()];
  }, [observations]);
  const save = async () => {
    if (!selectedArtist) return notify("Choose an artist before saving a review.", "warning");
    const payload = {
      reviewer, track_title: trackTitle || null, track_url: trackUrl || null,
      scores, verdict: "promising", notes,
      strengths: strengths.split("\n").map((x) => x.trim()).filter(Boolean),
      risks: risks.split("\n").map((x) => x.trim()).filter(Boolean),
      evidence: (selected?.evidence || []).slice(0, 12).map((item) => ({ source_id: item.source_id, title: item.title, url: item.url })),
    };
    const result = await saveReview(selectedArtist, payload);
    notify(`Artistic review saved · ${result.overall}/100`, "success");
    await reloadDetail();
  };
  const collect = async () => {
    if (!selectedArtist) return;
    setCollecting(true);
    try {
      const result = await collectEvidence(selectedArtist);
      notify(`${result.evidence_saved} new evidence items collected`, "success");
      await reloadDetail();
    } catch (error) { notify(error.message, "error"); }
    finally { setCollecting(false); }
  };
  return <div className="page-stack">
    <section className="section-heading"><div><div className="eyebrow">ARTIST INTELLIGENCE / EVIDENCE REVIEW</div><h1>Understand the <span>whole artist.</span></h1><p>Keep platform facts separate. Evaluate the music with structured human judgement, then make decisions with the complete picture.</p></div>
      <div className="select-wrap"><label>Artist profile</label><select value={selectedArtist || ""} onChange={(event) => setSelectedArtist(event.target.value)}><option value="">Select an artist…</option>{artists.map((artist) => <option key={artist.id} value={artist.id}>{artist.name}</option>)}</select></div>
    </section>
    {!selected ? <Empty title="Select an artist to analyse" body="Choose an artist from your directory to see their source identities, observations, press/community evidence and artistic review."/> :
      <>
        <div className="artist-profile-strip">
          <div className="artist-profile-avatar">{selected.image_url ? <img src={selected.image_url} alt=""/> : selected.name.slice(0,2).toUpperCase()}</div>
          <div className="artist-profile-copy"><div className="eyebrow">{selected.country || "COUNTRY UNVERIFIED"}{selected.city ? ` · ${selected.city}` : ""}</div><h2>{selected.name}</h2><p>{(selected.genres || []).join(" · ") || "Genre not yet classified"}</p><div className="profile-chips"><Badge tone="cyan">{selected.identities?.length || 0} source identities</Badge><Badge tone="success">{observations.length} observations</Badge><Badge>{selected.evidence?.length || 0} evidence items</Badge></div></div>
          <div className="profile-scores"><Score value={selected.discovery_score} label="DISCOVERY" tone="cyan"/><Score value={selected.artistic_score} label="ARTISTIC" tone="violet"/><Score value={selected.combined_score} label="COMBINED" tone="lime"/></div>
        </div>
        <div className="content-grid analyse-grid">
          <Panel title="Observed platform signals" sub="Latest values are source-attributed, not added into one synthetic audience count." action={<Badge tone="cyan">TIME-STAMPED</Badge>}>
            {latestMetrics.length === 0 ? <Empty title="No numeric observations yet" body="Discovery only stores metrics returned by an authorised source. Connect a source that provides permitted public or owner-authorised counts."/> :
              <div className="metric-grid">{latestMetrics.map((item) => <div className="metric-card" key={item.id}><span>{item.metric.replaceAll("_"," ")}</span><strong>{fmtMetric(item.value, item.metric)}</strong><small>{item.source_id} · {dateLabel(item.observed_at)}</small></div>)}</div>}
            <ObservationTimeline observations={observations}/>
            <div className="source-observation-list">{selected.identities?.map((identity) => <div key={identity.id} className="source-identity-row"><span className="source-favicon">{identity.source_id.slice(0,2).toUpperCase()}</span><div><strong>{identity.source_id}</strong><small>{identity.external_id} · {identity.verified ? "verified" : "unverified match"}</small></div><a href={identity.source_url} target="_blank" rel="noreferrer"><Icon name="external" size={14}/></a></div>)}</div>
          </Panel>
          <Panel title="Evidence library" sub="Links that help explain activity around the artist." action={<button className="btn btn-soft btn-small" onClick={collect} disabled={collecting}><Icon name="refresh" size={14}/>{collecting ? "Collecting…" : "Collect evidence"}</button>}>
            {selected.evidence?.length ? <div className="evidence-list">{selected.evidence.slice(0,12).map((item) => <a className="evidence-item" href={item.url} target="_blank" rel="noreferrer" key={item.id}><div className="evidence-type">{(item.evidence_type || "source").slice(0,3).toUpperCase()}</div><div><strong>{item.title}</strong><span>{item.source_id} · {dateLabel(item.published_at || item.collected_at)}</span>{item.summary && <p>{item.summary}</p>}</div><Icon name="external" size={14}/></a>)}</div> : <Empty title="No evidence collected" body="Enable GDELT, Reddit or licensed/public evidence sources in Settings, then collect source-linked items here."/>}
          </Panel>
        </div>
        <Panel title="Artistic review" sub="A structured A&R scorecard. Scores are entered by a reviewer; this form does not invent an AI listening result." action={<Badge tone="violet">{selected.reviews?.length ? `${selected.reviews.length} reviews` : "HUMAN-LED REVIEW"}</Badge>}>
          <Notice tone="info">AI audio scoring is intentionally not represented as live until an audio-capable model and permitted track input are configured. Your team can complete this professional rubric now.</Notice>
          <div className="review-layout">
            <div className="review-score-fields">{SCORE_LABELS.map(([key, label, hint]) => <div className="review-score-row" key={key}><div className="review-score-label"><strong>{label}</strong><small>{hint}</small></div><input type="range" min="0" max="10" step="0.5" value={scores[key] ?? 5} onChange={(event) => setScores({ ...scores, [key]: Number(event.target.value) })}/><b>{Number(scores[key] ?? 5).toFixed(1)}</b></div>)}</div>
            <div className="review-input-fields">
              <label className="field"><span>Reviewer</span><input value={reviewer} onChange={(event) => setReviewer(event.target.value)}/></label>
              <label className="field"><span>Track reviewed (optional)</span><input value={trackTitle} onChange={(event) => setTrackTitle(event.target.value)} placeholder="Track title"/></label>
              <label className="field"><span>Track URL (optional)</span><input value={trackUrl} onChange={(event) => setTrackUrl(event.target.value)} placeholder="https://…"/></label>
              <label className="field"><span>Review notes</span><textarea rows="4" value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="Describe what works, what needs development and what you would want to hear next…"/></label>
              <div className="review-two-col"><label className="field"><span>Strengths · one per line</span><textarea rows="3" value={strengths} onChange={(event) => setStrengths(event.target.value)} placeholder="Distinctive vocal tone&#10;Memorable hook"/></label><label className="field"><span>Risks · one per line</span><textarea rows="3" value={risks} onChange={(event) => setRisks(event.target.value)} placeholder="Needs live assessment&#10;Inconsistent release cadence"/></label></div>
              <div className="review-footer"><div><span>Weighted artistic score</span><strong>{Math.round(SCORE_LABELS.reduce((sum, [key]) => sum + (Number(scores[key]) * 10), 0) / SCORE_LABELS.length)}</strong><small>/100 · review weights are configurable in Settings</small></div><button className="btn btn-primary" onClick={save} disabled={busy}>Save artistic review <Icon name="arrow" size={15}/></button></div>
            </div>
          </div>
        </Panel>
      </>}
  </div>;
}

function RecommendationsSection({ recommendations, reload, notify }) {
  const [notes, setNotes] = useState({});
  const [saving, setSaving] = useState("");
  const grouped = useMemo(() => {
    const groups = { pursue: [], meet: [], watch: [], hold: [] };
    recommendations.forEach((item) => groups[item.recommendation?.tier || "hold"].push(item));
    return groups;
  }, [recommendations]);
  const decisions = [
    { id: "pursue", label: "Pursue", tone: "success" },
    { id: "meet", label: "Meet", tone: "cyan" },
    { id: "watch", label: "Watch", tone: "warning" },
    { id: "hold", label: "Hold", tone: "neutral" },
  ];
  const choose = async (artist, decision) => {
    setSaving(artist.id);
    try {
      await saveDecision(artist.id, { decision, owner: "A&R Team", note: notes[artist.id] || "" });
      notify(`${artist.name}: ${decision} decision recorded`, "success");
      await reload();
    } catch (error) { notify(error.message, "error"); }
    finally { setSaving(""); }
  };
  return <div className="page-stack">
    <section className="section-heading"><div><div className="eyebrow">A&R WORKBENCH / DECISION SUPPORT</div><h1>Turn signals into <span>decisions.</span></h1><p>Recommendations combine discovery momentum with artistic quality. An artist cannot reach “Pursue” without a completed artistic review.</p></div><button className="btn btn-soft" onClick={reload}><Icon name="refresh" size={15}/> Refresh recommendations</button></section>
    <div className="tier-overview">{[
      ["pursue","Pursue","Highest combined evidence","success"],["meet","Meet","Worth a conversation","cyan"],["watch","Watch","Needs more evidence","warning"],["hold","Hold","Awaiting review or signal","neutral"],
    ].map(([id,label,sub,tone]) => <div className={`tier-card tier-${tone}`} key={id}><span>{label.toUpperCase()}</span><strong>{grouped[id].length}</strong><small>{sub}</small></div>)}</div>
    <Notice tone="info">A 0–100 score is a transparent ranking index, not a probability of commercial success. Missing data lowers confidence and incomplete artistic reviews remain on Hold.</Notice>
    {recommendations.length === 0 ? <Empty title="No artist decisions to recommend yet" body="Accept artists from Discovery, then complete an artistic review in Analyse to activate the recommendation workflow."/> :
      <div className="recommendation-list">{recommendations.map((artist) => <article className="recommendation-card" key={artist.id}>
        <div className="recommendation-top"><div className="table-artist"><div className="mini-avatar">{artist.image_url ? <img src={artist.image_url} alt=""/> : artist.name.slice(0,2).toUpperCase()}</div><div><strong>{artist.name}</strong><small>{[artist.country, ...(artist.genres || []).slice(0,2)].filter(Boolean).join(" · ")}</small></div></div>
          <div className="recommendation-scores"><div><b>{artist.discovery_score == null ? "—" : Math.round(artist.discovery_score)}</b><small>DISCOVERY</small></div><div><b>{artist.artistic_score == null ? "—" : Math.round(artist.artistic_score)}</b><small>ARTISTIC</small></div><Score value={artist.recommendation?.score} label="TOTAL"/></div>
          <Badge tone={artist.recommendation?.tier === "pursue" ? "success" : artist.recommendation?.tier === "meet" ? "cyan" : artist.recommendation?.tier === "watch" ? "warning" : "neutral"}>{artist.recommendation?.tier || "hold"}</Badge>
        </div>
        <p className="recommendation-reason">{artist.recommendation?.reason}</p>
        <div className="recommendation-bottom"><label className="field note-field"><span>Decision note</span><input value={notes[artist.id] ?? ""} onChange={(event) => setNotes({ ...notes, [artist.id]: event.target.value })} placeholder="Rationale, next action or follow-up date…"/></label>
          <div className="decision-buttons">{decisions.map((option) => <button key={option.id} disabled={saving === artist.id} className={`btn btn-decision decision-${option.tone}`} onClick={() => choose(artist, option.id)}>{option.label}</button>)}</div>
        </div>
      </article>)}</div>}
  </div>;
}

function SettingsSection({ sources, setSources, settings, setSettings, automation, onSaveSources, onSaveSettings, savingSources, savingSettings, notify }) {
  const [sourceQuery, setSourceQuery] = useState("");
  const [category, setCategory] = useState("All");
  const [expanded, setExpanded] = useState("");
  const [credentials, setCredentials] = useState({});
  const [clears, setClears] = useState([]);
  const categories = ["All", ...new Set(sources.map((source) => source.category).filter(Boolean))].sort((a,b) => a === "All" ? -1 : a.localeCompare(b));
  const filtered = sources.filter((source) =>
    (category === "All" || source.category === category) &&
    (!sourceQuery || `${source.name} ${source.description} ${source.category}`.toLowerCase().includes(sourceQuery.toLowerCase())),
  );
  const enabledCount = sources.filter((source) => source.enabled).length;
  const readyCount = sources.filter((source) => source.status === "ready").length;
  const statusLabel = {
    ready: "Ready", needs_credentials: "Needs credentials", approval_required: "Approval required",
    research_only: "Research only", licensed_access: "Licensed access", partner_access: "Partner access",
    artist_authorisation: "Artist authorisation", manual_setup: "Manual setup", client_only: "Client implementation",
    disabled: "Disabled", not_implemented: "Not implemented",
  };
  const updateSource = (id, changes) => setSources((current) => current.map((source) => source.id === id ? { ...source, ...changes } : source));
  const updateConfig = (path, value) => setSettings((current) => {
    const next = structuredClone(current || {});
    const keys = path.split(".");
    let pointer = next;
    for (const key of keys.slice(0,-1)) pointer = pointer[key] ||= {};
    pointer[keys[keys.length - 1]] = value;
    return next;
  });
  const saveSourceConfig = () => onSaveSources(credentials, clears);
  return <div className="page-stack">
    <section className="section-heading settings-page-heading"><div><div className="eyebrow">SETTINGS / DATA GOVERNANCE</div><h1>Workspace settings</h1><p>Manage connected data providers, discovery automation and the A&R scoring framework.</p></div></section>

    <Panel className="source-panel" title={<><span className="source-eyebrow">SOURCE CONFIGURATION</span><span>Data providers · {sources.length}</span></>} sub="Choose which sources power manual and scheduled search. Provider keys are sent only to this backend and never returned to the browser.">
      <div className="source-toolbar-note"><span><strong>{readyCount}</strong> configured for search</span><span><strong>{enabledCount}</strong> selected</span><span>Sources are tested when a scan runs</span></div>
      <div className="source-filter-row"><div className="input-icon source-search"><Icon name="search" size={15}/><input value={sourceQuery} onChange={(event) => setSourceQuery(event.target.value)} placeholder="Search 73 data sources…"/></div><select value={category} onChange={(event) => setCategory(event.target.value)}>{categories.map((item) => <option key={item}>{item}</option>)}</select><span className="source-filter-count">{filtered.length} results</span></div>
      <div className="source-grid">{filtered.map((source) => {
        const isReady = source.status === "ready";
        const statusTone = isReady ? "ready" : source.status === "disabled" ? "disabled" : "restricted";
        const icon = source.category?.toLowerCase().includes("social") || source.category?.toLowerCase().includes("video") ? "users" : "database";
        return <article className={`source-card ${source.enabled ? "source-enabled" : ""} ${expanded === source.id ? "source-expanded" : ""}`} key={source.id}>
          <div className="source-provider-row">
            <label className="switch source-checkbox" title={`Enable ${source.name}`}><input type="checkbox" checked={source.enabled} onChange={(event) => updateSource(source.id,{enabled:event.target.checked})}/><span/></label>
            <div className={`source-icon-tile source-icon-${statusTone}`}><Icon name={icon} size={21}/></div>
            <div className="source-title"><strong>{source.name}</strong><span className={`provider-status provider-status-${statusTone}`}>{isReady ? "Ready" : source.status === "disabled" ? "Disabled" : statusLabel[source.status] || source.status}</span></div>
          </div>
          <p className="source-description">{source.description}</p>
          {source.access_note && <p className="source-access-note">{source.access_note}</p>}
          <div className="source-card-links"><button className="text-button" onClick={() => setExpanded(expanded === source.id ? "" : source.id)}>{expanded === source.id ? "Hide configuration" : "Configure source"} <Icon name="chevron" size={13}/></button>{source.docs_url && <a href={source.docs_url} target="_blank" rel="noreferrer">Provider docs <Icon name="arrow" size={13}/></a>}</div>
          {expanded === source.id && <div className="source-config">
            <div className="source-config-meta"><span>{source.category}</span><span>{source.capability === "evidence_enrichment" ? "Evidence enrichment" : source.implemented ? "Identity search adapter" : "Directory entry only"}</span></div>
            {source.fields?.length ? source.fields.map((field) => <label className="field" key={field.key}><span>{field.label}{field.configured && <em>Saved</em>}</span><input autoComplete="off" type={field.secret ? "password" : "text"} value={credentials[source.id]?.[field.key] || ""} onChange={(event) => setCredentials((prev) => ({...prev,[source.id]:{...(prev[source.id]||{}),[field.key]:event.target.value}}))} placeholder={field.configured ? "Configured · enter to replace" : `Enter ${field.label.toLowerCase()}`}/></label>) : <small>No credential fields are required for this source.</small>}
            {source.docs_url && <a className="source-doc-link" href={source.docs_url} target="_blank" rel="noreferrer">Official developer documentation <Icon name="external" size={12}/></a>}
          </div>}
        </article>;
      })}</div>
      <div className="settings-actions"><span>Secret values are encrypted by the backend and never returned to the browser.</span><button className="btn btn-primary" onClick={saveSourceConfig} disabled={savingSources}>{savingSources ? "Saving…" : "Save source configuration"} <Icon name="arrow" size={15}/></button></div>
    </Panel>

    <Panel className="automation-panel" title="Autonomous collection" sub="A live worker heartbeat shows whether background collection is actually running.">
      <div className="automation-status-row">
        <div className={`automation-indicator ${automation?.worker_online ? "is-online" : "is-offline"}`}><span/>{automation?.worker_online ? "Worker online" : "Worker not detected"}</div>
        <div className="automation-stat"><small>Last heartbeat</small><strong>{automation?.last_seen_at ? timeAgo(automation.last_seen_at) : "Not yet seen"}</strong></div>
        <div className="automation-stat"><small>Last discovery</small><strong>{automation?.last_discovery_at ? timeAgo(automation.last_discovery_at) : "No run yet"}</strong></div>
        <div className="automation-stat"><small>Next scheduled scan</small><strong>{automation?.next_discovery_at ? dateLabel(automation.next_discovery_at) : "Waiting for worker"}</strong></div>
      </div>
      {automation?.last_error && <Notice tone="warning">Last worker error: {automation.last_error}</Notice>}
      <p className="automation-caption">The background worker executes recurring multi-source searches, rechecks accepted artist identities, records source-specific metric history and refreshes public evidence links. Provider outages and exhausted quotas are surfaced in run history.</p>
    </Panel>

    <div className="content-grid settings-grid">
      <Panel title="Discovery controls" sub="Set the markets, seeds and minimum corroboration needed to enter your queue.">
        <div className="form-grid">
          <label className="field"><span>Regional focus</span><select value={settings.region_focus || "africa"} onChange={(event) => updateConfig("region_focus",event.target.value)}><option value="africa">Africa-wide</option><option value="east">East Africa first</option></select></label>
          <label className="field"><span>Minimum independent sources</span><input type="number" min="1" max="10" value={settings.min_sources_for_candidate ?? 2} onChange={(event) => updateConfig("min_sources_for_candidate",Number(event.target.value))}/></label>
          <label className="field"><span>Maximum candidates per run</span><input type="number" min="1" max="250" value={settings.max_artists_per_run ?? 100} onChange={(event) => updateConfig("max_artists_per_run",Number(event.target.value))}/></label>
          <label className="field"><span>Minimum history (days)</span><input type="number" min="1" max="90" value={settings.min_observation_days ?? 7} onChange={(event) => updateConfig("min_observation_days",Number(event.target.value))}/></label>
          <label className="field"><span>Discovery interval (hours)</span><input type="number" min="1" max="168" value={settings.auto_discovery_interval_hours ?? 6} onChange={(event) => updateConfig("auto_discovery_interval_hours",Number(event.target.value))}/></label>
        </div>
        <label className="field seeds-field"><span>Discovery seeds · one per line</span><textarea rows="6" value={(settings.discovery_seeds || []).join("\n")} onChange={(event) => updateConfig("discovery_seeds",event.target.value.split("\n").map((x) => x.trim()).filter(Boolean))}/></label>
        <label className="check-row"><input type="checkbox" checked={Boolean(settings.auto_discovery_enabled ?? true)} onChange={(event) => updateConfig("auto_discovery_enabled",event.target.checked)}/><span><strong>Enable scheduled discovery</strong><small>Scan the configured markets every {settings.auto_discovery_interval_hours ?? 6} hours. Pause it here at any time.</small></span></label>
        <label className="check-row"><input type="checkbox" checked={Boolean(settings.auto_evidence_enabled ?? true)} onChange={(event) => updateConfig("auto_evidence_enabled",event.target.checked)}/><span><strong>Refresh artist evidence automatically</strong><small>Recheck a rotating batch of tracked artists every {settings.auto_evidence_interval_hours ?? 24} hours for press, community and open-media references.</small></span></label>
        <label className="field"><span>Evidence refresh interval (hours)</span><input type="number" min="1" max="168" value={settings.auto_evidence_interval_hours ?? 24} onChange={(event) => updateConfig("auto_evidence_interval_hours",Number(event.target.value))}/></label>
        <button className="btn btn-primary" onClick={onSaveSettings} disabled={savingSettings}>{savingSettings ? "Saving…" : "Save discovery controls"}</button>
      </Panel>
      <Panel title="Scoring policy" sub="Transparent weights. Missing signals reduce confidence rather than being filled with synthetic values.">
        <div className="weight-section"><h3>Discovery index</h3>{Object.entries(settings.discovery_weights || DEFAULT_WEIGHTS.discovery_weights).map(([key,value]) => <div className="weight-row" key={key}><label>{key.replaceAll("_"," ")}</label><input type="range" min="0" max="50" step="1" value={value} onChange={(event) => updateConfig(`discovery_weights.${key}`,Number(event.target.value))}/><strong>{value}%</strong></div>)}</div>
        <div className="weight-section"><h3>Artistic contribution</h3><div className="weight-row"><label>Artistic score share</label><input type="range" min="0" max="100" value={settings.artistic_share ?? 60} onChange={(event) => updateConfig("artistic_share",Number(event.target.value))}/><strong>{settings.artistic_share ?? 60}%</strong></div></div>
        <div className="thresholds"><h3>Recommendation thresholds</h3><div className="threshold-row"><span>Pursue · artistic floor</span><strong>{settings.tier_rules?.pursue_artistic ?? 78}</strong></div><div className="threshold-row"><span>Pursue · combined</span><strong>{settings.tier_rules?.pursue_combined ?? 75}</strong></div><div className="threshold-row"><span>Meet · artistic floor</span><strong>{settings.tier_rules?.meet_artistic ?? 68}</strong></div><div className="threshold-row"><span>Meet · combined</span><strong>{settings.tier_rules?.meet_combined ?? 65}</strong></div><div className="threshold-row"><span>Watch · combined</span><strong>{settings.tier_rules?.watch_combined ?? 48}</strong></div></div>
        <button className="btn btn-primary" onClick={onSaveSettings} disabled={savingSettings}>{savingSettings ? "Saving…" : "Save scoring policy"}</button>
      </Panel>
    </div>
    <Notice tone="warning">Access is not implied by catalogue presence. TikTok Research, Meta research, licensed analytics feeds, partner APIs and artist-authorised dashboards require their stated approval, contract or account permission.</Notice>
  </div>;
}

export default function App() {
  const [section, setSection] = useState("discovery");
  const [dark, setDark] = useState(false);
  const [globalSearch, setGlobalSearch] = useState("");
  const [automation, setAutomation] = useState(null);
  const [health, setHealth] = useState(null);
  const [dashboard, setDashboard] = useState(null);
  const [sources, setSources] = useState([]);
  const [settings, setSettings] = useState({});
  const [candidates, setCandidates] = useState([]);
  const [artists, setArtists] = useState([]);
  const [recommendations, setRecommendations] = useState([]);
  const [selectedArtist, setSelectedArtist] = useState("");
  const [artistDetail, setArtistDetail] = useState(null);
  const [filters, setFilters] = useState({ query: "", country: "", genre: "" });
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [savingSources, setSavingSources] = useState(false);
  const [savingSettings, setSavingSettings] = useState(false);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState(null);
  const [mobileMenu, setMobileMenu] = useState(false);

  const notify = (message, tone = "info") => {
    setToast({ message, tone });
    window.clearTimeout(window.__brToastTimer);
    window.__brToastTimer = window.setTimeout(() => setToast(null), 4200);
  };
  const refreshCore = async () => {
    setLoading(true);
    const [healthResult, dashboardResult, sourceResult, settingsResult, candidateResult, artistResult, recResult, automationResult] = await Promise.allSettled([
      getHealth(), getDashboard(), getSources(), getSettings(), getCandidates({limit:100}), getArtists({limit:200}), getRecommendations(), getAutomationStatus(),
    ]);
    if (healthResult.status === "fulfilled") setHealth(healthResult.value);
    else setHealth({status:"error",error:healthResult.reason?.message || "API unavailable"});
    if (dashboardResult.status === "fulfilled") setDashboard(dashboardResult.value);
    if (sourceResult.status === "fulfilled") setSources(sourceResult.value.items || []);
    if (settingsResult.status === "fulfilled") setSettings(settingsResult.value.config || {});
    if (candidateResult.status === "fulfilled") setCandidates(candidateResult.value.items || []);
    if (artistResult.status === "fulfilled") setArtists(artistResult.value.items || []);
    if (recResult.status === "fulfilled") setRecommendations(recResult.value.items || []);
    if (automationResult.status === "fulfilled") setAutomation(automationResult.value);
    setLoading(false);
  };
  const refreshDetail = async () => {
    if (!selectedArtist) { setArtistDetail(null); return; }
    try { setArtistDetail(await getArtist(selectedArtist)); }
    catch (error) { notify(error.message,"error"); }
  };
  useEffect(() => {
    refreshCore();
    const saved = localStorage.getItem("br-theme");
    if (saved === "light") setDark(false);
  }, []);
  useEffect(() => {
    document.documentElement.classList.toggle("dark",dark);
    localStorage.setItem("br-theme",dark ? "dark" : "light");
  }, [dark]);
  useEffect(() => {
    const poll = async () => {
      const results = await Promise.allSettled([getDashboard(), getCandidates({limit:100}), getArtists({limit:200}), getRecommendations(), getAutomationStatus()]);
      if (results[0].status === "fulfilled") setDashboard(results[0].value);
      if (results[1].status === "fulfilled") setCandidates(results[1].value.items || []);
      if (results[2].status === "fulfilled") setArtists(results[2].value.items || []);
      if (results[3].status === "fulfilled") setRecommendations(results[3].value.items || []);
      if (results[4].status === "fulfilled") setAutomation(results[4].value);
    };
    const timer = window.setInterval(poll, 60000);
    return () => window.clearInterval(timer);
  }, []);
  useEffect(() => { refreshDetail(); }, [selectedArtist]);
  useEffect(() => {
    const handleShortcut = (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        document.querySelector(".global-search input")?.focus();
      }
    };
    window.addEventListener("keydown", handleShortcut);
    return () => window.removeEventListener("keydown", handleShortcut);
  }, []);
  const onRun = async (filterOverrides = null) => {
    const activeFilters = filterOverrides ? { ...filters, ...filterOverrides } : filters;
    setRunning(true);
    try {
      const result = await runDiscovery({...activeFilters, source_ids: sources.filter((source) => source.enabled && source.status === "ready" && source.implemented && source.capability === "identity_search").map((source) => source.id), limit:20});
      notify(`Scan complete · ${result.candidates_found} candidate identities found`,result.status === "completed" ? "success" : "warning");
      await refreshCore();
    } catch (error) { notify(error.message,"error"); }
    finally { setRunning(false); }
  };
  const onReview = async (candidate, action) => {
    try {
      const id = candidate.candidate_ids?.[0];
      await reviewCandidate(id,action,action === "accept" ? "Accepted by A&R review." : "Dismissed by A&R review.");
      notify(action === "accept" ? `${candidate.name} added to the artist directory` : `${candidate.name} dismissed`,action === "accept" ? "success" : "info");
      await refreshCore();
    } catch (error) { notify(error.message,"error"); }
  };
  const onSaveSources = async (credentialUpdates, clears) => {
    setSavingSources(true);
    try {
      const payload = {
        enabled_source_ids: sources.filter((source) => source.enabled).map((source) => source.id),
        credential_updates: Object.fromEntries(Object.entries(credentialUpdates).map(([id,fields]) => [id,Object.fromEntries(Object.entries(fields).filter(([,value]) => String(value).trim()))]).filter(([,fields]) => Object.keys(fields).length)),
        clear_credentials: clears,
      };
      const result = await saveSources(payload);
      setSources(result.items || []);
      notify(`Saved ${payload.enabled_source_ids.length} source selections`, "success");
      await refreshCore();
    } catch (error) { notify(error.message,"error"); }
    finally { setSavingSources(false); }
  };
  const onSaveSettings = async () => {
    setSavingSettings(true);
    try {
      const result = await saveSettings(settings);
      setSettings(result.config || settings);
      notify("Discovery and scoring settings saved", "success");
      await refreshCore();
    } catch (error) { notify(error.message,"error"); }
    finally { setSavingSettings(false); }
  };
  const reloadRecommendations = async () => {
    const result = await getRecommendations();
    setRecommendations(result.items || []);
    const artistPage = await getArtists({limit:200});
    setArtists(artistPage.items || []);
  };
  const submitGlobalSearch = (event) => {
    event.preventDefault();
    const query = globalSearch.trim();
    if (!query || running) return;
    const nextFilters = { ...filters, query };
    setFilters(nextFilters);
    setSection("discovery");
    void onRun(nextFilters);
  };
  const current = NAV.find((item) => item.id === section);
  const selectedProfile = artists.find((artist) => artist.id === selectedArtist);

  return <div className={`app-shell ${dark ? "theme-dark" : "theme-light"}`}>
    <aside className={`sidebar ${mobileMenu ? "sidebar-open" : ""}`}>
      <div className="brand"><div className="brand-symbol"><Icon name="music" size={25}/></div><div className="brand-name">BREAKOUT <b>RADAR</b><small>A&R INTELLIGENCE</small></div><button className="mobile-close icon-btn" onClick={() => setMobileMenu(false)}><Icon name="x"/></button></div>
      <div className="sidebar-label">WORKSPACE</div>
      <nav aria-label="Main navigation">{NAV.map((item) => <button key={item.id} className={`nav-item ${section === item.id ? "nav-active" : ""}`} onClick={() => {setSection(item.id);setMobileMenu(false);}}><span className="nav-icon"><Icon name={item.icon}/></span><span><strong>{item.label}</strong><small>{item.short}</small></span>{item.id === "discovery" && candidates.length > 0 && <span className="nav-count">{candidates.length > 99 ? "99+" : candidates.length}</span>}{section === item.id && <i/>}</button>)}</nav>
      <div className="sidebar-bottom"><div className="workspace-card"><div className="workspace-avatar">AR</div><div><strong>A&R Workspace</strong><small>Local research environment</small></div><Badge tone="success">PRIVATE</Badge></div><div className="security-note"><Icon name="shield" size={14}/><span>Credentials encrypted at rest.<br/>API bound to localhost.</span></div></div>
    </aside>
    {mobileMenu && <button className="mobile-scrim" aria-label="Close navigation" onClick={() => setMobileMenu(false)}/>}
    <main className="main-shell">
      <header className="topbar"><button className="mobile-menu icon-btn" onClick={() => setMobileMenu(true)}><Icon name="menu"/></button><form className="global-search" onSubmit={submitGlobalSearch}><Icon name="search" size={17}/><input aria-label="Search artist, city or genre" value={globalSearch} onChange={(event) => setGlobalSearch(event.target.value)} placeholder="Search artist, city, genre..."/><kbd>⌘K</kbd></form><div className="topbar-right"><div className="api-status"><span className={health?.status === "ok" ? "status-dot" : "status-dot status-down"}/>{health?.status === "ok" ? "API connected" : "API unavailable"}</div><button className="icon-btn topbar-refresh" aria-label="Refresh workspace" onClick={refreshCore}><Icon name="refresh"/></button><div className="user-chip"><span>A</span></div></div></header>
      <div className="page-container">
        {health?.status === "error" && <Notice tone="error">Backend unavailable: {health.error}. Start the FastAPI service on port 8000, then refresh.</Notice>}
        {loading && !dashboard ? <div className="loading-screen"><div className="loading-orbit"><Icon name="radar" size={34}/></div><strong>Preparing your intelligence workspace</strong><span>Connecting to source registry and artist records…</span></div> :
          section === "discovery" ? <DiscoverySection dashboard={dashboard} candidates={candidates} artists={artists} sources={sources} loading={loading} running={running} filters={filters} setFilters={setFilters} onRun={onRun} onReview={onReview} selectedArtist={selectedArtist} setSelectedArtist={(id) => {setSelectedArtist(id);setSection("analyse");}}/> :
          section === "analyse" ? <AnalyseSection artists={artists} selectedArtist={selectedArtist} setSelectedArtist={setSelectedArtist} artistDetail={artistDetail} reloadDetail={refreshDetail} busy={busy} notify={notify}/> :
          section === "recommendations" ? <RecommendationsSection recommendations={recommendations} reload={reloadRecommendations} notify={notify}/> :
          <SettingsSection sources={sources} setSources={setSources} settings={settings} setSettings={setSettings} automation={automation} onSaveSources={onSaveSources} onSaveSettings={onSaveSettings} savingSources={savingSources} savingSettings={savingSettings} notify={notify}/>}
      </div>
      <footer className="app-footer"><span>BREAKOUT RADAR <b>v3.1</b></span><span>Evidence first. People decide.</span><span>{health?.authentication || "Local environment"}</span></footer>
    </main>
    {toast && <div className={`toast toast-${toast.tone}`} role="status"><span className="toast-mark"><Icon name={toast.tone === "error" ? "x" : "check"} size={14}/></span>{toast.message}<button className="icon-btn" onClick={() => setToast(null)}><Icon name="x" size={14}/></button></div>}
  </div>;
}
