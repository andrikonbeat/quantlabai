// Package onboarding implements the `quantlab onboarding` TUI flow.
// It is a standalone Bubbletea model, independent from the install/configure
// wizard. The TUI owns consent collection and tool installation execution so
// the CLI wrapper (internal/app) only consumes the resulting choices.
package onboarding

import (
	"encoding/json"
	"fmt"
	"os"
	"runtime"
	"strings"
	"path/filepath"

	"github.com/charmbracelet/bubbles/textinput"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"

	"github.com/andrikonbeat/quantlabai/internal/assets"
	"github.com/andrikonbeat/quantlabai/internal/config"
	"github.com/andrikonbeat/quantlabai/internal/sdk"
	"github.com/andrikonbeat/quantlabai/internal/tui/screens"
	"github.com/andrikonbeat/quantlabai/internal/tui/theme"
	"github.com/andrikonbeat/quantlabai/internal/tools"
)

// Step identifies the current onboarding step.
type Step int

const (
	StepOSDetect Step = iota
	StepIntro
	StepConsentOpenCode
	StepConsentGentleAI
	StepInstalling
	StepInstallFailed
	StepInstallManual
	StepSQX
	StepJForex
	StepVerify
	StepPostInstall
	stepCount
)

// maxInstallAttempts bounds consecutive install failures before the flow
// forces manual mode.
const maxInstallAttempts = 3

// Tool identifiers used across consent, install queue and readiness.
const (
	toolOpenCode = "opencode"
	toolGentleAI = "gentle-ai"
)

// Verification marks.
const (
	markOK      = "✓"
	markMissing = "✗"
	markWarn    = "⚠"
)

// Install and documentation copy shared by consent and manual steps.
const (
	openCodeInstallCommand = "curl -fsSL https://opencode.ai/install | bash"
	openCodeDocsURL        = "https://opencode.ai/docs/"
	gentleAIInstallCommand = "curl -fsSL https://raw.githubusercontent.com/Gentleman-Programming/gentle-ai/main/scripts/install.sh | bash"
	gentleAIDocsURL        = "https://github.com/Gentleman-Programming/gentle-ai"
	delegationSample       = "Instalá o actualizá OpenCode y gentle-ai, y verificá el entorno de QuantLab."
)

// Result captures the user's onboarding choices.
type Result struct {
	Consent struct {
		OpenCode bool
		GentleAI bool
	}
	// OpenCodeReady/GentleAIReady are true when the tool was detected at
	// start or installed successfully during the flow.
	OpenCodeReady bool
	GentleAIReady bool
	EngramReady   bool
	SQX           struct {
		InstallPath string
	}
	JForex struct {
		InstallPath string
		AccountMode string
		Username    string
		Password    string
	}
	PrimaryAgent string
}

// installDoneMsg is emitted when an install job finishes.
type installDoneMsg struct {
	tool    string
	display string
	err     error
}

// checkItem is one line of the functional verification checklist.
type checkItem struct {
	Label string
	Mark  string
}

// Model is the Bubbletea model for the onboarding flow.
type Model struct {
	step     Step
	width    int
	height   int
	err      error
	quitting bool
	result   Result
	steps    []PostInstallStep

	// StepIntro
	introScroll int

	// Consent steps
	consentOpenCode   bool
	consentGentleAI   bool
	openCodeInstalled bool
	gentleAIInstalled bool
	engramInstalled   bool

	// Install execution — injectable for tests.
	installOpenCodeFn func(home string) (string, error)
	installGentleAIFn func(home string) (string, error)
	homeFn            func() (string, error)
	sdkDetectFn       func() (bool, error)

	// Install queue / failure bookkeeping
	installQueue    []string
	installAttempts int
	currentTool     string
	installError    string
	manualTool      string
	manualDisplay   string
	manualTools     map[string]bool

	// StepSQX
	sqxInput textinput.Model
	sqxError string

	// StepJForex
	jforexPathInput  textinput.Model
	jforexUserInput  textinput.Model
	jforexPassInput  textinput.Model
	accountModeIndex int

	// StepVerify
	verifyItems []checkItem
	verifyBuilt bool

	// StepPostInstall
	primaryAgentIndex int

	// StepOSDetect
	osInfo string
}

