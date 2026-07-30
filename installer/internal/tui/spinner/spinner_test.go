package spinner

import (
	"errors"
	"testing"

	tea "github.com/charmbracelet/bubbletea"
)

func TestNewModel(t *testing.T) {
	m := NewModel("Testing...")
	if m.msg != "Testing..." {
		t.Fatalf("msg = %q, want Testing...", m.msg)
	}
	if m.done {
		t.Fatal("new model should not be done")
	}
}

func TestModel_Init(t *testing.T) {
	m := NewModel("test")
	cmd := m.Init()
	if cmd == nil {
		t.Fatal("Init() should return a command (spinner.Tick)")
	}
}

func TestModel_UpdateKeyMsg(t *testing.T) {
	m := NewModel("test")
	updated, cmd := m.Update(tea.KeyMsg{})
	if cmd != nil {
		t.Fatal("unexpected cmd for generic key msg")
	}
	if _, ok := updated.(model); !ok {
		t.Fatal("Update returned wrong type")
	}
}

func TestModel_UpdateCtrlC(t *testing.T) {
	m := NewModel("test")
	updated, cmd := m.Update(tea.KeyMsg{
		Type:  tea.KeyRunes,
		Runes: []rune{'c'},
	})
	if updated.(model).quitting {
		t.Fatal("just 'c' should not quit")
	}
	_ = cmd
}

func TestModel_QuitOnCtrlC(t *testing.T) {
	// Send an actual ctrl+c message
	m := NewModel("test")
	updated, cmd := m.Update(tea.KeyMsg{
		Type:  tea.KeyCtrlC,
		String: "ctrl+c",
	})
	if !updated.(model).quitting {
		t.Fatal("ctrl+c should set quitting")
	}
	if cmd != tea.Quit {
		t.Fatalf("expected tea.Quit, got %v", cmd)
	}
}

func TestModel_ViewRunning(t *testing.T) {
	m := NewModel("Working...")
	view := m.View()
	// Should contain the message
	if len(view) == 0 {
		t.Fatal("View() returned empty for running state")
	}
}

func TestModel_ViewDone(t *testing.T) {
	m := NewModel("Done!")
	m.done = true
	view := m.View()
	if len(view) == 0 {
		t.Fatal("View() returned empty for done state")
	}
}

func TestModel_ViewDoneError(t *testing.T) {
	m := NewModel("Failed!")
	m.done = true
	m.err = errors.New("oops")
	view := m.View()
	if len(view) == 0 {
		t.Fatal("View() returned empty for error state")
	}
}
