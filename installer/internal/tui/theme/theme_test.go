package theme

import "testing"

// TestTagline asserts the QuantLab-branded tagline carries the version. The
// branding is deliberately different from the gentle-ai reference theme.
func TestTagline(t *testing.T) {
	got := Tagline("0.1.0")
	if got == "" {
		t.Fatal("Tagline returned empty string")
	}
	if want := "QuantLab AI 0.1.0"; !contains(got, want) {
		t.Fatalf("Tagline = %q, want it to contain %q", got, want)
	}
	if contains(got, "Gentle-AI") {
		t.Fatalf("Tagline must not carry gentle-ai branding: %q", got)
	}
}

// TestCursorIsNonEmpty guards the focused-item prefix used by RenderOptions,
// RenderCheckbox and RenderRadio.
func TestCursorIsNonEmpty(t *testing.T) {
	if Cursor == "" {
		t.Fatal("Cursor is empty")
	}
}

// TestStylesRender checks the shared styles still render their payload when
// the terminal profile strips colours.
func TestStylesRender(t *testing.T) {
	cases := []struct {
		name string
		fn   func(...string) string
	}{
		{"TitleStyle", TitleStyle.Render},
		{"HeadingStyle", HeadingStyle.Render},
		{"HelpStyle", HelpStyle.Render},
		{"SubtextStyle", SubtextStyle.Render},
		{"SelectedStyle", SelectedStyle.Render},
		{"UnselectedStyle", UnselectedStyle.Render},
		{"SuccessStyle", SuccessStyle.Render},
		{"ErrorStyle", ErrorStyle.Render},
		{"WarningStyle", WarningStyle.Render},
		{"PanelStyle", PanelStyle.Render},
		{"PercentStyle", PercentStyle.Render},
		{"ProgressFilled", ProgressFilled.Render},
		{"ProgressEmpty", ProgressEmpty.Render},
	}
	for _, tc := range cases {
		if got := tc.fn("payload"); got == "" {
			t.Errorf("%s.Render returned empty string", tc.name)
		}
	}

	// FrameStyle adds a border, so it must grow the payload, never shrink it.
	if got := FrameStyle.Render("x"); len(got) <= len("x") {
		t.Errorf("FrameStyle.Render(%q) = %q, expected a bordered frame", "x", got)
	}
}

func contains(haystack, needle string) bool {
	return len(needle) == 0 || indexOf(haystack, needle) >= 0
}

func indexOf(haystack, needle string) int {
	for i := 0; i+len(needle) <= len(haystack); i++ {
		if haystack[i:i+len(needle)] == needle {
			return i
		}
	}
	return -1
}