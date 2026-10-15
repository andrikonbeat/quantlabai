// Package installing runs the install pipeline inside the TUI so the user
// watches every step land live — progress bar, per-step marks, trailing
// logs — instead of staring at a frozen screen.
//
// The pipeline itself runs in a goroutine owned by the caller (see
// internal/app/install.go): it publishes StepProgressMsg per state change
// and one PipelineDoneMsg at the end. This model only reduces messages into
// view state. The async-runner pattern is adapted from the gentle-ai
// reference TUI (https://github.com/Gentleman-Programming/gentle-ai,
// MIT © 2025 Gentleman Programming); the payload copy is QuantLab's own.
package installing

import (
	"strings"
	"time"

	tea "github.com/charmbracelet/bubbletea"

	"github.com/andrikonbeat/quantlabai/internal/pipeline"
	"github.com/andrikonbeat/quantlabai/internal/tui/screens"
)

// StepProgressMsg carries one pipeline state change into the TUI.
type StepProgressMsg struct {
	Stage  pipeline.Stage
	StepID string
	// Status is "running", "completed" or "failed" (pipeline.ProgressEvent).
	Status string
	Err    error
}

// PipelineDoneMsg ends the run. Err is the pipeline.Run error (nil on
// success); rollback already happened inside the pipeline.
type PipelineDoneMsg struct {
	Err error
}

// TickMsg drives the spinner while steps run.
type TickMsg time.Time

// Item statuses rendered by screens.RenderInstalling.
const (
	StatusPending    = "pending"
	StatusRunning    = "running"
	StatusSucceeded  = "succeeded"
	StatusFailed     = "failed"
	StatusRolledBack = "rolled-back"
	StatusSkipped    = "skipped"
)

// spinnerFrames is the braille spinner cycle for running steps.
var spinnerFrames = []string{"⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"}

// maxStoredLogs bounds memory: the view only shows the last 5.
const maxStoredLogs = 50

// Model is the live-install TUI program.
type Model struct {
	plan       pipeline.StagePlan
	items      []Item
	current    int
	logs       []string
	done       bool
	failed     bool
	runErr     error
	failStage  pipeline.Stage
	agents     int
	components int
	spinner    int
	width      int

	payload      screens.CompletePayload
	payloadBuilt bool
}

// Item is one install step with its display status.
type Item struct {
	Label  string
	Status string
}

// NewModel builds the installing screen from the plan: prepare steps first,
// then apply steps, all pending.
func NewModel(plan pipeline.StagePlan, agents, components int) Model {
	labels := make([]string, 0, len(plan.Prepare)+len(plan.Apply))
	for _, s := range plan.Prepare {
		labels = append(labels, s.ID())
	}
	for _, s := range plan.Apply {
		labels = append(labels, s.ID())
	}
	items := make([]Item, 0, len(labels))
	for _, l := range labels {
		items = append(items, Item{Label: l, Status: StatusPending})
	}
	return Model{
		plan:       plan,
		items:      items,
		current:    -1,
		agents:     agents,
		components: components,
	}
}

// Plan returns the pipeline plan this model was built from.
func (m Model) Plan() pipeline.StagePlan { return m.plan }

// Init starts the spinner ticker. The caller launches the pipeline itself in
// a goroutine and Sends StepProgressMsg/PipelineDoneMsg into the program.
func (m Model) Init() tea.Cmd {
	return tickCmd()
}

func tickCmd() tea.Cmd {
	return tea.Tick(100*time.Millisecond, func(t time.Time) tea.Msg {
		return TickMsg(t)
	})
}

// Update reduces progress messages into view state.
func (m Model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.width = msg.Width
		return m, nil

	case TickMsg:
		if m.done {
			return m, nil
		}
		m.spinner = (m.spinner + 1) % len(spinnerFrames)
		return m, tickCmd()

	case StepProgressMsg:
		m.applyProgress(msg)
		return m, nil

	case PipelineDoneMsg:
		m.done = true
		m.runErr = msg.Err
		m.failed = msg.Err != nil
		m.current = len(m.items)
		m.buildPayload()
		return m, nil

	case tea.KeyMsg:
		switch msg.String() {
		case "ctrl+c":
			return m, tea.Quit
		case "enter", " ":
			if m.done {
				return m, tea.Quit
			}
			// Swallow Enter while running: quitting mid-pipeline would
			// hide a half-applied install. Ctrl+C stays as the escape hatch.
			return m, nil
		case "esc":
			// Same reason: Esc never aborts a running install.
			if m.done {
				return m, tea.Quit
			}
			return m, nil
		}
	}

	return m, nil
}

