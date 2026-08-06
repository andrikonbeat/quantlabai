// Package filemerge provides atomic file-writing and JSON merge utilities.
package filemerge

import (
	"bytes"
	"io/fs"
	"os"
	"path/filepath"
)

// WriteResult describes the outcome of WriteFileAtomic.
type WriteResult struct {
	Changed bool
}

// WriteFileAtomic writes data to path using a temp-file + rename pattern.
// If the content at path is already identical to data, no write occurs (compare-and-swap).
// Parent directories are created as needed.
func WriteFileAtomic(path string, data []byte, perm fs.FileMode) (WriteResult, error) {
	if existing, err := os.ReadFile(path); err == nil && bytes.Equal(existing, data) {
		return WriteResult{Changed: false}, nil
	}

	dir := filepath.Dir(path)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return WriteResult{}, err
	}

	tmpPath := path + ".tmp"
	if err := os.WriteFile(tmpPath, data, perm); err != nil {
		return WriteResult{}, err
	}
	if err := os.Rename(tmpPath, path); err != nil {
		os.Remove(tmpPath)
		return WriteResult{}, err
	}

	return WriteResult{Changed: true}, nil
}
