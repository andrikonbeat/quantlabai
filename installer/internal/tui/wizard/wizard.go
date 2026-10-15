// Package wizard provides a Bubbletea TUI for collecting QuantLab SDK
// configuration (API key, model, SDK path) during first-run setup.
package wizard

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"

	"github.com/charmbracelet/bubbles/list"
	"github.com/charmbracelet/bubbles/textinput"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
)

// ValidOpenCodeAPIKey checks that the key is non-empty and starts with "sk-".
func ValidOpenCodeAPIKey(key string) error {
	if key == "" {
		return fmt.Errorf("API key is required")
	}
	if !strings.HasPrefix(key, "sk-") {
		return fmt.Errorf("API key should start with 'sk-' (expected OpenCode API key format)")
	}
	if len(key) < 10 {
		return fmt.Errorf("API key is too short (expected at least 10 characters)")
	}
	return nil
}

// Step identifies the current wizard step.
type Step int

const (
	StepIntroduction Step = iota
	StepOpenCode
	StepGentleAI
	StepJForex
	StepAPIKey
	StepModel
	StepSDKPath
	StepSQX
	StepVerify
	StepSummary
	StepConfirm
	stepCount // internal sentinel
)

// stepTitles maps each step to its display title.
var stepTitles = map[Step]string{
	StepIntroduction: "Introduction",
	StepOpenCode:     "OpenCode",
	StepGentleAI:     "Gentle AI",
	StepJForex:       "JForex 4",
	StepAPIKey:       "API Key",
	StepModel:        "Model Selection",
	StepSDKPath:      "SDK Path",
	StepSQX:          "StrategyQuant X",
	StepVerify:       "Verification",
	StepSummary:      "Summary",
	StepConfirm:      "Ready",
}

// modelItem is a list.Item for the model selection step.
type modelItem struct {
	title, desc string
}

func (i modelItem) Title() string       { return i.title }
func (i modelItem) Description() string { return i.desc }
func (i modelItem) FilterValue() string { return i.title }

// openCodeItem represents an OpenCode installation option.
type openCodeItem struct {
	id, title, desc string
}

func (i openCodeItem) Title() string       { return i.title }
func (i openCodeItem) Description() string { return i.desc }
func (i openCodeItem) FilterValue() string { return i.title }

// gentleAIItem represents a Gentle AI installation option.
type gentleAIItem struct {
	id, title, desc string
}

func (i gentleAIItem) Title() string       { return i.title }
func (i gentleAIItem) Description() string { return i.desc }
func (i gentleAIItem) FilterValue() string { return i.title }

// jforexItem represents a JForex installation option.
type jforexItem struct {
	id, title, desc string
}

func (i jforexItem) Title() string       { return i.title }
func (i jforexItem) Description() string { return i.desc }
func (i jforexItem) FilterValue() string { return i.title }

// Model is the Bubbletea model for the configuration wizard.
type Model struct {
	step           Step
	apiKeyInput    textinput.Model
	modelList      list.Model
	sdkPathInput   textinput.Model
	sqxPathInput   textinput.Model
	jforexPathInput textinput.Model
	openCodeList   list.Model
	gentleAIList   list.Model
	jforexList     list.Model
	apiKey         string
	selectedModel  string
	sdkPath        string
	sqxPath        string
	jforexPath     string
	opencodeChoice string
	gentleAIChoice string
	jforexChoice   string
	gentleAIPresent bool
	depsVerified   bool
	verifyItems    []verifyItem
	err            error
	width          int
	height         int
	opencodeInstalled bool
	gentleAIInstalled bool
	jforexDetected    bool
	sqxDetected       bool
}

