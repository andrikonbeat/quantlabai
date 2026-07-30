package qllm

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestNewClient(t *testing.T) {
	c := NewClient("sk-test-key")
	if c.BaseURL != DefaultBaseURL {
		t.Fatalf("BaseURL = %q, want %q", c.BaseURL, DefaultBaseURL)
	}
	if c.APIKey != "sk-test-key" {
		t.Fatalf("APIKey = %q", c.APIKey)
	}
}

func TestDefaultBaseURL(t *testing.T) {
	if DefaultBaseURL != "https://opencode.ai/zen/v1" {
		t.Fatalf("DefaultBaseURL = %q", DefaultBaseURL)
	}
}

func TestVerifyKey_Success(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Header.Get("Authorization") != "Bearer sk-test" {
			w.WriteHeader(http.StatusUnauthorized)
			return
		}
		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(map[string]any{"data": []string{}})
	}))
	defer srv.Close()

	c := NewClient("sk-test")
	c.SetBaseURL(srv.URL)

	err := c.VerifyKey(context.Background())
	if err != nil {
		t.Fatalf("VerifyKey() error = %v", err)
	}
}

func TestVerifyKey_Invalid(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusUnauthorized)
		json.NewEncoder(w).Encode(map[string]string{"error": "invalid key"})
	}))
	defer srv.Close()

	c := NewClient("bad-key")
	c.SetBaseURL(srv.URL)

	err := c.VerifyKey(context.Background())
	if err == nil {
		t.Fatal("VerifyKey() expected error for invalid key")
	}
}

func TestVerifyKey_ServerError(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
	}))
	defer srv.Close()

	c := NewClient("sk-test")
	c.SetBaseURL(srv.URL)

	err := c.VerifyKey(context.Background())
	if err == nil {
		t.Fatal("VerifyKey() expected error for server error")
	}
}

func TestListModels(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		resp := map[string]any{
			"data": []map[string]string{
				{"id": "model-1", "name": "Model One", "owned_by": "test"},
				{"id": "model-2", "name": "Model Two", "owned_by": "test"},
			},
		}
		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(resp)
	}))
	defer srv.Close()

	c := NewClient("sk-test")
	c.SetBaseURL(srv.URL)

	models, err := c.ListModels(context.Background())
	if err != nil {
		t.Fatalf("ListModels() error = %v", err)
	}
	if len(models) != 2 {
		t.Fatalf("got %d models, want 2", len(models))
	}
	if models[0].ID != "model-1" {
		t.Fatalf("models[0].ID = %q", models[0].ID)
	}
}

func TestListModels_ServerError(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusForbidden)
	}))
	defer srv.Close()

	c := NewClient("sk-test")
	c.SetBaseURL(srv.URL)

	_, err := c.ListModels(context.Background())
	if err == nil {
		t.Fatal("ListModels() expected error")
	}
}

func TestSetBaseURL(t *testing.T) {
	c := NewClient("sk-test")
	c.SetBaseURL("https://example.com/api/")
	if c.BaseURL != "https://example.com/api" { // trailing slash stripped
		t.Fatalf("BaseURL after SetBaseURL = %q", c.BaseURL)
	}
}
