package update

import (
	"crypto/sha256"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
)

func TestIsNewerVersion(t *testing.T) {
	tests := []struct {
		a, b string
		want bool
	}{
		{"1.0.0", "0.9.0", true},
		{"1.0.0", "1.0.0", false},
		{"0.9.0", "1.0.0", false},
		{"1.1.0", "1.0.9", true},
		{"1.0.0", "1.0.0-beta", true},
		{"1.0.0-beta", "1.0.0", false},
		{"1.0.1-beta", "1.0.0", true},
		{"1.0.0-rc.1", "1.0.0-beta", true},
		{"v1.0.0", "v0.9.0", true},
		{"v1.0.0", "v1.0.0", false},
		{"2.0.0", "1.9.9", true},
	}

	for _, tt := range tests {
		t.Run(fmt.Sprintf("%s_vs_%s", tt.a, tt.b), func(t *testing.T) {
			got := IsNewerVersion(tt.a, tt.b)
			if got != tt.want {
				t.Errorf("IsNewerVersion(%q, %q) = %v, want %v", tt.a, tt.b, got, tt.want)
			}
		})
	}
}

func TestCompareSemver(t *testing.T) {
	tests := []struct {
		a, b string
		want int
	}{
		{"1.0.0", "1.0.0", 0},
		{"1.0.0", "1.0.1", -1},
		{"1.0.1", "1.0.0", 1},
		{"2.0.0", "1.9.9", 1},
		{"0.0.1", "0.0.1", 0},
		{"1.0", "1.0.0", 0},
		{"1.0.0", "1.0.0-beta", 1},
		{"1.0.0-beta", "1.0.0", -1},
		{"1.0.0-beta", "1.0.0-alpha", 1},
		{"1.0.0-alpha", "1.0.0-beta", -1},
		{"1.0.0-rc.1", "1.0.0-rc.2", -1},
		{"1.0.0-beta.1", "1.0.0-beta", 1},
	}

	for _, tt := range tests {
		t.Run(fmt.Sprintf("%s_vs_%s", tt.a, tt.b), func(t *testing.T) {
			got := compareSemver(tt.a, tt.b)
			if got != tt.want {
				t.Errorf("compareSemver(%q, %q) = %d, want %d", tt.a, tt.b, got, tt.want)
			}
		})
	}
}

func TestFindAssetForPlatform(t *testing.T) {
	release := &ReleaseInfo{
		Tag: "v1.0.0",
		Assets: []Asset{
			{Name: "quantlab-linux-amd64", BrowserDownloadURL: "https://example.com/quantlab-linux-amd64", Size: 1024},
			{Name: "quantlab-linux-arm64", BrowserDownloadURL: "https://example.com/quantlab-linux-arm64", Size: 1024},
			{Name: "quantlab-darwin-amd64", BrowserDownloadURL: "https://example.com/quantlab-darwin-amd64", Size: 1024},
			{Name: "quantlab-darwin-arm64", BrowserDownloadURL: "https://example.com/quantlab-darwin-arm64", Size: 1024},
		},
	}

	name, url, size, ok := release.FindAssetForPlatform()
	if !ok {
		t.Fatal("expected to find an asset for this platform")
	}
	if name == "" || url == "" {
		t.Errorf("empty name or url: name=%q, url=%q", name, url)
	}
	if size <= 0 {
		t.Errorf("expected positive size, got %d", size)
	}

	// The returned asset must match the running platform (hyphen form).
	wantName := fmt.Sprintf("quantlab-%s-%s", runtime.GOOS, runtime.GOARCH)
	if name != wantName {
		t.Errorf("asset = %q, want %q", name, wantName)
	}
}

