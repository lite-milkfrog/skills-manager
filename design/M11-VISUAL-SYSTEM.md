# SCP-M11 Visual System and Component Redesign

STABLE_CORE_VERSION = LE-STABLE-2026-09-22.2
PROGRAM_ID = SKILL-CONTROL-PLANE-UNIFIED-LOCAL-20260922
CURRENT_STAGE = SCP-M11-VISUAL-SYSTEM-AND-COMPONENT-REDESIGN
NEXT_STAGE = SCP-M12-FULL-BROWSER-USABILITY-QA
AFTER_NEXT_STAGE = SCP-M08-DESKTOP-ONE-CLICK-AND-REBOOT-FINAL-INTEGRATION

## 1. Design truth

M10 fixed the product hierarchy, not the visual language. The accepted M10 screenshot proves the remaining defect: the page is still a dark engineering/admin console with border-heavy panels, repeated same-weight cards, cramped hierarchy and technical chrome that visually competes with beginner content.

M11 keeps M10's beginner-first IA and M09's one-frontend/i18n/a11y/branding foundation, while replacing M09's dark developer-first presentation.

Target audience: a capable user who knows what they want AI to do but may not know Skill Control Plane internals. The UI should feel calm, legible, local and trustworthy. It should not feel like a terminal, enterprise admin suite, marketing landing page or toy dashboard.

## 2. Personality and anti-patterns

Personality:
- clear before clever;
- calm, warm-neutral and modern;
- practical rather than decorative;
- approachable without hiding real technical depth;
- recognizably Skill Control Plane through its routed-node mark and blue-green accent.

Avoid:
- default dark mode as the beginner surface;
- generic purple/blue AI gradients, glow, glassmorphism or sparkles;
- wrapping every section in a bordered card;
- equal-weight card grids for every content type;
- decorative metric tiles and hero KPI templates;
- monospace as a generic technical aesthetic;
- huge radii, floating glass panels or excessive drop shadows;
- emoji as the primary icon system;
- raw IDs, source authority, SQLite/parity/ports in the beginner reading path.

## 3. Theme decision

Default = light.

Evidence:
- the M10 screenshot's dark graphite shell preserves the old admin-tool mental model;
- beginner tasks are primarily scanning, reading, searching and choosing, where a high-lightness canvas reduces perceived density;
- the existing teal routed-node brand works as a rare accent on light tinted neutrals without becoming generic AI neon.

Dark mode is not implemented in M11. It can be a later theme, not a hidden second visual system.

## 4. Core tokens

### Color

Use perceptually tinted neutrals; avoid pure black/white.

- canvas: oklch(98.2% 0.008 205)
- canvas-muted: oklch(96.4% 0.010 205)
- surface: oklch(99.4% 0.004 205)
- surface-raised: oklch(100% 0 0)
- ink-strong: oklch(24% 0.024 220)
- ink: oklch(32% 0.022 220)
- ink-muted: oklch(49% 0.020 220)
- border: oklch(88% 0.014 210)
- border-strong: oklch(80% 0.020 210)
- accent: oklch(50% 0.105 188)
- accent-strong: oklch(42% 0.105 188)
- accent-soft: oklch(94% 0.035 188)
- accent-soft-strong: oklch(89% 0.050 188)
- success: oklch(48% 0.105 155)
- success-soft: oklch(94% 0.035 155)
- warning: oklch(58% 0.110 80)
- warning-soft: oklch(95% 0.045 80)
- danger: oklch(52% 0.125 25)
- danger-soft: oklch(95% 0.035 25)
- focus: oklch(55% 0.120 200)

Semantic text/background pairs must meet WCAG 2.1 AA. Status is never conveyed by color alone.

### Typography

UI stack:
"Segoe UI Variable", "Segoe UI", "Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC", system-ui, sans-serif.

Technical stack:
"Cascadia Mono", "JetBrains Mono", Consolas, "Microsoft YaHei UI", monospace.

Roles:
- display: 2.25rem / 1.12 / 700 desktop; 1.8rem mobile;
- page title: 1.75rem / 1.2 / 700;
- section title: 1.25rem / 1.3 / 700;
- card title: 1rem / 1.35 / 650;
- body: 1rem / 1.58 / 400;
- secondary: 0.875rem / 1.5 / 400;
- caption/metadata: 0.78rem / 1.45 / 500.

Technical IDs may use monospace. Ordinary product copy may not.

### Spacing

Base scale: 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 56 / 72.

- related controls: 8-12;
- card internals: 12-16;
- section heading to content: 16-20;
- major section separation: 40-56;
- page breathing room: 32-56.