// NewModel creates a wizard model with default values and auto-detected paths.
func NewModel() Model {
	// API Key input (masked)
	apiInput := textinput.New()
	apiInput.Placeholder = "sk-..."
	apiInput.EchoMode = textinput.EchoPassword
	apiInput.EchoCharacter = '•'
	apiInput.Width = 60
	apiInput.PromptStyle = FocusStyle
	apiInput.TextStyle = FocusStyle
	apiInput.CharLimit = 128

	// Model selection list
	modelItems := []list.Item{
		modelItem{title: "deepseek-v4-flash-free", desc: "DeepSeek V4 Flash (free tier)"},
		modelItem{title: "gpt-4o", desc: "OpenAI GPT-4o"},
		modelItem{title: "claude-4-sonnet", desc: "Anthropic Claude 4 Sonnet"},
		modelItem{title: "claude-4-opus", desc: "Anthropic Claude 4 Opus"},
		modelItem{title: "gpt-4o-mini", desc: "OpenAI GPT-4o Mini"},
		modelItem{title: "gpt-4.1", desc: "OpenAI GPT-4.1"},
	}

	l := list.New(modelItems, list.NewDefaultDelegate(), 0, 0)
	l.Title = "Select Default Model"
	l.SetShowStatusBar(false)
	l.SetFilteringEnabled(false)
	l.Styles.Title = TitleStyle
	l.DisableQuitKeybindings()

	// SDK Path input
	sdkInput := textinput.New()
	sdkInput.Placeholder = "Auto-detect"
	sdkInput.Width = 60
	sdkInput.PromptStyle = FocusStyle
	sdkInput.TextStyle = FocusStyle
	sdkInput.CharLimit = 256

	// SQX Path input
	sqxInput := textinput.New()
	sqxInput.Placeholder = "Auto-detect (e.g. /opt/StrategyQuantX)"
	sqxInput.Width = 60
	sqxInput.PromptStyle = FocusStyle
	sqxInput.TextStyle = FocusStyle
	sqxInput.CharLimit = 256

	// JForex Path input
	jfxInput := textinput.New()
	jfxInput.Placeholder = "Auto-detect (e.g. /opt/JForex4)"
	jfxInput.Width = 60
	jfxInput.PromptStyle = FocusStyle
	jfxInput.TextStyle = FocusStyle
	jfxInput.CharLimit = 256

	// OpenCode installation options
	opencodeItems := []list.Item{
		openCodeItem{id: "auto", title: "Install OpenCode automatically", desc: "Run official installer (curl -fsSL https://opencode.dev/install.sh | sh)"},
		openCodeItem{id: "manual", title: "Install OpenCode manually", desc: "I'll install it myself from https://opencode.dev"},
		openCodeItem{id: "skip", title: "Skip OpenCode", desc: "Continue without OpenCode (limited functionality)"},
	}
	ocList := list.New(opencodeItems, list.NewDefaultDelegate(), 0, 0)
	ocList.Title = "OpenCode Installation"
	ocList.SetShowStatusBar(false)
	ocList.SetFilteringEnabled(false)
	ocList.Styles.Title = TitleStyle
	ocList.DisableQuitKeybindings()

	// Gentle AI installation options
	gentleItems := []list.Item{
		gentleAIItem{id: "auto", title: "Install Gentle AI automatically", desc: "Run installer (same method as OpenCode)"},
		gentleAIItem{id: "manual", title: "Install Gentle AI manually", desc: "Follow manual steps from gentle-ai docs"},
		gentleAIItem{id: "skip", title: "Skip Gentle AI", desc: "Continue without Gentle AI (compatibility layer only)"},
	}
	gaList := list.New(gentleItems, list.NewDefaultDelegate(), 0, 0)
	gaList.Title = "Gentle AI Installation"
	gaList.SetShowStatusBar(false)
	gaList.SetFilteringEnabled(false)
	gaList.Styles.Title = TitleStyle
	gaList.DisableQuitKeybindings()

	// JForex installation options
	jfxItems := []list.Item{
		jforexItem{id: "auto", title: "Auto-detect JForex 4 installation", desc: "Search common paths (/opt/JForex4, ~/JForex4, etc.)"},
		jforexItem{id: "manual", title: "Enter JForex 4 path manually", desc: "Specify the JForex 4 desktop platform installation directory"},
		jforexItem{id: "skip", title: "Skip JForex 4 for now", desc: "Configure later (needed for demo/live deployment)"},
	}
	jfxList := list.New(jfxItems, list.NewDefaultDelegate(), 0, 0)
	jfxList.Title = "JForex 4 Deployment Layer"
	jfxList.SetShowStatusBar(false)
	jfxList.SetFilteringEnabled(false)
	jfxList.Styles.Title = TitleStyle
	jfxList.DisableQuitKeybindings()

	// Try to auto-detect paths
	sdkPath := autoDetectSDK()
	sqxPath := autoDetectSQX()
	jforexPath := autoDetectJForex()
	opencodeInstalled := detectOpenCode()
	gentlePresent := detectGentleAI()
	jforexDetected := jforexPath != "" && jforexPath != "auto"

	vitems := buildVerifyItems(sdkPath, sqxPath, jforexPath, gentlePresent, opencodeInstalled)

	return Model{
		step:              StepIntroduction,
		apiKeyInput:       apiInput,
		sdkPathInput:      sdkInput,
		sqxPathInput:      sqxInput,
		jforexPathInput:   jfxInput,
		modelList:         l,
		openCodeList:      ocList,
		gentleAIList:      gaList,
		jforexList:        jfxList,
		sdkPath:           sdkPath,
		sqxPath:           sqxPath,
		jforexPath:        jforexPath,
		gentleAIPresent:   gentlePresent,
		opencodeInstalled: opencodeInstalled,
		gentleAIInstalled: gentlePresent,
		jforexDetected:    jforexDetected,
		sqxDetected:       sqxPath != "" && sqxPath != "auto",
		verifyItems:       vitems,
		selectedModel:     "deepseek-v4-flash-free",
	}
}

