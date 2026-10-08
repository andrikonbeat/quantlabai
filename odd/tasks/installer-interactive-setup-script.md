# ODD Task Document: installer-interactive-setup-script

## Objective

Create an interactive one-command installer experience for QuantLab AI that guides the user through OS detection, explains QuantLab and third-party dependencies, offers automatic/manual OpenCode installation, guides SQX and JForex setup with licensing notes, performs a final verification checklist, and outputs a clear "ready to start" message with the recommended OpenCode command + initial prompt.

## Problem

The current installer (Go) runs `quantlab install` which launches the Bubbletea wizard, but the desired UX is: copy-paste a single command into terminal → OS/env check → explanatory TUI → choice of manual/automatic install paths → install OpenCode (auto via official installer or manual URL) → guide SQX (license info: paid or 30-day free) and JForex (deployment + 14-day free account) → verification → recommendation to run OpenCode in `~/projects/QuantLab` (or chosen path) with the initial prompt to install QuantLab-AI and start the first campaign.

## Why

Lower the barrier for non-developer traders: make setup fully guided, explain dependencies clearly, avoid manual steps, and leave them ready to run OpenCode with `quantlab-orchestrator` and the concrete first command to start a campaign.

## Scope

### In Scope
- Create an install script (shell) that can be downloaded/run via curl|bash style (common pattern) or distributed. Include robust OS/arch/distro detection (Linux/macOS/Windows guidance or WSL note). 
- Interactive TUI (gum/dialog/whiptail or plain shell with clear menus) to explain: what is QuantLab, StrategyQuant X (computation engine), OpenCode (agentic orchestrator), gentle-ai (compat), JForex (deployment/broker bridge).
- Flow: OpenCode install - offer automatic (detect OS and suggest official installer command/path) or manual (show official URL). Explain it's the agentic layer that orchestrates.
- Guide SQX installation from official site + explain license: paid or 30-day free trial works; how to obtain license.
- Guide JForex 4 deployment + explain JForex account (14-day free) and cloud option vs VPS notes.
- Verification checklist: OpenCode present? SQX path valid? gentle-ai present? JForex accessible? SDK state? Show ✓/✗ with actionable fixes.
- Final step: instruct to open OpenCode in project folder `cd /home/projects/QuantLab && opencode` (note path may vary by user; suggest creating ~/projects/QuantLab) and paste prompt: "Instala la herramienta QuantLab-AI en mi ordenador y dame la guía de introducción." OR continue manual steps. 
- Also recommend starting with: "Comienza una campaña para un portafolio de 100USD" and ensure orchestrator is prepared for the risk-aware analysis flow described (warn concrete risks for 100USD, research, pick market/timeframe/instruments with constraints, document decision).

### Out of Scope
- Modifying existing Go installer TUI beyond minimal hooks if needed (already done). This is a new user-facing bootstrap script.
- Downloading SQX/JForex binaries automatically (licensing). Only guide + official links.
- Changing orchestrator agent logic itself (prompting guidance in script/output is OK).

## Authorized Scope
- `install.sh` (new) at repo root or `scripts/install-interactive.sh`
- `docs/INSTALL_INTERACTIVE.md` (brief usage)
- `odd/tasks/installer-interactive-setup-script.md` (this doc)

## Acceptance Criteria
- [ ] Single copy-paste command works on Linux/macOS (WSL noted). Script detects OS/arch.
- [ ] Explains QuantLab + deps in Spanish as requested, briefly and clearly.
- [ ] Offers manual/automatic OpenCode install; shows official URL; gives automatic install path guidance.
- [ ] Guides SQX (license paid/30-day free) and JForex (14-day free) with official links and notes.
- [ ] Verification checklist gates next step; if failing, suggests delegating to OpenCode agent.
- [ ] Final output gives: cd to project dir (suggest `~/projects/QuantLab`), `opencode` command, and the exact prompt to paste.
- [ ] Recommends starting campaign with "Comienza una campaña para un portafolio de 100USD" and includes the risk-aware checklist in output for user/agent awareness.
- [ ] Script is idempotent-ish (safe to re-run), uses `set -euo pipefail`, clear UX.

## Tasks
- [x] T1: Create install script scaffold with OS/arch detection and basic checks
- [x] T2: Build interactive TUI (menus/prompts) with Spanish explanations
- [x] T3: OpenCode install flow (auto/manual) with links and guidance
- [x] T4: SQX + JForex guidance (licensing, links, notes)
- [x] T5: Verification checklist + remediation
- [x] T6: Final instructions + campaign prompt + risk-aware guidance
- [x] T7: Docs + smoke tests (syntax check)

## Progress
- Created: 2025-10-06
- Status: completed
- Active Task: none

## Rationale For Accepted Changes
Implemented interactive one-command installer script (install.sh) with OS detection, explanatory TUI, OpenCode/SQX/JForex guidance, verification checklist, final instructions and campaign startup guidance. Added docs/INSTALL_INTERACTIVE.md. Shell syntax validated.

## Next Step
Ready to close.