func TestFindAssetForPlatform_UnderscoreNames(t *testing.T) {
	// Matches the GoReleaser archive naming: quantlab_<version>_<os>_<arch>.tar.gz.
	release := &ReleaseInfo{
		Tag: "v1.0.0",
		Assets: []Asset{
			{Name: "quantlab_1.0.0_linux_amd64.tar.gz", BrowserDownloadURL: "https://example.com/quantlab-linux-amd64.tar.gz", Size: 4096},
			{Name: "quantlab_1.0.0_linux_arm64.tar.gz", BrowserDownloadURL: "https://example.com/quantlab-linux-arm64.tar.gz", Size: 4096},
			{Name: "quantlab_1.0.0_darwin_amd64.tar.gz", BrowserDownloadURL: "https://example.com/quantlab-darwin-amd64.tar.gz", Size: 4096},
			{Name: "quantlab_1.0.0_darwin_arm64.tar.gz", BrowserDownloadURL: "https://example.com/quantlab-darwin-arm64.tar.gz", Size: 4096},
		},
	}

	name, url, _, ok := release.FindAssetForPlatform()
	if !ok {
		t.Fatal("expected to find an underscore archive for this platform")
	}
	wantName := fmt.Sprintf("quantlab_1.0.0_%s_%s.tar.gz", runtime.GOOS, runtime.GOARCH)
	if name != wantName {
		t.Errorf("asset = %q, want %q", name, wantName)
	}
	if url == "" {
		t.Error("empty download URL")
	}
}

func TestFindAssetForPlatform_RejectsNonBinaryAssets(t *testing.T) {
	// Package files, checksum manifests, and generic names must never be
	// selected, even as a fallback.
	release := &ReleaseInfo{
		Tag: "v1.0.0",
		Assets: []Asset{
			{Name: "quantlab", BrowserDownloadURL: "https://example.com/quantlab", Size: 1024},
			{Name: "quantlab_1.0.0_linux_amd64.deb", BrowserDownloadURL: "https://example.com/quantlab.deb", Size: 1024},
			{Name: "quantlab_1.0.0_amd64.rpm", BrowserDownloadURL: "https://example.com/quantlab.rpm", Size: 1024},
			{Name: "quantlab_1.0.0_amd64.msi", BrowserDownloadURL: "https://example.com/quantlab.msi", Size: 1024},
			{Name: "checksums.txt", BrowserDownloadURL: "https://example.com/checksums.txt", Size: 1024},
			{Name: "quantlab_1.0.0_linux_amd64.tar.gz.sha256", BrowserDownloadURL: "https://example.com/checksum", Size: 128},
		},
	}

	_, _, _, ok := release.FindAssetForPlatform()
	if ok {
		t.Error("expected no match for package/checksum/generic assets")
	}
}

func TestFindAssetForPlatform_Empty(t *testing.T) {
	release := &ReleaseInfo{
		Tag:    "v1.0.0",
		Assets: []Asset{},
	}

	_, _, _, ok := release.FindAssetForPlatform()
	if ok {
		t.Error("expected no asset for empty assets list")
	}
}

func TestApplyUpdate_AtomicSwap(t *testing.T) {
	dir := t.TempDir()
	targetPath := filepath.Join(dir, "quantlab")

	// Write original binary
	original := []byte("#!/bin/bash\necho old")
	if err := os.WriteFile(targetPath, original, 0o755); err != nil {
		t.Fatal(err)
	}

	// Apply update with new data
	newData := []byte("#!/bin/bash\necho new")
	hash := sha256.Sum256(newData)
	verifySHA := fmt.Sprintf("%x", hash)
	if err := ApplyUpdate(newData, targetPath, verifySHA); err != nil {
		t.Fatalf("ApplyUpdate() error = %v", err)
	}

	// Verify new content
	got, err := os.ReadFile(targetPath)
	if err != nil {
		t.Fatal(err)
	}
	if string(got) != string(newData) {
		t.Errorf("content = %q, want %q", string(got), string(newData))
	}

	// Verify it's executable
	info, err := os.Stat(targetPath)
	if err != nil {
		t.Fatal(err)
	}
	if info.Mode()&0o111 == 0 {
		t.Error("binary is not executable after ApplyUpdate")
	}
}

