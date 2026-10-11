// Package screens holds the portable render helpers shared by the QuantLab AI
// installer TUI. Every function here is a pure renderer: it takes data and
// returns a styled string, with no model, state or I/O of its own.
//
// The render patterns are adapted from the gentle-ai reference TUI
// (https://github.com/Gentleman-Programming/gentle-ai, MIT © 2025 Gentleman
// Programming); the copy, payload types and next steps are QuantLab's own.
package screens

import (
	"fmt"
	"strings"

	"github.com/andrikonbeat/quantlabai/internal/tui/theme"
)

// RenderOptions renders a vertical list of options with the item at cursor
// highlighted.
func RenderOptions(options []string, cursor int) string {
	output := ""
	for idx, option := range options {
		if idx == cursor {
			output += theme.SelectedStyle.Render(theme.Cursor+option) + "\n"
		} else {
			output += theme.UnselectedStyle.Render("  "+option) + "\n"
		}
	}

	return output
}

// RenderCheckbox renders one checkbox row. focused highlights the whole row.
func RenderCheckbox(label string, checked bool, focused bool) string {
	marker := "[ ]"
	markerStyle := theme.UnselectedStyle
	if checked {
		marker = "[x]"
		markerStyle = theme.SuccessStyle
	}

	prefix := "  "
	if focused {
		prefix = theme.Cursor
		return theme.SelectedStyle.Render(prefix+markerStyle.Render(marker)+" "+label) + "\n"
	}

	return theme.UnselectedStyle.Render(prefix+markerStyle.Render(marker)+" "+label) + "\n"
}

// RenderRadio renders one radio row. focused highlights the whole row.
func RenderRadio(label string, selected bool, focused bool) string {
	marker := "( )"
	markerStyle := theme.UnselectedStyle
	if selected {
		marker = "(*)"
		markerStyle = theme.SelectedStyle
	}

	prefix := "  "
	if focused {
		prefix = theme.Cursor
		return theme.SelectedStyle.Render(prefix+markerStyle.Render(marker)+" "+label) + "\n"
	}

	return theme.UnselectedStyle.Render(prefix+markerStyle.Render(marker)+" "+label) + "\n"
}

// RenderOperationRunning renders a long-running operation screen: title,
// spinner + detail, and a "please wait" footer.
func RenderOperationRunning(title, detail string, spinner string) string {
	return theme.TitleStyle.Render(title) + "\n\n" +
		theme.WarningStyle.Render(spinner+"  "+detail) + "\n\n" +
		theme.HelpStyle.Render("Please wait...")
}

// ProgressItem is one step of an installation progress list.
type ProgressItem struct {
	Label  string
	Status string
}

// InstallProgress carries everything RenderInstalling needs to draw the
// progress screen. Status values are "succeeded", "skipped", "rolled-back",
// "failed", "running" and anything else (rendered as a pending dot).
type InstallProgress struct {
	Percent     int
	CurrentStep string
	Items       []ProgressItem
	Logs        []string
	Done        bool
	Failed      bool
}

