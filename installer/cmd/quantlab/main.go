package main

import (
	"os"

	"github.com/ogzuz/quantlab/internal/app"
)

// version is set at build time via ldflags (e.g., -X main.version=0.1.0).
var version = "dev"

func main() {
	app.Version = version
	if err := app.RunArgs(os.Args[1:], os.Stdout); err != nil {
		os.Exit(1)
	}
}
