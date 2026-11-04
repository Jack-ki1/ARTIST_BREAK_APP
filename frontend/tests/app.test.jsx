import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../src/App.jsx";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
let root, host, calls = [], artists = [], candidates = [], recommendations = [];

const response = (body, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const artist = {
  id: "artist-1", name: "Nia K", country: "KE", city: "Nairobi", genres: ["Alternative R&B"],
  discovery_score: 58, discovery_confidence: 35, artistic_score: null, combined_score: 0,
  recommendation_tier: "hold", stage: "emerging", review_status: "unreviewed",
  identities: [], observations: [], evidence: [], reviews: [], decisions: [],
};
const config = {
  region_focus: "africa", discovery_seeds: ["Kenyan emerging artists", "East African new music"],
  min_sources_for_candidate: 2, max_artists_per_run: 100, min_observation_days: 7,
  discovery_weights: { momentum: 30, independent_breadth: 25, release_activity: 15, live_activity: 10, search_interest: 10, catalogue_headroom: 10 },
  artistic_weights: { songwriting: 2, vocals: 2, melody: 1.5, production: 1, originality: 1.5, performance: 1, identity: 1 },
  artistic_share: 60, tier_rules: { pursue_artistic: 78, pursue_combined: 75, meet_artistic: 68, meet_combined: 65, watch_combined: 48 },
  emerging_limits: { max_catalog_releases: 35, max_known_follower_count: 500000 }, auto_discovery_enabled: false,
};
function sourceList() {
  const names = [
    ["musicbrainz","MusicBrainz","ready",true,"identity_search",[]],
    ["spotify","Spotify","disabled",true,"identity_search",[{key:"client_id",label:"Client ID",secret:false,configured:false},{key:"client_secret",label:"Client secret",secret:true,configured:false}]],
    ["gdelt","GDELT Project","ready",true,"evidence_enrichment",[]],
    ["tiktok_research","TikTok Research API","disabled",false,"catalogue_only",[]],
  ];
  const list = names.map(([id,name,status,implemented,capability,fields]) => ({
    id,name,category:"Music metadata",access:"public",docs_url:"https://example.com",description:"Source description.",
    fields,missing_fields:[],enabled:status==="ready",implemented,capability,connected:status==="ready",status,access_note:"Official access terms apply.",
  }));
  while (list.length < 73) {
    const n=list.length+1;
    list.push({id:`source-${n}`,name:`Source ${n}`,category:"Music metadata",access:"partner",docs_url:"https://example.com",description:"Partner source.",fields:[],missing_fields:[],enabled:false,implemented:false,capability:"catalogue_only",connected:false,status:"disabled",access_note:"Partner access required."});
  }
  return list;
}
let sources = sourceList();
const dashboard = {overview:{artists_tracked:artists.length,pending_candidates:candidates.length,artistic_reviews:0,a_and_r_decisions:0,sources_total:73,sources_ready:2,emerging_artists:artists.length},recommendation_tiers:{},recent_runs:[],source_summary:{total:73,enabled:2,ready:2},settings:{region_focus:"africa",auto_discovery_enabled:false}};
function mockFetch() {
  calls=[];
  vi.stubGlobal("fetch",vi.fn(async (url,options={})=>{
    const path=String(url), method=options.method||"GET"; calls.push([path,options]);
    if(path==="/api/health") return response({status:"ok",database:"connected",version:"3.0.0",authentication:"disabled — loopback only",source_count:73});
    if(path==="/api/dashboard") return response(dashboard);
    if(path==="/api/sources" && method==="PUT") {
      const body=JSON.parse(options.body);
      sources=sources.map(x=>({...x,enabled:body.enabled_source_ids.includes(x.id),status:body.enabled_source_ids.includes(x.id)?"ready":"disabled",connected:body.enabled_source_ids.includes(x.id)}));
      return response({items:sources,summary:{total:73,enabled:body.enabled_source_ids.length,ready:body.enabled_source_ids.length}});
    }
    if(path==="/api/sources") return response({items:sources,summary:{total:73,enabled:2,ready:2}});
    if(path==="/api/settings" && method==="PUT") return response({config:JSON.parse(options.body).config});
    if(path==="/api/settings") return response({config});
    if(path.startsWith("/api/discovery/run")) return response({run_id:"run-1",status:"completed",sources_attempted:["musicbrainz"],source_results:{},candidates_found:1,artists_added:0});
    if(path.startsWith("/api/discovery/candidates/") && path.endsWith("/review")) return response({action:JSON.parse(options.body).action,linked_sources:1,artist_id:"artist-1"});
    if(path.startsWith("/api/discovery/candidates?")) return response({items:candidates,total:candidates.length,sources_scanned:["musicbrainz"]});
    if(path==="/api/artists" && method==="POST") return response({...artist,...JSON.parse(options.body)},201);
    if(path==="/api/artists" || path.startsWith("/api/artists?")) return response({items:artists,total:artists.length,limit:200,offset:0});
    if(path.endsWith("/reviews")) return response({id:"review-1",overall:84.5,tier:"watch",scores:JSON.parse(options.body).scores},201);
    if(path.endsWith("/decisions")) return response({id:"decision-1",decision:JSON.parse(options.body).decision},201);
    if(path.endsWith("/collect-evidence")) return response({evidence_saved:2,sources:{gdelt:{status:"success",saved:2}}});
    if(path.startsWith("/api/artists/")) return response(artist);
    if(path==="/api/recommendations") return response({items:recommendations,total:recommendations.length});
    if(path==="/api/runs" || path==="/api/alerts") return response({items:[]});
    return response({detail:`Unhandled ${method} ${path}`},404);
  }));
}
async function waitForText(value) {
  for(let i=0;i<40;i+=1) {
    if(document.body.textContent.includes(value)) return;
    await act(async()=>new Promise(resolve=>setTimeout(resolve,10)));
  }
  throw new Error(`Timed out: ${value}`);
}
async function render() {
  host=document.createElement("div"); document.body.append(host); root=createRoot(host);
  await act(async()=>root.render(<App/>)); await waitForText("Find the next");
}
async function click(label) {
  const button=[...document.querySelectorAll("button")].find(x=>x.textContent.includes(label));
  if(!button) throw new Error(`Button missing: ${label}`);
  await act(async()=>button.click());
}
async function nav(label) {
  const button=[...document.querySelectorAll('[aria-label="Main navigation"] button')].find(x=>x.textContent.includes(label));
  if(!button) throw new Error(`Nav missing: ${label}`);
  await act(async()=>button.click());
}
afterEach(async()=>{
  if(root) await act(async()=>root.unmount());
  host?.remove(); root=null; host=null; calls=[]; artists=[]; candidates=[]; recommendations=[];
  sources=sourceList(); vi.restoreAllMocks(); vi.unstubAllGlobals(); window.localStorage.clear();
});

describe("Breakout Radar v3",()=>{
  it("keeps exactly four primary sections",async()=>{
    mockFetch(); await render();
    expect([...document.querySelectorAll('[aria-label="Main navigation"] strong')].map(x=>x.textContent))
      .toEqual(["Discovery","Analyse","Recommendations","Settings"]);
    await nav("Analyse"); await waitForText("Understand the whole artist.");
    await nav("Recommendations"); await waitForText("Turn signals into");
    await nav("Settings"); await waitForText("Configure your");
  });
  it("runs discovery with enabled identity-search sources",async()=>{
    mockFetch(); await render();
    const input=document.querySelector(".scan-controls input");
    await act(async()=>{Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,"value").set.call(input,"Nia K");input.dispatchEvent(new Event("input",{bubbles:true}));});
    await click("Run discovery"); await waitForText("Scan complete");
    const call=calls.find(([url,options])=>url==="/api/discovery/run" && options.method==="POST");
    expect(JSON.parse(call[1].body)).toMatchObject({query:"Nia K",source_ids:["musicbrainz"],limit:20});
  });
  it("accepts a source-grouped candidate",async()=>{
    candidates=[{group_key:"nia k",name:"Nia K",country:"KE",city:"Nairobi",genres:["Alternative R&B"],source_ids:["musicbrainz"],source_count:1,candidate_ids:["candidate-1"],discovery_score:45,confidence:12.5,signal_summary:["Found on MusicBrainz"]}];
    mockFetch(); await render(); await waitForText("Nia K"); await click("Accept");
    await waitForText("added to the artist directory");
    expect(calls.some(([url,options])=>url==="/api/discovery/candidates/candidate-1/review" && options.method==="POST")).toBe(true);
  });
  it("lists 73 sources and supports credential entry",async()=>{
    mockFetch(); await render(); await nav("Settings"); await waitForText("73 Sources catalogued");
    const card=[...document.querySelectorAll(".source-card")].find(x=>x.textContent.includes("Spotify"));
    await act(async()=>card.querySelector(".switch input").click());
    await act(async()=>[...card.querySelectorAll(".source-config input")].forEach((input,i)=>{
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,"value").set.call(input,i?"client-secret":"client-id");
      input.dispatchEvent(new Event("input",{bubbles:true}));
    }));
    await click("Save source configuration"); await waitForText("Saved 3 source selections");
    const call=calls.find(([url,options])=>url==="/api/sources" && options.method==="PUT");
    expect(JSON.parse(call[1].body)).toMatchObject({enabled_source_ids:["musicbrainz","gdelt","spotify"],credential_updates:{spotify:{client_id:"client-id",client_secret:"client-secret"}}});
  });
  it("saves a structured artistic review",async()=>{
    artists=[artist]; mockFetch(); await render(); await nav("Analyse");
    const select=document.querySelector(".select-wrap select");
    await act(async()=>{select.value="artist-1";select.dispatchEvent(new Event("change",{bubbles:true}));});
    await waitForText("Artistic review"); await click("Save artistic review");
    await waitForText("Artistic review saved");
    const call=calls.find(([url,options])=>url==="/api/artists/artist-1/reviews" && options.method==="POST");
    expect(JSON.parse(call[1].body)).toMatchObject({reviewer:"A&R Team",scores:{songwriting:5,vocals:5}});
  });
  it("records an explicit A&R decision",async()=>{
    recommendations=[{...artist,recommendation:{score:55,tier:"watch",reason:"Promising signals."},decision_count:0}];
    mockFetch(); await render(); await nav("Recommendations"); await waitForText("Nia K"); await click("Watch");
    await waitForText("watch decision recorded");
    expect(calls.some(([url,options])=>url==="/api/artists/artist-1/decisions" && options.method==="POST")).toBe(true);
  });
});
