// Package onboarding implements the `quantlab onboarding` TUI flow.
// It is a standalone Bubbletea model with 5 steps, independent from the
// install/configure wizard.
package onboarding

import (
	"encoding/json"
	"fmt"
	"strings"

	"github.com/charmbracelet/bubbles/textinput"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"

	"github.com/ogzuz/quantlab/internal/assets"
	"github.com/ogzuz/quantlab/internal/config"
	"github.com/ogzuz/quantlab/internal/tools"
)

// Step identifies the current onboarding step.
type Step int

const (
	StepIntro Step = iota
	StepConsent
	StepSQX
	StepJForex
	StepPostInstall
	stepCount
)

// Result captures the user's onboarding choices.
type Result struct {
	Consent struct {
		OpenCode  bool
		GentleAI  bool
		SDK       bool
	}
	SQX struct {
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

// Model is the Bubbletea model for the onboarding flow.
type Model struct {
	step              Step
	width             int
	height            int
	err               error
	quitting          bool
	result            Result
	steps             []PostInstallStep

	// StepIntro
	introScroll int

	// StepConsent
	consentOpenCode   bool
	consentGentleAI   bool
	consentSDK        bool
	openCodeInstalled bool
	gentleAIInstalled bool

	// StepSQX
	sqxInput  textinput.Model
	sqxError  string

	// StepJForex
	jforexPathInput   textinput.Model
	jforexUserInput   textinput.Model
	jforexPassInput   textinput.Model
	accountModeIndex  int

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

	return Model{
		step:              StepIntro,
		consentSDK:        true,
		accountModeIndex:  0, // default demo
		primaryAgentIndex: 0, // default quantlab-orchestrator
		sqxInput:          sqxInput,
		jforexPathInput:   jforexPathInput,
		jforexUserInput:   jforexUserInput,
		jforexPassInput:   jforexPassInput,
		openCodeInstalled: tools.DetectOpenCode(),
		gentleAIInstalled: tools.DetectGentleAI(),
		steps:             loadPostInstallSteps(),
	}
}

func loadPostInstallSteps() []PostInstallStep {
	b, err := assets.FS.ReadFile("onboarding/steps.json")
	if err != nil {
		return defaultPostInstallSteps()
	}
	var steps []PostInstallStep
	if err := json.Unmarshal(b, &steps); err != nil {
		return defaultPostInstallSteps()
	}
	return steps
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
	switch msg := msg.(type) {
	case tea.KeyMsg:
		switch msg.Type {
		case tea.KeyCtrlC, tea.KeyEsc:
			m.quitting = true
			return m, tea.Quit
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

func (m *Model) handleEnter() (tea.Model, tea.Cmd) {
	switch m.step {
	case StepIntro:
		m.step = StepConsent
	case StepConsent:
		m.result.Consent.OpenCode = m.consentOpenCode
		m.result.Consent.GentleAI = m.consentGentleAI
		m.result.Consent.SDK = m.consentSDK
		m.step = StepSQX
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
	case StepConsent:
		return m.viewConsent()
	case StepSQX:
		return m.viewSQX()
	case StepJForex:
		return m.viewJForex()
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
			"Herramientas: OpenCode (orquestación LLM), gentle-ai (skills/revisión), StrategyQuantX (backtesting/optimización), JForex 4 (despliegue demo/real), Dukascopy (datos/ejecución).\n\n" +
			"Presiona Enter para continuar.",
	)
}

func (m *Model) viewConsent() string {
	sdkStatus := "QuantLab SDK (ya instalado ✓)"
	if !m.consentSDK {
		sdkStatus = "QuantLab SDK (pendiente)"
	}
	ocStatus := "[ ] OpenCode — orquestación de agentes"
	if m.openCodeInstalled {
		ocStatus = "[✓] OpenCode — ya instalado"
	}
	gaStatus := "[ ] gentle-ai — skills y revisión de código"
	if m.gentleAIInstalled {
		gaStatus = "[✓] gentle-ai — ya instalado"
	}
	return lipgloss.NewStyle().Padding(1).Render(
		"Seleccioná qué herramientas querés que configure el instalador.\n\n" +
			fmt.Sprintf("%s\n%s\n[%s] %s\n\n", ocStatus, gaStatus, ternary(m.consentSDK, "x", " "), sdkStatus) +
			"Enter = siguiente",
	)
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

func (m *Model) viewPostInstall() string {
	agents := []string{"quantlab-orchestrator", "guardian-orchestrator"}
	selected := agents[m.primaryAgentIndex]

	var b strings.Builder
	b.WriteString("¡Listo! Ahora usá QuantLab:\n\n")
	for _, s := range m.steps {
		ready := false
		switch s.ID {
		case "opencode":
			ready = m.openCodeInstalled
		case "gentle-ai":
			ready = m.gentleAIInstalled
		case "primary-agent":
			ready = selected != ""
		}
		mark := "☐"
		if ready {
			mark = "✓"
		}
		b.WriteString(fmt.Sprintf("%s %s: %s\n", mark, s.Title, s.Description))
	}
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

func ternary(cond bool, a, b string) string {
	if cond {
		return a
	}
	return b
}
