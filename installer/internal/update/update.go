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
// and true if found.
//
// Matching accepts both hyphen and underscore separators between the OS and
// architecture tokens, so quantlab-linux-amd64 and
// quantlab_1.0.0_linux_amd64.tar.gz both match on linux/amd64. Only binary
// archives are considered: package files (.deb, .rpm, .msi, …) and checksum
// manifests are never selected.
func (r *ReleaseInfo) FindAssetForPlatform() (name, url string, size int64, ok bool) {
	goos := runtime.GOOS
	goarch := runtime.GOARCH

	for _, asset := range r.Assets {
		if matchesPlatform(asset.Name, goos, goarch) {
			return asset.Name, asset.BrowserDownloadURL, asset.Size, true
		}
	}

	return "", "", 0, false
}

// matchesPlatform reports whether name is a binary archive for the given OS
// and architecture. Both hyphen and underscore separators are accepted, and
// package/checksum files are rejected so a fallback never grabs a .deb/.msi.
func matchesPlatform(name, goos, goarch string) bool {
	if !isBinaryArchive(name) {
		return false
	}

	norm := strings.ReplaceAll(strings.ToLower(name), "-", "_")

	osTokens := []string{goos}
	if goos == "darwin" {
		// Backward compatibility with asset names that spelled macOS instead
		// of darwin.
		osTokens = append(osTokens, "macos")
	}

	for _, osTok := range osTokens {
		if strings.Contains(norm, "_"+osTok+"_"+goarch) {
			return true
		}
	}
	return false
}

// isBinaryArchive reports whether name looks like a binary archive or bare
// binary rather than a package, checksum manifest, or source file.
func isBinaryArchive(name string) bool {
	lower := strings.ToLower(name)

	for _, pkg := range []string{".deb", ".rpm", ".msi", ".dmg", ".pkg", ".exe", ".snap", ".apk"} {
		if strings.HasSuffix(lower, pkg) {
			return false
		}
	}
	if strings.HasSuffix(lower, ".sha256") || strings.HasSuffix(lower, ".sha256sum") {
		return false
	}
	if strings.HasPrefix(lower, "checksums") {
		return false
	}
	return true
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

// ParseChecksum extracts the SHA-256 digest for the given asset from a
// checksum manifest. It supports the goreleaser checksums.txt format
// ("<hex>  <name>"), the sha256sum format ("<hex>  *name"), and a bare
// "<hex>" file. Returns an error (fail-closed) if no matching digest is
// found or the digest is not a valid 64-character hex string.
func ParseChecksum(content, assetName string) (string, error) {
	for _, line := range strings.Split(content, "\n") {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		fields := strings.Fields(line)
		digest := fields[0]
		if len(fields) == 1 {
			if isHexDigest(digest) {
				return digest, nil
			}
			continue
		}
		name := strings.TrimPrefix(fields[1], "*")
		if name != assetName && !strings.HasSuffix(name, "/"+assetName) {
			continue
		}
		if isHexDigest(digest) {
			return digest, nil
		}
	}
	return "", fmt.Errorf("no SHA-256 digest found for %q in checksum manifest", assetName)
}

// isHexDigest reports whether s is a hex-encoded 256-bit digest (exactly 64
// hexadecimal characters).
func isHexDigest(s string) bool {
	if len(s) != 64 {
		return false
	}
	for i := 0; i < len(s); i++ {
		c := s[i]
		if !((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f') || (c >= 'A' && c <= 'F')) {
			return false
		}
	}
	return true
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

	// Release tags are prefixed installer/vX.Y.Z (see
	// .github/workflows/release-installer.yml); strip both prefixes before
	// comparing against the version baked into the binary.
	tag := strings.TrimPrefix(release.Tag, "v")
	tag = strings.TrimPrefix(tag, "installer/")
	current := strings.TrimPrefix(currentVersion, "v")
	current = strings.TrimPrefix(current, "installer/")

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
// It writes to a temp file, chmod +x, then renames atomically. A non-empty
// SHA-256 checksum is mandatory: if verifySHA is empty the update is refused
// (fail-closed) rather than applied unverified.
func ApplyUpdate(data []byte, targetPath, verifySHA string) error {
	// SHA-256 verification is mandatory.
	if verifySHA == "" {
		return fmt.Errorf("cannot apply update: missing SHA-256 checksum")
	}
	hash := sha256.Sum256(data)
	got := fmt.Sprintf("%x", hash)
	if !strings.EqualFold(got, verifySHA) {
		return fmt.Errorf("SHA-256 mismatch: got %s, expected %s", got, verifySHA)
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
// A prerelease suffix (e.g. "1.0.0-beta") sorts below the stable
// release with the same version core ("1.0.0").
func compareSemver(a, b string) int {
	partsA := strings.Split(a, ".")
	partsB := strings.Split(b, ".")

	maxLen := len(partsA)
	if len(partsB) > maxLen {
		maxLen = len(partsB)
	}

	var preA, preB string

	for i := 0; i < maxLen; i++ {
		var numA, numB int
		if i < len(partsA) {
			numA, preA = parseVersionPart(partsA[i])
		}
		if i < len(partsB) {
			numB, preB = parseVersionPart(partsB[i])
		}
		if numA < numB {
			return -1
		}
		if numA > numB {
			return 1
		}
	}

	// Identical version cores: a release without a prerelease wins over
	// one with it; otherwise compare prereleases lexicographically.
	switch {
	case preA == "" && preB == "":
		return 0
	case preA == "":
		return 1
	case preB == "":
		return -1
	case preA < preB:
		return -1
	case preA > preB:
		return 1
	default:
		return 0
	}
}

// parseVersionPart splits a numeric version component from an optional
// prerelease suffix (e.g. "0-beta" → 0, "beta").
func parseVersionPart(part string) (int, string) {
	var n int
	if idx := strings.IndexByte(part, '-'); idx >= 0 {
		fmt.Sscanf(part[:idx], "%d", &n)
		return n, part[idx+1:]
	}
	fmt.Sscanf(part, "%d", &n)
	return n, ""
}
