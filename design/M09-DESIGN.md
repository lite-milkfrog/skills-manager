# SCP-M09 Design System

STABLE_CORE_VERSION = LE-STABLE-2026-09-17.2
PROGRAM_ID = SKILL-CONTROL-PLANE-UNIFIED-LOCAL-20260922
STAGE = SCP-M09-DESIGN-SYSTEM-I18N-AND-DESKTOP-BRANDING-POLISH

## Product context

Skill Control Plane is a local developer/admin instrument for inspecting and operating the already-closed Skill registry, workflow/run truth, deployment safety model, and system health. It is a high-density tool used for repeated technical work, not a marketing surface.

Primary tasks remain: find canonical Skills quickly; understand source authority and variants; inspect bodies lazily; organize metadata without moving files; inspect/version workflows; inspect durable Runs and evidence; preview safe deployment plans; verify system truth.

## Method source and route

This stage follows the user's Obsidian Web/UI method as the process source:

Requirements / Product Truth
→ Information Architecture
→ User Flow
→ Structural audit
→ DESIGN.md
→ Component System
→ Implementation
→ Browser Render
→ Screenshot QA / Diff
→ Responsive QA
→ Functional QA
→ Design + Accessibility QA
→ Engineering QA
→ Ship

Because this is PRODUCT UI / LOCAL ADMIN TOOL / DASHBOARD, structure comes first. No full-page concept-image generation is used. UI stays native HTML/CSS/JS; branding is SVG; the Windows shortcut derives an ICO from the editable SVG source.

## Skill selection

**PRIMARY: Impeccable**
- selected registry variant: `ed9eb9a002363078034709cf`
- selected path: <selected-skill-root>/impeccable/SKILL.md
- role: design context, hierarchy, spacing, typography, responsive behavior, anti-pattern review, hardening and polish.

Supporting only:
- `webapp-testing`: rendered-browser reconnaissance, interaction and screenshot QA.
- `web-design-guidelines`: narrow standards review.
- `accessibility-review`: WCAG 2.1 AA gate, keyboard/focus/contrast/touch targets.
- `design-qa`: NOT USED as a pass gate because its own contract requires a source visual target and rendered implementation; M09 has no source mock to compare against.
- `awesome-design-md`: inspected but NOT USED as an imported template because existing M05 product/visual truth plus the user's own methodology is more authoritative.
- `frontend-design`, `taste`: available but NOT stacked with the primary harness.
- `PixelClone`, `imagegen-frontend-web`, `design-taste-frontend`: not present in the current registry and not needed for this product-UI route.

## Baseline audit

Preserve:
- six-destination IA: Overview / Skills / Workflows / Runs / Deployments / System;
- graphite surfaces and restrained teal accent;
- compact 32–38 px desktop table density;
- 4/8-ish spacing rhythm;
- explicit source authority and safety semantics;
- lazy Skill body loading and pagination;
- internal table scrolling on narrow screens;
- minimal motion and typed API boundaries.

M09 defects to correct:
1. no real locale layer; document starts as `lang=en`;
2. no visible language switch or persistence;
3. human-facing English copy is spread throughout the frontend;
4. Chinese typography/fallback behavior is undefined;
5. 820 px collapsed navigation reduces destinations to first letters and weakens recognition;
6. generic text-only SCP brand tile and generic SHELL32 desktop icon provide no project-owned identity;
7. mobile top chrome needs deliberate language/health/search layout at 375 px;
8. focus treatment is visible but should use stable outline semantics rather than changing perceived component shape;
9. breadcrumbs expose raw route segments instead of localized human labels;
10. browser console contains extension-origin errors; app-origin console must be distinguished from injected extension noise.

The baseline does NOT justify a visual rewrite. There is no gratuitous purple gradient, neon, glassmorphism, excessive whitespace, or generic marketing hero. Cards and pills are mostly functional and restrained.

## Personality and visual direction

