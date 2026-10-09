// Package onboarding implements the `quantlab onboarding` TUI flow.
// It is a standalone Bubbletea model, independent from the install/configure
// wizard. The TUI owns consent collection and tool installation execution so
// the CLI wrapper (internal/app) only consumes the resulting choices.
package onboarding

import (
	"encoding/json"
	"fmt"
	"os"
	"strings"

	"github.com/charmbracelet/bubbles/textinput"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"

	"github.com/andrikonbeat/quantlabai/internal/assets"
	"github.com/andrikonbeat/quantlabai/internal/config"
	"github.com/andrikonbeat/quantlabai/internal/sdk"
	"github.com/andrikonbeat/quantlabai/internal/tools"
)

// Step identifies the current onboarding step.
type Step int

const (
	StepIntro Step = iota
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
	openCodeInstallCommand = "npm install -g --ignore-scripts opencode-ai@latest"
	openCodeDocsURL        = "https://opencode.ai/"
	gentleAIInstallCommand = "Descargá el binario desde GitHub y movelo a ~/.local/bin"
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

	return Model{
		step:              StepIntro,
		accountModeIndex:  0, // default demo
		primaryAgentIndex: 0, // default quantlab-orchestrator
		sqxInput:          sqxInput,
		jforexPathInput:   jforexPathInput,
		jforexUserInput:   jforexUserInput,
		jforexPassInput:   jforexPassInput,
		openCodeInstalled: openCodeInstalled,
		gentleAIInstalled: gentleAIInstalled,
		installOpenCodeFn: tools.InstallOpenCode,
		installGentleAIFn: tools.InstallGentleAI,
		homeFn:            os.UserHomeDir,
		sdkDetectFn:       detectSDKReady,
		manualTools:       map[string]bool{},
		steps:             loadPostInstallSteps(),
		result: Result{
			OpenCodeReady: openCodeInstalled,
			GentleAIReady: gentleAIInstalled,
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
		return lipgloss.NewStyle().Padding(1).Render("Onboarding completado.")
	}
	switch m.step {
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

func (m *Model) viewIntro() string {
	return lipgloss.NewStyle().Padding(1).Render(
		"QuantLab AI — Laboratorio de investigación cuantitativa\n\n" +
			"Flujo: research → hypothesis → config → review → dispatch → monitor → retest → optimize → portfolio → compile → deploy → demo → archive → live-ops\n\n" +
			"QuantLab orquesta un pipeline de investigación con dependencias propias (SDK de QuantLab, OpenCode como centro de control) y herramientas de terceros: OpenCode (orquestación LLM), gentle-ai (skills/revisión), StrategyQuantX (backtesting/optimización), JForex 4 (despliegue demo/real), Dukascopy (datos/ejecución).\n\n" +
			"Presiona Enter para continuar.",
	)
}

// viewConsentTool renders the consent step for one tool. Detected tools show
// informational text plus how to delegate management to the OpenCode agent;
// missing tools show an interactive Sí/No prompt.
func (m *Model) viewConsentTool(name, role string, detected bool, docs, command string) string {
	var b strings.Builder
	b.WriteString(fmt.Sprintf("%s — %s.\n\n", name, role))
	if detected {
		b.WriteString(fmt.Sprintf("%s ya está instalado ✓.\n\n", name))
		b.WriteString("Podés delegar la gestión de herramientas al agente OpenCode:\n")
	} else {
		b.WriteString(fmt.Sprintf("¿Instalar %s automáticamente? [S/N]\n", name))
		b.WriteString("  S = instalar ahora    N = omitir e instalarlo después\n\n")
		b.WriteString("También podés delegarlo al agente OpenCode:\n")
	}
	b.WriteString("  Comando: " + command + "\n")
	b.WriteString("  Instrucción de ejemplo: \"" + delegationSample + "\"\n")
	b.WriteString("  Docs: " + docs + "\n")
	if detected {
		b.WriteString("\nEnter = siguiente")
	}
	return lipgloss.NewStyle().Padding(1).Render(b.String())
}

func (m *Model) viewInstalling() string {
	tool := m.currentTool
	if tool == "" {
		tool = "herramientas"
	}
	return lipgloss.NewStyle().Padding(1).Render(
		fmt.Sprintf("Instalando %s...\n\nPor favor esperá.", tool))
}

func (m *Model) viewInstallFailed() string {
	base := fmt.Sprintf("✗ Falló la instalación de %s (intento %d/%d).\n\n%s\n\n",
		m.currentTool, m.installAttempts, maxInstallAttempts, m.installError)
	options := "[R] reintentar  |  [M] instalación manual  |  [O] omitir"
	if m.installAttempts >= maxInstallAttempts {
		options = "[M] instalación manual  |  [O] omitir"
	}
	return lipgloss.NewStyle().Padding(1).Render(base + options)
}

func (m *Model) viewInstallManual() string {
	url, instruction := manualInstallInfo(m.manualTool)
	body := fmt.Sprintf("Instalación manual de %s\n\n", m.manualTool) +
		"Descargalo desde: " + url + "\n" +
		"Instrucción: " + instruction + "\n"
	if m.manualDisplay != "" {
		body += "\nNota del instalador: " + m.manualDisplay + "\n"
	}
	body += "\nCuando termines (o si preferís continuar), Enter = siguiente"
	return lipgloss.NewStyle().Padding(1).Render(body)
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
	base := "StrategyQuantX (SQX) — motor de backtesting y generación de estrategias.\n" +
		"Descargalo manualmente desde https://strategyquant.com/ y descomprimilo.\n\n" +
		"Carpeta de instalación de SQX:\n" + m.sqxInput.View() + "\n\n" +
		"Enter = siguiente  |  Tab = siguiente campo"
	if m.sqxError != "" {
		base = "⚠ " + m.sqxError + "\n\n" + base
	}
	return lipgloss.NewStyle().Padding(1).Render(base)
}

func (m *Model) viewJForex() string {
	modes := []string{"demo", "live"}
	mode := modes[m.accountModeIndex]
	return lipgloss.NewStyle().Padding(1).Render(
		"JForex 4 — plataforma de trading de Dukascopy.\n" +
			"Descargala manualmente desde https://www.dukascopy.com/downloads/bank/jforex/\n" +
			"Cuenta demo: registro por email, 14 días. Cuenta live: requiere verificación.\n\n" +
			"Carpeta de instalación:\n" + m.jforexPathInput.View() + "\n\n" +
			"Usuario: " + m.jforexUserInput.View() + "\n" +
			"Contraseña: " + m.jforexPassInput.View() + "\n" +
			fmt.Sprintf("Modo: %s (Tab para cambiar)\n\n", mode) +
			"Enter = siguiente  |  Tab = siguiente campo",
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

func (m *Model) viewVerify() string {
	items := m.verifyChecklist()
	var b strings.Builder
	b.WriteString("Verificación funcional del entorno\n\n")
	missing := false
	for _, it := range items {
		b.WriteString(fmt.Sprintf("%s %s\n", it.Mark, it.Label))
		if it.Mark == markMissing {
			missing = true
		}
	}
	if missing {
		b.WriteString("\n⚠ Faltan componentes. Recomendamos completar la instalación desde el agente OpenCode:\n")
		b.WriteString("  Abrí OpenCode y pedile: \"" + delegationSample + "\"\n")
	}
	b.WriteString("\nEnter = continuar")
	return lipgloss.NewStyle().Padding(1).Render(b.String())
}

func (m *Model) viewPostInstall() string {
	agents := []string{"quantlab-orchestrator", "guardian-orchestrator"}
	selected := agents[m.primaryAgentIndex]

	var b strings.Builder
	b.WriteString("¡Listo! Ahora usá QuantLab:\n\n")
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
		mark := "☐"
		if ready {
			mark = "✓"
		}
		b.WriteString(fmt.Sprintf("%s %s: %s\n", mark, s.Title, s.Description))
	}
	b.WriteString("\nPara empezar:\n")
	b.WriteString("  1) cd \"<campañas>/\" && opencode\n")
	b.WriteString("  2) Elegí el agente " + selected + "\n")
	b.WriteString("  3) Prompt de ejemplo: \"Comienza una campaña para un portafolio de 100USD\"\n")
	b.WriteString("\nEnter = finalizar")
	return lipgloss.NewStyle().Padding(1).Render(b.String())
}

// Result returns the user's onboarding choices.
func (m *Model) Result() Result {
	return m.result
}

// Steps returns the loaded post-install guide steps.
func (m *Model) Steps() []PostInstallStep {
	return m.steps
}
