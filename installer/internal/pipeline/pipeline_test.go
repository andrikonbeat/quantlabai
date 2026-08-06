package pipeline_test

import (
	"errors"
	"testing"

	"github.com/ogzuz/quantlab/internal/pipeline"
)

// testStep is a basic step that records whether it ran
type testStep struct {
	id      string
	runErr  error
	ran     bool
}

func (s *testStep) ID() string          { return s.id }
func (s *testStep) Run() error {
	s.ran = true
	return s.runErr
}

// testRollbackStep implements RollbackStep
type testRollbackStep struct {
	id         string
	runErr     error
	rollbackErr error
	ran        bool
	rolledBack bool
}

func (s *testRollbackStep) ID() string            { return s.id }
func (s *testRollbackStep) Run() error {
	s.ran = true
	return s.runErr
}
func (s *testRollbackStep) Rollback() error {
	s.rolledBack = true
	return s.rollbackErr
}

func TestRun_AllStepsSucceed(t *testing.T) {
	prepare := []pipeline.Step{&testStep{id: "p1"}, &testStep{id: "p2"}}
	apply := []pipeline.Step{&testStep{id: "a1"}, &testStep{id: "a2"}}

	plan := pipeline.StagePlan{
		Prepare: prepare,
		Apply:   apply,
	}

	err := pipeline.Run(plan, nil)
	if err != nil {
		t.Fatalf("Run() = %v, want nil", err)
	}

	for _, s := range prepare {
		if !s.(*testStep).ran {
			t.Errorf("prepare step %q did not run", s.ID())
		}
	}
	for _, s := range apply {
		if !s.(*testStep).ran {
			t.Errorf("apply step %q did not run", s.ID())
		}
	}
}

func TestRun_PrepareStepFails(t *testing.T) {
	prepare := []pipeline.Step{
		&testStep{id: "p1"},
		&testStep{id: "p2", runErr: errors.New("prepare failed")},
		&testStep{id: "p3"},
	}
	apply := []pipeline.Step{&testStep{id: "a1"}}

	plan := pipeline.StagePlan{
		Prepare: prepare,
		Apply:   apply,
	}

	err := pipeline.Run(plan, nil)
	if err == nil {
		t.Fatal("Run() = nil, want error")
	}

	if !prepare[0].(*testStep).ran {
		t.Error("prepare step 1 should have run")
	}
	if prepare[2].(*testStep).ran {
		t.Error("prepare step 3 should NOT have run (blocked by step 2 failure)")
	}
}

func TestRun_ApplyStepFails_RollsBack(t *testing.T) {
	rb1 := &testRollbackStep{id: "rb1"}
	rb2 := &testRollbackStep{id: "rb2"}
	failStep := &testRollbackStep{id: "fail", runErr: errors.New("apply failed")}
	rb3 := &testRollbackStep{id: "rb3"} // should not run

	plan := pipeline.StagePlan{
		Apply: []pipeline.Step{rb1, rb2, failStep, rb3},
	}

	err := pipeline.Run(plan, nil)
	if err == nil {
		t.Fatal("Run() = nil, want error")
	}

	if !rb1.ran {
		t.Error("rb1 should have ran")
	}
	if !rb2.ran {
		t.Error("rb2 should have ran")
	}
	if !failStep.ran {
		t.Error("failStep should have ran")
	}
	if rb3.ran {
		t.Error("rb3 should NOT have ran (after failure)")
	}

	// Rollback should happen in reverse order: rb2 then rb1
	if !rb2.rolledBack {
		t.Error("rb2 should have been rolled back")
	}
	if !rb1.rolledBack {
		t.Error("rb1 should have been rolled back")
	}
}

func TestRun_ProgressEvents(t *testing.T) {
	var events []pipeline.ProgressEvent

	progress := func(e pipeline.ProgressEvent) {
		events = append(events, e)
	}

	plan := pipeline.StagePlan{
		Prepare: []pipeline.Step{&testStep{id: "prep1"}, &testStep{id: "prep2"}},
		Apply:   []pipeline.Step{&testStep{id: "apply1"}},
	}

	if err := pipeline.Run(plan, progress); err != nil {
		t.Fatalf("Run() = %v, want nil", err)
	}

	// Expect: prep1 running, prep1 completed, prep2 running, prep2 completed,
	//         apply1 running, apply1 completed = 6 events
	if len(events) != 6 {
		t.Fatalf("got %d progress events, want 6", len(events))
	}

	// Check first event
	if events[0].Stage != pipeline.StagePrepare {
		t.Errorf("event[0].Stage = %v, want prepare", events[0].Stage)
	}
	if events[0].StepID != "prep1" {
		t.Errorf("event[0].StepID = %q, want %q", events[0].StepID, "prep1")
	}
	if events[0].Status != "running" {
		t.Errorf("event[0].Status = %q, want %q", events[0].Status, "running")
	}

	// Check completed event
	if events[1].Status != "completed" {
		t.Errorf("event[1].Status = %q, want %q", events[1].Status, "completed")
	}
	if events[1].Completed != 1 {
		t.Errorf("event[1].Completed = %d, want 1", events[1].Completed)
	}
}

func TestRun_ApplyWithProgressAndRollback(t *testing.T) {
	var events []pipeline.ProgressEvent
	progress := func(e pipeline.ProgressEvent) {
		events = append(events, e)
	}

	rb1 := &testRollbackStep{id: "safe1"}
	failStep := &testRollbackStep{id: "will-fail", runErr: errors.New("boom")}

	plan := pipeline.StagePlan{
		Apply: []pipeline.Step{rb1, failStep},
	}

	err := pipeline.Run(plan, progress)
	if err == nil {
		t.Fatal("Run() = nil, want error")
	}

	// Should have: safe1 running, safe1 completed, will-fail running, will-fail failed,
	//              safe1 rollback running, safe1 rollback completed = 6 events
	if len(events) < 5 {
		t.Fatalf("got %d events, want >= 5 (should include rollback events)", len(events))
	}

	// Check that the rollback event was emitted
	hasRollback := false
	for _, e := range events {
		if e.Stage == pipeline.StageRollback {
			hasRollback = true
			break
		}
	}
	if !hasRollback {
		t.Error("expected at least one rollback progress event, got none")
	}

	// Verify rollback actually ran
	if !rb1.rolledBack {
		t.Error("rb1 should have been rolled back")
	}
}

func TestRun_ProgressTotalCounts(t *testing.T) {
	var events []pipeline.ProgressEvent
	progress := func(e pipeline.ProgressEvent) {
		events = append(events, e)
	}

	prepSteps := []pipeline.Step{&testStep{id: "p1"}, &testStep{id: "p2"}, &testStep{id: "p3"}}
	applySteps := []pipeline.Step{&testStep{id: "a1"}}

	plan := pipeline.StagePlan{
		Prepare: prepSteps,
		Apply:   applySteps,
	}

	if err := pipeline.Run(plan, progress); err != nil {
		t.Fatalf("Run() = %v, want nil", err)
	}

	// Check Total values
	for _, e := range events {
		if e.Stage == pipeline.StagePrepare && e.Total != 3 {
			t.Errorf("prepare event Total = %d, want 3 (step %q)", e.Total, e.StepID)
		}
		if e.Stage == pipeline.StageApply && e.Total != 1 {
			t.Errorf("apply event Total = %d, want 1 (step %q)", e.Total, e.StepID)
		}
	}
}
