package app

import (
	"bytes"
	"strings"
	"testing"
)

func TestCmdHelp_NoSubcommand(t *testing.T) {
	var buf bytes.Buffer
	err := cmdHelp(&buf, "")
	if err != nil {
		t.Fatalf("cmdHelp('') error = %v", err)
	}

	output := buf.String()
	checks := []string{
		"Usage:",
		"install",
		"uninstall",
		"sync",
		"update",
		"configure",
		"dashboard",
		"status",
		"version",
	}

	for _, check := range checks {
		if !strings.Contains(output, check) {
			t.Errorf("output missing %q", check)
		}
	}
}

func TestCmdHelp_SpecificCommand(t *testing.T) {
	tests := []struct {
		cmd     string
		expects []string
	}{
		{"install", []string{"quantlab install", "Python", "SDK"}},
		{"uninstall", []string{"quantlab uninstall", "default_agent"}},
		{"sync", []string{"quantlab sync", "components", "assets"}},
		{"update", []string{"quantlab update", "GitHub", "checksum"}},
		{"configure", []string{"quantlab configure", "--reset", "wizard"}},
		{"dashboard", []string{"quantlab dashboard", "browser", "URL"}},
		{"status", []string{"quantlab status", "version", "health"}},
		{"version", []string{"quantlab version", "version"}},
	}

	for _, tt := range tests {
		t.Run(tt.cmd, func(t *testing.T) {
			var buf bytes.Buffer
			err := cmdHelp(&buf, tt.cmd)
			if err != nil {
				t.Fatalf("cmdHelp(%q) error = %v", tt.cmd, err)
			}
			output := buf.String()
			for _, expect := range tt.expects {
				if !strings.Contains(output, expect) {
					t.Errorf("help for %q missing %q\nOutput:\n%s", tt.cmd, expect, output)
				}
			}
		})
	}
}

func TestCmdHelp_UnknownCommand(t *testing.T) {
	var buf bytes.Buffer
	err := cmdHelp(&buf, "nonexistent")
	if err != nil {
		t.Fatalf("cmdHelp('nonexistent') error = %v", err)
	}
	// Should fall back to general help
	output := buf.String()
	if !strings.Contains(output, "Usage:") {
		t.Errorf("unknown command help should show general usage, got: %s", output)
	}
}

func TestCmdHelp_EmptySubcommand(t *testing.T) {
	var buf bytes.Buffer
	err := cmdHelp(&buf, "")
	if err != nil {
		t.Fatalf("cmdHelp('') error = %v", err)
	}
	output := buf.String()
	if !strings.Contains(output, "QuantLab AI") {
		t.Errorf("general help should contain title, got: %s", output)
	}
}

func TestIsValidCommand(t *testing.T) {
	valid := []string{"install", "uninstall", "sync", "update", "configure", "dashboard", "status", "version", "help"}
	invalid := []string{"", "nope", "installer", "remove"}

	for _, cmd := range valid {
		if !isValidCommand(cmd) {
			t.Errorf("isValidCommand(%q) = false, want true", cmd)
		}
	}
	for _, cmd := range invalid {
		if isValidCommand(cmd) {
			t.Errorf("isValidCommand(%q) = true, want false", cmd)
		}
	}
}

func TestFormatHelpSummary(t *testing.T) {
	summary := FormatHelpSummary()
	if !strings.Contains(summary, "install") {
		t.Errorf("summary missing 'install'")
	}
	if !strings.Contains(summary, "status") {
		t.Errorf("summary missing 'status'")
	}
	if strings.Count(summary, "\n  ") < 8 {
		t.Errorf("expected at least 8 command lines in summary")
	}
}

func TestCommandHelpMap_AllValid(t *testing.T) {
	// Every valid command should have help text
	for _, cmd := range validCommands {
		help, ok := commandHelp[cmd]
		if !ok {
			t.Errorf("commandHelp missing entry for %q", cmd)
			continue
		}
		if len(help) == 0 {
			t.Errorf("commandHelp for %q is empty", cmd)
		}
	}
}

func TestPrintGeneralHelp(t *testing.T) {
	var buf bytes.Buffer
	err := printGeneralHelp(&buf)
	if err != nil {
		t.Fatalf("printGeneralHelp() error = %v", err)
	}
	output := buf.String()

	// Should not include any command's detailed help
	if strings.Contains(output, "Python 3.11") {
		t.Error("general help should not contain command-specific details")
	}
}
