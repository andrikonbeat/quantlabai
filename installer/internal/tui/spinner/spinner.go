// Package spinner provides an async spinner component for Bubbletea TUI.
// It runs a function with a visual spinner and shows success/failure on
// completion.
package spinner

import (
	"fmt"

	"github.com/charmbracelet/bubbles/spinner"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
)

type errMsg struct{ error }
type doneMsg struct{}

// model implements tea.Model for the spinner view.
type model struct {
	spinner  spinner.Model
	msg      string
	done     bool
	err      error
	quitting bool
}

// NewModel creates a spinner model with the given status message.
func NewModel(msg string) model {
	s := spinner.New()
	s.Style = lipgloss.NewStyle().Foreground(lipgloss.Color("37")) // teal
	s.Spinner = spinner.Dot
	return model{
		spinner: s,
		msg:     msg,
	}
}

func (m model) Init() tea.Cmd {
	return m.spinner.Tick
}

func (m model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.KeyMsg:
		if msg.String() == "ctrl+c" {
			m.quitting = true
			return m, tea.Quit
		}
		return m, nil

	case errMsg:
		m.done = true
		m.err = msg
		return m, tea.Quit

	case doneMsg:
		m.done = true
		return m, tea.Quit

	default:
		var cmd tea.Cmd
		m.spinner, cmd = m.spinner.Update(msg)
		return m, cmd
	}
}

func (m model) View() string {
	if m.quitting {
		return ""
	}
	if m.done {
		if m.err != nil {
			return fmt.Sprintf("✗ %s: %v\n", m.msg, m.err)
		}
		return fmt.Sprintf("✓ %s\n", m.msg)
	}
	return fmt.Sprintf("%s %s", m.spinner.View(), m.msg)
}

// RunWithSpinner displays a spinner with the given message while fn runs
// in the background. Returns fn's error or nil.
func RunWithSpinner(msg string, fn func() error) error {
	p := tea.NewProgram(NewModel(msg))

	go func() {
		if err := fn(); err != nil {
			p.Send(errMsg{err})
		} else {
			p.Send(doneMsg{})
		}
	}()

	m, err := p.Run()
	if err != nil {
		return err
	}

	if m, ok := m.(model); ok && m.err != nil {
		return m.err
	}

	return nil
}
