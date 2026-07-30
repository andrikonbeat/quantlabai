// Package app provides the QuantLab CLI dispatch mechanism.
// Replicates Gentle AI's app.go pattern with manual command routing.
package app

import (
	"fmt"
	"io"
)

// Version is set at build time via ldflags.
var Version = "dev"

// RunArgs dispatches the given command-line arguments to the appropriate
// handler. Output is written to stdout. Returns nil on success, or an error
// for fatal failures (help and unknown command errors are not fatal).
func RunArgs(args []string, stdout io.Writer) error {
	if len(args) == 0 {
		return printHelp(stdout)
	}

	cmd := args[0]

	switch cmd {
	case "install":
		return cmdInstall(stdout)
	case "uninstall":
		return cmdUninstall(stdout)
	case "sync":
		return cmdSync(stdout)
	case "update":
		return cmdUpdate(stdout)
	case "configure":
		return cmdConfigure(stdout)
	case "dashboard":
		return cmdDashboard(stdout)
	case "status":
		return cmdStatus(stdout)
	case "version":
		return cmdVersion(stdout)
	case "help":
		return printHelp(stdout)
	default:
		return cmdUnknown(stdout, cmd)
	}
}

func cmdSync(w io.Writer) error {
	_, err := fmt.Fprintln(w, "quantlab sync: not yet implemented")
	return err
}

func cmdUpdate(w io.Writer) error {
	_, err := fmt.Fprintln(w, "quantlab update: not yet implemented")
	return err
}

func cmdConfigure(w io.Writer) error {
	_, err := fmt.Fprintln(w, "quantlab configure: not yet implemented")
	return err
}

func cmdDashboard(w io.Writer) error {
	_, err := fmt.Fprintln(w, "quantlab dashboard: not yet implemented")
	return err
}

func cmdStatus(w io.Writer) error {
	_, err := fmt.Fprintln(w, "quantlab status: not yet implemented")
	return err
}

func cmdVersion(w io.Writer) error {
	_, err := fmt.Fprintf(w, "quantlab version %s\n", Version)
	return err
}

func cmdUnknown(w io.Writer, cmd string) error {
	fmt.Fprintf(w, "quantlab: unknown command %q\n", cmd)
	return printHelp(w)
}

func printHelp(w io.Writer) error {
	help := `QuantLab AI Installer

Usage:
  quantlab <command> [flags]

Commands:
  install     Install QuantLab AI
  uninstall   Remove QuantLab AI
  sync        Refresh components
  update      Self-update binary
  configure   Run config wizard
  dashboard   Open web dashboard
  status      Show installation status
  version     Print version
  help        Show this help message
`
	_, err := fmt.Fprint(w, help)
	return err
}