// PostInstallStep describes one bullet in the post-install guide.
type PostInstallStep struct {
	ID          string `json:"id"`
	Title       string `json:"title"`
	Description string `json:"description"`
}

// NewModel creates the onboarding model with default values.
func NewModel() Model {
	sqxInput := textinput.New()
	sqxInput.Placeholder = "/opt/SQX o ruta a la carpeta descomprimida"
	sqxInput.Focus()
	sqxInput.CharLimit = 256
	sqxInput.Width = 60

	jforexPathInput := textinput.New()
	jforexPathInput.Placeholder = "/opt/JForex o ruta de instalación"
	jforexPathInput.CharLimit = 256
	jforexPathInput.Width = 60

	jforexUserInput := textinput.New()
	jforexUserInput.Placeholder = "usuario Dukascopy"
	jforexUserInput.CharLimit = 128
	jforexUserInput.Width = 60

	jforexPassInput := textinput.New()
	jforexPassInput.Placeholder = "contraseña"
	jforexPassInput.EchoMode = textinput.EchoPassword
	jforexPassInput.EchoCharacter = '•'
	jforexPassInput.CharLimit = 128
	jforexPassInput.Width = 60

	openCodeInstalled := tools.DetectOpenCode()
	gentleAIInstalled := tools.DetectGentleAI()

	// Auto-detect JForex 4 installation
	jforexPath := autoDetectJForex()
	if jforexPath != "" {
		jforexPathInput.SetValue(jforexPath)
	}

	// OS detection for pre-check
	osInfo := detectOSInfo()

	return Model{
		step:              StepOSDetect,
		accountModeIndex:  0, // default demo
		primaryAgentIndex: 0, // default quantlab-orchestrator
		sqxInput:          sqxInput,
		jforexPathInput:   jforexPathInput,
		jforexUserInput:   jforexUserInput,
		jforexPassInput:   jforexPassInput,
		openCodeInstalled: openCodeInstalled,
		gentleAIInstalled: gentleAIInstalled,
	engramInstalled:   tools.DetectEngram(),
		installOpenCodeFn: tools.InstallOpenCode,
		installGentleAIFn: tools.InstallGentleAI,
		homeFn:            os.UserHomeDir,
		sdkDetectFn:       detectSDKReady,
		manualTools:       map[string]bool{},
		steps:             loadPostInstallSteps(),
		osInfo:            osInfo,
		result: Result{
			OpenCodeReady: openCodeInstalled,
			GentleAIReady: gentleAIInstalled,
			EngramReady:   tools.DetectEngram(),
		},
	}
}

// detectSDKReady reports whether the QuantLab SDK is installed.
func detectSDKReady() (bool, error) {
	info, err := sdk.DetectInstalledSDK()
	if err != nil {
		return false, err
	}
	return info.Installed, nil
}

// detectOSInfo returns a human-readable string with OS, architecture, and
// Linux distribution (when applicable).
func detectOSInfo() string {
	goos := runtime.GOOS
	goarch := runtime.GOARCH
	var distro string
	if goos == "linux" {
		if data, err := os.ReadFile("/etc/os-release"); err == nil {
			for _, line := range strings.Split(string(data), "\n") {
				if strings.HasPrefix(line, "PRETTY_NAME=") {
					distro = strings.Trim(strings.TrimPrefix(line, "PRETTY_NAME="), "\"")
					break
				}
			}
		}
	}
	parts := []string{fmt.Sprintf("OS: %s/%s", goos, goarch)}
	if distro != "" {
		parts = append(parts, fmt.Sprintf("Distro: %s", distro))
	}
	return strings.Join(parts, "  |  ")
}

