# Mobius Catalog UI Direction

Date: 2026-07-08
Status: draft recommendations

## Evidence

- Mobbin MCP screen searches for Notes, catalog browsing, builder workspaces,
  news readers, fitness logs, task managers, map apps, and graph/canvas apps.
- Visual inspection of the returned screen images, not metadata alone.
- Current Mobius catalog apps and their existing `mobius-ui:*` fenced CSS
  blocks in Notes, App Store, Editor, News, Workout, Atlas, Memory, and related
  apps.
- Existing Notes design docs, including the Apple-standard draft and the
  live-inline markdown design.
- The named `impeccable` skill was used after installation for the follow-up
  platform/catalog polish pass, alongside local review and Mobbin references.
- Follow-up Mobbin MCP searches on 2026-07-09 inspected: [Evernote note
  home](https://mobbin.com/screens/cafe4bcd-124d-4283-a4f2-21cb162b80bc),
  [Bear markdown editor](https://mobbin.com/screens/f42a17c8-2928-4329-9cd0-a83e58bc72e1),
  [Etsy catalog grid](https://mobbin.com/screens/d120f7f8-a2fe-4087-949c-35ac8497c90f),
  and [Tiimo task list](https://mobbin.com/screens/c8293b88-23c9-454b-81fc-d9f9366c59d6).
- Follow-up Mobbin MCP searches on 2026-07-09 for the information/workflow
  app batch inspected: [Apple Notes note detail](https://mobbin.com/screens/8fa54f4b-6d25-4b49-9b8b-8a55a2cedcb6),
  [Notion inline editor](https://mobbin.com/screens/a73664f1-2d06-4276-84be-8b40fd8ea601),
  [Apple News feed](https://mobbin.com/screens/c1c3231e-6bcf-4602-bd90-54b09a38a72d),
  and [Raycast model/settings list](https://mobbin.com/screens/1a81fa7c-b427-4521-a082-4262147e6e6e).

## Direction

Mobius should not copy any one reference app. The stronger direction is a shared
OS-quality language: quiet dark surfaces, crisp type, dense but breathable
cards, clear hierarchy, one primary action per screen, secondary actions tucked
into icon toolbars or menus, and overlay sheets instead of disruptive page
replacements.

The existing catalog already has good raw material. Several apps define
`mobius-ui:Root`, `Focus`, `Button`, `Segmented`, `Card`, `Sheet`,
`Scrollskin`, and `ChatEmbed` blocks. The next step should be copy-based
convergence: keep mechanically synchronized local versions of these primitives
so the catalog reads as one product rather than a set of sibling experiments.
Do not introduce a shared UI dependency until the copied shapes have proven
stable across multiple apps.

## Shared Standard

- App root: full-height, overflow-hidden app frame, theme tokens only,
  antialiased text, no visible body-level scrollbars.
- Header: compact brand/action row, safe-area aware, no marketing copy inside
  utility apps.
- Search: prominent when browsing or filtering is core; bottom-anchored on
  phone-like Notes/catalog flows, top or sidebar in workspace apps.
- Navigation: segmented controls for top-level modes; tabs only when switching
  peer views; back controls aligned with the same toolbar as actions.
- Cards: 8px radius default, no nested cards, content first, metadata and
  actions secondary.
- Actions: 44px touch targets, icon-only where the icon is standard, tooltip or
  `aria-label` always present, destructive actions confirmed in-app.
- Sheets: details and editors open over the current page when context matters;
  outside click closes non-destructive overlays.
- States: every app should share skeleton, empty, offline, error, pending-sync,
  and confirm-delete patterns.
- Scroll: no visible persistent scrollbars in normal catalog surfaces; internal
  scrollers should use the same hidden or subdued scrollskin.
- Motion: small state transitions only, with full reduced-motion handling.

## Mobbin References

| Mobius area | References | What fits Mobius |
| --- | --- | --- |
| Notes | [Apple Notes grouped list](https://mobbin.com/screens/109e936a-6169-4e79-a82a-b3478012acf2), [Apple Notes dense rows](https://mobbin.com/screens/88417883-d999-4072-8d43-b9874f8b9e0a), [Apple Notes menu](https://mobbin.com/screens/0fe5b5f2-60cf-40d5-8489-5f55b8ece6d0), [Bear notes list](https://mobbin.com/screens/ffb4da29-91c5-4e2a-9dde-308f6d89aa6d), [Evernote note home](https://mobbin.com/screens/c5fa25d2-4859-4c6f-9d5b-115774c244e6) | Date-grouped recency, compact note previews, bottom search/create ergonomics, attachment thumbnails, and a menu for secondary view/sort actions. |
| App Store/catalog | [Apple Games catalog](https://mobbin.com/screens/1a1ad2f8-7e2a-4435-a977-b5c26f2835a7), [Meta Quest store](https://mobbin.com/screens/bdc98a4a-1e49-4f3b-a55b-3828d169e634) | Featured sections, larger app cards, install/update state, screenshot-led details, and consistent permission/update rows. |
| Builder apps | [Google AI Studio workspace](https://mobbin.com/screens/915541ca-412a-436f-8632-fb2e22c2bd71), [v0 code workspace](https://mobbin.com/screens/a18ebbf1-2b4a-4673-9df0-8f87fe3b827e), [Replit workspace](https://mobbin.com/screens/d9d37708-b18b-4b18-957c-5e274fe5bc50) | Stable three-pane architecture: file/project nav, central editor or preview, right/bottom agent or inspector panel, with a slim top action rail. |
| News, Reflection, Tandem | [Ground News feed](https://mobbin.com/screens/b529b112-bb8f-4e7a-9d2c-d5f8b439aab1), [Particle News digest](https://mobbin.com/screens/547456ac-562e-448f-86ce-b0a63e44257e), [Perplexity answer surface](https://mobbin.com/screens/df9ce517-6e93-40e7-bbe5-4b700a1ab20f) | Digest cards with provenance chips, summaries that scan quickly, reader sheets, and source/question actions kept close to the content. |
| Workout | [Fitbod log](https://mobbin.com/screens/969d14a3-471c-4cb0-8f5c-cb64db2a47bf), [Runna training view](https://mobbin.com/screens/8c89f937-c894-4a5f-92a3-59d9e196d762) | Daily timeline, stats strip, streak/progress visualization, and one obvious log/start action. |
| Tasks | [Todoist upcoming](https://mobbin.com/screens/1ae63b10-6840-42ec-838a-0117cb219e99), [Tiimo schedule](https://mobbin.com/screens/8a6a1881-0e17-4cfa-9aa4-114d0b90aeec), [Jira issue list](https://mobbin.com/screens/098ce53c-ccf8-48c1-a8d6-97fda934d532) | Date-grouped agenda rows, status badges, compact filters, and a floating or bottom primary add action. |
| Memory | [FLORA canvas](https://mobbin.com/screens/9976aa98-6db2-458f-8bcf-e8e6472a04c9), [Weavy board](https://mobbin.com/screens/7688c8a9-518e-48e6-928f-69739a75417f) | Sparse canvas with clustered items, persistent tool rail, and an inspector/detail surface instead of full-page jumps. |
| Atlas | [FocusFlight map view](https://mobbin.com/screens/731c964f-dddf-4726-9297-148688001844) | Full-bleed map/globe, bottom sheet for selected places, and a restrained stats rail. |
| Skills, Contribute, settings-like app lists | [Raycast model/settings list](https://mobbin.com/screens/1a81fa7c-b427-4521-a082-4262147e6e6e), [Notion inline editor](https://mobbin.com/screens/a73664f1-2d06-4276-84be-8b40fd8ea601) | Plain rows, direct toggles/actions, no decorative status chrome, and markdown/detail views that read as edited documents rather than raw files. |

## Notes Reference App

Notes should remain the first catalog app to bring up to Apple-standard polish.
The current direction is right, but it should be judged against these specifics:

- Home should feel like a crisp Apple Notes/Bear hybrid: readable previews,
  strong title rendering, image/file hints where useful, and clear recency.
- Editing a note should update its `updated` time and move it to the beginning;
  merely opening or closing should not.
- Locked notes should prevent accidental editing and deletion. This is an edit
  guard, not encryption. A real private-notes mode would need platform-level
  encrypted storage later.
- Card actions should stay in the bottom strip: pin, color, lock, delete.
- Open note should be an overlay over the grid, not a whole-page replacement.
  Back should sit on the same row as note actions, and outside click should
  close when there is no destructive pending choice.
- The open note should not repeat the "Notes" title. The content owns the
  surface.
- Image and file inputs should be icon-only controls with labels/tooltips.
- Markdown should remain live-inline: editing and preview happen in one surface,
  with inactive markdown syntax visually resolved and active-line syntax
  editable. Checkbox previews should render as checkbox items, not bullets plus
  checkboxes.
- Visual quality bar: no blurry preview text, no low-contrast toolbar icons, no
  visible persistent scrollbars, and no status icons in note titles unless they
  communicate an unavoidable state.

## Catalog Rollout

1. Stabilize copied primitives.
   - Keep the existing fenced CSS blocks synchronized as a shared spec first:
     Root, Header, Button, IconButton, Segmented, SearchField, StatusChip,
     Card, ListRow, EmptyState, Skeleton, Sheet, ConfirmModal, Toast,
     SyncPill, Scrollskin, and ChatEmbed.
   - Keep class prefixes local and copy the blocks for now, but align
     dimensions, radius, focus rings, safe-area padding, and state names.
   - Consider a package only after several apps carry byte-identical fenced
     blocks and the extraction becomes mechanical.

2. Finish Notes as the reference implementation.
   - Use it to validate overlay sheets, bottom action strips, hidden scroll,
     live markdown, lock semantics, and recency sorting.
   - Add a visual regression capture once the app-frame harness is convenient.

3. Bring list/catalog apps into the same language.
   - App Store: move toward featured sections plus polished detail sheets,
     using Apple Games and Meta Quest as inspiration.
   - Tasks, Skills, Contribute: use the same list row/card/status chip system
     so they feel operational and scannable.

4. Bring reader/digest apps into the same language.
   - News, Reflection, Tandem: shared reader overlay, provenance chips, compact
     digest cards, and consistent chat/agent panel behavior.

5. Bring builder apps into the same language.
   - Editor, LaTeX, Web Studio: align the file tree, central work surface,
     preview, chat panel, and top action rail using the Google AI Studio/v0
     structure as the benchmark.

6. Bring specialty apps into the same language.
   - Workout: timeline plus stat strip plus one primary log/start action.
   - Memory: graph/canvas with persistent tool rail and detail inspector.
   - Atlas: full-bleed globe/map with bottom sheet and stats rail.
   - CubeRun: keep the game expressive; only shell-adjacent screens, settings,
     and catalog metadata need the standard Mobius chrome.

## Implementation Pass 1

Applied 2026-07-08, copy-based only. No shared dependency was introduced.

- Added or aligned copied `mobius-ui:Scrollskin v2` blocks so normal app
  surfaces stay scrollable without persistent visible scrollbars.
- Tightened root primitives in copied app CSS: `width/max-width`, font
  smoothing, tap-highlight suppression, overflow containment, and word-wrapping
  where apps were behind the newer Notes/App Store shape.
- Normalized accent-filled controls to use `--accent-fg` instead of hardcoded
  white foregrounds in App Store, Reflection, Tandem, and Workout.
- Removed detector-flagged side-rail accents from Skills markdown, News app
  surfaces and generated report HTML, Reflection latest cards, and Memory
  markdown. Replaced them with full-border/accent-tinted surfaces.
- Removed Atlas' height transition on the bottom sheet; drag still updates
  height directly, but snap state no longer animates a layout property.
- Kept app identity intact: CubeRun remains immersive, Atlas keeps its globe
  identity palette, Reflection keeps its violet accent, and builder apps keep
  their local file/editor/preview vocabulary.

## Implementation Pass 2

Applied 2026-07-09, still copy-based. No shared dependency was introduced.

- Brought the Mobius shell/platform polish in line with the catalog pass:
  system UI font stack for product chrome, self-hosted mono retained for code,
  solid-color wordmark/empty-state text, hidden scrollbars, and short ease-out
  motion.
- Replaced shell-side side-rail accents with full-border/tinted notice
  treatments for chat errors and markdown blockquotes.
- Replaced bounce-arrow motion in install and walkthrough surfaces with quieter
  opacity/translate cues.
- Updated `app-component-shapes.md` and `theming.md` so future agents copy the
  same local blocks and avoid side stripes, gradient text, bouncy motion, and
  visible scrollbars.
- Updated Notes' copied `Scrollskin` fences to v2 so the reference app matches
  the hidden-scroll standard.

## Implementation Pass 3

Applied 2026-07-09, still copy-based. No shared dependency was introduced.

- Removed remaining negative letter-spacing from copied catalog app UI chrome
  so titles, rows, empty states, and sheet headings render crisply with the
  system font stack.
- Hid the remaining visible drawer scrollbar in the platform shell while
  preserving the drawer fade mask and native scrolling behavior.
- Tokenized platform accent/danger filled controls that still used hardcoded
  white foregrounds.
- Replaced Reflection's remaining generated-report questions side stripe with
  the same full-border/tinted treatment.
- Updated the WebStudio starter seed to use the same platform font stack and a
  local `--brand-fg` foreground token for its CTA.

## Implementation Pass 4

Applied 2026-07-09, still copy-based. No shared dependency was introduced.

- Removed Notes' remaining tone side stripe so colored notes now rely on
  background tint, border tint, and the bottom tone dot rather than a side rail.
- Normalized copied section labels, status chips, report metadata, file labels,
  and table headers across Notes, Store, Tasks, News, Reflection, Editor,
  Workout, Atlas, Contribute, LaTeX, and Web Studio to use Mobius' calmer
  product typography: title-case-capable labels, no decorative uppercase
  transform, and letter-spacing `0`.
- Kept functional 1px pane dividers in builder apps; those are structural
  split boundaries, not decorative side accents.
- Rebuilt Notes so `index.jsx` matches the edited `src/ui/css.js` source.

## Implementation Pass 5

Applied 2026-07-09, still copy-based. No shared dependency was introduced.

- Built a temporary real-module preview harness at `/tmp/mobius-info-preview/`
  for Memory, Skills, Contribute, News, and Reflection using mocked Mobius
  runtime data.
- Captured app-batch screenshots:
  `/tmp/mobius-info-preview/info-overview-desktop.png`,
  `/tmp/mobius-info-preview/memory-list-mobile.png`,
  `/tmp/mobius-info-preview/skills-detail-desktop.png`,
  `/tmp/mobius-info-preview/contribute-feed-desktop.png`,
  `/tmp/mobius-info-preview/news-reader-desktop.png`, and
  `/tmp/mobius-info-preview/reflection-detail-desktop.png`.
- Fixed Skills detail rendering so installed skill YAML frontmatter is parsed
  as metadata and no longer appears as visible prose. The detail view now reads
  like documentation, matching the Notion/Raycast reference direction.
- Aligned Skills search with the current Mobius copied input primitive:
  10px radius, 3px accent-dim focus halo, and calmer secondary button/back
  weights.
- Changed Contribute to own its app-frame scroll: `height: 100%`,
  overflow-hidden root, scrollable `.co-page`, hidden scrollskin, and contained
  overscroll. Long contribution feeds no longer rely on host/body scrolling.
- Tightened Memory's narrow list view: mobile hides nonessential numeric
  columns and keeps Note/Type visible without horizontal overflow. Memory's
  table, legend, severity, and detail context labels also moved away from
  tracked-uppercase chrome toward the shared sentence-case product style.
- Visual QA showed no page-level desktop/mobile scrollbars in the harness. The
  Memory graph view shows an expected preview-only vendor-script 404 because
  `/vendor/d3` and `/vendor/pixi` are not served by the temporary harness.

## Implementation Pass 6

Applied 2026-07-09, still copy-based. No shared dependency was introduced.

- Built a temporary real-module preview harness at
  `/tmp/mobius-builder-preview/` for Editor, Web Studio, and LaTeX using mocked
  filesystem, app storage, build status, project lists, and embedded chat.
- Captured workbench screenshots:
  `/tmp/mobius-builder-preview/editor-desktop.png`,
  `/tmp/mobius-builder-preview/editor-mobile-drawer.png`,
  `/tmp/mobius-builder-preview/webstudio-preview-desktop.png`,
  `/tmp/mobius-builder-preview/webstudio-mobile-drawer.png`,
  `/tmp/mobius-builder-preview/latex-desktop.png`, and
  `/tmp/mobius-builder-preview/latex-mobile-drawer.png`.
- Aligned Editor's drawer create actions with Web Studio and LaTeX by copying
  local file/folder-plus icons and using icon-only 44px controls with accessible
  labels.
- Added the same active drawer-toggle treatment to Web Studio and LaTeX that
  Editor already used: neutral hover/focus, accent-dim open state, and press
  feedback. LaTeX also regained a visible keyboard focus ring on the brand
  drawer toggle.
- Gated Web Studio and LaTeX hover-only row/action treatments behind
  `@media (hover: hover)` so touch devices do not keep sticky hover states.
- Removed LaTeX PDF viewer's reserved scrollbar gutter while preserving
  scrollability and the hidden-scroll standard.
- Rebased the builder preview harness and Web Studio starter seed from a
  mint/sage palette to the platform's neutral charcoal plus Mobius violet
  defaults, so screenshots reflect the actual shell direction instead of a
  green cast.
- Visual QA showed no page-level desktop/mobile scrollbars, no visible
  scrollbar gutters, and no control text overflow in the builder harness.

## Implementation Pass 7

Applied 2026-07-09, still copy-based. No shared dependency was introduced.

- Normalized standard catalog app brand marks to the platform shape:
  34px icons with 8px radius in Atlas, Contribute, Reflection, Store, Tandem,
  and the existing builder/workout/news family; Notes' 32px mark now uses the
  same 8px corner.
- Added Tandem's missing copied `mobius-ui:Focus v1` floor so every non-game
  catalog app has Root, Scrollskin, Focus, and reduced-motion coverage.
- Brought Memory's older hybrid inline-style surface into the marker system:
  added `mg-root`, `Root`, `Focus`, `Scrollskin`, and `ReducedMotion` fences,
  moved hover-only affordances behind pointer media queries, and changed its
  fallback mark from a glowing circle to the same subdued accent tile.
- Added Cuberun wrapper coverage for `Root`, `Focus`, and `ReducedMotion`
  while keeping the game itself immersive. Its loading/error fallback panel now
  uses the same 8px platform radius and touch-safe hover behavior.
- Tightened host-shell everyday chrome: shell logo radius now matches app
  marks, drawer rows use the 8px product shape, the New chat hover state no
  longer sticks on touch devices, and toasts use the same compact radius.
- Tightened first-run Login and Setup surfaces: removed an unused green setup
  token, aligned card/input/button/help radii with the 8px platform vocabulary,
  and gated hover-only feedback behind pointer media queries.
- Verification: the full `impeccable` detector sweep across shell CSS and all
  catalog style entry points returned no findings. Notes, Store, Memory,
  Reflection, Tandem, Tasks, and the Cuberun wrapper checks passed. Atlas pure
  behavior tests passed; Atlas persistence and one frontend runtime-store suite
  still hit the existing Node 22 `global.navigator` harness issue before app
  code runs.

## Implementation Pass 8

Applied 2026-07-09, still copy-based. No shared dependency was introduced.

Additional inspected Mobbin references:

- [Snapchat map + bottom sheet](https://mobbin.com/screens/ef785564-396a-47a0-8fd9-9b79b97d1d37): direct map manipulation with a compact search/filter sheet that does not compete with the map.
- [Tabby map/list surface](https://mobbin.com/screens/5617ab31-7cb2-4aa9-8eb8-707f8e098266): map markers/status carry the primary spatial state while the list remains steady and compact.
- [Cosmos new note sheet](https://mobbin.com/screens/4083390b-0ac0-477e-90b2-48070d52fc0c): over-current-page note creation with a quiet header and inline formatting rail.
- [Fabric note editor](https://mobbin.com/screens/b2e9c0e3-4dbc-4a43-879f-0b5c47dba046): icon-first media/action controls and compact save flow.

Atlas implementation:

- Fixed globe selection reliability by resolving a tap from the final pointer
  coordinate, instead of relying only on SVG click bubbling after pointer
  capture.
- Added a 6px tap/drag threshold so tiny web pointer jitter no longer rotates
  the globe or suppresses selection.
- Stopped the globe from entering its lower-precision "moving" render state on
  plain pointer-down; it now promotes only after an actual drag or pinch.
- Normalized wheel zoom for mouse-wheel and trackpad delta modes, reduced zoom
  step size, and shortened release inertia so rotation feels controlled rather
  than slippery.
- Preserved Atlas' current stable sheet-height behavior on selection; the
  detail view stays inside the user's chosen sheet stop while the fixed header,
  scrollable facts, and pinned CTAs keep the selected country readable.
- Tempered Atlas' visited green by mixing it with the active accent and land
  fill; the state still reads as visited but avoids a screenshot-wide green
  cast.

Atlas verification:

- Pure Atlas behavior tests passed: 22 tests.
- Browser QA passed in a temporary harness at `/tmp/atlas-harness/`: tiny-jitter
  tap selected Germany, drag changed globe geometry, wheel zoom increased globe
  radius, body scroll stayed at `0,0`, and desktop/mobile visible-scrollbar
  checks returned none.
- Final rebased captures: `/tmp/atlas-harness/playwright-rebased-selected.png`
  and `/tmp/atlas-harness/playwright-rebased-mobile.png`.

## Production Gaps To Watch

- Do not ship any app with hidden keyboard traps, unlabelled icon buttons, or
  controls below 44px.
- Avoid decorative hero layouts inside utility apps. The first screen should be
  the usable app.
- Avoid one-off palettes. Use theme tokens, with small app-specific accents
  only where they communicate domain meaning.
- Keep destructive actions reversible or confirmed.
- Keep app data states explicit: loading, empty, offline, pending sync,
  conflict/error, and success.
- Prefer overlay detail/editor surfaces where context helps the user, but make
  focus return and escape/outside-click behavior reliable.
