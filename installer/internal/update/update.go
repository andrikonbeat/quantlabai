// Package update implements self-update functionality for the QuantLab
// installer binary. It handles GitHub release discovery, binary download,
// SHA-256 verification, and atomic replacement of the running binary.
package update

import (
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"time"
)

// Asset describes a single file attached to a GitHub release.
type Asset struct {
	Name               string `json:"name"`
	BrowserDownloadURL string `json:"browser_download_url"`
	Size               int64  `json:"size"`
}

// ReleaseInfo describes a GitHub release.
type ReleaseInfo struct {
	Tag       string    `json:"tag_name"`
	Name      string    `json:"name"`
	Published time.Time `json:"published_at"`
	Body      string    `json:"body"`
	Assets    []Asset   `json:"assets"`
}

// LatestGitHubRelease fetches the latest release from the GitHub Releases API
// for the given owner/repo.
func LatestGitHubRelease(owner, repo string) (*ReleaseInfo, error) {
	url := fmt.Sprintf("https://api.github.com/repos/%s/%s/releases/latest", owner, repo)

	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return nil, fmt.Errorf("create release request: %w", err)
	}
	req.Header.Set("Accept", "application/json")
	req.Header.Set("User-Agent", "quantlab-installer")

	client := &http.Client{Timeout: 15 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("fetch latest release: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("GitHub API returned HTTP %d: %s", resp.StatusCode, strings.TrimSpace(string(body)))
	}

	var release ReleaseInfo
	if err := json.NewDecoder(resp.Body).Decode(&release); err != nil {
		return nil, fmt.Errorf("decode release response: %w", err)
	}

	return &release, nil
}

// FindAssetForPlatform searches the release assets for a binary matching the
// current OS and architecture. Returns the asset name, download URL, size,
// and true if found. The matching logic looks for:
//   - exact match: quantlab-{os}-{arch} or quantlab-{os}-{arch}.tar.gz
//   - fallback: any asset starting with "quantlab-"
func (r *ReleaseInfo) FindAssetForPlatform() (name, url string, size int64, ok bool) {
	goos := runtime.GOOS
	goarch := runtime.GOARCH

	// Try exact matches first
	suffixes := []string{
		fmt.Sprintf("quantlab-%s-%s", goos, goarch),
		fmt.Sprintf("quantlab-%s-%s.tar.gz", goos, goarch),
		fmt.Sprintf("quantlab-%s-%s.zip", goos, goarch),
		fmt.Sprintf("quantlab-%s-%s.gz", goos, goarch),
	}

	for _, suffix := range suffixes {
		for _, asset := range r.Assets {
			if asset.Name == suffix {
				return asset.Name, asset.BrowserDownloadURL, asset.Size, true
			}
		}
	}

	// Fallback: contains the os-arch pair
	for _, asset := range r.Assets {
		if strings.Contains(asset.Name, fmt.Sprintf("%s-%s", goos, goarch)) {
			return asset.Name, asset.BrowserDownloadURL, asset.Size, true
		}
	}

	// Last resort: any asset starting with "quantlab-"
	for _, asset := range r.Assets {
		if strings.HasPrefix(asset.Name, "quantlab-") {
			return asset.Name, asset.BrowserDownloadURL, asset.Size, true
		}
	}

	return "", "", 0, false
}

// FindChecksumAsset searches the release assets for a SHA-256 checksum file
// matching the given binary name. Returns the download URL and content if found.
func (r *ReleaseInfo) FindChecksumAsset(binaryName string) (url, content string, ok bool) {
	checksumNames := []string{
		binaryName + ".sha256",
		"checksums.txt",
		"checksums.sha256",
		"SHA256SUMS",
	}

	for _, name := range checksumNames {
		for _, asset := range r.Assets {
			if asset.Name == name {
				return asset.BrowserDownloadURL, "", true
			}
		}
	}

	return "", "", false
}

