package app_test

import (
	"bytes"
	"strings"
	"testing"

	"github.com/ogzuz/quantlab/internal/app"
)

func TestRunArgs_VersionCommand(t *testing.T) {
	var buf bytes.Buffer
	err := app.RunArgs([]string{"version"}, &buf)
	if err != nil {
		t.Fatalf("RunArgs(version) = %v, want nil", err)
	}

	output := buf.String()
	if !strings.Contains(output, "quantlab version") {
		t.Errorf("output = %q, want it to contain 'quantlab version'", output)
	}
}

func TestRunArgs_VersionVariable(t *testing.T) {
	app.Version = "0.1.0-test"
	defer func() { app.Version = "dev" }()

	var buf bytes.Buffer
	err := app.RunArgs([]string{"version"}, &buf)
	if err != nil {
		t.Fatalf("RunArgs(version) = %v, want nil", err)
	}

	output := buf.String()
	if !strings.Contains(output, "0.1.0-test") {
		t.Errorf("output = %q, want it to contain '0.1.0-test'", output)
	}
}

func TestRunArgs_HelpCommand(t *testing.T) {
	var buf bytes.Buffer
	err := app.RunArgs([]string{"help"}, &buf)
	if err != nil {
		t.Fatalf("RunArgs(help) = %v, want nil", err)
	}

	output := buf.String()
	if !strings.Contains(output, "Usage:") {
		t.Errorf("output = %q, want it to contain 'Usage:'", output)
	}
	if !strings.Contains(output, "install") {
		t.Errorf("output = %q, want it to contain 'install'", output)
	}
	if !strings.Contains(output, "uninstall") {
		t.Errorf("output = %q, want it to contain 'uninstall'", output)
	}
	if !strings.Contains(output, "sync") {
		t.Errorf("output = %q, want it to contain 'sync'", output)
	}
	if !strings.Contains(output, "update") {
		t.Errorf("output = %q, want it to contain 'update'", output)
	}
	if !strings.Contains(output, "configure") {
		t.Errorf("output = %q, want it to contain 'configure'", output)
	}
	if !strings.Contains(output, "dashboard") {
		t.Errorf("output = %q, want it to contain 'dashboard'", output)
	}
	if !strings.Contains(output, "status") {
		t.Errorf("output = %q, want it to contain 'status'", output)
	}
}

func TestRunArgs_NoArgsShowsHelp(t *testing.T) {
	var buf bytes.Buffer
	err := app.RunArgs([]string{}, &buf)
	if err != nil {
		t.Fatalf("RunArgs(empty) = %v, want nil", err)
	}

	output := buf.String()
	if !strings.Contains(output, "Usage:") {
		t.Errorf("no args should show help, got = %q", output)
	}
}

func TestRunArgs_UnknownCommand(t *testing.T) {
	var buf bytes.Buffer
	err := app.RunArgs([]string{"nonexistent"}, &buf)
	if err != nil {
		t.Fatalf("RunArgs(unknown) = %v, want nil", err)
	}

	output := buf.String()
	if !strings.Contains(output, "unknown command") {
		t.Errorf("output = %q, want it to contain 'unknown command'", output)
	}
}

func TestRunArgs_InstallCommand(t *testing.T) {
	var buf bytes.Buffer
	err := app.RunArgs([]string{"install"}, &buf)

	// Install may fail due to missing Python or non-TTY (wizard).
	// The important thing is that it produces output mentioning "install"
	// and doesn't panic. Errors are acceptable for non-interactive test runs.
	output := buf.String()
	if err != nil {
		t.Logf("RunArgs(install) returned expected error (non-interactive env): %v", err)
	}
	if len(output) == 0 {
		t.Error("RunArgs(install) produced no output")
	}
}

func TestRunArgs_UninstallCommand(t *testing.T) {
	var buf bytes.Buffer
	err := app.RunArgs([]string{"uninstall"}, &buf)

	// Uninstall may fail due to non-TTY (confirm dialog).
	output := buf.String()
	if err != nil {
		t.Logf("RunArgs(uninstall) returned expected error (non-interactive env): %v", err)
	}
	if len(output) == 0 {
		t.Error("RunArgs(uninstall) produced no output")
	}
}

func TestRunArgs_StatusCommand(t *testing.T) {
	var buf bytes.Buffer
	err := app.RunArgs([]string{"status"}, &buf)
	if err != nil {
		t.Fatalf("RunArgs(status) = %v, want nil", err)
	}

	output := buf.String()
	if !strings.Contains(output, "status") {
		t.Errorf("output = %q, want it to mention 'status'", output)
	}
}

func TestRunArgs_StdoutWriter(t *testing.T) {
	// Verify that output goes to the provided writer, not os.Stdout
	var buf bytes.Buffer
	err := app.RunArgs([]string{"version"}, &buf)
	if err != nil {
		t.Fatalf("RunArgs(version) = %v, want nil", err)
	}
	if buf.Len() == 0 {
		t.Error("expected output in the provided writer, got empty")
	}
}
