package model_test

import (
	"testing"

	"github.com/ogzuz/quantlab/internal/model"
)

func TestAgentIDConstants(t *testing.T) {
	tests := []struct {
		name string
		id   model.AgentID
		want string
	}{
		{"QuantLabOrchestrator", model.AgentQuantLabOrchestrator, "quantlab-orchestrator"},
		{"QuantLabRun", model.AgentQuantLabRun, "quantlab-run"},
		{"QuantLabMonitor", model.AgentQuantLabMonitor, "quantlab-monitor"},
		{"QuantLabCompare", model.AgentQuantLabCompare, "quantlab-compare"},
		{"QuantLabStatus", model.AgentQuantLabStatus, "quantlab-status"},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := string(tt.id); got != tt.want {
				t.Errorf("AgentID = %q, want %q", got, tt.want)
			}
		})
	}
}

func TestComponentIDConstants(t *testing.T) {
	tests := []struct {
		name string
		id   model.ComponentID
		want string
	}{
		{"SDK", model.ComponentSDK, "sdk"},
		{"OpenCodeAgents", model.ComponentOpenCodeAgents, "agents"},
		{"Skills", model.ComponentSkills, "skills"},
		{"Prompts", model.ComponentPrompts, "prompts"},
		{"Config", model.ComponentConfig, "config"},
		{"Wizard", model.ComponentWizard, "wizard"},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := string(tt.id); got != tt.want {
				t.Errorf("ComponentID = %q, want %q", got, tt.want)
			}
		})
	}
}

func TestSkillIDConstants(t *testing.T) {
	tests := []struct {
		name string
		id   model.SkillID
		want string
	}{
		{"QuantLabAgent", model.SkillQuantLabAgent, "quantlab-agent"},
		{"QuantLabOrchestrate", model.SkillQuantLabOrchestrate, "quantlab-orchestrate"},
		{"QuantLabTrading", model.SkillQuantLabTrading, "quantlab-trading"},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := string(tt.id); got != tt.want {
				t.Errorf("SkillID = %q, want %q", got, tt.want)
			}
		})
	}
}

func TestInstallStateStruct(t *testing.T) {
	s := model.InstallState{
		Version:   "1",
		InstallID: "test-uuid",
		QLVersion: "0.1.0",
		Components: []model.Component{
			{ID: model.ComponentSDK, Status: "installed"},
		},
		Agents: []string{"quantlab-orchestrator"},
	}

	if s.Version != "1" {
		t.Errorf("InstallState.Version = %q, want %q", s.Version, "1")
	}
	if s.InstallID != "test-uuid" {
		t.Errorf("InstallState.InstallID = %q, want %q", s.InstallID, "test-uuid")
	}
	if s.QLVersion != "0.1.0" {
		t.Errorf("InstallState.QLVersion = %q, want %q", s.QLVersion, "0.1.0")
	}
	if len(s.Components) != 1 {
		t.Fatalf("len(Components) = %d, want 1", len(s.Components))
	}
	if s.Components[0].Status != "installed" {
		t.Errorf("Component.Status = %q, want %q", s.Components[0].Status, "installed")
	}
	if len(s.Agents) != 1 || s.Agents[0] != "quantlab-orchestrator" {
		t.Errorf("Agents = %v, want [quantlab-orchestrator]", s.Agents)
	}
}

func TestComponentStruct(t *testing.T) {
	c := model.Component{
		ID:     model.ComponentSkills,
		Status: "pending",
		Path:   "~/.config/opencode/skills",
		Count:  3,
	}

	if c.ID != model.ComponentSkills {
		t.Errorf("Component.ID = %q, want %q", c.ID, model.ComponentSkills)
	}
	if c.Status != "pending" {
		t.Errorf("Component.Status = %q, want %q", c.Status, "pending")
	}
	if c.Path != "~/.config/opencode/skills" {
		t.Errorf("Component.Path = %q, want %q", c.Path, "~/.config/opencode/skills")
	}
	if c.Count != 3 {
		t.Errorf("Component.Count = %d, want 3", c.Count)
	}
}
