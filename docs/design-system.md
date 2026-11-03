# Design system and brand

## 1. Audit of the previous light theme

| Area | What was wrong |
|---|---|
| Palette | Cool violet and electric-blue gradients on white: the default look of AI SaaS. No warmth, no material. |
| Surfaces | Rounded translucent "glass" cards everywhere, nested cards inside cards, glows. Every section had the same weight. |
| Hierarchy | Page titles, panel titles and metrics sat at similar sizes; boxed stat tiles competed with content. |
| Layout | Every landing section used the same centred heading plus card grid. No imagery, no rhythm, no framing. |
| Theming | One palette hard-coded in about 60 places (SVG fills, chart colours, editor theme). No theme switch. |
| Brand | A text wordmark with a generic gradient chevron. |

## 2. Reference: what was taken from Balkon, and what was not

The Balkon template (architecture studio) was studied for its principles, not its assets:

- a framed page: a slim fixed left rail with a rotated label, a quiet top bar;
- tiny tracked uppercase navigation and annotation labels;
- a bold geometric display face with tight leading;
- black square buttons, short heavy bars as section markers, hairline rules;
- full-bleed photography in split-screen and overlapping band compositions; generous whitespace.

Nothing was copied: no images, icons, logo, text or code. Balkon's photography is replaced by **original renders** (below), its triangular "A" logo has no counterpart here, and the colour, type and component system are new.

## 3. Brand: Axiomera

| Candidate | Public usage found | Domain (.com) | Notes | Verdict |
|---|---|---|---|---|
| Synora | Synora Inc. (Crunchbase) and several "Syn…" software firms | registered 2008 | Existing company with the exact name | Rejected |
| Aurestr | none | no registration record | Hard to pronounce ("-str" ending); reads as a spelling of the old name | Rejected |
| Traverta | none (adjacent: Traverse accounting software) | registered Dec 2025 | Nice "travertine + traverse" idea; recent unknown registrant | Reserve |
| Tectora | none exact; Tectura (Microsoft partner) | — | Confusion risk with Tectura | Rejected |
| **Axiomera** | none in software | registered 2024 (.io 2026) | US filings only in class 10 (massage chairs) and class 21 (make-up sponges) | **Selected** |

**Why Axiomera:** *axiom + era*. The product's defining property is that consequential decisions follow explicit, auditable rules (deterministic classification, approval policies, scope hashes) rather than model discretion; "an era of axioms" says that. It is pronounceable in English and German (ak-see-oh-MEH-rah), distinctive, does not end in "AI" or "Pilot", and "axis" gives it an architectural reading. **This is a provisional name**: the checks above are basic web, RDAP and third-party trademark-summary lookups, not legal clearance, and a commercial launch would need its own domain and a proper trademark search.

**Mark:** a portal (two columns under an overhanging lintel) bisected by a single axis, with a bronze square where decisions are taken: the gate every consequential action passes through. Drawn on a 32-unit grid in `currentColor` plus the accent token, so one SVG serves light, dark, the sidebar, the favicon (`public/icon.svg`, legible at 16 px) and the README (`docs/media/axiomera-wordmark-*.svg`). Wordmark: Manrope 700, uppercase, +0.24 em tracking.

**What keeps the old name:** `ORKESTR_*` environment variables, `X-Orkestr-*` webhook headers, Docker service names, database names, demo e-mail addresses and historical records. Renaming them would break existing deployments and n8n integrations for no user-visible gain.

## 4. Tokens

All colours are CSS variables holding RGB channels (`--accent: 130 86 46`), exposed to Tailwind as semantic names, so `/<alpha>` modifiers work and components never mention a theme.

| Token | Role | Light ("Travertine") | Dark (original night palette) |
|---|---|---|---|
| `page` | canvas | `#F4F0E8` ivory | `#070A14` |
| `surface` | sheets, tables, dialogs | `#FBF9F4` | `#0E1426` |
| `raised` | stone: hover, selection, insets | `#ECE6DB` | `#131B33` |
| `ink` / `-soft` / `-mute` / `-faint` | text ramp | `#181613` → `#6C645A` | `#EEF1FF` → `#7C84AA` |
| `accent` | bronze / violet | `#82562E` | `#8B7CFF` |
| `signal` | live / active | `#A24E2E` terracotta | `#38E1F0` |
| `ok` `warn` `bad` `info` | status | sage, ochre, brick, slate | original |
| `primary` | primary button | rich black | violet |
| `inverse` | emphasis band | charcoal `#1E1B17` | `#151E3A` |
| `line` | hairlines | ink at 13 % | indigo at 16 % |
| `chart-1…4` | categorical series | `#B8622E #2A78D6 #1A9E70 #6250D6` | `#8B7CFF #1FA3B5 #3D7BFF #D26A92` |

