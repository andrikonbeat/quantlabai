// Package assets embeds the installer's runtime assets — skills, prompts,
// and templates — into the binary so releases are fully self-contained.
package assets

import "embed"

// FS holds the embedded skill, prompt, and template files. The embedded paths
// mirror the repository layout: skills/, prompts/, templates/.
//
//go:embed skills prompts templates
var FS embed.FS