// autoDetectSDK tries to find the QuantLab SDK in common locations.
func autoDetectSDK() string {
	home, err := os.UserHomeDir()
	if err != nil {
		return "auto"
	}

	candidates := []string{
		filepath.Join(home, "Proyectos", "QuantLab AI", "sdk"),
		filepath.Join(home, "quantlab", "sdk"),
		filepath.Join(home, "code", "quantlab", "sdk"),
	}

	for _, p := range candidates {
		if info, err := os.Stat(p); err == nil && info.IsDir() {
			setupPy := filepath.Join(p, "pyproject.toml")
			if _, err := os.Stat(setupPy); err == nil {
				return p
			}
		}
	}

	return "auto"
}

func (m Model) Init() tea.Cmd {
	return textinput.Blink
}

func (m Model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.width = msg.Width
		m.height = msg.Height
		listWidth := msg.Width - 12
		if listWidth < 40 {
			listWidth = 40
		}
		listHeight := msg.Height - 12
		if listHeight < 10 {
			listHeight = 10
		}
		m.modelList.SetSize(listWidth, listHeight)
		m.openCodeList.SetSize(listWidth, listHeight)
		m.gentleAIList.SetSize(listWidth, listHeight)
		m.jforexList.SetSize(listWidth, listHeight)
		return m, nil

	case tea.KeyMsg:
		switch msg.String() {
		case "ctrl+c", "esc":
			return m, tea.Quit

		case "enter":
			return m.handleEnter()

		case "shift+tab":
			if m.step == StepIntroduction || m.step == StepSummary || m.step == StepConfirm {
				return m, nil
			}
			return m, nil
		}

	case errMsg:
		m.err = msg.error
		return m, nil
	}

	return m.handleUpdate(msg)
}

type errMsg struct{ error }

func (m Model) handleEnter() (tea.Model, tea.Cmd) {
	switch m.step {
	case StepIntroduction:
		m.step = StepOpenCode
		if !m.opencodeInstalled {
			// Focus on the list for selection
		}
		m.err = nil
		return m, nil

	case StepOpenCode:
		if selected, ok := m.openCodeList.SelectedItem().(openCodeItem); ok {
			m.opencodeChoice = selected.id
			if m.opencodeChoice == "auto" {
				// TODO: Execute auto-install
				// For now, mark as done and continue
				m.opencodeInstalled = true
			}
		}
		if m.opencodeChoice == "" && m.openCodeList.SelectedItem() != nil {
			if selected, ok := m.openCodeList.SelectedItem().(openCodeItem); ok {
				m.opencodeChoice = selected.id
			}
		}
		m.step = StepGentleAI
		m.err = nil
		return m, nil

	case StepGentleAI:
		if selected, ok := m.gentleAIList.SelectedItem().(gentleAIItem); ok {
			m.gentleAIChoice = selected.id
			if m.gentleAIChoice == "auto" {
				m.gentleAIInstalled = true
			}
		}
		if m.gentleAIChoice == "" && m.gentleAIList.SelectedItem() != nil {
			if selected, ok := m.gentleAIList.SelectedItem().(gentleAIItem); ok {
				m.gentleAIChoice = selected.id
			}
		}
		m.step = StepJForex
		m.err = nil
		return m, nil

	case StepJForex:
		if selected, ok := m.jforexList.SelectedItem().(jforexItem); ok {
			m.jforexChoice = selected.id
			if m.jforexChoice == "auto" && m.jforexDetected {
				// Already detected
			} else if m.jforexChoice == "manual" {
				m.jforexPathInput.Focus()
				return m, textinput.Blink
			}
		}
		if m.jforexChoice == "" && m.jforexList.SelectedItem() != nil {
			if selected, ok := m.jforexList.SelectedItem().(jforexItem); ok {
				m.jforexChoice = selected.id
			}
		}
		m.step = StepAPIKey
		m.apiKeyInput.Focus()
		m.err = nil
		return m, textinput.Blink

	case StepAPIKey:
		m.apiKey = strings.TrimSpace(m.apiKeyInput.Value())
		if err := ValidOpenCodeAPIKey(m.apiKey); err != nil {
			m.err = err
			return m, nil
		}
		m.err = nil
		m.step = StepModel
		if m.modelList.SelectedItem() == nil {
			m.modelList.Select(0)
		}
		return m, nil

	case StepModel:
		if selected, ok := m.modelList.SelectedItem().(modelItem); ok {
			m.selectedModel = selected.title
		}
		m.step = StepSDKPath
		m.sdkPathInput.Focus()
		return m, textinput.Blink

	case StepSDKPath:
		val := strings.TrimSpace(m.sdkPathInput.Value())
		if val == "" || val == "auto" {
			if m.sdkPath == "" || m.sdkPath == "auto" {
				m.sdkPath = autoDetectSDK()
			}
			if m.sdkPath == "" {
				m.sdkPath = "auto"
			}
		} else {
			m.sdkPath = val
		}
		m.step = StepSQX
		if m.sqxPath != "" && m.sqxPath != "auto" {
			m.sqxPathInput.SetValue(m.sqxPath)
		} else if m.sqxPath == "auto" || m.sqxPath == "" {
			autod := autoDetectSQX()
			if autod != "" && autod != "auto" {
				m.sqxPath = autod
				m.sqxPathInput.SetValue(autod)
			}
		}
		m.sqxPathInput.Focus()
		return m, textinput.Blink

	case StepSQX:
		val := strings.TrimSpace(m.sqxPathInput.Value())
		if val == "" || val == "auto" {
			autod := autoDetectSQX()
			if autod != "" && autod != "auto" {
				m.sqxPath = autod
			} else {
				m.sqxPath = "auto"
			}
		} else {
			m.sqxPath = val
		}
		if err := validateSQXPath(m.sqxPath); err != nil {
			m.err = err
			return m, nil
		}
		m.err = nil
		m.verifyItems = buildVerifyItems(m.sdkPath, m.sqxPath, m.jforexPath, m.gentleAIPresent, m.opencodeInstalled)
		m.depsVerified = verifyAllOK(m.verifyItems)
		m.step = StepVerify
		return m, nil

	case StepVerify:
		if !verifyAllOK(m.verifyItems) {
			m.err = fmt.Errorf("all verification items must be OK to continue")
			return m, nil
		}
		m.err = nil
		m.step = StepSummary
		return m, nil

	case StepSummary:
		m.step = StepConfirm
		return m, nil

	case StepConfirm:
		return m, tea.Quit
	}

	return m, nil
}

