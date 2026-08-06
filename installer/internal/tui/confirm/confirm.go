// Package confirm provides a simple yes/no confirmation dialog using
// Bubbletea TUI.
package confirm

import (
	"fmt"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
)

// ConfirmModel implements a yes/no confirmation prompt with keyboard
// navigation (tab/arrows to switch, enter to confirm).
type ConfirmModel struct {
	Prompt    string
	Selected  bool // true = Yes (default), false = No
	Confirmed bool
	Quitting  bool
}

// NewConfirmModel creates a confirm dialog with the given prompt text.
func NewConfirmModel(prompt string) ConfirmModel {
	return ConfirmModel{
		Prompt:   prompt,
		Selected: true, // default to Yes
	}
}

func (m ConfirmModel) Init() tea.Cmd { return nil }

func (m ConfirmModel) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.KeyMsg:
		switch msg.String() {
		case "ctrl+c", "q", "esc":
			m.Quitting = true
			return m, tea.Quit
		case "left", "right", "tab", "shift+tab":
			m.Selected = !m.Selected
			return m, nil
		case "enter":
			m.Confirmed = true
			return m, tea.Quit
		}
	}
	return m, nil
}

func (m ConfirmModel) View() string {
	if m.Quitting {
		return ""
	}

	yesStyle := lipgloss.NewStyle().Padding(0, 3)
	noStyle := lipgloss.NewStyle().Padding(0, 3)
	mutedStyle := lipgloss.NewStyle().Foreground(lipgloss.Color("245"))

	if m.Selected {
		yesStyle = yesStyle.
			Background(lipgloss.Color("39")).
			Foreground(lipgloss.Color("0")).
			Bold(true)
		noStyle = noStyle.Foreground(lipgloss.Color("245"))
	} else {
		noStyle = noStyle.
			Background(lipgloss.Color("39")).
			Foreground(lipgloss.Color("0")).
			Bold(true)
		yesStyle = yesStyle.Foreground(lipgloss.Color("245"))
	}

	s := fmt.Sprintf("\n  %s\n\n", m.Prompt)
	s += fmt.Sprintf("  %s  %s\n\n", yesStyle.Render("Yes"), noStyle.Render("No"))
	s += mutedStyle.Render("  tab/arrows to switch · enter to confirm · esc to cancel")
	s += "\n"

	return s
}

// RunConfirm starts a Bubbletea program with a yes/no confirmation prompt.
// Returns true if the user selected Yes, false for No or if they cancelled.
func RunConfirm(prompt string) (bool, error) {
	p := tea.NewProgram(NewConfirmModel(prompt))
	final, err := p.Run()
	if err != nil {
		return false, err
	}

	m, ok := final.(ConfirmModel)
	if !ok {
		return false, fmt.Errorf("unexpected model type: %T", final)
	}

	if m.Quitting || !m.Confirmed {
		return false, nil
	}

	return m.Selected, nil
}
