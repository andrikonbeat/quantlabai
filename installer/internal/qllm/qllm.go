// Package qllm provides a client for the QuantLab LLM / OpenCode API,
// used to verify API keys and list available models during the install wizard.
package qllm

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"strings"
	"time"
)

// Client wraps an HTTP client for the OpenCode API.
type Client struct {
	BaseURL    string
	APIKey     string
	HTTPClient *http.Client
}

// Model represents an AI model available through the API.
type Model struct {
	ID      string `json:"id"`
	Name    string `json:"name,omitempty"`
	OwnedBy string `json:"owned_by,omitempty"`
}

// NewClient creates a new API client with the given API key.
func NewClient(apiKey string) *Client {
	return &Client{
		BaseURL: DefaultBaseURL,
		APIKey:  apiKey,
		HTTPClient: &http.Client{
			Timeout: 10 * time.Second,
		},
	}
}

// DefaultBaseURL is the default OpenCode API endpoint.
const DefaultBaseURL = "https://opencode.ai/zen/v1"

// VerifyKey tests that the configured API key is valid by making a request
// to the models endpoint. Returns nil on success.
func (c *Client) VerifyKey(ctx context.Context) error {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, c.BaseURL+"/models", nil)
	if err != nil {
		return fmt.Errorf("create request: %w", err)
	}
	req.Header.Set("Authorization", "Bearer "+c.APIKey)

	resp, err := c.HTTPClient.Do(req)
	if err != nil {
		return fmt.Errorf("verify key: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusUnauthorized {
		return fmt.Errorf("invalid API key (401)")
	}
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("unexpected status verifying key: %d", resp.StatusCode)
	}

	return nil
}

// ListModels fetches the list of available models from the API.
func (c *Client) ListModels(ctx context.Context) ([]Model, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, c.BaseURL+"/models", nil)
	if err != nil {
		return nil, fmt.Errorf("create request: %w", err)
	}
	req.Header.Set("Authorization", "Bearer "+c.APIKey)

	resp, err := c.HTTPClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("list models: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("list models: unexpected status %d", resp.StatusCode)
	}

	var result struct {
		Data []struct {
			ID      string `json:"id"`
			Name    string `json:"name,omitempty"`
			OwnedBy string `json:"owned_by,omitempty"`
		} `json:"data"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("decode models response: %w", err)
	}

	models := make([]Model, len(result.Data))
	for i, m := range result.Data {
		models[i] = Model{
			ID:      m.ID,
			Name:    m.Name,
			OwnedBy: m.OwnedBy,
		}
	}

	return models, nil
}

// SetBaseURL changes the client's base URL. Useful for testing with
// local servers.
func (c *Client) SetBaseURL(url string) {
	c.BaseURL = strings.TrimRight(url, "/")
}
