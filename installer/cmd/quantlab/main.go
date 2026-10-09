package main

import (
	"os"

	"github.com/andrikonbeat/quantlabai/internal/app"
)

func main() {
	if err := app.RunArgs(os.Args[1:], os.Stdout); err != nil {
		os.Exit(1)
	}
}
