package main

import (
	"os"

	"github.com/ogzuz/quantlab/internal/app"
)

func main() {
	if err := app.RunArgs(os.Args[1:], os.Stdout); err != nil {
		os.Exit(1)
	}
}
