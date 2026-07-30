package app

import (
	"testing"
)

func TestHasResetFlag(t *testing.T) {
	tests := []struct {
		args []string
		want bool
	}{
		{[]string{"--reset"}, true},
		{[]string{"--reset", "--verbose"}, true},
		{[]string{"--verbose", "--reset"}, true},
		{[]string{}, false},
		{[]string{"--verbose"}, false},
		{[]string{"--no-reset"}, false},
	}

	for _, tt := range tests {
		t.Run("", func(t *testing.T) {
			got := hasResetFlag(tt.args)
			if got != tt.want {
				t.Errorf("hasResetFlag(%v) = %v, want %v", tt.args, got, tt.want)
			}
		})
	}
}