Personality: calm, precise, engineering-oriented, inspectable, dense but legible, local-first.

Visual direction: dark graphite control surface with a single restrained mineral-teal accent. Brand recognition comes from geometry and hierarchy, not glow, gradient, glass, or decorative animation.

One memorable element: a project-owned **control-plane mark** — three horizontally connected control nodes held inside an open square plane. It suggests orchestration, routing and structured local control without using a gear, robot, sparkle, brain or neon hexagon.

## Typography

UI stack:
`"Segoe UI Variable", "Segoe UI", "Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC", system-ui, sans-serif`

Monospace:
`"Cascadia Mono", "JetBrains Mono", Consolas, "Microsoft YaHei UI", monospace`

Chinese:
- prefer system CJK UI glyphs;
- body line-height 1.5–1.6 where prose appears;
- do not force letter spacing on Chinese labels;
- uppercase micro-label treatment is disabled for zh-CN.

English:
- compact labels may use slight letter spacing;
- avoid all-caps body copy;
- page titles remain 24–28 px at desktop.

Type scale:
- 11 px metadata / captions;
- 12–13 px controls / table body;
- 14 px emphasized body;
- 16–18 px section emphasis when needed;
- 26 px page title.

## Surfaces and color roles

- Canvas: #101316
- Sidebar/top chrome: #12161a
- Panel: #171b20
- Raised/interactive panel: #1d2329
- Strong raised panel: #252c33
- Border: #343d46
- Soft divider: #293139
- Primary text: #e8ecef
- Muted text: #98a4ae
- Accent: #52c3b3
- Accent surface: #163a36
- Healthy: #69ca8b
- Warning/dry-run: #e2b85e
- Error/physical risk: #e77777
- Focus: #72d8ca

No decorative gradients. A loading shimmer is allowed only as a functional skeleton; prefer restrained opacity motion.

## Geometry

Radius:
- controls: 4 px
- panels/tables: 6 px
- badges: 4 px or compact capsule only when semantic grouping benefits
- no large 16–32 px SaaS-card rounding.

Borders are the primary separation mechanism; shadows are exceptional and reserved for transient overlays/toasts.

## Spacing and density

Scale: 4 / 6 / 8 / 10 / 12 / 16 / 24 / 32.

Desktop:
- table row 34–38 px;
- topbar 56 px;
- sidebar 232 px;
- page horizontal padding 18 px;
- page blocks generally 10–14 px apart.

Mobile:
- interactive targets >=44 px;
- body padding 12 px;
- tables scroll inside their own wrapper;
- do not remove canonical identifiers or safety truth just to reduce width.

## Navigation

Primary IA is frozen:
Overview / Skills / Workflows / Runs / Deployments / System.

Desktop >= 900 px: full labelled sidebar.
Tablet 700–899 px: keep recognizable icon + label treatment; do not degrade to ambiguous first letters.
Mobile <700 px: off-canvas labelled navigation with a visible menu control and Escape close behavior.

Active state uses accent surface + edge/marker, never color alone.

## Tables

Tables remain the primary dense inventory representation.
- sticky headers;
- compact rows;
- semantic `th scope=col`;
- internal horizontal scroll is acceptable on narrow screens;
- long IDs/paths truncate visually but remain available by title/copy/detail;
- row actions must remain keyboard reachable.

## Forms and buttons

- labels remain visible whenever the field is not self-evident;
- technical JSON/IDs keep monospace where useful;
- primary action is restrained teal, not oversized;
- danger only for destructive metadata actions;
- disabled physical actions always include textual reason;
- no mutation is auto-retried after conflict.

## Badges and status

Status color is always paired with text.
Human-facing status words are translated; machine codes in payloads remain unchanged.
Semantic statuses keep consistent meaning across both locales.

## Tabs

Tabs are compact, horizontally scrollable when needed, with selected state indicated by text color + bottom rule. Both languages use the same DOM and routing model.

## Empty / loading / error states