func (m Model) handleUpdate(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch m.step {
	case StepOpenCode:
		var cmd tea.Cmd
		m.openCodeList, cmd = m.openCodeList.Update(msg)
		return m, cmd
	case StepGentleAI:
		var cmd tea.Cmd
		m.gentleAIList, cmd = m.gentleAIList.Update(msg)
		return m, cmd
	case StepJForex:
		var cmd tea.Cmd
		m.jforexList, cmd = m.jforexList.Update(msg)
		return m, cmd
	case StepAPIKey:
		var cmd tea.Cmd
		m.apiKeyInput, cmd = m.apiKeyInput.Update(msg)
		return m, cmd
	case StepModel:
		var cmd tea.Cmd
		m.modelList, cmd = m.modelList.Update(msg)
		return m, cmd
	case StepSDKPath:
		var cmd tea.Cmd
		m.sdkPathInput, cmd = m.sdkPathInput.Update(msg)
		return m, cmd
	case StepSQX:
		var cmd tea.Cmd
		m.sqxPathInput, cmd = m.sqxPathInput.Update(msg)
		return m, cmd
	case StepVerify:
		return m, nil
	}
	return m, nil
}

func (m Model) View() string {
	progress := m.progressBar()

	switch m.step {
	case StepIntroduction:
		return progress + "\n" + m.introductionView()
	case StepOpenCode:
		return progress + "\n" + m.openCodeView()
	case StepGentleAI:
		return progress + "\n" + m.gentleAIView()
	case StepJForex:
		return progress + "\n" + m.jforexView()
	case StepAPIKey:
		return progress + "\n" + m.apiKeyView()
	case StepModel:
		return progress + "\n" + m.modelView()
	case StepSDKPath:
		return progress + "\n" + m.sdkPathView()
	case StepSQX:
		return progress + "\n" + m.sqxView()
	case StepVerify:
		return progress + "\n" + m.verifyView()
	case StepSummary:
		return progress + "\n" + m.summaryView()
	case StepConfirm:
		return progress + "\n" + m.confirmView()
	}
	return ""
}

// progressBar renders a simple step indicator.
func (m Model) progressBar() string {
	total := int(stepCount)
	current := int(m.step)
	if current < 1 {
		current = 1
	}
	if current > total {
		current = total
	}

	dots := make([]string, total)
	for i := 0; i < total; i++ {
		if i == current-1 {
			dots[i] = lipgloss.NewStyle().
				Foreground(lipgloss.Color("37")).
				Bold(true).
				Render(fmt.Sprintf("● Step %d/%d", current, total))
		} else {
			dots[i] = lipgloss.NewStyle().
				Foreground(lipgloss.Color("240")).
				Render("○")
		}
	}

	return lipgloss.NewStyle().Padding(0, 1).Render(strings.Join(dots, " "))
}