// postInstallGuide mirrors the embedded onboarding/steps.json envelope, which
// wraps the guide list under a "steps" key.
type postInstallGuide struct {
	Steps []PostInstallStep `json:"steps"`
}

func loadPostInstallSteps() []PostInstallStep {
	b, err := assets.FS.ReadFile("onboarding/steps.json")
	if err != nil {
		return defaultPostInstallSteps()
	}
	var guide postInstallGuide
	if err := json.Unmarshal(b, &guide); err != nil || len(guide.Steps) == 0 {
		return defaultPostInstallSteps()
	}
	return guide.Steps
}

func defaultPostInstallSteps() []PostInstallStep {
	return []PostInstallStep{
		{ID: "campaigns-folder", Title: "Carpeta de campañas", Description: "Creá una carpeta dedicada para tus campañas de trading (ej: ~/trading/)."},
		{ID: "opencode", Title: "Abrí OpenCode", Description: "Abrí OpenCode en la carpeta de campañas. OpenCode es el centro de control que orquesta los agentes."},
		{ID: "primary-agent", Title: "Elegí el agente primario", Description: "quantlab-orchestrator: campañas de investigación. guardian-orchestrator: live-ops 24/7."},
		{ID: "example-prompt", Title: "Ejemplo de prompt", Description: "Ejecuta una campaña completa para EURUSD M5 con riesgo 1%."},
	}
}

// Init starts the model on the intro step.
func (m *Model) Init() tea.Cmd {
	return nil
}

// Update handles input for the current step.
func (m *Model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	if done, ok := msg.(installDoneMsg); ok {
		return m.handleInstallDone(done)
	}

	if key, ok := msg.(tea.KeyMsg); ok {
		switch key.Type {
		case tea.KeyCtrlC, tea.KeyEsc:
			m.quitting = true
			return m, tea.Quit
		}
		switch m.step {
		case StepConsentOpenCode, StepConsentGentleAI:
			if handled, cmd := m.handleConsentKey(key); handled {
				return m, cmd
			}
		case StepInstallFailed:
			if handled, cmd := m.handleInstallFailedKey(key); handled {
				return m, cmd
			}
		}
		switch key.Type {
		case tea.KeyEnter:
			return m.handleEnter()
		case tea.KeyTab:
			m.handleTab()
		}
	}

	switch m.step {
	case StepSQX:
		sqxModel, cmd := m.sqxInput.Update(msg)
		m.sqxInput = sqxModel
		return m, cmd
	case StepJForex:
		switch {
		case m.jforexPathInput.Focused():
			model, cmd := m.jforexPathInput.Update(msg)
			m.jforexPathInput = model
			return m, cmd
		case m.jforexUserInput.Focused():
			model, cmd := m.jforexUserInput.Update(msg)
			m.jforexUserInput = model
			return m, cmd
		case m.jforexPassInput.Focused():
			model, cmd := m.jforexPassInput.Update(msg)
			m.jforexPassInput = model
			return m, cmd
		}
	}

	return m, nil
}

// handleConsentKey handles the Sí/No prompt when a tool is missing. It returns
// handled=false for keys the consent step does not own (e.g. Enter).
func (m *Model) handleConsentKey(key tea.KeyMsg) (bool, tea.Cmd) {
	detected := m.openCodeInstalled
	if m.step == StepConsentGentleAI {
		detected = m.gentleAIInstalled
	}
	if detected {
		return false, nil
	}
	switch strings.ToLower(key.String()) {
	case "s", "y":
		if m.step == StepConsentOpenCode {
			m.consentOpenCode = true
		} else {
			m.consentGentleAI = true
		}
		return true, m.advanceConsent()
	case "n":
		return true, m.advanceConsent()
	}
	return false, nil
}

