package app

import (
	"fmt"
	"io"
	"os/exec"
	"runtime"
)

// dashboardURL is the default QuantLab web dashboard URL.
const dashboardURL = "https://quantlab-ai.com/dashboard"

// cmdDashboard implements the `quantlab dashboard` command. It attempts to
// open the QuantLab web dashboard in the default browser, or prints the URL
// if the browser cannot be opened.
func cmdDashboard(w io.Writer) error {
	fmt.Fprintf(w, "\n📊 Opening QuantLab Dashboard...\n\n")

	opened, err := openURL(dashboardURL)
	if err != nil {
		fmt.Fprintf(w, "  ⚠ Could not open browser: %v\n", err)
	}

	if opened {
		fmt.Fprintf(w, "  ✓ Dashboard opened in your default browser.\n")
	} else {
		fmt.Fprintf(w, "  → Dashboard URL:\n")
		fmt.Fprintf(w, "    %s\n", dashboardURL)
		fmt.Fprintf(w, "\n  Open this URL in your browser to access the QuantLab dashboard.\n")
	}

	fmt.Fprintf(w, "\n  The QuantLab SDK serves the dashboard at:\n")
	fmt.Fprintf(w, "    http://localhost:5000/dashboard\n")
	fmt.Fprintf(w, "  (Start the SDK to enable the local dashboard)\n")
	fmt.Fprintf(w, "\n")

	return nil
}

// openURL tries to open the given URL in the default browser using the
// platform's native command. Returns true if the browser was opened.
func openURL(url string) (bool, error) {
	switch runtime.GOOS {
	case "linux":
		return tryOpen("xdg-open", url)
	case "darwin":
		return tryOpen("open", url)
	default:
		return false, nil
	}
}

// tryOpen attempts to run the given command with the URL as argument.
func tryOpen(command, url string) (bool, error) {
	cmd := exec.Command(command, url)
	if err := cmd.Start(); err != nil {
		return false, err
	}
	// Don't wait — the browser process is detached
	return true, nil
}
