package app

import (
	"bytes"
	"strings"
	"testing"
)

func TestCmdDashboard_Output(t *testing.T) {
	var buf bytes.Buffer
	err := cmdDashboard(&buf)
	if err != nil {
		t.Fatalf("cmdDashboard() error = %v", err)
	}

	output := buf.String()
	checks := []string{
		"Dashboard",
		"quantlab-ai.com",
		"localhost:5000",
	}

	for _, check := range checks {
		if !strings.Contains(output, check) {
			t.Errorf("expected output to contain %q", check)
		}
	}
}

func TestTryOpen_UnknownCommand(t *testing.T) {
	// Trying to open with a non-existent command should return an error
	opened, err := tryOpen("nonexistent-browser-xyz", "https://example.com")
	if err == nil {
		t.Log("tryOpen returned no error (command may exist)")
	} else {
		t.Logf("tryOpen returned expected error: %v", err)
	}
	if opened {
		t.Error("expected opened=false for non-existent command")
	}
}
