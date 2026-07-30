package wizard

import (
	"testing"

	tea "github.com/charmbracelet/bubbletea"
)

func TestNewModel(t *testing.T) {
	m := NewModel()
	if m.step != StepWelcome {
		t.Fatalf("initial step = %d, want %d", m.step, StepWelcome)
	}
	if m.selectedModel != "deepseek-v4-flash-free" {
		t.Fatalf("default model = %q", m.selectedModel)
	}
	if m.sdkPath == "" {
		t.Fatal("sdkPath should not be empty (auto-detect)")
	}
}

func TestModel_Init(t *testing.T) {
	m := NewModel()
	cmd := m.Init()
	if cmd == nil {
		t.Fatal("Init() should return a command (textinput.Blink)")
	}
}

func TestModel_WelcomeEnter(t *testing.T) {
	m := NewModel()
	updated, cmd := m.Update(tea.KeyMsg{String: "enter"})
	newM := updated.(Model)
	if newM.step != StepAPIKey {
		t.Fatalf("after enter on welcome, step = %d, want %d", newM.step, StepAPIKey)
	}
	if cmd == nil {
		t.Fatal("expected a command after entering API key step")
	}
}

func TestModel_EscapeQuits(t *testing.T) {
	m := NewModel()
	updated, cmd := m.Update(tea.KeyMsg{String: "esc"})
	newM := updated.(Model)
	if cmd != tea.Quit {
		t.Fatalf("expected tea.Quit, got %v", cmd)
	}
	_ = newM
}

func TestModel_StepTitles(t *testing.T) {
	if stepTitles[StepWelcome] != "Welcome" {
		t.Fatalf("StepWelcome title = %q", stepTitles[StepWelcome])
	}
	if stepTitles[StepAPIKey] != "API Key" {
		t.Fatalf("StepAPIKey title = %q", stepTitles[StepAPIKey])
	}
	if stepTitles[StepModel] != "Model Selection" {
		t.Fatalf("StepModel title = %q", stepTitles[StepModel])
	}
	if stepTitles[StepConfirm] != "Ready" {
		t.Fatalf("StepConfirm title = %q", stepTitles[StepConfirm])
	}
}

func TestModel_APIKeyProgress(t *testing.T) {
	m := NewModel()
	m.step = StepAPIKey

	// Type an API key
	m.apiKeyInput.SetValue("sk-test-key-12345")

	updated, cmd := m.Update(tea.KeyMsg{String: "enter"})
	newM := updated.(Model)
	if newM.step != StepModel {
		t.Fatalf("after entering API key, step = %d, want %d", newM.step, StepModel)
	}
	if newM.apiKey != "sk-test-key-12345" {
		t.Fatalf("apiKey = %q", newM.apiKey)
	}
	if cmd != nil {
		t.Logf("command from model step: %v", cmd)
	}
}

func TestModel_APIKeyRequired(t *testing.T) {
	m := NewModel()
	m.step = StepAPIKey
	// Empty API key
	m.apiKeyInput.SetValue("")

	updated, _ := m.Update(tea.KeyMsg{String: "enter"})
	newM := updated.(Model)
	if newM.step != StepAPIKey {
		t.Fatal("should stay on API key step when empty")
	}
	if newM.err == nil {
		t.Fatal("should have error for empty API key")
	}
}

func TestModel_ModelStep(t *testing.T) {
	m := NewModel()
	m.step = StepModel

	updated, cmd := m.Update(tea.KeyMsg{String: "enter"})
	newM := updated.(Model)
	if newM.step != StepSDKPath {
		t.Fatalf("after model step, got step %d", newM.step)
	}
	if cmd != nil {
		t.Logf("command: %v", cmd)
	}
}

func TestModel_SDKPathStep(t *testing.T) {
	m := NewModel()
	m.step = StepSDKPath
	m.sdkPathInput.SetValue("/custom/path")

	updated, _ := m.Update(tea.KeyMsg{String: "enter"})
	newM := updated.(Model)
	if newM.step != StepSummary {
		t.Fatalf("after SDK path step, step = %d", newM.step)
	}
	if newM.sdkPath != "/custom/path" {
		t.Fatalf("sdkPath = %q", newM.sdkPath)
	}
}

func TestModel_SDKPathAuto(t *testing.T) {
	m := NewModel()
	m.step = StepSDKPath
	m.sdkPathInput.SetValue("") // empty → auto

	updated, _ := m.Update(tea.KeyMsg{String: "enter"})
	newM := updated.(Model)
	if newM.sdkPath != "auto" {
		t.Fatalf("empty sdk path should become 'auto', got %q", newM.sdkPath)
	}
}

