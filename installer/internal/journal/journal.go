// Package journal implements a mutation journal that captures file before-images
// and supports atomic rollback. Modeled after Gentle AI's journal pattern.
package journal

import (
	"bytes"
	"io/fs"
	"os"
	"path/filepath"
)

// WriteResult describes the outcome of a journal write operation.
type WriteResult struct {
	Changed bool
}

// RemoveResult describes the outcome of a journal remove operation.
type RemoveResult struct {
	Removed bool
}

// journalEntry stores the before-image of a single file.
type journalEntry struct {
	originalPath string
	beforeData   []byte
	beforeMode   fs.FileMode
	existed      bool
}

// Journal tracks file mutations and can restore the original state.
type Journal struct {
	roots  []string
	before map[string]*journalEntry
}

// New creates a Journal with the given roots. Roots determine where restore
// can write files. If no roots are provided, defaults to ~/.quantlab and
// ~/.config/opencode.
func New(roots ...string) *Journal {
	if len(roots) == 0 {
		home, _ := os.UserHomeDir()
		roots = []string{
			filepath.Join(home, ".quantlab"),
			filepath.Join(home, ".config", "opencode"),
		}
	}
	return &Journal{
		roots:  roots,
		before: make(map[string]*journalEntry),
	}
}

// Capture stores the before-image of the file at the given path. If the file
// does not exist, the entry is still created so Restore can remove it.
func (j *Journal) Capture(path string) error {
	data, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			j.before[path] = &journalEntry{
				originalPath: path,
				existed:      false,
			}
			return nil
		}
		return err
	}

	info, err := os.Stat(path)
	if err != nil {
		return err
	}

	j.before[path] = &journalEntry{
		originalPath: path,
		beforeData:   data,
		beforeMode:   info.Mode(),
		existed:      true,
	}
	return nil
}

// Restore replays all captured before-images, restoring each file to its
// original state. Files that didn't exist before are removed.
func (j *Journal) Restore() error {
	var lastErr error
	for path, entry := range j.before {
		if entry == nil {
			continue
		}
		if !entry.existed {
			if err := os.Remove(path); err != nil && !os.IsNotExist(err) {
				lastErr = err
			}
			continue
		}
		if err := os.WriteFile(path, entry.beforeData, entry.beforeMode); err != nil {
			lastErr = err
		}
	}
	return lastErr
}

// WriteWithMode atomically writes data to the given path using a temp-file +
// rename pattern. The before-image is captured if not already tracked. Returns
// a WriteResult indicating whether the file was actually changed.
func (j *Journal) WriteWithMode(path string, data []byte, mode fs.FileMode) (*WriteResult, error) {
	if _, exists := j.before[path]; !exists {
		if err := j.Capture(path); err != nil {
			return nil, err
		}
	}

	// Compare-and-swap: skip write if content is identical
	entry := j.before[path]
	if entry != nil && entry.existed && bytes.Equal(entry.beforeData, data) {
		return &WriteResult{Changed: false}, nil
	}

	dir := filepath.Dir(path)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return nil, err
	}

	tmpPath := path + ".tmp"
	if err := os.WriteFile(tmpPath, data, mode); err != nil {
		return nil, err
	}
	if err := os.Rename(tmpPath, path); err != nil {
		os.Remove(tmpPath)
		return nil, err
	}

	return &WriteResult{Changed: true}, nil
}

// Remove removes the file at path after capturing its before-image. Returns a
// RemoveResult indicating whether the file was actually removed.
func (j *Journal) Remove(path string) (*RemoveResult, error) {
	if _, exists := j.before[path]; !exists {
		if err := j.Capture(path); err != nil {
			return nil, err
		}
	}

	if err := os.Remove(path); err != nil {
		if os.IsNotExist(err) {
			return &RemoveResult{Removed: false}, nil
		}
		return nil, err
	}

	return &RemoveResult{Removed: true}, nil
}