// RenderInstalling draws the install progress screen: bar, current step,
// per-step status marks and the tail of the log.
func RenderInstalling(progress InstallProgress, spinner string) string {
	var b strings.Builder

	b.WriteString("\n")
	b.WriteString(theme.TitleStyle.Render("Installing"))
	b.WriteString("\n\n")
	b.WriteString(RenderBar(progress.Percent))
	b.WriteString(" ")
	b.WriteString(theme.PercentStyle.Render(fmt.Sprintf("%d%%", progress.Percent)))
	b.WriteString("\n")

	if progress.CurrentStep != "" {
		b.WriteString(theme.SubtextStyle.Render("Current: " + progress.CurrentStep))
		b.WriteString("\n")
	}
	b.WriteString("\n")

	for _, item := range progress.Items {
		var icon string
		switch item.Status {
		case "succeeded":
			icon = theme.SuccessStyle.Render("✓")
		case "skipped":
			icon = theme.SubtextStyle.Render("−")
			item.Label += " (skipped)"
		case "rolled-back":
			icon = theme.SubtextStyle.Render("↶")
			item.Label += " (rolled back)"
		case "failed":
			icon = theme.ErrorStyle.Render("✗")
		case "running":
			icon = theme.WarningStyle.Render(spinner)
		default:
			icon = theme.SubtextStyle.Render("·")
		}
		b.WriteString(fmt.Sprintf("  %s %s\n", icon, theme.UnselectedStyle.Render(item.Label)))
	}

	if len(progress.Logs) > 0 {
		b.WriteString("\n")
		b.WriteString(theme.HeadingStyle.Render("Logs"))
		b.WriteString("\n")
		start := 0
		if len(progress.Logs) > 5 {
			start = len(progress.Logs) - 5
		}
		for _, entry := range progress.Logs[start:] {
			for _, line := range strings.Split(entry, "\n") {
				b.WriteString(theme.SubtextStyle.Render("  " + line))
				b.WriteString("\n")
			}
		}
	}

	if progress.Done {
		b.WriteString("\n")
		succeeded, failed := countResults(progress.Items)
		skipped := 0
		for _, item := range progress.Items {
			if item.Status == "skipped" {
				skipped++
			}
		}
		if progress.Failed {
			b.WriteString(theme.WarningStyle.Render(fmt.Sprintf("Completed with errors: %d succeeded, %d failed", succeeded, failed)))
			b.WriteString("\n")
		} else if skipped > 0 {
			b.WriteString(theme.SubtextStyle.Render(fmt.Sprintf("Completed: %d succeeded, %d skipped\n", succeeded, skipped)))
		} else {
			b.WriteString(theme.SuccessStyle.Render(fmt.Sprintf("All %d steps completed successfully.", succeeded)))
			b.WriteString("\n")
		}
		b.WriteString(theme.HelpStyle.Render("Press Enter to continue."))
		b.WriteString("\n")
	}

	return b.String()
}

func countResults(items []ProgressItem) (succeeded, failed int) {
	for _, item := range items {
		switch item.Status {
		case "succeeded":
			succeeded++
		case "failed":
			failed++
		}
	}
	return
}

// barWidth is the fixed width of the install progress bar.
const barWidth = 30

// RenderBar renders a clamped 0..100 progress bar.
func RenderBar(percent int) string {
	if percent < 0 {
		percent = 0
	}
	if percent > 100 {
		percent = 100
	}

	filled := (percent * barWidth) / 100
	empty := barWidth - filled

	return theme.ProgressFilled.Render(strings.Repeat("█", filled)) +
		theme.ProgressEmpty.Render(strings.Repeat("░", empty))
}

// maxErrorLines bounds how much of a failed step's error is echoed back.
const maxErrorLines = 15

// FailedStep is one pipeline step that failed, with its error text.
type FailedStep struct {
	ID    string
	Error string
}

// MissingDep is a dependency the installer could not satisfy.
type MissingDep struct {
	Name        string
	InstallHint string
}

// CompleteCheckItem is a single line in the post-install checklist.
type CompleteCheckItem struct {
	Label string
	Done  bool
}

// CompletePayload carries everything RenderComplete needs for the closing
// screen. When FailedSteps is non-empty the failure screen is rendered,
// otherwise the success screen.
type CompletePayload struct {
	ConfiguredAgents    int
	InstalledComponents int
	// Checklist is an optional status list (post-install guide, readiness).
	Checklist []CompleteCheckItem
	FailedSteps         []FailedStep
	RollbackPerformed   bool
	RollbackComplete    bool
	MissingDeps         []MissingDep
	ManualActions       []string
	// NextSteps overrides the default QuantLab next steps when non-empty.
	NextSteps []string
	// Footer is the trailing help line. It is omitted when empty.
	Footer string
}

// defaultNextSteps is the QuantLab close-out guide.
var defaultNextSteps = []string{
	"1. Configurá tus API keys, o exportá las variables de entorno de OpenCode/LLM",
	"2. Entrá a tu carpeta de campañas y corré: opencode",
	"3. Elegí el agente quantlab-orchestrator",
	"4. Describí el objetivo de la campaña; cada una de las 14 fases espera tu confirmación",
}

// RenderComplete draws the closing screen for a successful or failed install.
func RenderComplete(data CompletePayload) string {
	if len(data.FailedSteps) > 0 {
		return renderCompleteFailed(data)
	}
	return renderCompleteSuccess(data)
}

