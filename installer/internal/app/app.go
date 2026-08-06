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
		if err := cmdHelp(stdout, ""); err != nil {
			return err
		}
		fmt.Fprintf(stdout, "\nTip: run 'quantlab install' to get started.\n")
		return nil
	}

	cmd := args[0]

	switch cmd {
	case "install":
		return cmdInstall(stdout, args[1:])
	case "uninstall":
		return cmdUninstall(stdout)
	case "sync":
		return cmdSync(stdout)
	case "update":
		return cmdUpdate(stdout)
	case "configure":
		return cmdConfigure(stdout, args[1:])
	case "dashboard":
		return cmdDashboard(stdout)
	case "status":
		return cmdStatus(stdout)
	case "version":
		return cmdVersion(stdout)
	case "help":
		subcmd := ""
		if len(args) > 1 {
			subcmd = args[1]
		}
		return cmdHelp(stdout, subcmd)
	default:
		return cmdUnknown(stdout, cmd)
	}
}

func cmdVersion(w io.Writer) error {
	info := GetVersionInfo()
	_, err := fmt.Fprintf(w, "quantlab %s\n  commit:  %s\n  date:    %s\n", info.Version, info.Commit, info.Date)
	return err
}

func cmdUnknown(w io.Writer, cmd string) error {
	fmt.Fprintf(w, "quantlab: unknown command %q\n", cmd)
	fmt.Fprintf(w, "Run 'quantlab help' for usage.\n")
	return nil
}
