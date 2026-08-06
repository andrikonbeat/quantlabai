package pipeline

import "errors"

// Run executes the given StagePlan. Prepare steps run first; if any fail the
// pipeline stops. Then Apply steps run; if any fails, completed RollbackSteps
// are rolled back in reverse order. Progress events are emitted via the
// optional progress callback.
func Run(plan StagePlan, progress ProgressFunc) error {
	// Run prepare steps
	for i, step := range plan.Prepare {
		if progress != nil {
			progress(ProgressEvent{
				Stage:     StagePrepare,
				StepID:    step.ID(),
				Status:    "running",
				Total:     len(plan.Prepare),
				Completed: i,
			})
		}

		if err := step.Run(); err != nil {
			if progress != nil {
				progress(ProgressEvent{
					Stage:     StagePrepare,
					StepID:    step.ID(),
					Status:    "failed",
					Error:     err,
					Total:     len(plan.Prepare),
					Completed: i,
				})
			}
			return err
		}

		if progress != nil {
			progress(ProgressEvent{
				Stage:     StagePrepare,
				StepID:    step.ID(),
				Status:    "completed",
				Total:     len(plan.Prepare),
				Completed: i + 1,
			})
		}
	}

	// Run apply steps, collecting completed rollback steps
	var completedApply []RollbackStep

	for i, step := range plan.Apply {
		if progress != nil {
			progress(ProgressEvent{
				Stage:     StageApply,
				StepID:    step.ID(),
				Status:    "running",
				Total:     len(plan.Apply),
				Completed: i,
			})
		}

		if err := step.Run(); err != nil {
			if progress != nil {
				progress(ProgressEvent{
					Stage:     StageApply,
					StepID:    step.ID(),
					Status:    "failed",
					Error:     err,
					Total:     len(plan.Apply),
					Completed: i,
				})
			}

			rollbackErr := rollbackSteps(completedApply, progress)
			if rollbackErr != nil {
				return errors.Join(err, rollbackErr)
			}
			return err
		}

		if progress != nil {
			progress(ProgressEvent{
				Stage:     StageApply,
				StepID:    step.ID(),
				Status:    "completed",
				Total:     len(plan.Apply),
				Completed: i + 1,
			})
		}

		if rb, ok := step.(RollbackStep); ok {
			// Prepend for reverse-order execution
			completedApply = append([]RollbackStep{rb}, completedApply...)
		}
	}

	return nil
}

// rollbackSteps executes rollback steps in order (already reversed). Continues
// on individual rollback failures and returns the last error, if any.
func rollbackSteps(steps []RollbackStep, progress ProgressFunc) error {
	var rollbackErr error
	for i, step := range steps {
		if progress != nil {
			progress(ProgressEvent{
				Stage:     StageRollback,
				StepID:    step.ID(),
				Status:    "running",
				Total:     len(steps),
				Completed: i,
			})
		}

		if err := step.Rollback(); err != nil {
			if progress != nil {
				progress(ProgressEvent{
					Stage:     StageRollback,
					StepID:    step.ID(),
					Status:    "failed",
					Error:     err,
					Total:     len(steps),
					Completed: i,
				})
			}
			rollbackErr = errors.Join(rollbackErr, err)
			continue
		}

		if progress != nil {
			progress(ProgressEvent{
				Stage:     StageRollback,
				StepID:    step.ID(),
				Status:    "completed",
				Total:     len(steps),
				Completed: i + 1,
			})
		}
	}
	return rollbackErr
}