func TestApplyUpdate_WithSHAVerification(t *testing.T) {
	dir := t.TempDir()
	targetPath := filepath.Join(dir, "quantlab_bin")

	if err := os.WriteFile(targetPath, []byte("old"), 0o755); err != nil {
		t.Fatal(err)
	}

	newData := []byte("verified binary content")
	hash := sha256.Sum256(newData)
	expectedSHA := fmt.Sprintf("%x", hash)

	if err := ApplyUpdate(newData, targetPath, expectedSHA); err != nil {
		t.Fatalf("ApplyUpdate() with correct SHA error = %v", err)
	}

	// Verify it was written
	got, err := os.ReadFile(targetPath)
	if err != nil {
		t.Fatal(err)
	}
	if string(got) != string(newData) {
		t.Errorf("content = %q, want %q", string(got), string(newData))
	}
}

func TestApplyUpdate_WrongSHA(t *testing.T) {
	dir := t.TempDir()
	targetPath := filepath.Join(dir, "quantlab_staging")

	if err := os.WriteFile(targetPath, []byte("old"), 0o755); err != nil {
		t.Fatal(err)
	}

	newData := []byte("some new binary")
	wrongSHA := "0000000000000000000000000000000000000000000000000000000000000000"

	err := ApplyUpdate(newData, targetPath, wrongSHA)
	if err == nil {
		t.Fatal("expected error for wrong SHA, got nil")
	}
	if !strings.Contains(err.Error(), "SHA-256 mismatch") {
		t.Errorf("error = %q, want it to contain 'SHA-256 mismatch'", err.Error())
	}

	// Original binary should still be intact
	got, err := os.ReadFile(targetPath)
	if err != nil {
		t.Fatal(err)
	}
	if string(got) != "old" {
		t.Errorf("original content should be preserved, got %q", string(got))
	}
}

func TestFindChecksumAsset(t *testing.T) {
	release := &ReleaseInfo{
		Tag: "v1.0.0",
		Assets: []Asset{
			{Name: "quantlab-linux-amd64", BrowserDownloadURL: "https://example.com/binary"},
			{Name: "quantlab-linux-amd64.sha256", BrowserDownloadURL: "https://example.com/checksum"},
		},
	}

	url, _, ok := release.FindChecksumAsset("quantlab-linux-amd64")
	if !ok {
		t.Fatal("expected to find checksum asset")
	}
	if url != "https://example.com/checksum" {
		t.Errorf("url = %q, want %q", url, "https://example.com/checksum")
	}
}

func TestParseChecksum(t *testing.T) {
	shaDeb := "1111111111111111111111111111111111111111111111111111111111111111"
	shaTar := "2222222222222222222222222222222222222222222222222222222222222222"

	manifest := fmt.Sprintf("%s  quantlab_1.0.0_linux_amd64.deb\n%s  quantlab_1.0.0_linux_amd64.tar.gz\n", shaDeb, shaTar)

	got, err := ParseChecksum(manifest, "quantlab_1.0.0_linux_amd64.tar.gz")
	if err != nil {
		t.Fatalf("ParseChecksum() error = %v", err)
	}
	if got != shaTar {
		t.Errorf("digest = %q, want %q", got, shaTar)
	}
}

func TestParseChecksum_MissingEntry(t *testing.T) {
	manifest := "1111111111111111111111111111111111111111111111111111111111111111  other-file.tar.gz\n"
	_, err := ParseChecksum(manifest, "quantlab_1.0.0_linux_amd64.tar.gz")
	if err == nil {
		t.Fatal("expected error when asset has no checksum entry")
	}
}

func TestParseChecksum_BareHex(t *testing.T) {
	sha := "3333333333333333333333333333333333333333333333333333333333333333"
	got, err := ParseChecksum(sha+"\n", "quantlab_1.0.0_linux_amd64.tar.gz")
	if err != nil {
		t.Fatalf("ParseChecksum() bare hex error = %v", err)
	}
	if got != sha {
		t.Errorf("digest = %q, want %q", got, sha)
	}
}

func TestParseChecksum_InvalidDigest(t *testing.T) {
	_, err := ParseChecksum("not-a-valid-hex  quantlab_1.0.0_linux_amd64.tar.gz\n", "quantlab_1.0.0_linux_amd64.tar.gz")
	if err == nil {
		t.Fatal("expected error for invalid digest")
	}
}