// advanceConsent records the current consent decision and moves to the next
// consent step, kicking off installs once both are collected.
func (m *Model) advanceConsent() tea.Cmd {
	if m.step == StepConsentOpenCode {
		m.step = StepConsentGentleAI
		return nil
	}
	if m.consentOpenCode || m.consentGentleAI {
		m.step = StepInstalling
		return m.beginInstalls()
	}
	m.step = StepSQX
	return nil
}

// handleInstallFailedKey handles retry / manual / skip on the failure step.
func (m *Model) handleInstallFailedKey(key tea.KeyMsg) (bool, tea.Cmd) {
	switch strings.ToLower(key.String()) {
	case "r":
		if m.installAttempts >= maxInstallAttempts {
			return true, nil
		}
		m.step = StepInstalling
		return true, m.runInstall(m.currentTool)
	case "m":
		m.manualTool = m.currentTool
		m.step = StepInstallManual
		return true, nil
	case "o":
		m.step = StepInstalling
		return true, m.nextInstall()
	}
	return false, nil
}

// handleInstallDone processes the result of one install job.
func (m *Model) handleInstallDone(done installDoneMsg) (tea.Model, tea.Cmd) {
	if done.err == nil && done.display == "" {
		m.markReady(done.tool)
		m.installError = ""
		return m, m.nextInstall()
	}
	if done.err == nil {
		// The tool could not be installed automatically and the installer
		// returned manual instructions: treat it as a manual fallback.
		m.manualTool = done.tool
		m.manualTools[done.tool] = true
		m.manualDisplay = done.display
		m.step = StepInstallManual
		return m, nil
	}
	m.installError = done.err.Error()
	m.installAttempts++
	if m.installAttempts >= maxInstallAttempts {
		m.manualTool = done.tool
		m.step = StepInstallManual
		return m, nil
	}
	m.step = StepInstallFailed
	return m, nil
}

func (m *Model) markReady(tool string) {
	switch tool {
	case toolOpenCode:
		m.result.OpenCodeReady = true
	case toolGentleAI:
		m.result.GentleAIReady = true
	}
}

// beginInstalls builds the install queue from consent and starts the first job.
func (m *Model) beginInstalls() tea.Cmd {
	m.installQueue = nil
	if m.consentOpenCode {
		m.installQueue = append(m.installQueue, toolOpenCode)
	}
	if m.consentGentleAI {
		m.installQueue = append(m.installQueue, toolGentleAI)
	}
	return m.nextInstall()
}

// nextInstall pops the next job from the queue and runs it, one per command.
// When the queue is empty it advances to the SQX step.
func (m *Model) nextInstall() tea.Cmd {
	if len(m.installQueue) == 0 {
		m.step = StepSQX
		return nil
	}
	tool := m.installQueue[0]
	m.installQueue = m.installQueue[1:]
	m.currentTool = tool
	m.installAttempts = 0
	return m.runInstall(tool)
}

// runInstall returns a tea.Cmd that executes the installer for the given tool.
func (m *Model) runInstall(tool string) tea.Cmd {
	runner := m.runnerFor(tool)
	homeFn := m.homeFn
	return func() tea.Msg {
		if runner == nil {
			return installDoneMsg{tool: tool, err: fmt.Errorf("no installer registered for %q", tool)}
		}
		home, err := homeFn()
		if err != nil {
			return installDoneMsg{tool: tool, err: fmt.Errorf("home dir: %w", err)}
		}
		display, err := runner(home)
		return installDoneMsg{tool: tool, display: display, err: err}
	}
}

func (m *Model) runnerFor(tool string) func(home string) (string, error) {
	switch tool {
	case toolOpenCode:
		return m.installOpenCodeFn
	case toolGentleAI:
		return m.installGentleAIFn
	}
	return nil
}

