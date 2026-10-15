// Package opencode — prompt ownership.
//
// QuantLab shares ~/.config/opencode/prompts/ with the user's own prompts,
// so uninstall must delete exactly what QuantLab installed — never the whole
// directory. Ownership is recorded in a manifest dotfile that both prompt
// writers maintain:
//
//   - the Go installer records its embedded top-level prompts
//     (e.g. "guardian-orchestrator.md"),
//   - ai/opencode/sync_prompts.py records "quantlab/<name>" entries.
//
// On uninstall only listed entries are deleted; foreign files are left
// untouched, and the manifest itself is removed last.
package opencode

import (
	"encoding/json"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"github.com/andrikonbeat/quantlabai/internal/filemerge"
)

// PromptManifestName is the dotfile, inside the prompts directory, listing
// every prompt path QuantLab manages. Paths are slash-separated and relative
// to the prompts dir ("guardian-orchestrator.md", "quantlab/campaign.md").
const PromptManifestName = ".quantlab-managed.json"

// promptManifest is the on-disk shape of the ownership file.
type promptManifest struct {
	Prompts []string `json:"prompts"`
}

// ManagedPromptsPath returns the manifest path for a prompts directory.
func ManagedPromptsPath(promptsDir string) string {
	return filepath.Join(promptsDir, PromptManifestName)
}

// ReadManagedPrompts returns the recorded managed prompt paths, sorted and
// deduplicated. A missing manifest means "nothing recorded" (empty, nil) —
// callers fall back to the embedded asset names.
func ReadManagedPrompts(promptsDir string) ([]string, error) {
	if promptsDir == "" {
		return nil, fmt.Errorf("prompts directory is empty")
	}
	data, err := os.ReadFile(ManagedPromptsPath(promptsDir))
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil
		}
		return nil, fmt.Errorf("read prompt manifest: %w", err)
	}
	var m promptManifest
	if err := json.Unmarshal(data, &m); err != nil {
		return nil, fmt.Errorf("parse prompt manifest: %w", err)
	}
	return dedupeSorted(m.Prompts), nil
}

// RecordManagedPrompts merges names (relative slash-separated paths) into the
// manifest, creating it when absent. Existing foreign entries are preserved:
// both writers union into the same file. A no-op when names is empty and the
// manifest already exists; creates an empty manifest otherwise so later reads
// distinguish "recorded, nothing managed" from "never recorded".
func RecordManagedPrompts(promptsDir string, names []string) error {
	if promptsDir == "" {
		return fmt.Errorf("prompts directory is empty")
	}
	if err := os.MkdirAll(promptsDir, 0o755); err != nil {
		return fmt.Errorf("create prompts dir: %w", err)
	}
	existing, err := ReadManagedPrompts(promptsDir)
	if err != nil {
		return err
	}
	merged := dedupeSorted(append(append([]string(nil), existing...), names...))
	data, err := json.MarshalIndent(promptManifest{Prompts: merged}, "", "  ")
	if err != nil {
		return fmt.Errorf("marshal prompt manifest: %w", err)
	}
	data = append(data, '\n')
	if _, err := filemerge.WriteFileAtomic(ManagedPromptsPath(promptsDir), data, 0o644); err != nil {
		return fmt.Errorf("write prompt manifest: %w", err)
	}
	return nil
}

// EmbeddedPromptNames lists the top-level prompt files in the embedded
// assets ("prompts" dir of the given FS). Used to record ownership at install
// time and as a conservative fallback when no manifest exists.
func EmbeddedPromptNames(assets fs.FS) ([]string, error) {
	var names []string
	err := fs.WalkDir(assets, "prompts", func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if d.IsDir() {
			return nil
		}
		rel, err := filepath.Rel("prompts", path)
		if err != nil {
			return err
		}
		names = append(names, filepath.ToSlash(rel))
		return nil
	})
	if err != nil {
		return nil, fmt.Errorf("walk embedded prompts directory: %w", err)
	}
	return dedupeSorted(names), nil
}

