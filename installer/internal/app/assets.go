package app

import (
	"io/fs"

	"github.com/ogzuz/quantlab/internal/assets"
)

// assetFS returns the embedded asset filesystem containing the skills,
// prompts, and templates. Assets are compiled into the binary via go:embed
// (see internal/assets), so released binaries are self-contained and no
// runtime path resolution against the source tree is needed.
func assetFS() fs.FS {
	return assets.FS
}
