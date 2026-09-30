package opencode

import "embed"

//go:embed overlay.json
var overlayFS embed.FS

func readLocalOverlay() ([]byte, error) {
	return overlayFS.ReadFile("overlay.json")
}
