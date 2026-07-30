package opencode

import (
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"strings"

	"github.com/ogzuz/quantlab/installer/internal/filemerge"
)

// InstallSkills copies embedded skill files from the given embed.FS to the
// target skills directory. Each skill subdirectory under assets/skills/ is
// copied to <skillsDir>/<skill-name>/SKILL.md. Returns the list of installed
// or updated file paths.
func InstallSkills(assets fs.FS, skillsDir string) ([]string, error) {
	if skillsDir == "" {
		return nil, fmt.Errorf("skills directory is empty")
	}

	entries, err := fs.ReadDir(assets, "skills")
	if err != nil {
		return nil, fmt.Errorf("read embedded skills directory: %w", err)
	}

	var installed []string

	for _, entry := range entries {
		if !entry.IsDir() {
			continue
		}
		skillName := entry.Name()
		assetDir := filepath.Join("skills", skillName)

		skillFiles, err := fs.ReadDir(assets, assetDir)
		if err != nil {
			return nil, fmt.Errorf("read skill %q: %w", skillName, err)
		}

		for _, file := range skillFiles {
			if file.IsDir() {
				continue
			}
			assetPath := filepath.ToSlash(filepath.Join(assetDir, file.Name()))
			content, err := fs.ReadFile(assets, assetPath)
			if err != nil {
				return nil, fmt.Errorf("read embedded skill file %q: %w", assetPath, err)
			}
			if len(content) == 0 {
				return nil, fmt.Errorf("embedded skill file %q is empty", assetPath)
			}

			destPath := filepath.Join(skillsDir, skillName, file.Name())
			result, err := filemerge.WriteFileAtomic(destPath, content, 0o644)
			if err != nil {
				return nil, fmt.Errorf("write skill %q: %w", destPath, err)
			}
			if result.Changed {
				installed = append(installed, destPath)
			}
		}
	}

	return installed, nil
}

// InstallPrompts copies embedded prompt files from the given embed.FS to the
// target prompts directory. Returns the list of installed or updated file paths.
func InstallPrompts(assets fs.FS, promptsDir string) ([]string, error) {
	if promptsDir == "" {
		return nil, fmt.Errorf("prompts directory is empty")
	}

	entries, err := fs.ReadDir(assets, "prompts")
	if err != nil {
		return nil, fmt.Errorf("read embedded prompts directory: %w", err)
	}

	var installed []string

	for _, entry := range entries {
		if entry.IsDir() {
			continue
		}
		assetPath := filepath.ToSlash(filepath.Join("prompts", entry.Name()))
		content, err := fs.ReadFile(assets, assetPath)
		if err != nil {
			return nil, fmt.Errorf("read embedded prompt %q: %w", assetPath, err)
		}
		if len(content) == 0 {
			return nil, fmt.Errorf("embedded prompt %q is empty", assetPath)
		}

		destPath := filepath.Join(promptsDir, entry.Name())
		result, err := filemerge.WriteFileAtomic(destPath, content, 0o644)
		if err != nil {
			return nil, fmt.Errorf("write prompt %q: %w", destPath, err)
		}
		if result.Changed {
			installed = append(installed, destPath)
		}
	}

	return installed, nil
}

// RemovePrompts removes all files in the given prompts directory.
// Returns the list of removed file paths.
func RemovePrompts(promptsDir string) ([]string, error) {
	if promptsDir == "" {
		return nil, fmt.Errorf("prompts directory is empty")
	}

	entries, err := os.ReadDir(promptsDir)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil
		}
		return nil, fmt.Errorf("read prompts dir %q: %w", promptsDir, err)
	}

	var removed []string
	for _, entry := range entries {
		if entry.IsDir() {
			continue
		}
		promptPath := filepath.Join(promptsDir, entry.Name())
		if err := os.Remove(promptPath); err != nil {
			return removed, fmt.Errorf("remove prompt %q: %w", promptPath, err)
		}
		removed = append(removed, promptPath)
	}

	return removed, nil
}

// RemoveSkills removes all QuantLab skill directories from the target
// skills directory. Returns the list of removed directories.
func RemoveSkills(skillsDir string) ([]string, error) {
	if skillsDir == "" {
		return nil, fmt.Errorf("skills directory is empty")
	}

	entries, err := os.ReadDir(skillsDir)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil
		}
		return nil, fmt.Errorf("read skills dir %q: %w", skillsDir, err)
	}

	var removed []string

	for _, entry := range entries {
		if !entry.IsDir() {
			continue
		}
		if !strings.HasPrefix(entry.Name(), "quantlab-") {
			continue
		}
		skillPath := filepath.Join(skillsDir, entry.Name())
		if err := os.RemoveAll(skillPath); err != nil {
			return removed, fmt.Errorf("remove skill %q: %w", skillPath, err)
		}
		removed = append(removed, skillPath)
	}

	return removed, nil
}