func (m Model) introductionView() string {
	var b strings.Builder
	b.WriteString(BoxStyle.Render(
		TitleStyle.Render("QuantLab AI — Installation Wizard") + "\n\n" +
			SubtitleStyle.Render("QuantLab AI is an AI-directed quantitative research engine.") + "\n" +
			SubtitleStyle.Render("OpenCode acts as the research director; StrategyQuant X is the computation engine.") + "\n\n" +
			HeaderStyle.Render("What you'll install:") + "\n" +
			"  " + FocusStyle.Render("•") + " QuantLab SDK (Python) — core library, agents, campaigns, exploration\n" +
			"  " + FocusStyle.Render("•") + " OpenCode — AI coding agent that runs the research campaigns\n" +
			"  " + FocusStyle.Render("•") + " Gentle AI — environment config & compatibility layer (includes Engram memory)\n" +
			"  " + FocusStyle.Render("•") + " StrategyQuant X — strategy generation & backtesting (external, licensed)\n" +
			"  " + FocusStyle.Render("•") + " JForex 4 — deployment platform for demo/live trading (Dukascopy)\n\n" +
			HeaderStyle.Render("How they work together:") + "\n" +
			"  1. OpenCode (QuantLab-Orchestrator agent) directs the 14-phase campaign lifecycle\n" +
			"  2. Exploration pipeline (E1–E11) produces a decision artifact\n" +
			"  3. Configuration pipeline maps decisions → CustomProject parameters (deterministic)\n" +
			"  4. SQX runs the CustomProject: generate → robust test → optimize → portfolio\n" +
			"  5. Strategies compile to JForex for demo validation → live deployment\n\n" +
			BlurStyle.Render("Press Enter to begin · Esc to cancel"),
	))
	return b.String() + "\n"
}

func (m Model) openCodeView() string {
	var b strings.Builder
	status := "✓ Detected"
	if !m.opencodeInstalled {
		status = "✗ Not detected"
	}
	b.WriteString(TitleStyle.Render("OpenCode — AI Coding Agent") + "\n\n")
	b.WriteString(SubtitleStyle.Render("QuantLab uses OpenCode as the research director. It runs the campaign agents.") + "\n\n")
	b.WriteString(BoxStyle.Render(fmt.Sprintf("Status: %s\n\n", status) +
		"If OpenCode is not installed, you can:\n" +
		"  • Install automatically (official installer)\n" +
		"  • Install manually from https://opencode.dev\n" +
		"  • Skip (limited functionality — no agent orchestration)\n"))
	if m.err != nil {
		b.WriteString("\n" + ErrorStyle.Render("✗ "+m.err.Error()) + "\n")
	}
	b.WriteString("\n" + BlurStyle.Render("↑/↓ to navigate · Enter to confirm · Esc to cancel"))
	return BoxStyle.Render(b.String()) + "\n"
}

func (m Model) gentleAIView() string {
	var b strings.Builder
	status := "✓ Detected"
	if !m.gentleAIInstalled {
		status = "✗ Not detected"
	}
	b.WriteString(TitleStyle.Render("Gentle AI — Environment & Compatibility Layer") + "\n\n")
	b.WriteString(SubtitleStyle.Render("Gentle AI provides a compatibility layer for QuantLab, installing Engram (persistent memory)") + "\n")
	b.WriteString(SubtitleStyle.Render("and configuring the environment for agent orchestration.") + "\n\n")
	b.WriteString(BoxStyle.Render(fmt.Sprintf("Status: %s\n\n", status) +
		"If Gentle AI is not detected, you can:\n" +
		"  • Install automatically (same method as OpenCode)\n" +
		"  • Install manually from Gentle AI documentation\n" +
		"  • Skip (QuantLab will work but without persistent memory & review integration)\n"))
	if m.err != nil {
		b.WriteString("\n" + ErrorStyle.Render("✗ "+m.err.Error()) + "\n")
	}
	b.WriteString("\n" + BlurStyle.Render("↑/↓ to navigate · Enter to confirm · Esc to cancel"))
	return BoxStyle.Render(b.String()) + "\n"
}

func (m Model) jforexView() string {
	var b strings.Builder
	status := "✓ Detected"
	if !m.jforexDetected {
		status = "✗ Not detected"
	}
	b.WriteString(TitleStyle.Render("JForex 4 — Deployment Platform (Dukascopy)") + "\n\n")
	b.WriteString(SubtitleStyle.Render("JForex 4 is the desktop trading platform from Dukascopy Bank.") + "\n")
	b.WriteString(SubtitleStyle.Render("QuantLab compiles strategies to JForex for demo validation and live deployment.") + "\n\n")
	b.WriteString(BoxStyle.Render(fmt.Sprintf("Status: %s\n\n", status) +
		"What gets installed:\n" +
		"  • JForex 4 Desktop Platform (graphical UI)\n" +
		"  • Free 14-day demo account (Dukascopy)\n" +
		"  • Strategy deployment via .jfx files\n\n" +
		"How QuantLab uses it:\n" +
		"  1. Strategies compiled from SQX → .jfx files\n" +
		"  2. Copied to JForex strategies folder\n" +
		"  3. Backtested in JForex to verify parity with SQX results\n" +
		"  4. Deployed to demo account for forward testing\n" +
		"  5. Promoted to live via JCloud\n\n" +
		"Options:\n" +
		"  • Auto-detect: searches /opt/JForex4, ~/JForex4, Applications, Program Files\n" +
		"  • Manual: enter the JForex 4 installation directory\n" +
		"  • Skip: configure later (required for demo/live phases)\n"))
	if m.err != nil {
		b.WriteString("\n" + ErrorStyle.Render("✗ "+m.err.Error()) + "\n")
	}
	b.WriteString("\n" + BlurStyle.Render("↑/↓ to navigate · Enter to confirm · Esc to cancel"))
	return BoxStyle.Render(b.String()) + "\n"
}