func TestModel_SummaryToConfirm(t *testing.T) {
	m := NewModel()
	m.step = StepSummary

	updated, _ := m.Update(tea.KeyMsg{String: "enter"})
	newM := updated.(Model)
	if newM.step != StepConfirm {
		t.Fatalf("after summary, step = %d, want %d", newM.step, StepConfirm)
	}
}

func TestModel_ConfirmQuits(t *testing.T) {
	m := NewModel()
	m.step = StepConfirm

	updated, cmd := m.Update(tea.KeyMsg{String: "enter"})
	newM := updated.(Model)
	if cmd != tea.Quit {
		t.Fatalf("enter on confirm should quit, got %v", cmd)
	}
	_ = newM
}

func TestModel_Result(t *testing.T) {
	m := NewModel()
	m.apiKey = "sk-test"
	m.selectedModel = "gpt-4o"
	m.sdkPath = "/test/path"

	apiKey, model, sdkPath := m.Result()
	if apiKey != "sk-test" {
		t.Fatalf("Result apiKey = %q", apiKey)
	}
	if model != "gpt-4o" {
		t.Fatalf("Result model = %q", model)
	}
	if sdkPath != "/test/path" {
		t.Fatalf("Result sdkPath = %q", sdkPath)
	}
}

func TestMaskKey(t *testing.T) {
	tests := []struct {
		input string
		want  string
	}{
		{"", "••••••••"},
		{"ab", "••••••••"},
		{"12345678", "••••••••"},
		{"sk-test-key-12345", "sk-t••••12345"},
		{"abcdefghijkl", "abcd••••ijkl"},
	}

	for _, tc := range tests {
		got := maskKey(tc.input)
		if got != tc.want {
			t.Errorf("maskKey(%q) = %q, want %q", tc.input, got, tc.want)
		}
	}
}

func TestModel_View(t *testing.T) {
	m := NewModel()
	view := m.View()
	if len(view) == 0 {
		t.Fatal("View() returned empty for welcome step")
	}
}

func TestModel_ViewAPIKey(t *testing.T) {
	m := NewModel()
	m.step = StepAPIKey
	view := m.View()
	if len(view) == 0 {
		t.Fatal("View() returned empty for API key step")
	}
}

func TestModel_ViewModel(t *testing.T) {
	m := NewModel()
	m.step = StepModel
	view := m.View()
	if len(view) == 0 {
		t.Fatal("View() returned empty for model step")
	}
}

func TestModel_ViewSummary(t *testing.T) {
	m := NewModel()
	m.step = StepSummary
	m.apiKey = "sk-test-key-12345"
	m.selectedModel = "gpt-4o"
	m.sdkPath = "/test"
	view := m.View()
	if len(view) == 0 {
		t.Fatal("View() returned empty for summary step")
	}
}

func TestModel_ViewConfirm(t *testing.T) {
	m := NewModel()
	m.step = StepConfirm
	view := m.View()
	if len(view) == 0 {
		t.Fatal("View() returned empty for confirm step")
	}
}

func TestAutoDetectSDK(t *testing.T) {
	path := autoDetectSDK()
	// Should not panic, should return "auto" if not found
	if path == "" {
		t.Fatal("autoDetectSDK() returned empty (should be 'auto' at minimum)")
	}
}

func TestModel_ProgressBar(t *testing.T) {
	m := NewModel()
	bar := m.progressBar()
	if len(bar) == 0 {
		t.Fatal("progressBar() returned empty")
	}
}

func TestModel_WindowSize(t *testing.T) {
	m := NewModel()
	updated, _ := m.Update(tea.WindowSizeMsg{Width: 100, Height: 40})
	newM := updated.(Model)
	if newM.width != 100 {
		t.Fatalf("width = %d", newM.width)
	}
}

func TestModel_UnknownMsg(t *testing.T) {
	m := NewModel()
	// Unknown message should be ignored
	updated, _ := m.Update(struct{}{})
	if _, ok := updated.(Model); !ok {
		t.Fatal("unknown message should not break model")
	}
}

func TestValidOpenCodeAPIKey(t *testing.T) {
	tests := []struct {
		key   string
		valid bool
	}{
		{"", false},
		{"sk-test-key-12345", true},
		{"sk-abc", false},           // too short
		{"not-a-key", false},        // no sk- prefix
		{"sk-" + string(make([]byte, 100)), true}, // long valid key
		{"sk-", false},              // too short
	}
	for _, tt := range tests {
		err := ValidOpenCodeAPIKey(tt.key)
		if tt.valid && err != nil {
			t.Errorf("ValidOpenCodeAPIKey(%q) = %v, want nil", tt.key, err)
		}
		if !tt.valid && err == nil {
			t.Errorf("ValidOpenCodeAPIKey(%q) = nil, want error", tt.key)
		}
	}
}
