package app

import (
	"fmt"
	"io"
	"strings"
)

// cmdHelp displays help text. If subcommand is non-empty, shows help for that
// specific command. Otherwise shows general usage.
func cmdHelp(w io.Writer, subcommand string) error {
	if subcommand == "" {
		return printGeneralHelp(w)
	}

	help, ok := commandHelp[subcommand]
	if !ok {
		fmt.Fprintf(w, "quantlab: no help available for %q\n\n", subcommand)
		return printGeneralHelp(w)
	}

	_, err := fmt.Fprint(w, help)
	return err
}

// printGeneralHelp shows the top-level usage message listing all commands.
func printGeneralHelp(w io.Writer) error {
	help := `QuantLab AI — Installer & Lifecycle Manager

Usage:
  quantlab <command> [options]

Installation:
  install       Install QuantLab AI (wizard + SDK + OpenCode integration)
  uninstall     Remove QuantLab AI and all its components

Lifecycle:
  sync          Refresh installed components (agents, skills, prompts, SDK)
  update        Self-update the QuantLab binary
  configure     Re-run the configuration wizard

Monitoring:
  status        Show installation status and component health
  dashboard     Open the QuantLab web dashboard

General:
  version       Print the installed version
  help [cmd]    Show help for a specific command

Run 'quantlab help <command>' for command-specific help.
`
	_, err := fmt.Fprint(w, help)
	return err
}

// commandHelp maps each command to its detailed help text.
var commandHelp = map[string]string{
	"install": `Usage: quantlab install

Install QuantLab AI on your system. Runs a configuration wizard, then:

  1. Validates prerequisites (Python 3.11+, OpenCode)
  2. Collects API keys and model preferences
  3. Creates Python virtual environment and installs SDK
  4. Merges QuantLab agents into opencode.json
  5. Installs QuantLab skills and prompts
  6. Sets ownership marker for default_agent
  7. Writes installation state

The installation is fully rollbackable — any failure during apply
reverses all changes made so far.

Examples:
  quantlab install
`,

	"uninstall": `Usage: quantlab uninstall

Remove QuantLab AI and all its components. Before removal:

  1. Restores default_agent from the ownership marker
  2. Removes QuantLab agents from opencode.json
  3. Deletes QuantLab skills and prompts
  4. Removes the Python virtual environment
  5. Deletes ~/.quantlab/ directory

A confirmation prompt is shown before any changes are made.

Examples:
  quantlab uninstall
`,

	"sync": `Usage: quantlab sync

Refresh all installed QuantLab components to their latest versions:

  1. Re-merges QuantLab agents into opencode.json
  2. Re-installs skills from embedded assets
  3. Re-installs prompts from embedded assets
  4. Checks for SDK updates and re-installs if needed
  5. Updates installation state

Idempotent — safe to run multiple times. No configuration is lost.

Examples:
  quantlab sync
`,

	"update": `Usage: quantlab update

Self-update the QuantLab binary to the latest version from GitHub.

  1. Checks latest release on github.com/ogzuz/quantlab
  2. Downloads the binary matching your platform (OS + architecture)
  3. Verifies SHA-256 checksum
  4. Atomically replaces the running binary
  5. Prompts you to restart

State and configuration under ~/.quantlab/ are preserved.

Examples:
  quantlab update
`,

	"configure": `Usage: quantlab configure [--reset]

Re-run the configuration wizard to update settings.

Options:
  --reset   Clear existing configuration and start fresh

The wizard pre-fills fields from your existing config when available.
Settings are saved to ~/.quantlab/config.yaml with 0600 permissions.

Examples:
  quantlab configure
  quantlab configure --reset
`,

	"dashboard": `Usage: quantlab dashboard

Open the QuantLab web dashboard in your default browser.

If no browser is available, the dashboard URL is printed to the
terminal for manual access.

Examples:
  quantlab dashboard
`,

	"status": `Usage: quantlab status

Show the current QuantLab installation status:

  • Installed version
  • SDK version and path
  • Configured API keys (masked)
  • OpenCode integration status
  • Installed skills and prompts
  • Last update timestamp
  • Overall health status

Detects missing state, orphaned agents, or incomplete installations.

Examples:
  quantlab status
`,

	"version": `Usage: quantlab version

Print the installed QuantLab version.

Examples:
  quantlab version
`,

	"help": `Usage: quantlab help [command]

Show help for a specific command, or general usage.

Examples:
  quantlab help         # General help
  quantlab help sync    # Help for the sync command
`,
}

// validCommands lists all recognized commands for subcommand validation.
var validCommands = []string{
	"install", "uninstall", "sync", "update",
	"configure", "dashboard", "status", "version", "help",
}

// isValidCommand checks whether the given name is a recognized command.
func isValidCommand(name string) bool {
	for _, cmd := range validCommands {
		if cmd == name {
			return true
		}
	}
	return false
}

// FormatHelpSummary returns a compact one-line summary of all commands.
func FormatHelpSummary() string {
	lines := []string{
		"install       Install QuantLab AI",
		"uninstall     Remove QuantLab AI",
		"sync          Refresh components",
		"update        Self-update binary",
		"configure     Re-run config wizard",
		"dashboard     Open web dashboard",
		"status        Show installation status",
		"version       Print version",
		"help          Show help",
	}
	return "Commands:\n  " + strings.Join(lines, "\n  ") + "\n"
}