// applyProgress maps one pipeline event onto the item list.
func (m *Model) applyProgress(msg StepProgressMsg) {
	idx := -1
	for i := range m.items {
		if m.items[i].Label != msg.StepID {
			continue
		}
		// Rollback re-runs finished steps: a rollback-completed event
		// flips a succeeded step to rolled-back.
		if !isTerminal(m.items[i].Status) ||
			(msg.Stage == pipeline.StageRollback && msg.Status == "completed" && m.items[i].Status == StatusSucceeded) {
			idx = i
			break
		}
	}
	if idx < 0 {
		// Unknown or already-terminal step (e.g. duplicate events): log only.
		if msg.Err != nil {
			m.appendLog("✗ " + msg.StepID + ": " + firstLine(msg.Err.Error()))
		}
		return
	}

	switch msg.Status {
	case "running":
		// Rollback re-runs finished steps: show them running again.
		m.items[idx].Status = StatusRunning
		m.current = idx
	case "completed":
		if msg.Stage == pipeline.StageRollback {
			m.items[idx].Status = StatusRolledBack
			m.appendLog("↶ " + msg.StepID + " (rolled back)")
		} else {
			m.items[idx].Status = StatusSucceeded
			m.appendLog("✓ " + msg.StepID)
		}
		m.current = idx + 1
	case "failed":
		m.items[idx].Status = StatusFailed
		m.current = idx
		m.failStage = msg.Stage
		if msg.Err != nil {
			m.appendLog("✗ " + msg.StepID + ": " + firstLine(msg.Err.Error()))
		} else {
			m.appendLog("✗ " + msg.StepID)
		}
	}
}

func isTerminal(status string) bool {
	switch status {
	case StatusSucceeded, StatusFailed, StatusRolledBack, StatusSkipped:
		return true
	}
	return false
}

func (m *Model) appendLog(line string) {
	m.logs = append(m.logs, line)
	if len(m.logs) > maxStoredLogs {
		m.logs = m.logs[len(m.logs)-maxStoredLogs:]
	}
}

func firstLine(s string) string {
	if i := strings.IndexByte(s, '\n'); i >= 0 {
		return s[:i]
	}
	return s
}

// Percent returns 0..100 over terminal items.
func (m Model) Percent() int {
	if len(m.items) == 0 {
		return 100
	}
	done := 0
	for _, it := range m.items {
		if isTerminal(it.Status) {
			done++
		}
	}
	return (done * 100) / len(m.items)
}

// Done reports whether the pipeline finished (success or failure).
func (m Model) Done() bool { return m.done }

// Failed reports whether the run ended with an error.
func (m Model) Failed() bool { return m.failed }

// ViewModel converts progress state to the screens renderer input.
func (m Model) ViewModel() screens.InstallProgress {
	items := make([]screens.ProgressItem, 0, len(m.items))
	for _, it := range m.items {
		items = append(items, screens.ProgressItem{Label: it.Label, Status: it.Status})
	}
	current := ""
	if m.current >= 0 && m.current < len(m.items) {
		current = m.items[m.current].Label
	}
	return screens.InstallProgress{
		Percent:     m.Percent(),
		CurrentStep: current,
		Items:       items,
		Logs:        append([]string(nil), m.logs...),
		Done:        m.done,
		Failed:      m.failed,
	}
}

// View draws the live progress screen, or the complete screen once done.
func (m Model) View() string {
	if !m.done {
		return screens.RenderInstalling(m.ViewModel(), spinnerFrames[m.spinner]) + "\n" +
			"  Please wait — quitting now would hide a half-applied install (Ctrl+C to force).\n"
	}
	return screens.RenderComplete(m.payload) + "\n"
}

// buildPayload folds the finished run into the complete screen.
func (m *Model) buildPayload() {
	if m.payloadBuilt {
		return
	}
	m.payloadBuilt = true

	p := screens.CompletePayload{
		ConfiguredAgents:    m.agents,
		InstalledComponents: m.components,
		Footer:              "Press Enter to exit.",
	}
	if !m.failed {
		m.payload = p
		return
	}

	for _, it := range m.items {
		if it.Status != StatusFailed {
			continue
		}
		p.FailedSteps = append(p.FailedSteps, screens.FailedStep{
			ID:    it.Label,
			Error: m.errorFor(it.Label),
		})
	}
	// The pipeline only rolls back apply-stage work; a prepare-stage failure
	// has nothing to undo.
	if m.failStage == pipeline.StageApply {
		p.RollbackPerformed = true
		p.RollbackComplete = true
	}
	m.payload = p
}

func (m Model) errorFor(stepID string) string {
	prefix := "✗ " + stepID + ": "
	for i := len(m.logs) - 1; i >= 0; i-- {
		if strings.HasPrefix(m.logs[i], prefix) {
			return strings.TrimPrefix(m.logs[i], prefix)
		}
	}
	if m.runErr != nil {
		return firstLine(m.runErr.Error())
	}
	return "unknown error"
}

// Result returns the complete payload and the pipeline error. Call after the
// program quits.
func (m Model) Result() (screens.CompletePayload, error) {
	if !m.payloadBuilt {
		m.buildPayload()
	}
	return m.payload, m.runErr
}
