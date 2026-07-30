package wizard

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/charmbracelet/bubbles/list"
	"github.com/charmbracelet/bubbles/textinput"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
)

// Step identifies the current wizard step.
type Step int

const (
	StepWelcome Step = iota
	StepAPIKey
	StepModel
	StepSDKPath
	StepSummary
	StepConfirm
	stepCount // internal sentinel
)

// stepTitles maps each step to its display title.
var stepTitles = map[Step]string{
	StepWelcome: "Welcome",
	StepAPIKey:  "API Key",
	StepModel:   "Model Selection",
	StepSDKPath: "SDK Path",
	StepSummary: "Summary",
	StepConfirm: "Ready",
}

// modelItem is a list.Item for the model selection step.
type modelItem struct {
	title, desc string
}

func (i modelItem) Title() string       { return i.title }
func (i modelItem) Description() string { return i.desc }
func (i modelItem) FilterValue() string { return i.title }

// Model is the Bubbletea model for the configuration wizard.
type Model struct {
	step          Step
	apiKeyInput   textinput.Model
	modelList     list.Model
	sdkPathInput  textinput.Model
	apiKey        string
	selectedModel string
	sdkPath       string
	err           error
	width         int
	height        int
}

// NewModel creates a wizard model with default values and auto-detected SDK
// path.
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
	items := []list.Item{
		modelItem{title: "deepseek-v4-flash-free", desc: "DeepSeek V4 Flash (free tier)"},
		modelItem{title: "gpt-4o", desc: "OpenAI GPT-4o"},
		modelItem{title: "claude-4-sonnet", desc: "Anthropic Claude 4 Sonnet"},
		modelItem{title: "claude-4-opus", desc: "Anthropic Claude 4 Opus"},
		modelItem{title: "gpt-4o-mini", desc: "OpenAI GPT-4o Mini"},
		modelItem{title: "gpt-4.1", desc: "OpenAI GPT-4.1"},
	}

	l := list.New(items, list.NewDefaultDelegate(), 0, 0)
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

	// Try to auto-detect the SDK path
	sdkPath := autoDetectSDK()

	return Model{
		step:          StepWelcome,
		apiKeyInput:   apiInput,
		sdkPathInput:  sdkInput,
		sdkPath:       sdkPath,
		selectedModel: "deepseek-v4-flash-free",
		modelList:     l,
	}
}

// autoDetectSDK tries to find the QuantLab SDK in common locations.
func autoDetectSDK() string {
	home, err := os.UserHomeDir()
	if err != nil {
		return "auto"
	}

	// Common locations relative to the project
	candidates := []string{
		filepath.Join(home, "Proyectos", "QuantLab AI", "sdk"),
		filepath.Join(home, "quantlab", "sdk"),
		filepath.Join(home, "code", "quantlab", "sdk"),
	}

	for _, p := range candidates {
		if info, err := os.Stat(p); err == nil && info.IsDir() {
			// Check if it looks like a Python package
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
		return m, nil

	case tea.KeyMsg:
		switch msg.String() {
		case "ctrl+c", "esc":
			return m, tea.Quit

		case "enter":
			return m.handleEnter()

		case "shift+tab":
			if m.step == StepWelcome || m.step == StepSummary || m.step == StepConfirm {
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
	case StepWelcome:
		m.step = StepAPIKey
		m.apiKeyInput.Focus()
		m.err = nil
		return m, textinput.Blink

	case StepAPIKey:
		m.apiKey = strings.TrimSpace(m.apiKeyInput.Value())
		if m.apiKey == "" {
			m.err = fmt.Errorf("API key is required to proceed")
			return m, nil
		}
		m.err = nil
		m.step = StepModel
		// Select first item if nothing selected
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
		if val == "" {
			val = "auto"
		}
		m.sdkPath = val
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
	}
	return m, nil
}

func (m Model) View() string {
	progress := m.progressBar()

	switch m.step {
	case StepWelcome:
		return progress + "\n" + m.welcomeView()
	case StepAPIKey:
		return progress + "\n" + m.apiKeyView()
	case StepModel:
		return progress + "\n" + m.modelView()
	case StepSDKPath:
		return progress + "\n" + m.sdkPathView()
	case StepSummary:
		return progress + "\n" + m.summaryView()
	case StepConfirm:
		return progress + "\n" + m.confirmView()
	}
	return ""
}

// progressBar renders a simple step indicator (● Step 2/5 ○○○○).
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

func (m Model) welcomeView() string {
	var b strings.Builder
	b.WriteString(BoxStyle.Render(
		TitleStyle.Render("QuantLab AI — Setup Wizard") + "\n\n" +
			SubtitleStyle.Render("This wizard will help you configure your QuantLab AI") + "\n" +
			SubtitleStyle.Render("SDK connection. You'll need:") + "\n\n" +
			"  " + FocusStyle.Render("•") + " An OpenCode API key\n" +
			"  " + FocusStyle.Render("•") + " A default AI model\n" +
			"  " + FocusStyle.Render("•") + " The SDK installation path\n\n" +
			BlurStyle.Render("Press Enter to begin · Esc to cancel"),
	))
	return b.String() + "\n"
}

func (m Model) apiKeyView() string {
	var b strings.Builder
	b.WriteString(TitleStyle.Render("API Key") + "\n\n")
	b.WriteString(SubtitleStyle.Render("Enter your OpenCode API key:") + "\n\n")
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
	b.WriteString(SubtitleStyle.Render("Choose the default AI model:") + "\n\n")
	b.WriteString(m.modelList.View())
	b.WriteString("\n" + BlurStyle.Render("↑/↓ to navigate · Enter to confirm · Esc to cancel"))
	return BoxStyle.Render(b.String()) + "\n"
}

func (m Model) sdkPathView() string {
	var b strings.Builder
	b.WriteString(TitleStyle.Render("SDK Path") + "\n\n")
	b.WriteString(SubtitleStyle.Render("Path to the QuantLab SDK source (or 'auto' to detect):") + "\n\n")
	b.WriteString(m.sdkPathInput.View() + "\n")
	b.WriteString("\n" + BlurStyle.Render("Enter to confirm · Esc to cancel"))
	return BoxStyle.Render(b.String()) + "\n"
}

func (m Model) summaryView() string {
	var b strings.Builder
	b.WriteString(TitleStyle.Render("Configuration Summary") + "\n\n")
	b.WriteString(BoxStyle.Render(
		LabelStyle.Render("API Key:     ") + ValueStyle.Render(maskKey(m.apiKey)) + "\n"+
			LabelStyle.Render("Model:       ") + ValueStyle.Render(m.selectedModel)+"\n"+
			LabelStyle.Render("SDK Path:    ") + ValueStyle.Render(m.sdkPath)+"\n",
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
			"  "+FocusStyle.Render("•")+" Configure OpenCode agents\n"+
			"  "+FocusStyle.Render("•")+" Install skills and prompts\n\n"+
			FocusStyle.Render("Press Enter to apply · Esc to cancel"),
	))
	return b.String() + "\n"
}

// Result returns the collected configuration values after the wizard completes.
func (m Model) Result() (apiKey, model, sdkPath string) {
	return m.apiKey, m.selectedModel, m.sdkPath
}

// maskKey shows only the first 4 and last 4 characters of a key.
func maskKey(key string) string {
	if len(key) <= 8 {
		return "••••••••"
	}
	return key[:4] + "••••" + key[len(key)-4:]
}