Both chart palettes pass the dataviz validator for their own surface (lightness band, chroma floor, colour-blind separation, normal-vision separation, ≥3:1 against the surface). Single-series charts use slot 1 only.

### Measured text contrast (WCAG 2.x ratio; AA needs 4.5)

| Token | Light on page | Light on surface | Dark on page | Dark on surface |
|---|---|---|---|---|
| `ink` | 15.9 | 17.2 | 17.6 | 16.3 |
| `ink-soft` | 10.7 | 11.5 | 10.8 | 10.0 |
| `ink-mute` | 5.9 | 6.4 | 6.6 | 6.1 |
| `ink-faint` | 5.1 | 5.5 | 5.4 | 5.0 |
| `accent` | 5.6 | 6.0 | 6.0 | 5.6 |
| `signal` | 5.0 | 5.4 | 12.4 | 11.5 |
| `info` | 6.2 | 6.7 | 7.7 | 7.1 |
| `ok` | 5.8 | 6.2 | 10.3 | 9.5 |
| `warn` | 5.5 | 6.0 | 11.8 | 11.0 |
| `bad` | 5.7 | 6.2 | 7.3 | 6.8 |
| `on-primary` on `primary` | 17.2 | | 5.5 | |
| `on-inverse` on `inverse` | 15.1 | | 14.6 | |

## 5. Type, space, shape

- **Manrope** (variable) for interface and display; display weights 700 with −0.035 em tracking and 0.98 leading.
- **Instrument Serif italic** for editorial accents only ("*axioms.*", "*when*", the closing line).
- **IBM Plex Mono**, 11 px uppercase with 0.16 em tracking, for annotation labels: section indices, table heads, metadata. It does the job of the lettering on an architectural drawing.
- Corners: 2 px everywhere (`--radius-panel`, `--radius-control`). Hairline borders instead of shadows; one lift shadow for dialogs and screenshots.
- Rhythm: page sections 64 px apart in the app and 112–160 px on the landing page; 1400 px maximum content width on the landing page.

## 6. Components

`components/ui/primitives.tsx` holds the shared pieces: `PageHeader` (numbered section label from `lib/nav.ts`, display title, standfirst, closing rule), `DetailHeader` (numbered breadcrumb for single records), `Section` (lettered section without a box), `Stat` (metric in a hairline strip), `Badge`/`Status` (mono, square), `Tabs` (ink underline that draws in), `Panel`, `Modal`, `Field`, `Button` (primary = solid black / violet), `More` (arrow link). Screens are composed from these; nothing re-implements colours.

Screen-specific compositions: the command center's charcoal **decision band**; the workflow index as a lettered schedule; the agent **roster table**; the RFP **title block** (issuer, reference and key dates as a ruled grid, as on a drawing sheet); React Flow nodes as drawing-sheet cards with a state bar and an offset ink outline when selected.

## 7. Imagery

Five original renders of architectural study models (stepped cantilevers, a fin facade, a colonnade, a field of blocks, a dusk cantilever) made with three.js and ambient occlusion in headless Chromium, graded warm with fine grain. Night variants are graded to the dark palette. Source: `frontend/scripts/render-imagery.html` and `render-imagery.py`. Product screenshots on the landing page are real captures of the app in each theme (`frontend/scripts/product-shots.py`).

## 8. Motion

Restrained and optional: headline lines rise from a mask, sections fade up once on scroll, the hero picture drifts with slight parallax, tab underlines and active-nav bars draw in, dialogs rise in, the workflow trace advances step by step, and theme switches cross-fade colours only (no layout properties, so nothing shifts). Everything uses transforms and opacity, and `prefers-reduced-motion` turns it off.

## 9. Theme switching

`data-theme` on `<html>`, set by an inline script before first paint from `localStorage` (light by default). The toggle sits in the landing header, the login page, the app sidebar and the mobile top bar. Charts (ECharts), the Monaco editors and the React Flow canvas subscribe to theme changes. Verified by the E2E test UX-03: switching moves the page heading by 0 px and persists across navigation and reload.