Avoid equal spacing everywhere. Rhythm should communicate hierarchy.

### Geometry, borders and elevation

- control radius: 10px;
- card/panel radius: 14px;
- compact chips/status may use capsule geometry;
- 1px neutral borders only on bounded interactive surfaces;
- open page sections prefer spacing/dividers over containers;
- shadow-sm: 0 1px 2px rgb(20 40 45 / 0.05);
- shadow-md: 0 8px 24px rgb(20 40 45 / 0.08), for transient/raised use only;
- no nested-card shadows.

Focus = 2px visible outline with 2px offset.

## 5. Shell and navigation

Desktop sidebar:
- 248px, light tinted surface, subtle right divider;
- project-owned mark + product name + short Skill-hub descriptor;
- coherent line SVG icons + labels;
- active item uses accent-soft background, accent-strong text and a small edge marker;
- bottom status is compact and quiet, not a monitoring dashboard.

Topbar:
- content-aligned, 64px minimum height;
- global search is the main utility control and can grow;
- locale toggle is compact but fully labelled;
- health/status is secondary;
- mobile uses a deliberate two-row/grid arrangement rather than shrinking controls into collisions.

## 6. Icon system

Use a project-owned inline SVG icon set with shared 20/24px optical boxes:
- 1.75 stroke;
- round linecap/linejoin;
- currentColor;
- no emoji or multicolor pictograms.

Icons never replace text labels.

## 7. Homepage

Hero:
- open composition on the page canvas, not a KPI/admin card;
- small Skill Control Plane eyebrow;
- headline asks what the user wants AI to do;
- one concise explanation, max 62ch;
- prominent search field with search icon and task-oriented action button;
- system availability is quiet inline metadata below.

Use-case discovery:
- visual center of the page;
- 12 compact icon + title + one-line explanation items;
- a small finite set of soft accent tints differentiates groups;
- hover/focus refines border/background instead of large transforms;
- 3-4 columns desktop, one column mobile.

Quick entries:
- three larger action surfaces with distinct hierarchy;
- task-oriented title, short explanation and text-link action;
- deliberately different from the use-case card template.

Recent activity:
- timeline/list, not a table;
- human task first;
- status and secondary metadata compact;
- run_id appears only in detail/advanced context.

## 8. Skill Library

Header:
- title + plain-language description;
- task/use-case filter first;
- search and mode switch remain obvious;
- Advanced mode is visibly secondary.

Default Skill card:
- name + one-sentence purpose;
- max two lines of description;
- use-case chips;
- optional N-version secondary text;
- one clear View details affordance;
- no source path/authority/variant table by default.

Advanced table keeps dense inspectability and internal horizontal scrolling.

## 9. Skill detail

Beginner detail opens with title, human description, What it does content, use-case context and relevant workflow relation.

Tabs/sections:
- What it does;
- Categories & tags;
- Technical details.

Technical details are not selected by default and own source class, authority tier, variant IDs, hashes, path, validation, raw body and machine truth. Long body/code uses a bounded technical surface with monospace only inside the content.

## 10. Automations

List:
- explain “把多个技能按步骤串起来” / its English equivalent directly under the title;
- workflow name and human purpose first;
- version/stage counts second;
- workflow_id is not the scanning anchor.

Detail/editor:
- ordered steps read top-to-bottom with numbered markers and connector line;
- gates/retry/fallback remain in a clearly labelled advanced section;
- editor fields keep visible labels and typed safety semantics;
- immutable-version behavior remains unchanged.

## 11. Activity

List:
- human task/summary first;
- clear status text + icon;
- time/workflow relation secondary;
- run_id/audit/evidence secondary.

Detail:
- top summary answers what ran, current result and where it stopped;
- stage timeline/evidence is the main body;
- raw audit/IDs/JSON remain advanced.

## 12. Advanced Tools

Advanced is intentionally denser but uses the same tokens.

Hub groups Health, Sources, Organization, Contexts and Deployments as concise icon + description + destination surfaces, not a second dashboard.

Technical pages may use compact tables but must not return to the old black console aesthetic. Deployment remains safety-first and dry-run-only.

## 13. Responsive behavior

M12 owns exhaustive verification; M11 implements:
- >=1200: 248px sidebar + wide content canvas up to about 1440px;
- 900-1199: labelled sidebar; content grids reduce columns;
- 700-899: compact labelled navigation or off-canvas when pressure requires;
- <700: off-canvas nav, 16px page padding, stacked hero/search/actions;
- 375px: no body horizontal overflow; controls >=44px touch targets;
- technical tables scroll inside their own wrapper;
- flex/grid children use min-width: 0 and long text wraps/clamps;
- never hide a canonical action solely to make layout fit.