- Empty: explain whether the state is normal first-use, filtered no-match, or abnormal.
- Loading: preserve geometry; no decorative animation beyond restrained skeleton feedback.
- Error: scoped, actionable, preserve already-loaded truth where possible.
- Conflict: explicitly state server rejection, authoritative refresh, and no automatic retry.
- Degraded truth: persistent banner; reads remain available; dependent mutations disabled.

## Focus and keyboard

Use a 2 px high-contrast outline with offset rather than removing native affordance without replacement.
Maintain:
- Ctrl/Cmd+K search;
- / search when not editing;
- Escape closes transient mobile navigation and blurs editor controls;
- tabs, tables, controls and dialogs are keyboard reachable.

Touch targets are >=44 x 44 CSS px at mobile breakpoints.

## Responsive behavior

Required verification widths: 375 / 768 / 1024 / 1440 in both zh-CN and en.

- >=1200: full sidebar and wide tables.
- 900–1199: full labelled sidebar unless content pressure proves otherwise.
- 700–899: compact but recognizable navigation; never first-letter-only destinations.
- <700: off-canvas navigation; topbar becomes a deliberate grid so menu, search, language and health do not collide.
- No body-level horizontal overflow.
- Technical tables may scroll within `.table-wrap`.

## Motion

120–180 ms, quiet and purposeful.
Only state/navigation/feedback motion.
No bounce, parallax, pulse decoration, or animated charts.
Honor `prefers-reduced-motion`.

## Internationalization

Locales: `zh-CN` and `en`.
Default: `zh-CN`.
Persistence: `localStorage["scp.locale"]`.
Visible persistent control: 中文 / EN in the top chrome.
One frontend, one routing/state model, one centralized translation resource.

Translate:
- navigation;
- headings/descriptions;
- button labels;
- form labels/placeholders;
- empty/loading/error/help text;
- human-facing statuses;
- aria-label/title where human-facing;
- breadcrumbs for known route labels.

Do NOT translate:
- skill_id / run_id / workflow_id;
- hashes/digests;
- filesystem paths;
- API names;
- code blocks / SKILL.md bodies;
- raw JSON machine payloads / status machine codes where shown as technical data.

Changing locale must update `document.documentElement.lang`, update static chrome, rerender the current route without changing hash/deep-link state, and survive reload.

## Accessibility

Target WCAG 2.1 AA:
- normal text contrast >=4.5:1;
- UI/focus/non-text contrast >=3:1;
- visible focus;
- logical keyboard order;
- named controls;
- semantic tables/landmarks;
- mobile touch targets >=44 px;
- no information conveyed by color alone;
- 200% zoom must not hide persistent controls.

## Desktop branding

Source of truth: editable SVG under `web/manager/assets/`.
Windows shortcut: multi-resolution ICO derived from that mark, sizes 16/24/32/48/64/128/256 where tooling supports them.

Mark construction:
- open square/plane boundary;
- three control nodes on a routed line;
- asymmetric gap/open edge to imply flow rather than enclosure;
- graphite + teal only;
- legible monochrome silhouette at 16 px;
- no text inside the icon.

Installer points directly to project-owned ICO and validates the asset exists before saving the shortcut. Re-running installer must preserve exactly one WAC prestart integration block and refresh the same shortcut path.

## Architecture boundary

Web Manager remains semi-independent:
Desktop WAC lifecycle → existing gateway/MCP chain → machine-local prestart → ensure Manager.
Browser UI → 127.0.0.1:8955 → skill-control-plane/web/manager → typed local API.

No WAC frontend merge, second scanner, second identity model, second DB, workflow engine, generic filesystem browser, generic shell endpoint, mass relocation or physical apply controls.

## Acceptance boundary

M09 engineering may complete without a Windows reboot.
`USER_MANUAL_REBOOT_ACCEPTANCE = PENDING_USER`.
The user owns the final literal reboot acceptance; M09 must not claim it passed.
