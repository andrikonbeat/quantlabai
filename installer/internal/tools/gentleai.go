package tools

import (
	"archive/tar"
	"compress/gzip"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"time"

	"github.com/andrikonbeat/quantlabai/internal/update"
)

// InstallGentleAI installs gentle-ai from the latest GitHub release. If the
// install is not writable or the platform has no release, it returns a
// display-only fallback message.
func InstallGentleAI(home string) (string, error) {
	if !DetectNpmWritable() {
		return displayFallback("gentle-ai", "visit https://github.com/Gentleman-Programming/gentle-ai"), nil
	}

	release, err := update.LatestGitHubRelease("gentleman-programming", "gentle-ai")
	if err != nil {
		return displayFallback("gentle-ai", "visit https://github.com/Gentleman-Programming/gentle-ai"), nil
	}

	assetName, assetURL, _, ok := release.FindAssetForPlatform()
	if !ok {
		return displayFallback("gentle-ai", fmt.Sprintf("no release asset for %s/%s", runtime.GOOS, runtime.GOARCH)), nil
	}

	data, err := downloadBytes(assetURL)
	if err != nil {
		return displayFallback("gentle-ai", "visit https://github.com/Gentleman-Programming/gentle-ai"), nil
	}

	expected := ""
	if checksumURL, checksumContent, ok := release.FindChecksumAsset(assetName); ok {
		if checksumContent != "" {
			expected, err = update.ParseChecksum(checksumContent, assetName)
			if err != nil {
				return displayFallback("gentle-ai", "checksum parse failed"), nil
			}
		} else {
			checksumBytes, err := downloadBytes(checksumURL)
			if err != nil {
				return displayFallback("gentle-ai", "visit https://github.com/Gentleman-Programming/gentle-ai"), nil
			}
			expected, err = update.ParseChecksum(string(checksumBytes), assetName)
			if err != nil {
				return displayFallback("gentle-ai", "checksum parse failed"), nil
			}
		}
	}

	binaryData, err := extractBinaryFromTarGz(data, assetName)
	if err != nil {
		return displayFallback("gentle-ai", fmt.Sprintf("extract failed: %v", err)), nil
	}

	binDir := filepath.Join(home, ".local", "bin")
	if err := os.MkdirAll(binDir, 0o755); err != nil {
		return displayFallback("gentle-ai", fmt.Sprintf("mkdir bin dir: %v", err)), nil
	}
	binPath := filepath.Join(binDir, "gentle-ai")

	if expected != "" {
		if err := update.ApplyUpdate(binaryData, binPath, expected); err != nil {
			return displayFallback("gentle-ai", fmt.Sprintf("atomic swap failed: %v", err)), nil
		}
	} else {
		// No checksum available; write directly (degraded, but not blocked)
		if err := os.WriteFile(binPath, binaryData, 0o755); err != nil {
			return displayFallback("gentle-ai", fmt.Sprintf("write binary: %v", err)), nil
		}
	}

	return "", nil
}

func downloadBytes(url string) ([]byte, error) {
	client := &http.Client{Timeout: 120 * time.Second}
	resp, err := client.Get(url)
	if err != nil {
		return nil, fmt.Errorf("download %s: %w", url, err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("download %s: HTTP %d", url, resp.StatusCode)
	}
	return io.ReadAll(resp.Body)
}

func extractBinaryFromTarGz(data []byte, assetName string) ([]byte, error) {
	gr, err := gzip.NewReader(strings.NewReader(string(data)))
	if err != nil {
		return nil, fmt.Errorf("gzip reader: %w", err)
	}
	defer gr.Close()

	tr := tar.NewReader(gr)
	for {
		header, err := tr.Next()
		if err == io.EOF {
			break
		}
		if err != nil {
			return nil, fmt.Errorf("tar read: %w", err)
		}
		if header.Typeflag == tar.TypeReg {
			name := header.Name
			if strings.Contains(name, "gentle-ai") || strings.Contains(name, "gentle_ai") {
				return io.ReadAll(tr)
			}
		}
	}
	return nil, fmt.Errorf("no binary found in tar.gz")
}

func displayFallback(name, cmd string) string {
	return fmt.Sprintf("%s no se instaló automáticamente. Ejecutá manualmente: %s", name, cmd)
}
