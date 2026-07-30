# QuantLab Installer — Build System
#
# Targets:
#   build     — Compile the binary with version ldflags
#   test      — Run all tests
#   lint      — Run golangci-lint
#   clean     — Remove build artifacts
#   tidy      — Tidy go modules

VERSION ?= dev
COMMIT  ?= $(shell git rev-parse --short HEAD 2>/dev/null || echo "none")
DATE    ?= $(shell date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || echo "unknown")

LDFLAGS := -ldflags="\
	-X github.com/ogzuz/quantlab/internal/app.version=$(VERSION) \
	-X github.com/ogzuz/quantlab/internal/app.commit=$(COMMIT) \
	-X github.com/ogzuz/quantlab/internal/app.date=$(DATE)"

OUTPUT_DIR := build
BINARY     := quantlab
MAIN_PKG   := ./cmd/quantlab

.PHONY: build test lint clean tidy

build:
	@mkdir -p $(OUTPUT_DIR)
	@echo "Building $(BINARY) $(VERSION) ($(COMMIT))..."
	go build $(LDFLAGS) -o $(OUTPUT_DIR)/$(BINARY) $(MAIN_PKG)
	@echo "Done: $(OUTPUT_DIR)/$(BINARY)"

test:
	@echo "Running tests..."
	go test ./... -count=1
	@echo "All tests passed."

lint:
	@echo "Running golangci-lint..."
	golangci-lint run ./...
	@echo "Lint passed."

clean:
	@echo "Cleaning..."
	rm -rf $(OUTPUT_DIR)
	@echo "Clean."

tidy:
	@echo "Tidying modules..."
	go mod tidy
	@echo "Done."