## 14. Bilingual behavior

One frontend only. Locale remains localStorage["scp.locale"].

Every user-facing M10/M11 string lives in the centralized locale resource or derives from localized helpers. app.js must not contain presentation-specific Chinese literals except deliberate locale metadata/test fixtures.

zh-CN and en share structure and routes. Layout budgets for text expansion:
- controls size to content;
- headings wrap naturally;
- cards avoid fixed text widths;
- nav labels never collapse to initials;
- CJK uses normal tracking; English micro-labels may use slight tracking.

Technical IDs, code, hashes, paths and raw SKILL.md remain untranslated.

## 15. Motion and resilience

- 140-180ms ease-out transitions for color/border/opacity;
- no bounce, pulse, parallax or decorative animation;
- hover feedback never replaces focus;
- prefers-reduced-motion reduces transitions to near-zero;
- loading states preserve layout geometry;
- long text clamps/wraps safely;
- errors explain recovery without hiding already-loaded truth.

## 16. M11 visual acceptance

M11 is acceptable only when real browser evidence shows:
- the default surface no longer reads as the old dark admin console;
- hierarchy survives the squint test: hero/search -> use cases -> quick actions -> recent activity;
- cards are not the only grouping primitive;
- homepage, Skill Library, Skill detail, Advanced, Automations and Activity share one system;
- zh-CN and en fit without clipping or fallback Chinese copy;
- focus, contrast, touch targets and 375px overflow remain sound;
- at least one screenshot-driven fix iteration occurs after the first redesigned render if defects are visible.

M12 still owns the exhaustive 375/768/1024/1440 x zh/en matrix, classification sampling, accessibility audit and final browser regression.

## 17. Beginner capability model: Skills, Workflows, Tools

The beginner mental model is three layers:

1. **Skills = what the Agent knows how to do.**
2. **Workflows = how capabilities are arranged to finish a larger job.**
3. **Tools / MCP = what the Agent can actually operate: code, browser, desktop, services and other systems.**

Do not ask beginners to learn MCP, source authority or binding semantics before they can use
the product. Those remain visible in progressive disclosure, while the primary product language
stays task-oriented.

### Skill depth is not flat

The UI must not assume every `skill_id` represents one atomic action.

Derived presentation types:

- **Single Skill** — one focused capability.
- **Composite Skill** — contains a multi-step method or coordinates additional Skills.
- **Router Skill** — chooses an internal route / child Skill based on the current task.
- **Agent & tool Skill** — primarily defines tool/MCP routing, recovery, validation or an execution contract.

These are explanatory, derived labels. They do not change M01 canonical identity or authority.
List views may infer a likely type from name/description/path. Skill detail should improve the
classification by loading the selected canonical `SKILL.md` body on demand.

### Recursive Skill semantics

A Skill is an execution entry point, not a flat prompt token.

When an Agent is told to use a Skill:

1. open and read the selected canonical `SKILL.md` in full;
2. follow the Skill's own routing / workflow rules;
3. when it references `routes.md`, `references/`, `scripts/`, `assets/`,
   `EVOLUTION.md`, another Skill, or an MCP/tool workflow, load the material required by
   that route recursively;
4. preserve a composite/router Skill's internal workflow unless the outer Workflow explicitly
   pins or overrides an internal step;
5. discover the MCP/tools required by the loaded Skill and follow that Skill's documented
   recovery/fallback rules if a direct tool is unavailable.

The generated Agent prompt must carry this execution contract. It must never reduce a composite
Skill to “call this skill_id and move on”.

### Workflow visual model

The beginner editor is:

`goal -> ordered steps -> main Skill per step -> generated Agent prompt`

Each step may contain a Single Skill or an entire Composite/Router Skill. The UI shows the detected
capability type and makes it explicit that nested internal workflows remain intact.

Advanced binding type, conditions, retry/loop limits, fallbacks and JSON gates stay available inside
step-level progressive disclosure. They must not dominate the default editor.

The generated prompt is a first-class output, not an implementation detail. A user should be able
to build a workflow and copy one self-contained prompt that another Agent can follow.

### Location browsing

Skill discovery has two independent beginner views:

- **By use case** — what the user wants to accomplish.
- **By location** — where the Skill collection lives on the local machine.

Location browsing is presentation over existing path truth. It must not relocate files or change
source authority. Cards may show both the detected use case and detected location so duplicate or
historical Skill collections are understandable without exposing raw paths first.