// CheckForUpdate compares the current version against the latest GitHub release.
// Returns the release info and true if a newer version is available. Returns
// nil, false if already up-to-date. The "dev" version is always considered
// outdated (triggers an update check).
func CheckForUpdate(currentVersion string) (*ReleaseInfo, bool, error) {
	release, err := LatestGitHubRelease("ogzuz", "quantlab")
	if err != nil {
		return nil, false, fmt.Errorf("check for update: %w", err)
	}

	// "dev" is always considered outdated
	if currentVersion == "dev" {
		return release, true, nil
	}

	tag := strings.TrimPrefix(release.Tag, "v")
	current := strings.TrimPrefix(currentVersion, "v")

	if tag == current {
		return nil, false, nil
	}

	// If we can compare semver, do it; otherwise assume the tagged release is newer
	if IsNewerVersion(tag, current) {
		return release, true, nil
	}

	return nil, false, nil
}

// DownloadUpdate downloads the binary from the given URL and returns the raw
// bytes. Uses a 60-second timeout for downloads.
func DownloadUpdate(url string) ([]byte, error) {
	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return nil, fmt.Errorf("create download request: %w", err)
	}
	req.Header.Set("User-Agent", "quantlab-installer")

	client := &http.Client{Timeout: 120 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("download binary: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("download returned HTTP %d", resp.StatusCode)
	}

	data, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("read download response: %w", err)
	}

	return data, nil
}

// ApplyUpdate atomically replaces the binary at targetPath with the given data.
// It writes to a temp file, chmod +x, then renames atomically. If verifySHA is
// non-empty, the data is checked against the expected SHA-256 before writing.
func ApplyUpdate(data []byte, targetPath, verifySHA string) error {
	// Verify checksum if provided
	if verifySHA != "" {
		hash := sha256.Sum256(data)
		got := fmt.Sprintf("%x", hash)
		if !strings.EqualFold(got, verifySHA) {
			return fmt.Errorf("SHA-256 mismatch: got %s, expected %s", got, verifySHA)
		}
	}

	dir := filepath.Dir(targetPath)
	tmpPath := filepath.Join(dir, ".quantlab-update.tmp")

	// Write to temp file
	if err := os.WriteFile(tmpPath, data, 0o755); err != nil {
		return fmt.Errorf("write temporary binary: %w", err)
	}

	// Ensure it's executable
	if err := os.Chmod(tmpPath, 0o755); err != nil {
		os.Remove(tmpPath)
		return fmt.Errorf("chmod temporary binary: %w", err)
	}

	// Atomic rename (replaces the original binary)
	if err := os.Rename(tmpPath, targetPath); err != nil {
		os.Remove(tmpPath)
		return fmt.Errorf("atomic rename binary: %w", err)
	}

	return nil
}

// ExecPath returns the absolute path to the currently running executable.
func ExecPath() (string, error) {
	exe, err := os.Executable()
	if err != nil {
		return "", fmt.Errorf("get executable path: %w", err)
	}
	return exe, nil
}

// IsNewerVersion returns true if version a is semantically newer than version b.
// Strips optional "v" prefix. Handles simple semver (x.y.z) comparison.
func IsNewerVersion(a, b string) bool {
	cleanA := strings.TrimPrefix(a, "v")
	cleanB := strings.TrimPrefix(b, "v")
	return compareSemver(cleanA, cleanB) > 0
}

// compareSemver compares two dot-separated version strings.
// Returns -1 if a < b, 0 if equal, 1 if a > b.
func compareSemver(a, b string) int {
	partsA := strings.Split(a, ".")
	partsB := strings.Split(b, ".")

	maxLen := len(partsA)
	if len(partsB) > maxLen {
		maxLen = len(partsB)
	}

	for i := 0; i < maxLen; i++ {
		var numA, numB int
		if i < len(partsA) {
			if _, err := fmt.Sscanf(partsA[i], "%d", &numA); err != nil {
				return 0
			}
		}
		if i < len(partsB) {
			if _, err := fmt.Sscanf(partsB[i], "%d", &numB); err != nil {
				return 0
			}
		}
		if numA < numB {
			return -1
		}
		if numA > numB {
			return 1
		}
	}

	return 0
}
