package router

import "testing"

func TestNextScreen_LinearFlow(t *testing.T) {
	want := []struct {
		from Screen
		to   Screen
	}{
		{ScreenWelcome, ScreenAPIKey},
		{ScreenAPIKey, ScreenModel},
		{ScreenModel, ScreenSDKPath},
		{ScreenSDKPath, ScreenGentleAI},
		{ScreenGentleAI, ScreenSQX},
		{ScreenSQX, ScreenVerify},
		{ScreenVerify, ScreenSummary},
		{ScreenSummary, ScreenReview},
		{ScreenReview, ScreenConfirm},
	}

	for _, tc := range want {
		got, ok := NextScreen(tc.from)
		if !ok || got != tc.to {
			t.Errorf("NextScreen(%d) = (%d, %v), want (%d, true)", tc.from, got, ok, tc.to)
		}
	}

	if _, ok := NextScreen(ScreenConfirm); ok {
		t.Error("NextScreen(ScreenConfirm) should end the flow")
	}
	if _, ok := NextScreen(ScreenUnknown); ok {
		t.Error("NextScreen(ScreenUnknown) should end the flow")
	}
}

func TestPreviousScreen_BackNav(t *testing.T) {
	// Welcome has no backward neighbour: Esc quits there.
	if _, ok := PreviousScreen(ScreenWelcome); ok {
		t.Error("PreviousScreen(ScreenWelcome) should report no neighbour (quit)")
	}

	// Every other screen walks back to Welcome.
	screen := ScreenConfirm
	for i := 0; i < 20; i++ {
		prev, ok := PreviousScreen(screen)
		if !ok {
			t.Fatalf("PreviousScreen(%d) unexpectedly ended the chain", screen)
		}
		screen = prev
		if screen == ScreenWelcome {
			return
		}
	}
	t.Error("walking back from ScreenConfirm never reached ScreenWelcome")
}

func TestPreviousScreen_OneStep(t *testing.T) {
	cases := map[Screen]Screen{
		ScreenConfirm: ScreenReview,
		ScreenReview:  ScreenSummary,
		ScreenVerify:  ScreenSQX,
		ScreenAPIKey:  ScreenWelcome,
	}
	for from, want := range cases {
		got, ok := PreviousScreen(from)
		if !ok || got != want {
			t.Errorf("PreviousScreen(%d) = (%d, %v), want (%d, true)", from, got, ok, want)
		}
	}
}
