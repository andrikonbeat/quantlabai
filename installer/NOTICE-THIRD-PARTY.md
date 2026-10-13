# Third-Party Notices

The QuantLab AI installer (`installer/`) incorporates and adapts portions of
the **gentle-ai** installer TUI.

## gentle-ai

- Project: [gentle-ai](https://github.com/Gentleman-Programming/gentle-ai)
- License: MIT
- Copyright: © 2025 Gentleman Programming

```
MIT License

Copyright (c) 2025 Gentleman Programming

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

### What was adapted

The following files are derived from the gentle-ai reference TUI and were
rewritten for QuantLab's palette-independent, package-local use:

| QuantLab file | gentle-ai source | Nature of the adaptation |
|---|---|---|
| `internal/tui/theme/theme.go` | `internal/tui/styles/styles.go` | Rose Pine palette and reusable lipgloss styles (titles, help text, progress, frame). Branding copy (`Tagline`) is QuantLab's own. |
| `internal/tui/theme/theme.go` | `internal/tui/styles/logo.go` | Gradient banding technique only. No logo art is copied. |
| `internal/tui/screens/screens.go` | `internal/tui/screens/common.go`, `internal/tui/screens/installing.go`, `internal/tui/screens/complete.go` | Render helpers: option lists, checkbox/radio rows, running-operation screen, progress bar, installing screen and completion screen. Payload types and next-step copy are QuantLab's own. |
| `internal/tui/screens/detect.go` | `internal/tui/screens/detection.go` | Verification checklist render pattern, adapted to QuantLab verify items. |
| `internal/tui/router/router.go` | `internal/tui/router.go` | Forward/backward screen-route map pattern (`NextScreen`/`PreviousScreen`); the screen set is QuantLab's own. |
| `internal/tui/installing/model.go` | `internal/tui/model.go` (async progress) + `internal/tui/progress.go` (`ProgressState`, percent/logs folding) | Background-runner publishes step messages into the TUI; live progress + complete-payload folding. Pipeline, state and journal stay QuantLab's. |
| `internal/tui/screens/*_test.go` | — | New tests written for this port. |

The visual theme (colours, spacing, glyphs) is the part reused from gentle-ai.
All product naming, next-step text, checklist labels and payload structures are
QuantLab AI's own.

## Charm libraries

The installer depends on [Bubble Tea](https://github.com/charmbracelet/bubbletea),
[Bubbles](https://github.com/charmbracelet/bubbles) and
[Lip Gloss](https://github.com/charmbracelet/lipgloss), each MIT licensed,
copyright © Charmbracelet, Inc. See their repositories for full notices.