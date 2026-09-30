package tools

import (
	"testing"
)

func TestDetectCommand(t *testing.T) {
	if DetectCommand("ls") {
		t.Log("ls detected")
	} else {
		t.Log("ls not detected")
	}
	if DetectCommand("quantlab-nonexistent-xyz") {
		t.Error("expected nonexistent command to be undetected")
	}
}

func TestDetectOpenCode(t *testing.T) {
	_ = DetectOpenCode()
}

func TestDetectGentleAI(t *testing.T) {
	_ = DetectGentleAI()
}

func TestDetectNpmWritable_Short(t *testing.T) {
	if testing.Short() {
		t.Skip("skipping npm preflight in short mode")
	}
	_ = DetectNpmWritable()
}
