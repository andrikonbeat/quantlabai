package screens

import (
	"strings"
	"testing"
)

func TestRenderDetection(t *testing.T) {
	out := RenderDetection(
		"Verificación funcional",
		[]CheckItem{
			{Label: "Python 3.11+ available", OK: true, Note: "/usr/bin/python3.13"},
			{Label: "OpenCode settings accessible", OK: true},
			{Label: "GentleAI compatibility", OK: false, Note: "not detected"},
			{Label: "StrategyQuant X path valid", OK: true, Optional: true},
		},
		[]string{"Pedile al agente OpenCode que complete la instalación."},
		"Enter = siguiente  |  Esc = cancelar",
	)

	assertContains(t, "RenderDetection", out,
		"Verificación funcional",
		"Python 3.11+ available", "/usr/bin/python3.13",
		"OpenCode settings accessible",
		"GentleAI compatibility", "not detected",
		"StrategyQuant X path valid", "(optional)",
		"Pedile al agente OpenCode que complete la instalación.",
		"Enter = siguiente  |  Esc = cancelar",
	)
}

func TestRenderDetectionAllOKHasNoFailureMarks(t *testing.T) {
	out := RenderDetection("Verificación funcional", []CheckItem{
		{Label: "Python 3.11+ available", OK: true},
		{Label: "Write permissions", OK: true},
	}, nil, "Enter = siguiente")

	assertContains(t, "RenderDetection/ok", out, "Python 3.11+ available", "Write permissions")
	if strings.Contains(out, "✗") {
		t.Errorf("all-OK checklist must not render failure marks:\n%s", out)
	}
}

func TestRenderDetectionEmptyItems(t *testing.T) {
	out := RenderDetection("Sin items", nil, nil, "")
	if out == "" {
		t.Fatal("RenderDetection should still render the title for an empty checklist")
	}
}