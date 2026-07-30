package progress

import (
	"testing"
)

func TestNewProgress(t *testing.T) {
	steps := []ProgressStep{
		{Message: "Step 1"},
		{Message: "Step 2"},
		{Message: "Step 3"},
	}
	pt := NewProgress(steps)
	if pt == nil {
		t.Fatal("NewProgress returned nil")
	}
	if pt.Current != 0 {
		t.Fatalf("Current = %d, want 0", pt.Current)
	}
	if pt.Done {
		t.Fatal("New progress should not be done")
	}
}

func TestNext(t *testing.T) {
	steps := []ProgressStep{
		{Message: "A"},
		{Message: "B"},
	}
	pt := NewProgress(steps)

	if !pt.Next() {
		t.Fatal("Next() should return true for step 1")
	}
	if pt.Current != 1 {
		t.Fatalf("Current = %d, want 1", pt.Current)
	}

	if !pt.Next() {
		t.Fatal("Next() should return true for step 2")
	}
	if pt.Current != 2 {
		t.Fatalf("Current = %d, want 2", pt.Current)
	}
	if !pt.Done {
		t.Fatal("Should be done after last step")
	}

	if pt.Next() {
		t.Fatal("Next() should return false after all steps")
	}
}

func TestPercent(t *testing.T) {
	steps := []ProgressStep{
		{Message: "1"},
		{Message: "2"},
		{Message: "3"},
		{Message: "4"},
	}
	pt := NewProgress(steps)

	if pt.Percent() != 0.0 {
		t.Fatalf("initial Percent = %f, want 0", pt.Percent())
	}

	pt.Next()
	if pt.Percent() != 0.25 {
		t.Fatalf("after 1 step Percent = %f, want 0.25", pt.Percent())
	}

	pt.Next()
	pt.Next()
	if pt.Percent() != 0.75 {
		t.Fatalf("after 3 steps Percent = %f, want 0.75", pt.Percent())
	}
}

func TestPercent_NoSteps(t *testing.T) {
	pt := NewProgress([]ProgressStep{})
	if pt.Percent() != 1.0 {
		t.Fatalf("Percent for empty steps = %f, want 1.0", pt.Percent())
	}
}

func TestCurrentMessage(t *testing.T) {
	steps := []ProgressStep{
		{Message: "First"},
		{Message: "Second"},
	}
	pt := NewProgress(steps)
	if msg := pt.CurrentMessage(); msg != "First" {
		t.Fatalf("CurrentMessage = %q, want First", msg)
	}

	pt.Next()
	if msg := pt.CurrentMessage(); msg != "Second" {
		t.Fatalf("CurrentMessage = %q, want Second", msg)
	}

	pt.Next()
	if msg := pt.CurrentMessage(); msg != "" {
		t.Fatalf("CurrentMessage after done = %q, want empty", msg)
	}
}

func TestProgressMessage(t *testing.T) {
	steps := []ProgressStep{
		{Message: "Test"},
	}
	pt := NewProgress(steps)

	msg := pt.ProgressMessage()
	if len(msg) == 0 {
		t.Fatal("ProgressMessage() returned empty")
	}
}

func TestProgressMessage_Complete(t *testing.T) {
	steps := []ProgressStep{
		{Message: "Only"},
	}
	pt := NewProgress(steps)
	pt.Next()
	pt.Done = true

	msg := pt.ProgressMessage()
	if len(msg) == 0 {
		t.Fatal("ProgressMessage() after done returned empty")
	}
}