func renderCompleteSuccess(data CompletePayload) string {
	var b strings.Builder

	b.WriteString("\n")
	b.WriteString(theme.SuccessStyle.Render("Done! QuantLab AI is installed and ready."))
	b.WriteString("\n\n")

	b.WriteString("  " + theme.HeadingStyle.Render("Configured agents") + "  " + theme.SuccessStyle.Render(fmt.Sprintf("%d", data.ConfiguredAgents)) + "\n")
	b.WriteString("  " + theme.HeadingStyle.Render("Installed components") + "  " + theme.SuccessStyle.Render(fmt.Sprintf("%d", data.InstalledComponents)) + "\n")
	b.WriteString("\n")

	renderCompleteChecklist(&b, data.Checklist)
	renderMissingDeps(&b, data.MissingDeps)
	renderManualActions(&b, data.ManualActions)

	b.WriteString(theme.HeadingStyle.Render("Next steps"))
	b.WriteString("\n")
	for _, step := range nextStepsFor(data) {
		b.WriteString(theme.UnselectedStyle.Render("  " + step))
		b.WriteString("\n")
	}
	b.WriteString("\n")

	if data.Footer != "" {
		b.WriteString(theme.HelpStyle.Render(data.Footer))
	}

	return b.String()
}

func nextStepsFor(data CompletePayload) []string {
	if len(data.NextSteps) > 0 {
		return data.NextSteps
	}
	return defaultNextSteps
}

func renderManualActions(b *strings.Builder, actions []string) {
	if len(actions) == 0 {
		return
	}
	b.WriteString(theme.WarningStyle.Render("Manual actions required"))
	b.WriteString("\n")
	for _, action := range actions {
		b.WriteString("  " + theme.WarningStyle.Render(action) + "\n")
	}
	b.WriteString("\n")
}

func renderMissingDeps(b *strings.Builder, deps []MissingDep) {
	if len(deps) == 0 {
		return
	}

	b.WriteString(theme.WarningStyle.Render(fmt.Sprintf("Missing %d dependency(ies):", len(deps))))
	b.WriteString("\n")
	for _, dep := range deps {
		b.WriteString("  " + theme.WarningStyle.Render(dep.Name) + "  " + theme.SubtextStyle.Render(dep.InstallHint))
		b.WriteString("\n")
	}
	b.WriteString("\n")
}

func renderCompleteFailed(data CompletePayload) string {
	var b strings.Builder

	b.WriteString("\n")
	b.WriteString(theme.ErrorStyle.Render("Installation completed with errors."))
	b.WriteString("\n\n")

	b.WriteString(theme.HeadingStyle.Render("Failed steps"))
	b.WriteString("\n")
	for _, step := range data.FailedSteps {
		b.WriteString("  " + theme.ErrorStyle.Render("✗ "+step.ID))
		b.WriteString("\n")
		lines := strings.Split(step.Error, "\n")
		if len(lines) > maxErrorLines {
			lines = lines[:maxErrorLines]
			lines = append(lines, "... (truncated)")
		}
		for _, line := range lines {
			b.WriteString("    " + theme.SubtextStyle.Render(line))
			b.WriteString("\n")
		}
	}
	b.WriteString("\n")

	if data.RollbackPerformed {
		message := "Rollback completed — previous configuration restored."
		if !data.RollbackComplete {
			message = "Rollback partially completed — manual recovery may be required."
		}
		b.WriteString(theme.WarningStyle.Render(message))
		b.WriteString("\n\n")
	}

	renderManualActions(&b, data.ManualActions)
	renderMissingDeps(&b, data.MissingDeps)

	steps := data.NextSteps
	if len(steps) == 0 {
		steps = []string{
			"1. Revisá los mensajes de error anteriores",
			"2. Corregí la causa (dependencias faltantes, permisos, rutas)",
			"3. Volvé a correr 'quantlab install' para reintentar",
		}
	}
	b.WriteString(theme.HeadingStyle.Render("What to do"))
	b.WriteString("\n")
	for _, step := range steps {
		b.WriteString(theme.UnselectedStyle.Render("  " + step))
		b.WriteString("\n")
	}
	b.WriteString("\n")

	if data.Footer != "" {
		b.WriteString(theme.HelpStyle.Render(data.Footer))
	}

	return b.String()
}

func renderCompleteChecklist(b *strings.Builder, items []CompleteCheckItem) {
	if len(items) == 0 {
		return
	}
	b.WriteString(theme.HeadingStyle.Render("Checklist"))
	b.WriteString("\n")
	for _, it := range items {
		icon := "✓"
		style := theme.SuccessStyle
		if !it.Done {
			icon = "○"
			style = theme.SubtextStyle
		}
		b.WriteString("  " + style.Render(icon) + " " + theme.UnselectedStyle.Render(it.Label))
		b.WriteString("\n")
	}
	b.WriteString("\n")
}
