package installing

import (
	"errors"
	"strings"
	"testing"

	tea "github.com/charmbracelet/bubbletea"

	"github.com/andrikonbeat/quantlabai/internal/pipeline"
)

func testPlan() pipeline.StagePlan {
	return pipeline.StagePlan{
		Prepare: []pipeline.Step{
			&fakeStep{id: "Prepare A"},
		},
		Apply: []pipeline.Step{
			&fakeStep{id: "Apply B"},
			&fakeStep{id: "Apply C"},
		},
	}
}

func errBoom() error { return errors.New("boom") }

type fakeStep struct{ id string }

func (f *fakeStep) ID() string { return f.id }
func (f *fakeStep) Run() error { return nil }

func send(m Model, msg tea.Msg) Model {
	updated, _ := m.Update(msg)
	mm, ok := updated.(Model)
	if !ok {
		panic("Update did not return installing.Model")
	}
	return mm
}

func TestNewModel_AllPending(t *testing.T) {
	m := NewModel(testPlan(), 6, 5)
	if len(m.items) != 3 {
		t.Fatalf("want 3 items, got %d", len(m.items))
	}
	if m.Percent() != 0 {
		t.Fatalf("want 0%%, got %d", m.Percent())
	}
	if m.Done() || m.Failed() {
		t.Fatal("fresh model must not be done/failed")
	}
}

func TestProgressMapping(t *testing.T) {
	m := NewModel(testPlan(), 0, 0)

	m = send(m, StepProgressMsg{Stage: pipeline.StageApply, StepID: "Apply B", Status: "running"})
	if m.items[1].Status != StatusRunning {
		t.Fatalf("want running, got %q", m.items[1].Status)
	}

	m = send(m, StepProgressMsg{Stage: pipeline.StageApply, StepID: "Apply B", Status: "completed"})
	if m.items[1].Status != StatusSucceeded {
		t.Fatalf("want succeeded, got %q", m.items[1].Status)
	}
	if got := m.Percent(); got != 33 {
		t.Fatalf("want 33%%, got %d", got)
	}

	m = send(m, StepProgressMsg{Stage: pipeline.StageRollback, StepID: "Apply B", Status: "completed"})
	if m.items[1].Status != StatusRolledBack {
		t.Fatalf("want rolled-back, got %q", m.items[1].Status)
	}
}

func TestPipelineDone_SuccessPayload(t *testing.T) {
	m := NewModel(testPlan(), 6, 5)
	m = send(m, StepProgressMsg{Stage: pipeline.StageApply, StepID: "Apply B", Status: "completed"})
	m = send(m, PipelineDoneMsg{Err: nil})

	if !m.Done() || m.Failed() {
		t.Fatal("want done && !failed")
	}
	payload, err := m.Result()
	if err != nil {
		t.Fatalf("want nil error, got %v", err)
	}
	if payload.ConfiguredAgents != 6 || payload.InstalledComponents != 5 {
		t.Fatalf("counts lost: %+v", payload)
	}
	view := m.View()
	if !strings.Contains(view, "Done!") {
		t.Fatalf("complete view missing success headline:\n%s", view)
	}
}

func TestPipelineDone_FailurePayload(t *testing.T) {
	m := NewModel(testPlan(), 0, 0)
	m = send(m, StepProgressMsg{Stage: pipeline.StageApply, StepID: "Apply C", Status: "failed", Err: errBoom()})
	m = send(m, PipelineDoneMsg{Err: errBoom()})

	if !m.Done() || !m.Failed() {
		t.Fatal("want done && failed")
	}
	payload, err := m.Result()
	if err == nil {
		t.Fatal("want pipeline error back")
	}
	if len(payload.FailedSteps) != 1 || payload.FailedSteps[0].ID != "Apply C" {
		t.Fatalf("failed steps wrong: %+v", payload.FailedSteps)
	}
	if !payload.RollbackPerformed || !payload.RollbackComplete {
		t.Fatal("apply-stage failure must report rollback performed+complete")
	}
	view := m.View()
	if !strings.Contains(view, "completed with errors") {
		t.Fatalf("complete view missing failure headline:\n%s", view)
	}
}

func TestEnterSwallowedWhileRunning(t *testing.T) {
	m := NewModel(testPlan(), 0, 0)
	_, cmd := m.Update(tea.KeyMsg(tea.Key{Type: tea.KeyEnter}))
	if cmd != nil {
		t.Fatal("Enter while running must not quit (would hide half-applied install)")
	}
	m = send(m, PipelineDoneMsg{Err: nil})
	_, cmd = m.Update(tea.KeyMsg(tea.Key{Type: tea.KeyEnter}))
	if cmd == nil {
		t.Fatal("Enter when done must quit")
	}
}

func TestViewInstalling_ShowsBarAndSteps(t *testing.T) {
	m := NewModel(testPlan(), 0, 0)
	m = send(m, StepProgressMsg{Stage: pipeline.StageApply, StepID: "Apply B", Status: "running"})
	view := m.View()
	for _, want := range []string{"Installing", "Apply B", "Prepare A", "%"} {
		if !strings.Contains(view, want) {
			t.Fatalf("installing view missing %q:\n%s", want, view)
		}
	}
}