func (m *Model) handleEnter() (tea.Model, tea.Cmd) {
	switch m.step {
	case StepOSDetect:
		m.step = StepIntro
	case StepIntro:
		m.step = StepConsentOpenCode
	case StepConsentOpenCode, StepConsentGentleAI:
		return m, m.advanceConsent()
	case StepSQX:
		m.result.SQX.InstallPath = strings.TrimSpace(m.sqxInput.Value())
		if m.result.SQX.InstallPath != "" {
			if err := config.ValidateSQXPath(m.result.SQX.InstallPath); err != nil {
				m.sqxError = err.Error()
				return m, nil
			}
		}
		m.sqxError = ""
		m.step = StepJForex
	case StepJForex:
		m.result.JForex.InstallPath = strings.TrimSpace(m.jforexPathInput.Value())
		m.result.JForex.Username = strings.TrimSpace(m.jforexUserInput.Value())
		m.result.JForex.Password = strings.TrimSpace(m.jforexPassInput.Value())
		if m.accountModeIndex == 0 {
			m.result.JForex.AccountMode = "demo"
		} else {
			m.result.JForex.AccountMode = "live"
		}
		m.verifyBuilt = false
		m.step = StepVerify
	case StepInstallManual:
		m.manualTools[m.manualTool] = true
		m.step = StepInstalling
		return m, m.nextInstall()
	case StepVerify:
		m.step = StepPostInstall
	case StepPostInstall:
		agents := []string{"quantlab-orchestrator", "guardian-orchestrator"}
		if m.primaryAgentIndex < len(agents) {
			m.result.PrimaryAgent = agents[m.primaryAgentIndex]
		}
		m.quitting = true
		return m, tea.Quit
	}
	return m, nil
}

func (m *Model) handleTab() {
	switch {
	case m.jforexPathInput.Focused():
		m.jforexPathInput.Blur()
		m.jforexUserInput.Focus()
	case m.jforexUserInput.Focused():
		m.jforexUserInput.Blur()
		m.jforexPassInput.Focus()
	default:
		m.jforexPathInput.Focus()
	}
}

// View renders the current step.
func (m *Model) View() string {
	if m.quitting {
		return lipgloss.NewStyle().Padding(1).Render(theme.SuccessStyle.Render("Onboarding completado."))
	}
	switch m.step {
	case StepOSDetect:
		return m.viewOSDetect()
	case StepIntro:
		return m.viewIntro()
	case StepConsentOpenCode:
		return m.viewConsentTool("OpenCode", "orquestación de agentes", m.openCodeInstalled, openCodeDocsURL, openCodeInstallCommand)
	case StepConsentGentleAI:
		return m.viewConsentTool("gentle-ai", "skills y revisión de código", m.gentleAIInstalled, gentleAIDocsURL, gentleAIInstallCommand)
	case StepInstalling:
		return m.viewInstalling()
	case StepInstallFailed:
		return m.viewInstallFailed()
	case StepInstallManual:
		return m.viewInstallManual()
	case StepSQX:
		return m.viewSQX()
	case StepJForex:
		return m.viewJForex()
	case StepVerify:
		return m.viewVerify()
	case StepPostInstall:
		return m.viewPostInstall()
	default:
		return ""
	}
}

func (m *Model) viewOSDetect() string {
	return lipgloss.NewStyle().Padding(1).Render(
		theme.TitleStyle.Render("Detección del entorno") + "\n\n" +
		theme.SubtextStyle.Render(m.osInfo) + "\n\n" +
		theme.UnselectedStyle.Render("Verificá que el sistema operativo sea compatible con QuantLab AI.") + "\n\n" +
		theme.HelpStyle.Render("Presiona Enter para continuar."),
	)
}

func (m *Model) viewIntro() string {
	return lipgloss.NewStyle().Padding(1).Render(
		theme.TitleStyle.Render("QuantLab AI — Laboratorio de investigación cuantitativa") + "\n\n" +
			theme.SubtextStyle.Render("Flujo: research → hypothesis → config → review → dispatch → monitor → retest → optimize → portfolio → compile → deploy → demo → archive → live-ops") + "\n\n" +
			theme.UnselectedStyle.Render("QuantLab orquesta un pipeline de investigación con dependencias propias (SDK de QuantLab, OpenCode como centro de control) y herramientas de terceros: OpenCode (orquestación LLM), gentle-ai (skills/revisión), StrategyQuantX (backtesting/optimización), JForex 4 (despliegue demo/real), Dukascopy (datos/ejecución).") + "\n\n" +
			theme.HelpStyle.Render("Presiona Enter para continuar."),
	)
}