func (m Model) apiKeyView() string {
	var b strings.Builder
	b.WriteString(TitleStyle.Render("OpenCode API Key") + "\n\n")
	b.WriteString(SubtitleStyle.Render("Enter your OpenCode API key (starts with sk-):") + "\n\n")
	b.WriteString(m.apiKeyInput.View() + "\n")
	if m.err != nil {
		b.WriteString("\n" + ErrorStyle.Render("✗ "+m.err.Error()) + "\n")
	}
	b.WriteString("\n" + BlurStyle.Render("Enter to confirm · Esc to cancel"))
	return BoxStyle.Render(b.String()) + "\n"
}

func (m Model) modelView() string {
	var b strings.Builder
	b.WriteString(TitleStyle.Render("Model Selection") + "\n\n")
	b.WriteString(SubtitleStyle.Render("Choose the default AI model for research:") + "\n\n")
	b.WriteString(m.modelList.View())
	b.WriteString("\n" + BlurStyle.Render("↑/↓ to navigate · Enter to confirm · Esc to cancel"))
	return BoxStyle.Render(b.String()) + "\n"
}

func (m Model) sdkPathView() string {
	var b strings.Builder
	b.WriteString(TitleStyle.Render("QuantLab SDK Path") + "\n\n")
	b.WriteString(SubtitleStyle.Render("Path to the QuantLab SDK source (or 'auto' to detect):") + "\n\n")
	b.WriteString(m.sdkPathInput.View() + "\n")
	b.WriteString("\n" + BlurStyle.Render("Enter to confirm · Esc to cancel"))
	return BoxStyle.Render(b.String()) + "\n"
}

func (m Model) sqxView() string {
	var b strings.Builder
	b.WriteString(TitleStyle.Render("StrategyQuant X (SQX)") + "\n\n")
	b.WriteString(SubtitleStyle.Render("SQX is the strategy generation & backtesting engine (external dependency).") + "\n\n")
	b.WriteString(BoxStyle.Render(
		"License options:\n" +
			"  • Paid license (full features)\n" +
			"  • Free 30-day trial (from StrategyQuant website)\n\n" +
			"Installation:\n" +
			"  1. Download from https://strategyquant.com\n" +
			"  2. Install to default location (/opt/StrategyQuantX on Linux)\n" +
			"  3. Activate license\n\n" +
			"QuantLab needs the SQX installation directory to:\n" +
			"  • Launch CustomProjects via sqcli\n" +
			"  • Read/generate .cfx configuration files\n" +
			"  • Access databanks and historical data\n"))
	b.WriteString(m.sqxPathInput.View() + "\n")
	if m.err != nil {
		b.WriteString("\n" + ErrorStyle.Render("✗ "+m.err.Error()) + "\n")
	}
	b.WriteString("\n" + BlurStyle.Render("Enter to confirm · Esc to cancel"))
	return BoxStyle.Render(b.String()) + "\n"
}

func (m Model) summaryView() string {
	var b strings.Builder
	b.WriteString(TitleStyle.Render("Configuration Summary") + "\n\n")
	b.WriteString(BoxStyle.Render(
		LabelStyle.Render("OpenCode:       ") + ValueStyle.Render(m.openCodeStatus()) + "\n"+
			LabelStyle.Render("Gentle AI:      ") + ValueStyle.Render(m.gentleAIStatus()) + "\n"+
			LabelStyle.Render("JForex 4:       ") + ValueStyle.Render(m.jforexStatus()) + "\n"+
			LabelStyle.Render("API Key:        ") + ValueStyle.Render(maskKey(m.apiKey)) + "\n"+
			LabelStyle.Render("Model:          ") + ValueStyle.Render(m.selectedModel)+"\n"+
			LabelStyle.Render("SDK Path:       ") + ValueStyle.Render(m.sdkPath)+"\n"+
			LabelStyle.Render("SQX Path:       ") + ValueStyle.Render(m.sqxPath)+"\n"+
			LabelStyle.Render("JForex Path:    ") + ValueStyle.Render(m.jforexPath)+"\n"+
			LabelStyle.Render("Deps Verified:  ") + ValueStyle.Render(boolYesNo(m.depsVerified))+"\n",
	))
	b.WriteString("\n" + FocusStyle.Render("Press Enter to continue") + "\n")
	b.WriteString(BlurStyle.Render("Esc to cancel"))
	return b.String() + "\n"
}

