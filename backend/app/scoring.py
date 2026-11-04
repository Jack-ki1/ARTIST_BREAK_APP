"""Transparent, missing-data-aware A&R scoring. Scores are indices, never probabilities."""
from __future__ import annotations

from datetime import datetime, timezone
from math import log1p
from statistics import mean

DISCOVERY_WEIGHTS = {
    "momentum": 0.30,
    "independent_breadth": 0.25,
    "release_activity": 0.15,
    "live_activity": 0.10,
    "search_interest": 0.10,
    "catalogue_headroom": 0.10,
}
ARTISTIC_WEIGHTS = {
    "songwriting": 2.0,
    "vocals": 2.0,
    "melody": 1.5,
    "production": 1.0,
    "originality": 1.5,
    "performance": 1.0,
    "identity": 1.0,
}
DEFAULT_SETTINGS = {
    "region_focus": "africa",
    "discovery_seeds": [
        "Kenyan emerging artists", "East African new music", "Bongo Flava",
        "Kenyan hip hop", "Ugandan alternative music", "Rwandan music",
        "Ghanaian Afrobeats", "Nigerian alternative music", "African R&B",
        "Zambian music", "Ethiopian new music", "African amapiano",
    ],
    "countries": ["KE", "TZ", "UG", "RW", "NG", "GH", "ZA", "ZM", "ET"],
    "genres": [],
    "min_sources_for_candidate": 2,
    "max_artists_per_run": 100,
    "min_observation_days": 7,
    "discovery_weights": DISCOVERY_WEIGHTS,
    "artistic_weights": ARTISTIC_WEIGHTS,
    "artistic_share": 60,
    "tier_rules": {"pursue_artistic": 78, "pursue_combined": 75, "meet_artistic": 68, "meet_combined": 65, "watch_combined": 48},
    "emerging_limits": {"max_catalog_releases": 35, "max_known_follower_count": 500000},
    "exclude_names": [],
    "auto_discovery_enabled": False,
    "auto_discovery_interval_hours": 24,
    "analysis_batch_size": 10,
    "default_reviewer": "A&R Team",
    "ai_provider": "none",
    "ai_model": "",
}


def growth_percent(first: float, last: float, days: float) -> float | None:
    if days < 1 or first <= 0 or last < 0:
        return None
    daily_rate = (max(last, 0.000001) / first) ** (1 / days) - 1
    return round(((1 + daily_rate) ** 30 - 1) * 100, 2)


def source_momentum(observations: list[dict], metric: str) -> float | None:
    """A 0–100 momentum index for one source+metric, requiring two observations.

    The value is not a cross-platform count. It uses the relative change inside
    the same provider/metric series, clipped to avoid a single spike dominating.
    """
    rows = sorted(
        [r for r in observations if r.get("metric") == metric],
        key=lambda r: r.get("observed_at") or "",
    )
    if len(rows) < 2:
        return None
    first, last = rows[0], rows[-1]
    try:
        a, b = float(first["value"]), float(last["value"])
        days = (datetime.fromisoformat(str(last["observed_at"]).replace("Z", "+00:00")) -
                datetime.fromisoformat(str(first["observed_at"]).replace("Z", "+00:00"))).total_seconds() / 86400
    except (ValueError, TypeError, KeyError):
        return None
    change = growth_percent(a, b, days)
    if change is None:
        return None
    # 0% growth -> 50 index; +100%/30d -> 100; -100% -> 0.
    return round(max(0.0, min(100.0, 50 + change / 2)), 1)


def discovery_index(features: dict, weights: dict | None = None) -> dict:
    """Weighted ranking index; missing dimensions are omitted and reduce confidence."""
    weights = weights or DISCOVERY_WEIGHTS
    components = {
        "momentum": features.get("momentum"),
        "independent_breadth": min(100.0, float(features.get("independent_source_count", 0)) * 12.5),
        "release_activity": features.get("release_activity"),
        "live_activity": features.get("live_activity"),
        "search_interest": features.get("search_interest"),
        "catalogue_headroom": features.get("catalogue_headroom"),
    }
    active = [(name, max(0.0, min(100.0, float(value))), max(0.0, float(weights.get(name, 0))))
              for name, value in components.items() if value is not None]
    total_weight = sum(weight for _, _, weight in active)
    if total_weight <= 0:
        return {"score": 0, "confidence": 0, "components": components, "coverage": []}
    score = round(sum(value * weight for _, value, weight in active) / total_weight, 1)
    configured_weight = sum(max(0.0, float(v)) for v in weights.values()) or 1.0
    confidence = round(min(100.0, total_weight / configured_weight * 100), 1)
    return {"score": score, "confidence": confidence, "components": components,
            "coverage": [name for name, _, _ in active]}


def artistic_overall(scores: dict, weights: dict | None = None) -> float | None:
    weights = weights or ARTISTIC_WEIGHTS
    values = []
    for key, weight in weights.items():
        value = scores.get(key)
        if value is None:
            continue
        numeric = max(0.0, min(10.0, float(value)))
        if weight > 0:
            values.append((numeric * 10.0, float(weight)))
    if not values:
        return None
    return round(sum(v * w for v, w in values) / sum(w for _, w in values), 1)


def recommendation(discovery: float | None, artistic: float | None, settings: dict | None = None) -> dict:
    settings = settings or DEFAULT_SETTINGS
    share = max(0.0, min(100.0, float(settings.get("artistic_share", 60)))) / 100
    if discovery is None:
        discovery = 0.0
    if artistic is None:
        return {"score": round(discovery * (1 - share), 1), "tier": "hold",
                "reason": "No completed artistic review. Discovery signals alone cannot trigger a signing recommendation."}
    combined = round(artistic * share + discovery * (1 - share), 1)
    rules = settings.get("tier_rules", DEFAULT_SETTINGS["tier_rules"])
    if artistic >= rules["pursue_artistic"] and combined >= rules["pursue_combined"]:
        tier, reason = "pursue", "Strong artistic review and discovery momentum."
    elif artistic >= rules["meet_artistic"] and combined >= rules["meet_combined"]:
        tier, reason = "meet", "Artistic quality clears the meeting threshold."
    elif combined >= rules["watch_combined"]:
        tier, reason = "watch", "Promising signals; collect more evidence or review again."
    else:
        tier, reason = "hold", "Current evidence does not meet the configured thresholds."
    return {"score": combined, "tier": tier, "reason": reason}


def explain_discovery(features: dict, scored: dict) -> list[str]:
    notes = []
    for key, value in scored["components"].items():
        if value is None:
            notes.append(f"{key.replace('_', ' ').title()}: insufficient observations")
        else:
            notes.append(f"{key.replace('_', ' ').title()}: {float(value):.0f}/100")
    notes.append(f"Evidence coverage: {scored['confidence']:.0f}% of configured discovery weight")
    notes.append(f"Independent sources: {features.get('independent_source_count', 0)}")
    return notes
