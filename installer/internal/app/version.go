// Package app provides the QuantLab CLI dispatch mechanism.
// Build-time version injection via ldflags.
package app

// Build-time variables — set via ldflags:
//
//	go build -ldflags="\
//	  -X github.com/ogzuz/quantlab/internal/app.version=0.1.0 \
//	  -X github.com/ogzuz/quantlab/internal/app.commit=abc1234 \
//	  -X github.com/ogzuz/quantlab/internal/app.date=2026-07-30T14:00:00Z" \
//	  ./cmd/quantlab
var (
	version = "dev"
	commit  = "none"
	date    = "unknown"
)

// VersionInfo holds structured build-time version information.
type VersionInfo struct {
	Version string `json:"version"`
	Commit  string `json:"commit"`
	Date    string `json:"date"`
}

// GetVersionInfo returns the build-time version information as a struct.
func GetVersionInfo() VersionInfo {
	return VersionInfo{
		Version: Version,
		Commit:  commit,
		Date:    date,
	}
}

// UserAgent returns a User-Agent string suitable for HTTP request headers.
func UserAgent() string {
	return "quantlab/" + version
}

// Ensure the exported Version variable reflects the ldflags-injected value.
func init() {
	Version = version
}
