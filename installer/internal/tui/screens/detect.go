package screens

import (
	"fmt"
	"strings"

	"github.com/andrikonbeat/quantlabai/internal/tui/theme"
)

// CheckItem is one line of an environment verification checklist.
//
// Optional items are rendered with a "(optional)" suffix; an optional item
// that is not OK reads as an advisory warning (⚠) and is not counted as a
// blocking failure.
type CheckItem struct {
	Label    string
	OK       bool
	Note     string
	Optional bool
}

// RenderDetection renders the QuantLab verification checklist: title, one
// marked line per check, any failure/optional callout, the supplied notes and
// a standardised footer. It is a pure renderer — it detects nothing.
func RenderDetection(title string, items []CheckItem, notes []string, footer string) string {
	var b strings.Builder

	b.WriteString(theme.TitleStyle.Render(title))
	b.WriteString("\n\n")

	missing := 0
	for _, item := range items {
		mark := theme.ErrorStyle.Render("✗")
		switch {
		case item.OK:
			mark = theme.SuccessStyle.Render("✓")
		case item.Optional:
			mark = theme.WarningStyle.Render("⚠")
		default:
			missing++
		}

		label := item.Label
		if item.Note != "" {
			label += " — " + item.Note
		}
		if item.Optional {
			label += theme.SubtextStyle.Render(" (optional)")
		}

		b.WriteString("  " + mark + " " + theme.UnselectedStyle.Render(label))
		b.WriteString("\n")
	}

	if missing > 0 {
		b.WriteString("\n")
		b.WriteString(theme.WarningStyle.Render(
			fmt.Sprintf("Faltan %d verificación(es) — completalas antes de continuar.", missing)))
		b.WriteString("\n")
	}
	b.WriteString("\n")

	for _, note := range notes {
		b.WriteString(theme.WarningStyle.Render(note))
		b.WriteString("\n")
	}
	if len(notes) > 0 {
		b.WriteString("\n")
	}

	if footer != "" {
		b.WriteString(theme.HelpStyle.Render(footer))
	}

	return b.String()
}



// renderChecklist renders an optional status checklist on the close-out
// screen. Items that are not OK are drawn as warnings.
func renderChecklist(b *strings.Builder, items []CheckItem) {
	if len(items) == 0 {
		return
	}

	b.WriteString(theme.HeadingStyle.Render("Post-install checklist"))
	b.WriteString("\n")
	for _, item := range items {
		mark := theme.WarningStyle.Render("☐")
		if item.OK {
			mark = theme.SuccessStyle.Render("✓")
		}
		label := item.Label
		if item.Note != "" {
			label += " — " + item.Note
		}
		b.WriteString("  " + mark + " " + theme.UnselectedStyle.Render(label))
		b.WriteString("\n")
	}
	b.WriteString("\n")
}