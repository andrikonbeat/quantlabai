// Package router maps the QuantLab installer wizard screens into a
// navigable flow: every screen knows its forward and backward neighbour,
// so Esc always means "back" (and only quits on the welcome screen).
//
// The forward/backward map pattern is adapted from the gentle-ai reference
// TUI (https://github.com/Gentleman-Programming/gentle-ai, MIT © 2025
// Gentleman Programming); the screen set is QuantLab's own.
package router

// Screen identifies one installer wizard screen.
type Screen int

const (
	ScreenUnknown Screen = iota
	ScreenWelcome
	ScreenAPIKey
	ScreenModel
	ScreenSDKPath
	ScreenGentleAI
	ScreenSQX
	ScreenVerify
	ScreenSummary
	ScreenReview
	ScreenConfirm
)

// Route holds the forward and backward neighbour of a screen.
// ScreenUnknown means "no neighbour": forward-unknown ends the flow,
// backward-unknown quits it.
type Route struct {
	Forward  Screen
	Backward Screen
}

// linearRoutes is the single installer path: welcome → config → verify →
// review → confirm. The live install + complete screens belong to the
// installing program, not the wizard.
var linearRoutes = map[Screen]Route{
	ScreenWelcome:  {Forward: ScreenAPIKey},
	ScreenAPIKey:   {Forward: ScreenModel, Backward: ScreenWelcome},
	ScreenModel:    {Forward: ScreenSDKPath, Backward: ScreenAPIKey},
	ScreenSDKPath:  {Forward: ScreenGentleAI, Backward: ScreenModel},
	ScreenGentleAI: {Forward: ScreenSQX, Backward: ScreenSDKPath},
	ScreenSQX:      {Forward: ScreenVerify, Backward: ScreenGentleAI},
	ScreenVerify:   {Forward: ScreenSummary, Backward: ScreenSQX},
	ScreenSummary:  {Forward: ScreenReview, Backward: ScreenVerify},
	ScreenReview:   {Forward: ScreenConfirm, Backward: ScreenSummary},
	ScreenConfirm:  {Backward: ScreenReview},
}

// NextScreen returns the forward neighbour of screen, or false when the
// flow ends there.
func NextScreen(screen Screen) (Screen, bool) {
	route, ok := linearRoutes[screen]
	if !ok || route.Forward == ScreenUnknown {
		return ScreenUnknown, false
	}

	return route.Forward, true
}

// PreviousScreen returns the backward neighbour of screen, or false when
// there is none (welcome screen: Esc quits).
func PreviousScreen(screen Screen) (Screen, bool) {
	route, ok := linearRoutes[screen]
	if !ok || route.Backward == ScreenUnknown {
		return ScreenUnknown, false
	}

	return route.Backward, true
}
