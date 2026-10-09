package app

import (
	"fmt"
	"io"
	"net"
	"os/exec"
	"runtime"
	"time"
)

// dashboardURL is the local QuantLab web dashboard URL served by the SDK.
const dashboardURL = "http://localhost:5000/dashboard"

// dashboardPort is the local port the SDK dashboard listens on.
const dashboardPort = "5000"

// cmdDashboard implements the `quantlab dashboard` command. It checks whether
// the local SDK dashboard is reachable, opens it in the default browser when
// it is, and otherwise prints instructions to start the SDK.
func cmdDashboard(w io.Writer) error {
	fmt.Fprintf(w, "\n📊 Opening QuantLab Dashboard (local)...\n\n")

	if !dashboardReachable() {
		fmt.Fprintf(w, "  ⚠ Dashboard not reachable at %s\n", dashboardURL)
		fmt.Fprintf(w, "    The local SDK is not running.\n")
		fmt.Fprintf(w, "\n  Start the SDK first, then re-run this command:\n")
		fmt.Fprintf(w, "    quantlab-sdk start   (or your usual SDK startup command)\n")
		fmt.Fprintf(w, "\n  Dashboard URL once running:\n")
		fmt.Fprintf(w, "    %s\n", dashboardURL)
		fmt.Fprintf(w, "\n")
		return nil
	}

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
	fmt.Fprintf(w, "\n")

	return nil
}

// dashboardReachable reports whether something is listening on the local
// dashboard port within a short timeout.
func dashboardReachable() bool {
	conn, err := net.DialTimeout("tcp", "localhost:"+dashboardPort, 500*time.Millisecond)
	if err != nil {
		return false
	}
	_ = conn.Close()
	return true
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
