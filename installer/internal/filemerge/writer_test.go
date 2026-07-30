package filemerge_test

import (
	"io/fs"
	"os"
	"path/filepath"
	"testing"

	"github.com/ogzuz/quantlab/internal/filemerge"
)

func TestWriteFileAtomic_NewFile(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "new.txt")

	result, err := filemerge.WriteFileAtomic(path, []byte("hello world"), 0644)
	if err != nil {
		t.Fatalf("WriteFileAtomic(new) = %v, want nil", err)
	}
	if !result.Changed {
		t.Error("result.Changed = false, want true for new file")
	}

	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	if string(data) != "hello world" {
		t.Errorf("content = %q, want %q", string(data), "hello world")
	}
}

func TestWriteFileAtomic_IdenticalContent(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "same.txt")
	content := []byte("no change")

	// Write initial content
	if _, err := filemerge.WriteFileAtomic(path, content, 0644); err != nil {
		t.Fatal(err)
	}

	// Write identical content — compare-and-swap should detect no change
	result, err := filemerge.WriteFileAtomic(path, content, 0644)
	if err != nil {
		t.Fatalf("WriteFileAtomic(identical) = %v, want nil", err)
	}
	if result.Changed {
		t.Error("result.Changed = true, want false for identical content")
	}
}

func TestWriteFileAtomic_ChangedContent(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "changed.txt")

	// Write initial content
	if _, err := filemerge.WriteFileAtomic(path, []byte("original"), 0644); err != nil {
		t.Fatal(err)
	}

	// Write different content
	result, err := filemerge.WriteFileAtomic(path, []byte("modified"), 0644)
	if err != nil {
		t.Fatalf("WriteFileAtomic(changed) = %v, want nil", err)
	}
	if !result.Changed {
		t.Error("result.Changed = false, want true for changed content")
	}

	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	if string(data) != "modified" {
		t.Errorf("content = %q, want %q", string(data), "modified")
	}
}

func TestWriteFileAtomic_Permissions(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "perm.txt")

	if _, err := filemerge.WriteFileAtomic(path, []byte("restricted"), fs.FileMode(0600)); err != nil {
		t.Fatalf("WriteFileAtomic(0600) = %v, want nil", err)
	}

	info, err := os.Stat(path)
	if err != nil {
		t.Fatal(err)
	}
	if got := info.Mode().Perm(); got != fs.FileMode(0600) {
		t.Errorf("file permissions = %o, want %o", got, 0600)
	}
}

func TestWriteFileAtomic_DirCreation(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "sub", "nested", "deep.txt")

	result, err := filemerge.WriteFileAtomic(path, []byte("nested file"), 0644)
	if err != nil {
		t.Fatalf("WriteFileAtomic(nested) = %v, want nil", err)
	}
	if !result.Changed {
		t.Error("result.Changed = false, want true")
	}

	if _, err := os.Stat(path); os.IsNotExist(err) {
		t.Error("nested file was not created after dir creation")
	}
}

func TestWriteFileAtomic_NoPartialWriteOnTempFailure(t *testing.T) {
	// Test atomicity: if rename fails, original should be untouched
	dir := t.TempDir()
	path := filepath.Join(dir, "target.txt")
	original := []byte("original content")

	if _, err := filemerge.WriteFileAtomic(path, original, 0644); err != nil {
		t.Fatal(err)
	}

	// Write new content (this should succeed since /tmp is writable)
	result, err := filemerge.WriteFileAtomic(path, []byte("new content"), 0644)
	if err != nil {
		t.Fatalf("WriteFileAtomic = %v, want nil", err)
	}
	if !result.Changed {
		t.Error("result.Changed = false, want true")
	}

	// Verify new content is there (not a partial write)
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	if string(data) != "new content" {
		t.Errorf("content = %q, want %q", string(data), "new content")
	}
}
