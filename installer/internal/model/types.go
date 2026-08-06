package model

import "time"

// AgentID identifies an OpenCode agent managed by QuantLab.
type AgentID string

const (
	AgentQuantLabOrchestrator AgentID = "quantlab-orchestrator"
	AgentQuantLabRun          AgentID = "quantlab-run"
	AgentQuantLabMonitor      AgentID = "quantlab-monitor"
	AgentQuantLabCompare      AgentID = "quantlab-compare"
	AgentQuantLabStatus       AgentID = "quantlab-status"
)

// ComponentID identifies an installed QuantLab component.
type ComponentID string

const (
	ComponentSDK            ComponentID = "sdk"
	ComponentOpenCodeAgents ComponentID = "agents"
	ComponentSkills         ComponentID = "skills"
	ComponentPrompts        ComponentID = "prompts"
	ComponentConfig         ComponentID = "config"
	ComponentWizard         ComponentID = "wizard"
)

// SkillID identifies an embedded skill installed to ~/.config/opencode/skills/.
type SkillID string

const (
	SkillQuantLabAgent       SkillID = "quantlab-agent"
	SkillQuantLabOrchestrate SkillID = "quantlab-orchestrate"
	SkillQuantLabTrading     SkillID = "quantlab-trading"
)

// Component represents an installed QuantLab component in state.json.
type Component struct {
	ID     ComponentID `json:"id"`
	Status string      `json:"status"`
	Path   string      `json:"path,omitempty"`
	Count  int         `json:"count,omitempty"`
}

// InstallState is the persisted installation state stored in ~/.quantlab/state.json.
type InstallState struct {
	Version     string      `json:"version"`
	InstallID   string      `json:"install_id"`
	InstalledAt time.Time   `json:"installed_at"`
	QLVersion   string      `json:"quantlab_version"`
	Components  []Component `json:"components"`
	ConfigHash  string      `json:"config_hash"`
	Agents      []string    `json:"opencode_agents_created"`
}
