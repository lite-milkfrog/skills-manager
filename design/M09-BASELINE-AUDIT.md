# M09 Baseline UI Audit

PROGRAM_ID = SKILL-CONTROL-PLANE-UNIFIED-LOCAL-20260922

## Evidence basis

- Existing M05 product / IA / interaction / visual contracts.
- User-authored Obsidian Product UI workflow and skill-selection rules.
- Live Manager render at 127.0.0.1:8955.
- Current source in index.html / app.js / styles.css.
- Current registry Skill bodies, not historical inventory assumptions.

## What already works

The current UI is substantially aligned with the intended developer/admin character. It uses compact tables, low radii, graphite surfaces, restrained teal, clear semantic status colors, visible risk treatment, lazy body loading, deep links, mobile off-canvas navigation, keyboard shortcuts and reduced-motion handling. There is no reason to replace the IA or visual system wholesale.

## Actionable findings

P1
- No i18n architecture: html starts at en; no zh-CN switch, persistence, translated accessible labels or Chinese layout verification.
- Desktop shortcut uses generic SHELL32.dll,220 rather than project-owned branding.

P2
- Tablet collapsed nav communicates routes as first letters, which is ambiguous and visually weak.
- CJK font/line-height and label behavior are not specified.
- Mobile topbar has four competing responsibilities once locale control is added; needs explicit narrow layout.
- Raw breadcrumb route segments are not human/localized navigation labels.
- Brand tile is text-only “SCP” and is not shared with desktop identity.
- Focus style uses box-shadow only after globally suppressing outlines; move to an explicit outline contract.

P3
- Some semantic badges use full capsules; keep only where compact grouping benefits.
- Loading shimmer can be quieter.
- A few nested cards in Run legal-actions are acceptable structurally but should not gain more decoration.

## AI-slop audit

PASS / preserve:
- no purple-blue gratuitous gradient;
- no neon;
- no glassmorphism;
- no hero-template marketing layout;
- no excessive whitespace;
- no oversized fake-premium typography;
- no excessive large-radius cards.

The design task is therefore normalization and hardening, not restyling for novelty.

## Console note

The shared Edge/Playwright profile reports errors from browser extensions and previously visited Tencent Cloud telemetry endpoints. Those are not Manager-origin application errors. M09 browser QA must separately check requests/console attributable to 127.0.0.1:8955 and record extension noise honestly.