// RemoveManagedPrompts deletes exactly the listed managed prompt paths,
// relative to promptsDir. Foreign files are never touched. Entries escaping
// the directory (absolute paths, "..") are skipped. The manifest file itself
// is never deleted by this function — callers remove it explicitly last via
// RemovePromptManifest. Returns the removed relative paths.
func RemoveManagedPrompts(promptsDir string, managed []string) ([]string, error) {
	if promptsDir == "" {
		return nil, fmt.Errorf("prompts directory is empty")
	}
	var removed []string
	for _, rel := range managed {
		rel = filepath.FromSlash(rel)
		if filepath.IsAbs(rel) {
			continue
		}
		target := filepath.Join(promptsDir, rel)
		// Containment: the cleaned target must stay inside promptsDir.
		cleanRoot := filepath.Clean(promptsDir)
		cleanTarget := filepath.Clean(target)
		if cleanTarget != cleanRoot && !strings.HasPrefix(cleanTarget, cleanRoot+string(os.PathSeparator)) {
			continue
		}
		if filepath.Base(cleanTarget) == PromptManifestName {
			continue
		}
		if err := os.Remove(cleanTarget); err != nil {
			if os.IsNotExist(err) {
				continue
			}
			return removed, fmt.Errorf("remove managed prompt %q: %w", rel, err)
		}
		removed = append(removed, filepath.ToSlash(rel))
	}
	return removed, nil
}

// RemovePromptManifest deletes the ownership file itself. Call after
// RemoveManagedPrompts. Missing file is not an error.
func RemovePromptManifest(promptsDir string) error {
	if promptsDir == "" {
		return fmt.Errorf("prompts directory is empty")
	}
	if err := os.Remove(ManagedPromptsPath(promptsDir)); err != nil && !os.IsNotExist(err) {
		return fmt.Errorf("remove prompt manifest: %w", err)
	}
	return nil
}

// RemoveEmptyManagedDirs removes managed subdirectories (e.g. "quantlab/")
// when they are left empty after RemoveManagedPrompts. Directories still
// holding foreign files are kept. The prompts root itself is never removed.
func RemoveEmptyManagedDirs(promptsDir string, managed []string) error {
	if promptsDir == "" {
		return fmt.Errorf("prompts directory is empty")
	}
	dirs := make(map[string]bool)
	for _, rel := range managed {
		dir := filepath.Dir(filepath.FromSlash(rel))
		if dir != "." {
			dirs[dir] = true
		}
	}
	for dir := range dirs {
		target := filepath.Join(promptsDir, dir)
		cleanRoot := filepath.Clean(promptsDir)
		cleanTarget := filepath.Clean(target)
		if cleanTarget == cleanRoot || !strings.HasPrefix(cleanTarget, cleanRoot+string(os.PathSeparator)) {
			continue
		}
		// os.Remove only removes empty directories.
		if err := os.Remove(cleanTarget); err != nil && !os.IsNotExist(err) {
			// Non-empty (foreign files inside): keep it. Only report
			// unexpected errors; ENOTEMPTY/EEXIST mean "not empty".
			if !os.IsExist(err) && !strings.Contains(err.Error(), "not empty") && !strings.Contains(err.Error(), "directory not empty") {
				return fmt.Errorf("remove empty managed dir %q: %w", dir, err)
			}
		}
	}
	return nil
}

// CountForeignPrompts counts top-level files in promptsDir that are neither
// managed nor the manifest — i.e. the user's own prompts we must not touch.
// Subdirectories (e.g. quantlab/) are not counted here; their foreign files
// are protected by exact-name deletion instead.
func CountForeignPrompts(promptsDir string, managed []string) (int, error) {
	owned := make(map[string]bool, len(managed)+1)
	for _, rel := range managed {
		owned[filepath.FromSlash(rel)] = true
	}
	owned[PromptManifestName] = true
	entries, err := os.ReadDir(promptsDir)
	if err != nil {
		if os.IsNotExist(err) {
			return 0, nil
		}
		return 0, fmt.Errorf("read prompts dir: %w", err)
	}
	foreign := 0
	for _, e := range entries {
		if e.IsDir() {
			continue
		}
		if !owned[e.Name()] {
			foreign++
		}
	}
	return foreign, nil
}

func dedupeSorted(in []string) []string {
	seen := make(map[string]bool, len(in))
	out := make([]string, 0, len(in))
	for _, s := range in {
		s = strings.TrimSpace(s)
		if s == "" || s == "." || seen[s] {
			continue
		}
		seen[s] = true
		out = append(out, s)
	}
	sort.Strings(out)
	return out
}
