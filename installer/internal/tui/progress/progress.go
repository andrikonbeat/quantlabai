// Package progress provides a multi-step progress tracker for pipeline
// operations during QuantLab installation and uninstallation.
package progress

import (
	"fmt"
	"strings"

	"github.com/charmbracelet/bubbles/progress"
	"github.com/charmbracelet/lipgloss"
)

// ProgressStep defines a single step in a multi-step operation.
type ProgressStep struct {
	// Message is displayed for this step.
	Message string
}

// ProgressTracker tracks progress through a series of steps with a
// visual progress bar.
type ProgressTracker struct {
	Steps   []ProgressStep
	Current int
	Done    bool
	err     error
	bar     progress.Model
}

// NewProgress creates a ProgressTracker for the given steps.
func NewProgress(steps []ProgressStep) *ProgressTracker {
	p := progress.New(
		progress.WithDefaultGradient(),
		progress.WithWidth(50),
	)
	p.FullColor = lipgloss.Color("37")   // teal
	p.EmptyColor = lipgloss.Color("240") // dark grey
	return &ProgressTracker{
		Steps:   steps,
		Current: 0,
		bar:     p,
	}
}

// Next advances to the next step. Returns false if already at the end.
func (pt *ProgressTracker) Next() bool {
	if pt.Current >= len(pt.Steps) {
		return false
	}
	pt.Current++
	if pt.Current >= len(pt.Steps) {
		pt.Done = true
	}
	return true
}

// Percent returns the completion ratio as a float between 0 and 1.
func (pt *ProgressTracker) Percent() float64 {
	if len(pt.Steps) == 0 {
		return 1.0
	}
	return float64(pt.Current) / float64(len(pt.Steps))
}

// CurrentMessage returns the message for the current step, or empty
// string if all steps are complete.
func (pt *ProgressTracker) CurrentMessage() string {
	if pt.Current >= len(pt.Steps) {
		return ""
	}
	return pt.Steps[pt.Current].Message
}

// ProgressMessage returns a human-readable progress string like
// "Step 2/5: Installing SDK... [========            ] 40%".
func (pt *ProgressTracker) ProgressMessage() string {
	var b strings.Builder
	if !pt.Done {
		b.WriteString(fmt.Sprintf("Step %d/%d: %s\n",
			pt.Current+1, len(pt.Steps), pt.CurrentMessage()))
	} else {
		b.WriteString(fmt.Sprintf("Complete (%d steps)\n", len(pt.Steps)))
	}
	b.WriteString(pt.bar.ViewAs(pt.Percent()))
	return b.String()
}
