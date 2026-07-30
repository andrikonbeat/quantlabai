package app

import (
	"io/fs"
	"os"
	"path/filepath"
)

// assetFS returns an fs.FS rooted at the installer assets directory.
// It searches relative to the executable and the source tree.
func assetFS() fs.FS {
	// Try relative to CWD (development)
	candidates := []string{
		"assets",
		"installer/assets",
		"../assets",
		"../../assets",
	}

	exe, err := os.Executable()
	if err == nil {
		exeDir := filepath.Dir(exe)
		candidates = append(candidates,
			filepath.Join(exeDir, "assets"),
			filepath.Join(exeDir, "..", "assets"),
		)
	}

	for _, dir := range candidates {
		abs, err := filepath.Abs(dir)
		if err != nil {
			continue
		}
		if info, err := os.Stat(abs); err == nil && info.IsDir() {
			return os.DirFS(abs)
		}
	}

	// Last resort: try walking up from CWD
	wd, err := os.Getwd()
	if err == nil {
		for i := 0; i < 5; i++ {
			try := filepath.Join(wd, "assets")
			if info, err := os.Stat(try); err == nil && info.IsDir() {
				return os.DirFS(try)
			}
			wd = filepath.Dir(wd)
			if wd == "/" {
				break
			}
		}
	}

	return os.DirFS("assets")
}
