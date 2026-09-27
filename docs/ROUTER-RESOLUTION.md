# Router resolution and Workflow ownership

Skills Manager supports recursive Router/Composite resolution, but production Workflows should not assume that every broad natural-language task can safely delegate its critical owner to Router top-1 ranking.

## Finding from the production audit

Live resolver probes found useful matches, but also deterministic ties where discovery order could choose a broader capability before the intended expert:

- UI/UX design task → `ui-design` selected correctly
- frontend art direction → `frontend-design` selected correctly
- Web engineering task → `cloudbase` tied with `web-development` and could win
- browser QA task → generic `debug` could rank above `webapp-testing`
- final UI audit → generic `audit` could rank above `impeccable`
- broad creator research → a writing skill could rank above `hv-analysis`
- personal voice → `human-writing` selected correctly
- video frame review → `video-frame-extractor` selected correctly
- talking-head rough cut → `ai-jian-koubo` selected correctly

This is not a reason to flatten Routers. It is a reason to separate discovery from ownership.

## Production rule: Router + Owner

Use a Router for:

- current capability discovery
- authority/source recovery
- optional specialists
- newly installed capabilities
- fallbacks
- nested internal orchestration

Use an explicit owner binding when:

- a stage has a known professional responsibility
- selecting the wrong child changes the execution method materially
- the Workflow contract is meant to stay stable across runs

Current examples:

Frontend Product Builder v4:
`ui-design → frontend-design → web-development → webapp-testing → impeccable`

Creator Studio v4:
`human-writing` owns personal voice; media/visual engines are selected after the deliverable route is known.

Each frontend core owner can fall back to `web-ui` if unavailable, preserving self-healing without making ranking ambiguity the normal path.

## Future resolver improvement

A future resolver version may improve capability-kind priors, exact route aliases, semantic scoring, and tie-breaking. When that is proven by route tests, Workflows can safely move more ownership back into Router resolution.

Until then, do not “simplify” production Workflows by replacing known core owners with one broad Router binding.
