package confirm

import (
	"testing"

	tea "github.com/charmbracelet/bubbletea"
)

// isQuitCmd reports whether cmd is bubbletea's quit command. In
// bubbletea v1.3.4 tea.Quit is a Cmd (a func), which can only be
// compared to nil, so the command is invoked and its resulting
// QuitMsg is asserted instead.
func isQuitCmd(cmd tea.Cmd) bool {
	if cmd == nil {
		return false
	}
	msg := cmd()
	if msg == nil {
		return false
	}
	_, ok := msg.(tea.QuitMsg)
	return ok
}

func TestNewConfirmModel(t *testing.T) {
	m := NewConfirmModel("Are you sure?")
	if m.Prompt != "Are you sure?" {
		t.Fatalf("Prompt = %q", m.Prompt)
	}
	if !m.Selected {
		t.Fatal("default should be Yes (true)")
	}
	if m.Confirmed {
		t.Fatal("new model should not be confirmed")
	}
}

func TestConfirmModel_Init(t *testing.T) {
	m := NewConfirmModel("test")
	cmd := m.Init()
	if cmd != nil {
		t.Fatal("Init() should return nil")
	}
}

func TestConfirmModel_SelectYes(t *testing.T) {
	m := NewConfirmModel("test")
	m.Selected = true // default

	updated, cmd := m.Update(tea.KeyMsg(tea.Key{Type: tea.KeyEnter}))

	newM := updated.(ConfirmModel)
	if !newM.Confirmed {
		t.Fatal("enter should confirm")
	}
	if !isQuitCmd(cmd) {
		t.Fatalf("expected tea.Quit, got %v", cmd)
	}
}

func TestConfirmModel_ToggleSelection(t *testing.T) {
	m := NewConfirmModel("test")

	// Tab toggles
	updated, _ := m.Update(tea.KeyMsg(tea.Key{Type: tea.KeyTab}))
	newM := updated.(ConfirmModel)
	if newM.Selected {
		t.Fatal("tab should toggle to No")
	}

	// Tab again
	updated, _ = newM.Update(tea.KeyMsg(tea.Key{Type: tea.KeyTab}))
	newM2 := updated.(ConfirmModel)
	if !newM2.Selected {
		t.Fatal("second tab should toggle back to Yes")
	}
}

func TestConfirmModel_ArrowKeys(t *testing.T) {
	m := NewConfirmModel("test")

	// Left toggles to No
	updated, _ := m.Update(tea.KeyMsg(tea.Key{Type: tea.KeyLeft}))
	newM := updated.(ConfirmModel)
	if newM.Selected {
		t.Fatal("left should toggle to No")
	}

	// Right toggles to Yes
	updated, _ = newM.Update(tea.KeyMsg(tea.Key{Type: tea.KeyRight}))
	newM2 := updated.(ConfirmModel)
	if !newM2.Selected {
		t.Fatal("right should toggle to Yes")
	}
}

func TestConfirmModel_Quit(t *testing.T) {
	m := NewConfirmModel("test")

	updated, cmd := m.Update(tea.KeyMsg(tea.Key{Type: tea.KeyRunes, Runes: []rune("q")}))
	newM := updated.(ConfirmModel)
	if !newM.Quitting {
		t.Fatal("q should set quitting")
	}
	if !isQuitCmd(cmd) {
		t.Fatalf("expected tea.Quit, got %v", cmd)
	}
}

func TestConfirmModel_Escape(t *testing.T) {
	m := NewConfirmModel("test")

	updated, _ := m.Update(tea.KeyMsg(tea.Key{Type: tea.KeyEsc}))
	if !updated.(ConfirmModel).Quitting {
		t.Fatal("esc should set quitting")
	}
}

func TestConfirmModel_EnterNo(t *testing.T) {
	m := NewConfirmModel("test")
	m.Selected = false // No selected

	updated, _ := m.Update(tea.KeyMsg(tea.Key{Type: tea.KeyEnter}))
	newM := updated.(ConfirmModel)
	if !newM.Confirmed {
		t.Fatal("enter with No selected should still confirm")
	}
}

func TestConfirmModel_View(t *testing.T) {
	m := NewConfirmModel("Test prompt?")
	view := m.View()
	if len(view) == 0 {
		t.Fatal("View() returned empty")
	}
}

func TestConfirmModel_ViewQuitting(t *testing.T) {
	m := NewConfirmModel("test")
	m.Quitting = true
	view := m.View()
	if view != "" {
		t.Fatal("View() should be empty when quitting")
	}
}
