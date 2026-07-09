# Platform UI Mobbin Inspiration - 2026-07-09

This pass extends the catalog-app polish back into the Mobius host shell. The direction is product UI rather than marketing: calm density, native-feeling controls, clear hierarchy, and very little decoration.

## References

- [Maze settings-style product surface](https://mobbin.com/screens/b3d01cb4-1e38-4b2d-b6df-9f19eec33dd1): dense administrative layout with restrained panels and readable labels.
- [Clerk settings/navigation surface](https://mobbin.com/screens/64495603-2e48-4214-922d-2022463a27e2): quiet sidebar + content structure with standard controls.
- [Vercel settings/product surface](https://mobbin.com/screens/b3d975af-db84-4ea1-a067-5d9f32303e49): simple system typography, neutral card language, minimal ornament.
- [ChatGPT chat surface](https://mobbin.com/screens/0729631b-f0f3-423c-8eff-5903dc2d0ca9): composer stays visually anchored while the conversation remains the primary surface.

Earlier catalog-app references remain relevant for app interiors:

- [Evernote notes home](https://mobbin.com/screens/cafe4bcd-124d-4283-a4f2-21cb162b80bc)
- [Bear markdown editor](https://mobbin.com/screens/f42a17c8-2928-4329-9cd0-a83e58bc72e1)
- [Etsy catalog grid](https://mobbin.com/screens/d120f7f8-a2fe-4087-949c-35ac8497c90f)
- [Tiimo task list](https://mobbin.com/screens/c8293b88-23c9-454b-81fc-d9f9366c59d6)

## Platform Decisions

- Keep copied local primitives for now. Do not introduce a shared UI package until the repeated primitives stabilize.
- Prefer sentence-case, untracked labels across shell, chat, markdown, cards, sheets, and catalog apps.
- Use the Mobius purple for primary actions, active rows, focus, and clear selected states only.
- Keep scrollbars hidden globally while preserving scrollability.
- Avoid side-stripe alerts and heavily shadowed bordered cards. Use full borders, tone fills, and compact radii instead.
- Keep modal, toast, drawer, and popover elevation modest so they feel like platform chrome, not separate visual systems.

## 2026-07-09 Implementation Notes

- Normalized platform micro-labels in chat errors, queued-message counts, markdown code/table headers, question cards, model picker sections, model legacy pills, and app loading labels.
- Reduced heavy bordered-shadow treatment in drawer menus, popovers, install sheet, walkthrough card, error boundary, and toasts.
- Aligned setup, login, and provider-auth controls with Settings: 10px input/button radius, consistent focus rings, calmer light-mode elevation, and sentence-case/untracked labels.
- Added local default theme tokens to unauthenticated login/setup roots so they stay contrast-safe before `/api/theme` applies.
- Added a temporary screenshot harness at `/tmp/mobius-shell-preview/` that links to the real platform CSS files and renders the representative shell/chat/drawer states.
- Added route-level Playwright QA captures at `/tmp/mobius-route-qa/` for login, setup account, setup provider, shell chat, Settings, and AppCanvas at desktop/mobile sizes.

## 2026-07-09 Platform Continuation

- Reconciled the platform shell with the catalog app mark system: the shell logo
  and standard app marks now share the 8px corner language.
- Tightened default platform chrome that appears constantly: drawer rows,
  New chat hover behavior, toast radius, Login card/input/button shapes, and
  Setup card/input/button/help shapes.
- Removed the leftover Setup green token so first-run screens no longer carry a
  stale success hue that can tint audits or screenshots.
- Preserved the existing dark-neutral + Mobius violet identity: green remains
  reserved for semantic success/visited states, not platform identity.
- Verified with detector, frontend tests excluding the known Node 22
  `global.navigator` runtime-store harness issue, and diff whitespace checks.
- Rewired the temporary shell preview to symlink the real workspace CSS files
  and recaptured `/tmp/mobius-shell-preview/platform-shell-preview.png`.
  Diagnostics showed no body scroll; the only overflow candidate was the
  intentionally open drawer menu extending outside its row.

## 2026-07-09 Platform Continuation 2

Additional inspected references:

- [Vercel provider modal](https://mobbin.com/screens/d4c39bcb-41f6-4d2a-a8f4-ed90136fc2b3): compact provider rows inside a restrained modal, useful for Manage Models and auth/provider selection.
- [Relevance AI model picker](https://mobbin.com/screens/94a61b0c-d8b5-4254-8147-426391e60452): dense model rows, visible filters, and a quiet detail panel; reinforces row-first model management instead of decorative cards.
- [Fabric note editor](https://mobbin.com/screens/b2e9c0e3-4dbc-4a43-879f-0b5c47dba046): icon-forward editor actions and compact media controls that match the Notes direction without becoming a full-screen document app.

Implemented:

- Normalized the remaining platform settings/auth/model chrome to the 8px
  product shape: Settings sections/notices/inputs/buttons, ProviderAuth inputs,
  provider rows, Codex auth device blocks, Manage Models modal/sections/buttons,
  InstallSheet, Walkthrough, and ErrorBoundary cards.
- Replaced lingering hardcoded primary button foregrounds with
  `--accent-fg`, so theme accents do not create muddy or unexpectedly dark
  primary controls.
- Gated remaining hover-only feedback behind pointer media queries in Settings,
  ProviderAuth, Manage Models, ChatSettingsPanel, Walkthrough, and
  ErrorBoundary, preventing sticky hover states on touch devices.
- Hid Settings' own scrollbar while preserving internal scrollability, keeping
  it aligned with the no-visible-scrollbar app standard.
- Preserved green for semantic success/connected states only; platform identity
  remains neutral charcoal plus Mobius violet.

Verification:

- `impeccable` detector sweep returned no findings for the touched platform
  CSS and Atlas theme.
- Platform explicit frontend tests excluding the known Node 22
  `mobiusRuntimeStore.test.js` harness issue passed: 332 tests.
- ChatView hook tests passed: 36 tests.
- Diff whitespace checks passed for touched platform files.
