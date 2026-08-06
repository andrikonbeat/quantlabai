package app

import (
	"fmt"
	"io"
	"os"
	"runtime"
	"strings"
	"syscall"

	"github.com/ogzuz/quantlab/internal/tui/confirm"
	"github.com/ogzuz/quantlab/internal/tui/spinner"
	"github.com/ogzuz/quantlab/internal/update"
)

// cmdUpdate implements the `quantlab update` command. It checks for a newer
// version on GitHub, downloads it, verifies the checksum, performs an atomic
// swap, and prompts the user to restart.
func cmdUpdate(w io.Writer) error {
	// 1. Check current version
	currentVersion := Version

	fmt.Fprintf(w, "\n🔍 Checking for updates (current: %s)...\n\n", currentVersion)

	// 2. Check for update
	release, hasUpdate, err := update.CheckForUpdate(currentVersion)
	if err != nil {
		// Network errors are not fatal — just report and continue
		fmt.Fprintf(w, "  ⚠ Could not check for updates: %v\n", err)
		fmt.Fprintf(w, "  Check your internet connection or try again later.\n")
		return nil
	}

	if !hasUpdate {
		fmt.Fprintf(w, "  ✓ You're already running the latest version (%s).\n", currentVersion)
		return nil
	}

	newVersion := strings.TrimPrefix(release.Tag, "v")
	newVersion = strings.TrimPrefix(newVersion, "installer/")
	fmt.Fprintf(w, "  → New version available: %s\n", newVersion)

	// 3. Find the right asset for this platform
	assetName, assetURL, _, ok := release.FindAssetForPlatform()
	if !ok {
		fmt.Fprintf(w, "  ✗ No binary found for your platform (%s/%s).\n", runtime.GOOS, runtime.GOARCH)
		fmt.Fprintf(w, "    Release page: https://github.com/ogzuz/quantlab/releases/latest\n")
		return nil
	}

	fmt.Fprintf(w, "  → Downloading %s...\n", assetName)

	// 4. Download
	var data []byte
	err = spinner.RunWithSpinner("Downloading update...", func() error {
		var dlErr error
		data, dlErr = update.DownloadUpdate(assetURL)
		return dlErr
	})
	if err != nil {
		return fmt.Errorf("download failed: %w", err)
	}

	fmt.Fprintf(w, "  ✓ Downloaded %d bytes\n", len(data))

	// 5. Verify the SHA-256 checksum — verification is mandatory (fail-closed).
	checksumURL, _, found := release.FindChecksumAsset(assetName)
	if !found {
		return fmt.Errorf("no SHA-256 checksum asset found for %q; refusing to update", assetName)
	}
	fmt.Fprintf(w, "  → Verifying SHA-256 checksum...\n")
	checksumData, err := update.DownloadUpdate(checksumURL)
	if err != nil {
		return fmt.Errorf("download checksum: %w", err)
	}
	verifySHA, err := update.ParseChecksum(string(checksumData), assetName)
	if err != nil {
		return fmt.Errorf("verify checksum: %w", err)
	}

	// 6. Find our binary path
	exePath, err := update.ExecPath()
	if err != nil {
		return fmt.Errorf("cannot determine executable path: %w", err)
	}

	// 7. Apply update (verification already enforced above and inside ApplyUpdate)
	fmt.Fprintf(w, "  → Applying update...\n")
	if err := update.ApplyUpdate(data, exePath, verifySHA); err != nil {
		return fmt.Errorf("apply update failed: %w", err)
	}

	fmt.Fprintf(w, "  ✓ Update applied successfully!\n\n")

	// 8. Prompt restart
	fmt.Fprintf(w, "The binary has been updated to version %s.\n", newVersion)
	fmt.Fprintf(w, "You need to restart QuantLab for the change to take effect.\n\n")

	confirmed, err := confirm.RunConfirm("Restart QuantLab now?")
	if err != nil {
		fmt.Fprintf(w, "Could not show restart dialog: %v\n", err)
		fmt.Fprintf(w, "Please restart manually.\n")
		return nil
	}

	if confirmed {
		fmt.Fprintf(w, "\n🔄 Restarting...\n")
		// Re-exec with same args
		// Note: os.Exec is Unix-specific but we're Linux-only
		return reexec()
	}

	fmt.Fprintf(w, "\nYou can restart QuantLab later by running it again.\n")
	return nil
}

// reexec replaces the current process with a new invocation of the same binary
// with the same arguments. Only used after a successful self-update.
func reexec() error {
	args := os.Args
	exe, err := os.Executable()
	if err != nil {
		return fmt.Errorf("get executable for restart: %w", err)
	}
	return syscall.Exec(exe, args, os.Environ())
}