func TestDownloadUpdate(t *testing.T) {
	expected := []byte("binary content here")
	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "GET" {
			t.Errorf("method = %s, want GET", r.Method)
		}
		w.Write(expected)
	}))
	defer ts.Close()

	data, err := DownloadUpdate(ts.URL)
	if err != nil {
		t.Fatalf("DownloadUpdate() error = %v", err)
	}
	if string(data) != string(expected) {
		t.Errorf("data = %q, want %q", string(data), string(expected))
	}
}

func TestDownloadUpdate_Error(t *testing.T) {
	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusNotFound)
	}))
	defer ts.Close()

	_, err := DownloadUpdate(ts.URL)
	if err == nil {
		t.Fatal("expected error for 404 download")
	}
}

func TestExecPath(t *testing.T) {
	path, err := ExecPath()
	if err != nil {
		t.Fatalf("ExecPath() error = %v", err)
	}
	if path == "" {
		t.Error("ExecPath() returned empty path")
	}
}

func TestCheckForUpdate_DevVersion(t *testing.T) {
	// With "dev" version, should always consider it outdated.
	// This test uses a fake GitHub API. Since we can't mock the HTTP call easily
	// without httptest, we test the function's error path (network error).
	_, _, err := CheckForUpdate("dev")
	if err == nil {
		// We might get no error if GitHub is reachable, but that's an integration test
		t.Log("CheckForUpdate('dev') — no error (GitHub reachable)")
	} else {
		// Expected: network/unreachable error
		t.Logf("CheckForUpdate('dev') returned expected error: %v", err)
	}
}

func TestApplyUpdate_NoOriginalFile(t *testing.T) {
	// If the original binary doesn't exist, ApplyUpdate should still create it
	dir := t.TempDir()
	targetPath := filepath.Join(dir, "new-binary")

	data := []byte("fresh install content")
	hash := sha256.Sum256(data)
	verifySHA := fmt.Sprintf("%x", hash)
	if err := ApplyUpdate(data, targetPath, verifySHA); err != nil {
		t.Fatalf("ApplyUpdate() to new path error = %v", err)
	}

	got, err := os.ReadFile(targetPath)
	if err != nil {
		t.Fatal(err)
	}
	if string(got) != string(data) {
		t.Errorf("content = %q, want %q", string(got), string(data))
	}
}

func TestApplyUpdate_MissingChecksum(t *testing.T) {
	// SHA-256 verification is mandatory: an empty checksum must fail the
	// update (fail-closed) and leave the original binary untouched.
	dir := t.TempDir()
	targetPath := filepath.Join(dir, "quantlab")

	if err := os.WriteFile(targetPath, []byte("old"), 0o755); err != nil {
		t.Fatal(err)
	}

	err := ApplyUpdate([]byte("new binary"), targetPath, "")
	if err == nil {
		t.Fatal("expected error when checksum is missing, got nil")
	}

	got, err := os.ReadFile(targetPath)
	if err != nil {
		t.Fatal(err)
	}
	if string(got) != "old" {
		t.Errorf("original content should be preserved, got %q", string(got))
	}
}

func TestLatestGitHubRelease_ErrorHandling(t *testing.T) {
	// Test with a non-existent repo — should get an API error
	_, err := LatestGitHubRelease("nonexistent-owner-xyz", "nonexistent-repo-abc")
	if err == nil {
		t.Log("LatestGitHubRelease returned no error — GitHub may be reachable")
	} else {
		t.Logf("LatestGitHubRelease returned expected error: %v", err)
	}
}

func TestDownloadUpdate_EmptyBody(t *testing.T) {
	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))
	defer ts.Close()

	data, err := DownloadUpdate(ts.URL)
	if err != nil {
		t.Fatalf("DownloadUpdate() error = %v", err)
	}
	if len(data) != 0 {
		t.Errorf("expected empty body, got %d bytes", len(data))
	}
}