// viewConsentTool renders the consent step for one tool. Detected tools show
// informational text plus how to delegate management to the OpenCode agent;
// missing tools show an interactive Sí/No prompt.
func (m *Model) viewConsentTool(name, role string, detected bool, docs, command string) string {
	var b strings.Builder
	b.WriteString(theme.TitleStyle.Render(name) + " — " + theme.SubtextStyle.Render(role) + ".\n\n")
	if detected {
		b.WriteString(theme.SuccessStyle.Render(name+" ya está instalado ✓.") + "\n\n")
		b.WriteString(theme.UnselectedStyle.Render("Podés delegar la gestión de herramientas al agente OpenCode:") + "\n")
	} else {
		b.WriteString(theme.WarningStyle.Render("¿Instalar "+name+" automáticamente? [S/N]") + "\n")
		b.WriteString("  S = instalar ahora    N = omitir e instalarlo después\n\n")
		b.WriteString(theme.UnselectedStyle.Render("También podés delegarlo al agente OpenCode:") + "\n")
	}
	b.WriteString("  " + theme.HelpStyle.Render("Comando: ") + command + "\n")
	b.WriteString("  " + theme.HelpStyle.Render("Instrucción de ejemplo: \"") + delegationSample + "\"\n")
	b.WriteString("  " + theme.HelpStyle.Render("Docs: ") + docs + "\n")
	if detected {
		b.WriteString("\n" + theme.HelpStyle.Render("Enter = siguiente"))
	}
	return lipgloss.NewStyle().Padding(1).Render(b.String())
}

func (m *Model) viewInstalling() string {
	tool := m.currentTool
	if tool == "" {
		tool = "herramientas"
	}
	return lipgloss.NewStyle().Padding(1).Render(
		screens.RenderOperationRunning("Instalando "+tool+"...", "Por favor esperá.", "◐") + "\n")
}

func (m *Model) viewInstallFailed() string {
	options := "[R] reintentar  |  [M] instalación manual  |  [O] omitir"
	if m.installAttempts >= maxInstallAttempts {
		options = "[M] instalación manual  |  [O] omitir"
	}
	return lipgloss.NewStyle().Padding(1).Render(screens.RenderComplete(screens.CompletePayload{
		FailedSteps: []screens.FailedStep{{
			ID:    fmt.Sprintf("Instalación de %s (intento %d/%d)", m.currentTool, m.installAttempts, maxInstallAttempts),
			Error: m.installError,
		}},
		NextSteps: []string{options},
	}))
}

func (m *Model) viewInstallManual() string {
	url, instruction := manualInstallInfo(m.manualTool)
	var b strings.Builder
	b.WriteString(theme.TitleStyle.Render("Instalación manual de "+m.manualTool) + "\n\n")
	b.WriteString(theme.UnselectedStyle.Render("Descargalo desde: ") + url + "\n")
	b.WriteString(theme.UnselectedStyle.Render("Instrucción: ") + instruction + "\n")
	if m.manualDisplay != "" {
		b.WriteString("\n" + theme.WarningStyle.Render("Nota del instalador: "+m.manualDisplay) + "\n")
	}
	b.WriteString("\n" + theme.HelpStyle.Render("Cuando termines (o si preferís continuar), Enter = siguiente"))
	return lipgloss.NewStyle().Padding(1).Render(b.String())
}

func manualInstallInfo(tool string) (url, instruction string) {
	switch tool {
	case toolOpenCode:
		return openCodeDocsURL, openCodeInstallCommand
	case toolGentleAI:
		return gentleAIDocsURL, gentleAIInstallCommand
	default:
		return "", ""
	}
}

