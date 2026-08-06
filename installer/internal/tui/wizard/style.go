// Package wizard provides a Bubbletea TUI for collecting QuantLab SDK
// configuration (API key, model, SDK path) during first-run setup.
package wizard

import "github.com/charmbracelet/lipgloss"

// QuantLab colour palette:
//   Teal/Cyan:  #00B4D8 (37)
//   Blue:       #0077B6 (39)
//   Dark bg:    #1A1A2E
//   Accent:     #00B4D8

var (
	// TitleStyle is used for step headings and the welcome title.
	TitleStyle = lipgloss.NewStyle().
			Bold(true).
			Foreground(lipgloss.Color("37")).
			Padding(0, 1)

	// SubtitleStyle is used for descriptive text and instructions.
	SubtitleStyle = lipgloss.NewStyle().
			Foreground(lipgloss.Color("251")).
			Padding(0, 1)

	// FocusStyle highlights the active element or primary action.
	FocusStyle = lipgloss.NewStyle().
			Foreground(lipgloss.Color("39")).
			Bold(true)

	// BlurStyle is used for inactive or unfocused elements.
	BlurStyle = lipgloss.NewStyle().
			Foreground(lipgloss.Color("245"))

	// ErrorStyle highlights validation errors.
	ErrorStyle = lipgloss.NewStyle().
			Foreground(lipgloss.Color("196")).
			Bold(true)

	// SuccessStyle indicates a successful operation.
	SuccessStyle = lipgloss.NewStyle().
			Foreground(lipgloss.Color("42"))

	// HeaderStyle is used for section headers.
	HeaderStyle = lipgloss.NewStyle().
			Bold(true).
			Foreground(lipgloss.Color("37")).
			Padding(0, 1).
			MarginBottom(1)

	// BoxStyle wraps content in a rounded border with teal accent.
	BoxStyle = lipgloss.NewStyle().
			Border(lipgloss.RoundedBorder()).
			BorderForeground(lipgloss.Color("37")).
			Padding(1, 2)

	// LabelStyle is used for field labels in the summary.
	LabelStyle = lipgloss.NewStyle().
			Foreground(lipgloss.Color("251"))

	// ValueStyle is used for field values in the summary.
	ValueStyle = lipgloss.NewStyle().
			Foreground(lipgloss.Color("15"))
)
