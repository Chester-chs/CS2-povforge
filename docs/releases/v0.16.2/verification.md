# v0.16.2 global black/white text verification

User scope: check other pages as well, especially all settings tabs and the video
library, with black text in light mode and white text in dark mode. Keep the
existing visual style and do not launch CS2 or change game settings.

## TDD and checks

RED: tests/test_theme_text.py audited actual visible DOM text and failed on the
existing near-black/gray colors. Checkpoint b2a0604.

GREEN: primary text is #000/#fff; secondary/tertiary text aliases it. Text-specific
accent and status colors follow the same palette. Disabled labels and dragged
rows remain opaque; outlines distinguish their states. Colored icons, cards,
rounding, typography and layout remain. Dark accent-filled buttons are darkened
to support white text. Checkpoint 760860c: 5 browser regressions passed in 17.63s.

Final affected target: **8 passed in 18.62s**:

```
tests/test_theme_text.py tests/test_text_contrast.py
tests/test_workspace_browser.py tests/test_preflight_browser.py
tests/test_appearance_prefs.py
```

- 16 views/states: Demo library, setup, whole-match selection, four reel modes,
  video library, settings appearance/general/about, recording progress/error,
  update dialog, reference dialog and offline dialog.
- Audit each view in explicit light/dark and automatic system light/dark:
  **64 view audits**, checking exact text RGB, full ancestor opacity, and visible
  input/textarea placeholder colors. No recording command or queue mutation API
  is called; progress/errors use isolated fixture state.
- Check primary-button contrast >=4.5:1 for eight accents in both appearances:
  **16 accent/theme cases**. Canvas resolves CSS color-mix before luminance checks.
- Existing sampled contrast checks, mode/scroll behavior, 390/900/1920px layouts,
  library search/play actions and appearance persistence still pass.
- One existing test now waits for the library's visible width, because cached
  rows may exist before Alpine shows its section. The geometry requirement is
  unchanged. Setup of the new test was fixed before accepting its runtime RED.

Screenshots of every settings tab and the library in all theme combinations were
generated in an isolated private Chrome profile; light/general and dark/appearance
were visually inspected. JS syntax and diff checks passed. Unchanged backend and
media code reuse preceding verification; final release CI runs the whole suite
and packaged install/update/uninstall checks.

Design references consulted: Apple HIG Dark Mode and Microsoft Typography in
Windows. The user's explicit pure black/white preference governs the palette;
hierarchy is expressed through size, weight and spacing. This is not a complete
accessibility-conformance claim. Decorative colors and brief toast animation
remain; readable text is not permanently dimmed.

No CS2/HLAE launch, Steam/game settings changes, real recording, or user-window
control. Coverage/lint/type tooling remains unavailable; no such results claimed.