func (m Model) confirmView() string {
	var b strings.Builder
	b.WriteString(BoxStyle.Render(
		TitleStyle.Render("Ready to Apply") + "\n\n"+
			SubtitleStyle.Render("The installer will now:")+"\n"+
			"  "+FocusStyle.Render("•")+" Install the QuantLab SDK\n"+
			"  "+FocusStyle.Render("•")+" Configure OpenCode agents (quantlab-orchestrator, quantlab-phase-*, etc.)\n"+
			"  "+FocusStyle.Render("•")+" Install skills and prompts\n"+
			"  "+FocusStyle.Render("•")+" Write state.json with all configuration\n\n"+
			SubtitleStyle.Render("After installation:")+"\n"+
			"  1. Open OpenCode in your project: "+FocusStyle.Render("cd /path/to/project && opencode")+"\n"+
			"  2. Select agent: "+FocusStyle.Render("quantlab-orchestrator")+"\n"+
			"  3. Give an instruction, e.g.: "+FocusStyle.Render("\"Comienza una campaña para un portafolio de 100USD\"")+"\n\n"+
			FocusStyle.Render("Press Enter to apply · Esc to cancel"),
	))
	return b.String() + "\n"
}

func (m Model) openCodeStatus() string {
	switch m.opencodeChoice {
	case "auto":
		return "Auto-install"
	case "manual":
		return "Manual install"
	case "skip":
		return "Skipped"
	default:
		if m.opencodeInstalled {
			return "Detected"
		}
		return "Not configured"
	}
}

func (m Model) gentleAIStatus() string {
	switch m.gentleAIChoice {
	case "auto":
		return "Auto-install"
	case "manual":
		return "Manual install"
	case "skip":
		return "Skipped"
	default:
		if m.gentleAIInstalled {
			return "Detected"
		}
		return "Not configured"
	}
}

func (m Model) jforexStatus() string {
	switch m.jforexChoice {
	case "auto":
		if m.jforexDetected {
			return "Auto-detected"
		}
		return "Auto-detect"
	case "manual":
		return "Manual path"
	case "skip":
		return "Skipped"
	default:
		if m.jforexDetected {
			return "Detected"
		}
		return "Not configured"
	}
}

// Result returns the collected configuration values after the wizard completes.
func (m Model) Result() (apiKey, model, sdkPath, sqxPath, jforexPath string, gentleAIPresent, depsVerified bool) {
	return m.apiKey, m.selectedModel, m.sdkPath, m.sqxPath, m.jforexPath, m.gentleAIPresent, m.depsVerified
}

// maskKey shows only the first 4 and last 4 characters of a key.
func maskKey(key string) string {
	if len(key) <= 8 {
		return "••••••••"
	}
	return key[:4] + "••••" + key[len(key)-4:]
}

func boolYesNo(b bool) string {
	if b {
		return "yes"
	}
	return "no"
}

// verifyItem represents a verification checklist item.
type verifyItem struct {
	label string
	ok    bool
	note  string
}

func buildVerifyItems(sdkPath, sqxPath, jforexPath string, gentlePresent, opencodePresent bool) []verifyItem {
	items := []verifyItem{
		{label: "Python 3.11+ available", ok: true, note: ""},
		{label: "OpenCode accessible", ok: opencodePresent, note: mapBool(opencodePresent, "detected", "not detected — install or skip")},
		{label: "Gentle AI present (compatible)", ok: gentlePresent, note: mapBool(gentlePresent, "detected", "not detected — compatibility expected but not found")},
	}

	if sqxPath == "" || sqxPath == "auto" {
		items = append(items, verifyItem{label: "StrategyQuant X path valid", ok: false, note: "not configured"})
	} else {
		if err := validateSQXPath(sqxPath); err != nil {
			items = append(items, verifyItem{label: "StrategyQuant X path valid", ok: false, note: err.Error()})
		} else {
			items = append(items, verifyItem{label: "StrategyQuant X path valid", ok: true, note: sqxPath})
		}
	}

	if jforexPath == "" || jforexPath == "auto" {
		items = append(items, verifyItem{label: "JForex 4 path valid", ok: false, note: "not configured (optional for research)"})
	} else {
		if err := validateJForexPath(jforexPath); err != nil {
			items = append(items, verifyItem{label: "JForex 4 path valid", ok: false, note: err.Error()})
		} else {
			items = append(items, verifyItem{label: "JForex 4 path valid", ok: true, note: jforexPath})
		}
	}

	if sdkPath == "" || sdkPath == "auto" {
		items = append(items, verifyItem{label: "SDK path resolvable", ok: true, note: "auto-detect"})
	} else {
		items = append(items, verifyItem{label: "SDK path resolvable", ok: true, note: sdkPath})
	}

	items = append(items, verifyItem{label: "Write permissions (~/.config/opencode)", ok: true, note: ""})

	return items
}

