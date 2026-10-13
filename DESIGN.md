---
name: KGCR Dashboard
description: A numbered catalog sheet on matte black, one white hairline plot per view, for reviewing AWS configurations live.
colors:
  ground: "#0b0b0b"
  sleeve: "#121211"
  raised: "#191918"
  ink: "#efede6"
  ink-2: "#b0aea7"
  ink-3: "#8a8882"
  hair: "rgba(239, 237, 230, 0.15)"
  hair-2: "rgba(239, 237, 230, 0.32)"
  advisory: "#8d8c87"
  medium: "#2f6fd6"
  high: "#e8b622"
  critical: "#e03a2f"
  critical-ink: "#ff6a5c"
typography:
  display:
    fontFamily: "Archivo, ui-sans-serif, system-ui, sans-serif"
    fontSize: "64px"
    fontWeight: 500
    lineHeight: 0.85
    letterSpacing: "-0.025em"
    fontVariation: "'wdth' 125"
  headline:
    fontFamily: "Archivo, ui-sans-serif, system-ui, sans-serif"
    fontSize: "22px"
    fontWeight: 500
    lineHeight: 1.3
    letterSpacing: "-0.005em"
  title:
    fontFamily: "Archivo, ui-sans-serif, system-ui, sans-serif"
    fontSize: "16px"
    fontWeight: 500
    lineHeight: 1.55
  body:
    fontFamily: "Archivo, ui-sans-serif, system-ui, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.55
  label:
    fontFamily: "Archivo, ui-sans-serif, system-ui, sans-serif"
    fontSize: "12.5px"
    fontWeight: 400
    lineHeight: 1.55
  mono:
    fontFamily: "Martian Mono, ui-monospace, Cascadia Mono, monospace"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.55
    fontVariation: "'wdth' 90"
rounded:
  square: "0px"
spacing:
  inset-tight: "12px"
  inset: "16px"
  gap: "32px"
  page: "48px"
  page-mobile: "16px"
components:
  button:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.square}"
    height: "44px"
    padding: "0 0 0 16px"
  button-primary-tab:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.ground}"
    rounded: "{rounded.square}"
    width: "44px"
  button-spend-tab:
    backgroundColor: "{colors.high}"
    textColor: "{colors.ground}"
    rounded: "{rounded.square}"
    width: "44px"
  field-input:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.square}"
    height: "44px"
    padding: "0 12px"
---

# Design System: KGCR Dashboard

## Overview

**Creative North Star: "The Catalog Sheet"**

The dashboard reads as a numbered catalog sheet printed on matte black. Views, runs, jobs, reports and controls carry catalog numbers (KG 010, KG 020, KG 026), set in Archivo at 125 percent width or in Martian Mono. One white hairline plot owns each view; everything else is hairline rules, warm-white text and square controls. The product refuses the sidebar-plus-KPI-card admin template: there are no metric cards, no filled panels at rest, and no decorative gradients.

