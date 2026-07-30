package app_test

import (
	"testing"

	"github.com/ogzuz/quantlab/internal/app"
)

func TestGetVersionInfo_Defaults(t *testing.T) {
	info := app.GetVersionInfo()

	if info.Version != "dev" {
		t.Errorf("Version = %q, want %q", info.Version, "dev")
	}
	if info.Commit != "none" {
		t.Errorf("Commit = %q, want %q", info.Commit, "none")
	}
	if info.Date != "unknown" {
		t.Errorf("Date = %q, want %q", info.Date, "unknown")
	}
}

func TestUserAgent_Format(t *testing.T) {
	ua := app.UserAgent()
	if len(ua) == 0 {
		t.Fatal("UserAgent() returned empty string")
	}

	// Default: "quantlab/dev"
	expected := "quantlab/dev"
	if ua != expected {
		t.Errorf("UserAgent() = %q, want %q", ua, expected)
	}
}

func TestVersionVariable_InSync(t *testing.T) {
	// The exported Version var should be in sync with GetVersionInfo().
	info := app.GetVersionInfo()
	if app.Version != info.Version {
		t.Errorf("app.Version = %q, but GetVersionInfo().Version = %q", app.Version, info.Version)
	}
}