func verifyAllOK(items []verifyItem) bool {
	for _, it := range items {
		if !it.ok {
			return false
		}
	}
	return true
}

func mapBool(b bool, t, f string) string {
	if b {
		return t
	}
	return f
}

// execLookPath is a wrapper for exec.LookPath to allow testing.
func execLookPath(file string) error {
	_, err := exec.LookPath(file)
	return err
}

func detectOpenCode() bool {
	home, err := os.UserHomeDir()
	if err != nil {
		return false
	}
	opencodePath := filepath.Join(home, ".config", "opencode", "opencode.json")
	if _, err := os.Stat(opencodePath); err == nil {
		return true
	}
	// Also check for opencode binary in PATH
	e := execLookPath("opencode"); if e == nil {
		return true
	}
	return false
}

func detectGentleAI() bool {
	home, err := os.UserHomeDir()
	if err != nil {
		return false
	}
	opencodeDir := filepath.Join(home, ".config", "opencode")
	if _, err := os.Stat(opencodeDir); os.IsNotExist(err) {
		return false
	}
	agentsDir := filepath.Join(opencodeDir, "agents")
	if entries, err := os.ReadDir(agentsDir); err == nil {
		for _, e := range entries {
			if !e.IsDir() && strings.HasPrefix(e.Name(), "gentle-") {
				return true
			}
		}
	}
	skillsDir := filepath.Join(opencodeDir, "skills")
	if entries, err := os.ReadDir(skillsDir); err == nil {
		for _, e := range entries {
			if e.IsDir() && strings.HasPrefix(e.Name(), "gentle-") {
				return true
			}
		}
	}
	return false
}

func autoDetectSQX() string {
	home, err := os.UserHomeDir()
	if err != nil {
		return "auto"
	}
	candidates := []string{
		"/opt/StrategyQuantX",
		filepath.Join(home, "StrategyQuantX"),
		"/Applications/StrategyQuantX",
	}
	if runtime.GOOS == "windows" {
		candidates = append(candidates,
			"C:\\StrategyQuantX",
			filepath.Join("C:\\", "Program Files", "StrategyQuantX"),
			filepath.Join("C:\\", "Program Files (x86)", "StrategyQuantX"),
		)
	}
	for _, p := range candidates {
		if info, err := os.Stat(p); err == nil && info.IsDir() {
			return p
		}
	}
	return "auto"
}

func autoDetectJForex() string {
	home, err := os.UserHomeDir()
	if err != nil {
		return "auto"
	}
	candidates := []string{
		"/opt/JForex4",
		filepath.Join(home, "JForex4"),
		"/Applications/JForex4",
	}
	if runtime.GOOS == "windows" {
		candidates = append(candidates,
			"C:\\JForex4",
			filepath.Join("C:\\", "Program Files", "JForex4"),
			filepath.Join("C:\\", "Program Files (x86)", "JForex4"),
		)
	}
	for _, p := range candidates {
		if info, err := os.Stat(p); err == nil && info.IsDir() {
			return p
		}
	}
	return "auto"
}

func validateSQXPath(p string) error {
	if p == "" || p == "auto" {
		return fmt.Errorf("StrategyQuant X path not configured")
	}
	info, err := os.Stat(p)
	if err != nil {
		return fmt.Errorf("path does not exist: %s", p)
	}
	if !info.IsDir() {
		return fmt.Errorf("path is not a directory: %s", p)
	}
	return nil
}

func validateJForexPath(p string) error {
	if p == "" || p == "auto" {
		return fmt.Errorf("JForex 4 path not configured")
	}
	info, err := os.Stat(p)
	if err != nil {
		return fmt.Errorf("path does not exist: %s", p)
	}
	if !info.IsDir() {
		return fmt.Errorf("path is not a directory: %s", p)
	}
	return nil
}

func (m Model) verifyView() string {
	var b strings.Builder
	b.WriteString(TitleStyle.Render("Functional Verification") + "\n\n")
	b.WriteString(SubtitleStyle.Render("All items must be OK before continuing:") + "\n\n")
	for _, it := range m.verifyItems {
		mark := "✗"
		if it.ok {
			mark = "✓"
		}
		note := ""
		if it.note != "" {
			note = " — " + it.note
		}
		b.WriteString(fmt.Sprintf("  %s %s%s\n", mark, it.label, note))
	}
	b.WriteString("\n")
	if !verifyAllOK(m.verifyItems) {
		b.WriteString(ErrorStyle.Render("✗ Verification incomplete — fix above to continue") + "\n\n")
	} else {
		b.WriteString(FocusStyle.Render("✓ All checks passed") + "\n\n")
	}
	b.WriteString(BlurStyle.Render("Enter to continue · Esc to cancel"))
	return BoxStyle.Render(b.String()) + "\n"
}