Color is near-monochrome. Warm white ink (#efede6) carries structure and selection on a black ground. Four severity colors carry all chromatic meaning. Depth comes from hairlines and two graphite steps, never from shadow. The cover is sparse and the admin side is dense, under the same rules.

The build is dark only (`color-scheme: dark`). The sidecar's tonal ramps for the accent colors are synthesized for the live panel; they are not taken from the build.

**Key Characteristics:**
- One white hairline plot per view, drawn on load.
- Square 0px corners on every control and surface.
- Catalog numbers and Martian Mono identifiers instead of decorative labels.
- Hairline structure; selection is a double-weight white line.
- Severity colors reserved for meaning: grey advisory, blue medium, yellow high or spend, red critical or fault.
- Flat at rest; one soft shadow exists, on toasts.

## Colors

Near-monochrome warm neutrals on matte black, with one ink color for structure and a severity scale for meaning.

### Primary
- **Plot White** (#efede6): The only foreground accent. Plot lines, the primary button tab, focus outlines, selection lines, the wordmark and the cover plot. Reserved for the element that leads the view.

### Secondary (severity and spend)
- **Signal Yellow** (#e8b622): High severity, contested loop status, running jobs, and anything that spends money or calls a live service: the spend tab, the live-call checkbox, budget cells, the confirm panel.
- **Fault Red** (#e03a2f): Critical severity and failed states: failed gate figures, error notices, error toasts, critical plot ridges.
- **Fault Red Text** (#ff6a5c): Red text on the black ground for failed states and danger labels. Fault Red is used for fills and borders; this lighter variant is used for text, where Fault Red sits at the AA edge.
- **Medium Blue** (#2f6fd6): Medium severity only.
- **Advisory Grey** (#8d8c87): Advisory severity, the first block of the five-block severity code.

### Neutral
- **Matte Black** (#0b0b0b): Page and rail ground.
- **Sleeve Graphite** (#121211): Hover and selected rows, log and JSON panels, the sleeve behind a focused finding.
- **Raised Graphite** (#191918): Toast surface and the skeleton shimmer.
- **Muted Ink** (#b0aea7): Descriptions, ledes and secondary text.
- **Faint Ink** (#8a8882): Labels, metadata, table headers, disabled text.
- **Hairline** (rgba(239, 237, 230, 0.15)): Rules, row separators, plot grid.
- **Strong Hairline** (rgba(239, 237, 230, 0.32)): Control borders and tab dividers.

Build-only literals that are not tokens: #2a2a28 (unlit readout cells), #252523 (bar track), #f6f6f2 (figure ground behind the raster architecture diagrams).

### Named Rules
**The Red Is Fault Rule.** Red marks critical severity, failed states and destructive actions (cancelling a job) only. It does not mark emphasis, selection or ordinary actions.

**The Yellow Is Spend Rule.** Yellow marks high severity, contested status, in-flight runs and anything that spends budget or calls a live service.

## Typography

**Display Font:** Archivo (with ui-sans-serif, system-ui, sans-serif), variable width 62 to 125, served locally under the OFL.
**Body Font:** Archivo at default width.
**Label/Mono Font:** Martian Mono (with ui-monospace, Cascadia Mono, monospace), variable width 75 to 112.5, used at 90 percent width.

**Character:** A grotesque at two widths. Expanded width sets the catalog numbers and the wordmark; regular width carries reading text; the monospace face sets every identifier, hash, figure and log, so numbers stay aligned and legible.

### Hierarchy
- **Display** (500, 64px at 125 percent width, 0.85 line-height, -0.025em tracking): Catalog numbers on view heads. The cover wordmark runs from 72px to 132px at 125 percent width, 0.82 line-height.
- **Headline** (500, 22px, 1.3 line-height on the cover title): View titles and the cover title.
- **Title** (500, 16px): Block headings. Finding titles run at 15px.
- **Body** (400, 15px, 1.55): Page default. Rows and fields use 14px; notes use 13px to 13.5px. Ledes cap at 64ch, rendered explanations at 92ch.
- **Label** (400, 12.5px to 13px, Faint Ink): Table headers, field labels, metadata. No tracking, no uppercase.
- **Mono** (Martian Mono at 0.86em of the surrounding text, 12px to 13.5px in logs and renderings, tabular numerals): Identifiers, hashes, counts, claims, logs and explanations.

### Named Rules
**The Expanded Number Rule.** Expanded width (125 percent) is reserved for catalog numbers, the wordmark, the rail brand and gate figures.

**The Mono Identifier Rule.** Identifiers, run hashes, counts, claims and logs are set in Martian Mono with tabular numerals, never in the sans.

## Layout

- **Shell:** a 248px sticky rail (`--rail`) beside a fluid main with 40px 48px 96px padding, capped at 1480px.
- **Cover:** two columns (1fr and 1.05fr). The plot owns the right column, centered and capped at 74vh. The left column pads 56px with a 40px gap; the foot row spans full width.
- **View heads:** bottom-aligned flex row, 28px bottom padding and 36px margin before content, closed by a hairline.
- **Run form:** form plus a 320px side column, sticky at 24px from the top. Explanations use a 300px side column. Sleeves pair a plot with a 300px title block.
- **Gates:** four stage cells share hairline borders instead of gaps.
- **Responsive:** at 1180px multi-column layouts collapse to one column and the side column stops sticking. At 900px the rail becomes a masked, horizontally scrolling top strip, the cover stacks, and sleeves collapse. At 600px roster and stages go to one column and the doors drop their id column.
- **Spacing rhythm:** no complete scale is used. Recurring values: 4px to 8px inside clusters, 12px to 16px inside controls and cells, 18px to 24px inside bordered panels, 28px to 40px between blocks, 48px between sections. Shared tokens are the 32px gap and the 48px page inset (16px on mobile).
- **Density:** the admin side is dense, with one-line rows and tabular numbers. The cover keeps 48px to 56px of air.

### Named Rules
**The Single Plot Rule.** Each view is built around one white hairline plot, and the plot leads the view.

## Elevation & Depth

Flat. Depth comes from three graphite steps (Matte Black, Sleeve Graphite, Raised Graphite) and 1px hairlines. Selection and focus are inset lines, not shadows. The build has one shadow, on the toast, the only floating surface.

### Shadow Vocabulary
- **Overlay lift** (`box-shadow: 0 12px 32px rgba(0, 0, 0, 0.5)`): Toast notifications only.
- **Selection line** (`box-shadow: inset 0 0 0 2px #efede6`): Current page, pressed segment, selected row, checked cell and focused finding. Listed because it is the build's only state device built on box-shadow; it is a line, not depth.

### Named Rules
**The Flat Plane Rule.** Surfaces sit flat at rest. Only transient overlays lift.

## Shapes

Every surface and control has 0px corners. Strokes are 1px hairlines in two strengths. Curves belong to the plot: arcs, ridges and the polar core ring. Controls are square outlines with a 44px right-edge tab divided by a hairline. The tab carries the action icon and fills with Plot White (primary), Signal Yellow (spend), or takes Fault Red Text (danger). Severity marks are flat rectangles: 22 by 10px blocks, 14px in findings, 18px in strips.

## Components

### Buttons
- **Shape:** square, 44px minimum height, 1px Strong Hairline border, label inset 16px from the left, 44px tab on the right.
- **Primary:** the tab fills Plot White with a Matte Black icon. The label stays Plot White on a transparent ground.
- **Spend:** the tab fills Signal Yellow. Reserved for actions that spend budget or call live services.
- **Danger:** the tab takes Fault Red Text.
- **Hover / Focus:** the border shifts to Plot White; the tab icon nudges 2px right over 0.25s. Focus draws a 2px Plot White outline, offset 3px.
- **Active / Disabled:** press scales to 98.5 percent. Disabled uses a dashed border, Faint Ink text and no transform.

### Fields
- **Style:** transparent, 1px Strong Hairline, 0px radius, 44px tall, 12px horizontal padding. Identifiers and numbers in Martian Mono.
- **Focus:** border shifts to Plot White with an inset 1px Plot White line. No glow.
- **Error:** border becomes Fault Red. **Disabled:** dashed border.
- **Checkbox:** 18px square; checked fill is Signal Yellow with a Matte Black mark. Used on the live-call switch, which spends budget.

### Severity and State
- **Severity blocks:** Advisory Grey, Medium Blue, Signal Yellow, Fault Red, in that order on the cover legend, with Plot White as the closing block.
- **State markers:** 10px squares. Pass, done, converged and ok: Plot White fill. Failed: Fault Red fill with Fault Red Text. Contested, running and live: Signal Yellow. Queued, cancelled, disabled and planned: hollow 1px square.

### Findings (signature)
- **Shape:** rows divided by Hairline rules; a 30px severity column, a title with its evidence path, and a 220px aside.
- **Focus:** a focused or pressed finding takes the Sleeve Graphite fill and a 2px Plot White inset line on its left edge. The plot dims every other edge, tick and label to 30 percent opacity, and the focused path lifts to 2.8px.

### Tables and Rows
- Header in Faint Ink at 12.5px over a Hairline rule. Numeric columns right-aligned with tabular numerals.
- Selected row: 2px Plot White inset line on the left, Sleeve Graphite fill.

### Notices, Empty States, Logs
- **Notice:** 1px Strong Hairline box with a 10px marker. Attention border is Signal Yellow; error border is Fault Red.
- **Empty:** dashed Strong Hairline box, capped at 72ch.
- **Log and JSON:** Sleeve Graphite fill, 1px Hairline border, Martian Mono 12px at 1.6 line-height, scrolling inside a 320px to 520px maximum height.

### Toast
- Raised Graphite fill, 1px Strong Hairline, overlay lift, 10px marker: Fault Red for errors, Plot White for success.

### Cover Plot (signature)
- Polar estate plot in Plot White hairlines on Matte Black. Edges draw on load over 1.1s and are static under reduced motion. Critical ridges render in Fault Red; the core is a 1px white ring.

## Do's and Don'ts

### Do:
- **Do** lead every view heading with its catalog number in Display type.
- **Do** build each view around one white hairline plot and let it lead.
- **Do** use hairlines and graphite steps before any fill.
- **Do** mark selection and focus with the 2px Single White Line.
- **Do** set identifiers, hashes, counts and logs in Martian Mono with tabular numerals.
- **Do** put actions on the right-edge tab of a square control.

### Don't:
- **Don't** round any corner. Radius is 0px everywhere.
- **Don't** add shadows at rest. The only shadow is the toast overlay.
- **Don't** use Fault Red outside critical severity and failed states.
- **Don't** use Signal Yellow for anything that is not high severity, contested, in flight, or spending.
- **Don't** set labels in ALL CAPS or with letter-spacing.
- **Don't** use em or en dashes in rendered copy or documentation.
- **Don't** add a second accent color or a decorative gradient.