func (m *Model) viewSQX() string {
	var b strings.Builder
	b.WriteString(theme.TitleStyle.Render("StrategyQuantX (SQX)") + " — " + theme.SubtextStyle.Render("motor de backtesting y generación de estrategias.") + "\n")
	b.WriteString(theme.UnselectedStyle.Render("Descargalo manualmente desde https://strategyquant.com/ y descomprimilo.") + "\n\n")
	b.WriteString(theme.HeadingStyle.Render("Carpeta de instalación de SQX:") + "\n" + m.sqxInput.View() + "\n\n")
	b.WriteString(theme.HelpStyle.Render("Enter = siguiente  |  Tab = siguiente campo"))
	body := b.String()
	if m.sqxError != "" {
		body = theme.ErrorStyle.Render("⚠ "+m.sqxError) + "\n\n" + body
	}
	return lipgloss.NewStyle().Padding(1).Render(body)
}

func (m *Model) viewJForex() string {
	modes := []string{"demo", "live"}
	mode := modes[m.accountModeIndex]
	return lipgloss.NewStyle().Padding(1).Render(
		theme.TitleStyle.Render("JForex 4") + " — " + theme.SubtextStyle.Render("plataforma de trading de Dukascopy.") + "\n" +
			theme.UnselectedStyle.Render("Descargala manualmente desde https://www.dukascopy.com/downloads/bank/jforex/") + "\n" +
			theme.SubtextStyle.Render("Cuenta demo: registro por email, 14 días. Cuenta live: requiere verificación.") + "\n\n" +
			theme.HeadingStyle.Render("Carpeta de instalación:") + "\n" + m.jforexPathInput.View() + "\n\n" +
			theme.HeadingStyle.Render("Usuario: ") + m.jforexUserInput.View() + "\n" +
			theme.HeadingStyle.Render("Contraseña: ") + m.jforexPassInput.View() + "\n" +
			theme.HeadingStyle.Render(fmt.Sprintf("Modo: %s (Tab para cambiar)", mode)) + "\n\n" +
			theme.HelpStyle.Render("Enter = siguiente  |  Tab = siguiente campo"),
	)
}

// verifyChecklist builds (once) the functional verification checklist.
func (m *Model) verifyChecklist() []checkItem {
	if m.verifyBuilt {
		return m.verifyItems
	}
	m.verifyItems = m.buildVerifyChecklist()
	m.verifyBuilt = true
	return m.verifyItems
}

func (m *Model) buildVerifyChecklist() []checkItem {
	items := []checkItem{
		m.toolCheck("OpenCode", toolOpenCode, m.openCodeInstalled || m.result.OpenCodeReady),
		m.toolCheck("gentle-ai", toolGentleAI, m.gentleAIInstalled || m.result.GentleAIReady),
		m.toolCheck("Engram (memoria persistente)", "engram", m.engramInstalled || m.result.EngramReady),
	}

	switch {
	case m.result.SQX.InstallPath == "":
		items = append(items, checkItem{"Ruta de SQX", markWarn})
	case config.ValidateSQXPath(m.result.SQX.InstallPath) == nil:
		items = append(items, checkItem{"Ruta de SQX", markOK})
	default:
		items = append(items, checkItem{"Ruta de SQX", markMissing})
	}

	if m.result.JForex.InstallPath != "" {
		items = append(items, checkItem{"Ruta de JForex", markOK})
	} else {
		items = append(items, checkItem{"Ruta de JForex", markWarn})
	}

	ready, err := m.sdkDetectFn()
	switch {
	case err != nil:
		items = append(items, checkItem{"SDK de QuantLab", markWarn})
	case ready:
		items = append(items, checkItem{"SDK de QuantLab", markOK})
	default:
		items = append(items, checkItem{"SDK de QuantLab", markMissing})
	}
	return items
}

