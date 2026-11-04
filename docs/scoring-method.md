# Scoring and A&R decision method

## Purpose

The scoring layer is a transparent decision-support model for prioritising research. It does not estimate the probability that an artist will become commercially successful.

It returns separate measures for:
- Discovery index — what the current source evidence says about momentum and corroboration.
- Artistic score — what a human A&R reviewer records in a structured review.
- Combined index — a configurable blend used to order the work queue.
- Confidence — the configured discovery-weight coverage represented by observed data.

## Discovery index

The default discovery weights are:

| Component | Weight | Expected input |
|---|---:|---|
| Momentum | 30% | Growth within the same source + metric series over time |
| Independent-source breadth | 25% | Number of separate provider identities that corroborate the artist |
| Release activity | 15% | Provider-returned release or album activity |
| Live activity | 10% | Provider-returned event/live activity |
| Search interest | 10% | Authorised search-interest observation |
| Catalogue headroom | 10% | Configured emerging-artist/catalogue maturity signal |

Only non-missing components contribute to the score. The score is normalised over the available weights. Confidence is the share of configured discovery weight represented by actual observations.

### Momentum

Momentum requires multiple observations for the same artist, source and metric, separated by at least the configured minimum history (seven days by default). The calculation uses relative change in that one series. It never adds different platforms' followers, fans, subscribers or views together.

For a source series with first value (x_0), latest value (x_t) and elapsed days (d), the code annualises the observed rate to a 30-day-equivalent relative-growth rate. It then maps that rate to a bounded 0–100 index. Invalid, zero-baseline or too-short series are missing rather than assigned an invented value.

### Source breadth

Source breadth is corroboration of artist identity, not audience size. Multiple distinct provider identifiers increase evidence coverage. A matching name alone is not treated as definitive identity proof; the original provider links remain visible for human verification.

## Artistic review

The default rubric scores each dimension from 0 to 10:

| Dimension | Default relative weight |
|---|---:|
| Songwriting | 2.0 |
| Vocals | 2.0 |
| Melody | 1.5 |
| Production | 1.0 |
| Originality | 1.5 |
| Performance | 1.0 |
| Artist identity | 1.0 |

The rubric can be customised in Settings. The review records the reviewer, optional track URL/title, notes, strengths, risks and evidence references. A submitted score is reviewer-attributed. The current build does not claim to have an AI music-listening model or automatically grade audio.

## Combined index and recommendations

By default, the combined index assigns 60% to artistic review and 40% to discovery evidence. This share is editable.

Default tiers:

| Tier | Rule |
|---|---|
| Pursue | Artistic score at least 78 and combined score at least 75 |
| Meet | Artistic score at least 68 and combined score at least 65 |
| Watch | Combined score at least 48 |
| Hold | Anything below the Watch threshold, or no completed artistic review |

Without a completed artistic review, the tier remains Hold even when the discovery score is high. Teams can override a recommendation through an explicit decision record; the decision owner and rationale are retained.

## Guardrails

- No metric is inferred when the provider did not return it.
- No cross-platform fan total is calculated.
- Platform-specific metrics retain source and observation timestamps.
- Missing inputs lower confidence instead of being filled with synthetic values.
- Source presence, Wikipedia notability or a playlist/catalogue appearance is not treated as proof of artistic quality.
- Recommendations are review priorities, not automatic signing decisions.
- Predictive modelling is deferred until the product has authorised longitudinal observations, outcome labels, time-based validation and calibration.
