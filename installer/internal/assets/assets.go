// Package assets embeds the installer's runtime assets — skills, prompts,
// templates, and onboarding — into the binary so releases are fully self-contained.
package assets

import "embed"

// FS holds the embedded skill, prompt, template, and onboarding files. The embedded paths
// mirror the repository layout: skills/, prompts/, templates/, onboarding/.
//
//go:embed skills prompts templates onboarding
var FS embed.FS