func (m *Model) toolCheck(label, tool string, ready bool) checkItem {
	switch {
	case ready:
		return checkItem{label, markOK}
	case m.manualTools[tool]:
		return checkItem{label + " (instalación manual pendiente)", markWarn}
	default:
		return checkItem{label, markMissing}
	}
}

// verifyItems maps the internal checklist to the shared render model. The
// warning mark maps to a non-OK, non-blocking optional item.
func (m *Model) verifyRenderItems(items []checkItem) []screens.CheckItem {
	out := make([]screens.CheckItem, 0, len(items))
	for _, it := range items {
		out = append(out, screens.CheckItem{
			Label:    it.Label,
			OK:       it.Mark == markOK,
			Optional: it.Mark == markWarn,
		})
	}
	return out
}

func (m *Model) viewVerify() string {
	items := m.verifyChecklist()
	missing := false
	for _, it := range items {
		if it.Mark == markMissing {
			missing = true
		}
	}

	var notes []string
	if missing {
		notes = append(notes,
			"⚠ Faltan componentes. Recomendamos completar la instalación desde el agente OpenCode:",
			"  Abrí OpenCode y pedile: \""+delegationSample+"\"",
		)
	}

	return lipgloss.NewStyle().Padding(1).Render(
		screens.RenderDetection(
			"Verificación funcional del entorno",
			m.verifyRenderItems(items),
			notes,
			theme.HelpStyle.Render("Enter = continuar"),
		))
}

func (m *Model) viewPostInstall() string {
	agents := []string{"quantlab-orchestrator", "guardian-orchestrator"}
	selected := agents[m.primaryAgentIndex]

	checklist := make([]screens.CompleteCheckItem, 0, len(m.steps))
	for _, s := range m.steps {
		ready := false
		switch s.ID {
		case "opencode":
			ready = m.openCodeInstalled || m.result.OpenCodeReady
		case "gentle-ai":
			ready = m.gentleAIInstalled || m.result.GentleAIReady
		case "primary-agent":
			ready = selected != ""
		}
		checklist = append(checklist, screens.CompleteCheckItem{Label: s.Title, Done: ready})
	}

	var manual []string
	for _, tool := range []string{toolOpenCode, toolGentleAI} {
		if m.manualTools[tool] {
			manual = append(manual, "Completá la instalación manual de "+tool)
		}
	}

	ready := 0
	for _, c := range checklist {
		if c.Done {
			ready++
		}
	}

	return lipgloss.NewStyle().Padding(1).Render(screens.RenderComplete(screens.CompletePayload{
		ConfiguredAgents:    len(agents),
		InstalledComponents: ready,
		Checklist:           checklist,
		ManualActions:       manual,
		NextSteps: []string{
			`1) cd "<campañas>/" && opencode`,
			"2) Elegí el agente " + selected,
			`3) Prompt de ejemplo: "Comienza una campaña para un portafolio de 100USD"`,
		},
		Footer: theme.HelpStyle.Render("Enter = finalizar"),
	}))
}

// Result returns the user's onboarding choices.
func (m *Model) Result() Result {
	return m.result
}

// Steps returns the loaded post-install guide steps.
func (m *Model) Steps() []PostInstallStep {
	return m.steps
}

// autoDetectJForex tries to find the JForex 4 installation in common locations.
func autoDetectJForex() string {
	home, err := os.UserHomeDir()
	if err != nil {
		return ""
	}
	candidates := []string{
		"/opt/JForex4",
		filepath.Join(home, "JForex4"),
		filepath.Join(home, "Applications", "JForex4"),
		filepath.Join(home, ".jforex4"),
	}
	for _, p := range candidates {
		if info, err := os.Stat(p); err == nil && info.IsDir() {
			strategies := filepath.Join(p, "Strategies")
			if _, err := os.Stat(strategies); err == nil {
				return p
			}
		}
	}
	return ""
}
