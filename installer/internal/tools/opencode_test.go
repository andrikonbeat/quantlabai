package tools

import (
	"testing"
)

func TestInstallOpenCode_Compiles(t *testing.T) {
	var fn func(string) (string, error) = InstallOpenCode
	_ = fn
}

func TestInstallOpenCode_Integration(t *testing.T) {
	if testing.Short() {
		t.Skip("skipping npm install integration in short mode")
	}
	display, err := InstallOpenCode("")
	_ = display
	_ = err
}
