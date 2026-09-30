package tools

import (
	"testing"
)

func TestInstallGentleAI_Compiles(t *testing.T) {
	var fn func(string) (string, error) = InstallGentleAI
	_ = fn
}

func TestInstallGentleAI_Integration(t *testing.T) {
	if testing.Short() {
		t.Skip("skipping GitHub release integration in short mode")
	}
	display, err := InstallGentleAI("")
	_ = display
	_ = err
}
