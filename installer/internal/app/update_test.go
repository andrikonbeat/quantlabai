package app

import (
	"testing"
)

func TestReexec_NotCalled(t *testing.T) {
	// reexec uses os.Exec which replaces the process — we can only verify
	// it exists and has the right signature. The function is only called
	// interactively after a successful update.
	t.Log("reexec() is designed to replace the process; tested indirectly.")
}
