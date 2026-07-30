// Package pipeline implements the prepare → apply → rollback lifecycle.
package pipeline

// Stage identifies the current pipeline phase.
type Stage string

const (
	StagePrepare  Stage = "prepare"
	StageApply    Stage = "apply"
	StageRollback Stage = "rollback"
)

// Step represents a single unit of work in the pipeline.
type Step interface {
	ID() string
	Run() error
}

// RollbackStep extends Step with a rollback operation.
type RollbackStep interface {
	Step
	Rollback() error
}

// FailurePolicy controls how the pipeline reacts to step failures.
type FailurePolicy int

const (
	StopOnError    FailurePolicy = iota
	ContinueOnError
)

// ProgressEvent is emitted during pipeline execution to report progress.
type ProgressEvent struct {
	Stage     Stage
	StepID    string
	Status    string // "running", "completed", "failed"
	Error     error
	Total     int
	Completed int
}

// ProgressFunc is a callback emitted for each step state change.
type ProgressFunc func(ProgressEvent)

// StagePlan defines the steps to run in each pipeline phase.
type StagePlan struct {
	Prepare     []Step
	Apply       []Step
}
