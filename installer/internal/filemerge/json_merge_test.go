package filemerge

import (
	"encoding/json"
	"testing"
)

func TestMergeJSONObjectsDeepMerge(t *testing.T) {
	base := []byte(`{"settings":{"theme":"default","flags":{"x":true}},"plugins":["a"]}`)
	overlay := []byte(`{"settings":{"theme":"quantlab","flags":{"y":true}},"extra":1}`)

	merged, err := MergeJSONObjects(base, overlay)
	if err != nil {
		t.Fatalf("MergeJSONObjects() error = %v", err)
	}

	var got map[string]any
	if err := json.Unmarshal(merged, &got); err != nil {
		t.Fatalf("Unmarshal merged error = %v", err)
	}

	settings := got["settings"].(map[string]any)
	flags := settings["flags"].(map[string]any)

	if settings["theme"] != "quantlab" {
		t.Fatalf("theme = %v, want quantlab", settings["theme"])
	}
	if flags["x"] != true || flags["y"] != true {
		t.Fatalf("flags = %#v, want {x:true y:true}", flags)
	}
	plugins := got["plugins"].([]any)
	if len(plugins) != 1 || plugins[0] != "a" {
		t.Fatalf("plugins = %#v, want [a]", plugins)
	}
	if got["extra"] != float64(1) {
		t.Fatalf("extra = %v, want 1", got["extra"])
	}
}

func TestMergeJSONObjectsArrayReplacement(t *testing.T) {
	base := []byte(`{"items":[1,2,3]}`)
	overlay := []byte(`{"items":[4,5]}`)

	merged, err := MergeJSONObjects(base, overlay)
	if err != nil {
		t.Fatalf("MergeJSONObjects() error = %v", err)
	}

	var got map[string]any
	if err := json.Unmarshal(merged, &got); err != nil {
		t.Fatalf("Unmarshal merged error = %v", err)
	}

	items := got["items"].([]any)
	if len(items) != 2 || items[0] != float64(4) || items[1] != float64(5) {
		t.Fatalf("items = %#v, want [4 5]", items)
	}
}

func TestMergeJSONObjectsReplaceSentinel(t *testing.T) {
	base := []byte(`{"mcp":{"engram":{"command":"engram","args":["mcp"],"type":"local"}}}`)
	overlay := []byte(`{"mcp":{"engram":{"__replace__":{"command":["engram","mcp","--tools=agent"],"type":"local"}}}}`)

	merged, err := MergeJSONObjects(base, overlay)
	if err != nil {
		t.Fatalf("MergeJSONObjects() error = %v", err)
	}

	var got map[string]any
	if err := json.Unmarshal(merged, &got); err != nil {
		t.Fatalf("Unmarshal merged error = %v", err)
	}

	mcp := got["mcp"].(map[string]any)
	eng := mcp["engram"].(map[string]any)

	if _, ok := eng["args"]; ok {
		t.Fatalf("engram still has 'args' after __replace__")
	}
	cmd, ok := eng["command"].([]any)
	if !ok {
		t.Fatalf("engram command is not an array; got %T", eng["command"])
	}
	if len(cmd) != 3 {
		t.Fatalf("engram command has %d elements, want 3", len(cmd))
	}
	if _, ok := eng["__replace__"]; ok {
		t.Fatal("__replace__ sentinel leaked into output")
	}
}

func TestMergeJSONObjectsReplaceSentinelPreservesSiblings(t *testing.T) {
	base := []byte(`{"a":{"old":1},"b":"keep"}`)
	overlay := []byte(`{"a":{"__replace__":{"new":2}}}`)

	merged, err := MergeJSONObjects(base, overlay)
	if err != nil {
		t.Fatalf("MergeJSONObjects() error = %v", err)
	}

	var got map[string]any
	if err := json.Unmarshal(merged, &got); err != nil {
		t.Fatalf("Unmarshal merged error = %v", err)
	}

	if got["b"] != "keep" {
		t.Fatalf("sibling key 'b' lost; got %v", got)
	}

	a := got["a"].(map[string]any)
	if _, ok := a["old"]; ok {
		t.Fatalf("'a.old' survived __replace__")
	}
	if a["new"] != float64(2) {
		t.Fatalf("a.new = %v, want 2", a["new"])
	}
}

func TestMergeJSONObjectsEmpty(t *testing.T) {
	tests := []struct {
		name    string
		base    []byte
		overlay []byte
	}{
		{"base empty", []byte(`{}`), []byte(`{"key":"val"}`)},
		{"overlay empty", []byte(`{"key":"val"}`), []byte(`{}`)},
		{"both empty", []byte(`{}`), []byte(`{}`)},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			merged, err := MergeJSONObjects(tt.base, tt.overlay)
			if err != nil {
				t.Fatalf("MergeJSONObjects() error = %v", err)
			}
			if !json.Valid(merged) {
				t.Fatalf("merged output is not valid JSON: %s", string(merged))
			}
		})
	}
}

func TestMergeJSONObjectsMalformedBase(t *testing.T) {
	// Real user machines may have corrupted JSON — recover with {}
	tests := []struct {
		name    string
		base    []byte
		overlay []byte
		wantKey string
	}{
		{
			name:    "plain text",
			base:    []byte(`allow: all`),
			overlay: []byte(`{"servers":{"context7":{"type":"remote"}}}`),
			wantKey: "servers",
		},
		{
			name:    "unclosed object",
			base:    []byte(`{"ok":true`),
			overlay: []byte(`{"extra":1}`),
			wantKey: "extra",
		},
		{
			name:    "single char",
			base:    []byte(`a`),
			overlay: []byte(`{"key":"val"}`),
			wantKey: "key",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			merged, err := MergeJSONObjects(tt.base, tt.overlay)
			if err != nil {
				t.Fatalf("MergeJSONObjects() error = %v", err)
			}
			var got map[string]any
			if err := json.Unmarshal(merged, &got); err != nil {
				t.Fatalf("merged not valid JSON: %v", err)
			}
			if _, ok := got[tt.wantKey]; !ok {
				t.Fatalf("merged missing key %q from overlay", tt.wantKey)
			}
		})
	}
}

func TestUnmarshalJSONObject(t *testing.T) {
	t.Run("valid json", func(t *testing.T) {
		obj, err := UnmarshalJSONObject([]byte(`{"a":1,"b":2}`))
		if err != nil {
			t.Fatalf("UnmarshalJSONObject() error = %v", err)
		}
		if obj["a"] != float64(1) || obj["b"] != float64(2) {
			t.Fatalf("got %#v", obj)
		}
	})

	t.Run("jsonc comments", func(t *testing.T) {
		raw := []byte(`{
			// comment
			"a": 1,
			/* block */
			"b": 2,
		}`)
		obj, err := UnmarshalJSONObject(raw)
		if err != nil {
			t.Fatalf("UnmarshalJSONObject() error = %v", err)
		}
		if obj["a"] != float64(1) || obj["b"] != float64(2) {
			t.Fatalf("got %#v", obj)
		}
	})

	t.Run("empty", func(t *testing.T) {
		obj, err := UnmarshalJSONObject([]byte(``))
		if err != nil {
			t.Fatalf("UnmarshalJSONObject() error = %v", err)
		}
		if len(obj) != 0 {
			t.Fatalf("expected empty map, got %#v", obj)
		}
	})
}

func TestNormalizeJSON(t *testing.T) {
	input := []byte(`{
		// line comment
		"a": 1,
		/* block comment */
		"b": 2,
	}`)
	normalized, err := NormalizeJSON(input)
	if err != nil {
		t.Fatalf("NormalizeJSON() error = %v", err)
	}

	var obj map[string]any
	if err := json.Unmarshal(normalized, &obj); err != nil {
		t.Fatalf("Unmarshal normalized error = %v", err)
	}
	if obj["a"] != float64(1) || obj["b"] != float64(2) {
		t.Fatalf("got %#v", obj)
	}
}

func TestMergeJSONObjectsIdempotent(t *testing.T) {
	base := []byte(`{"a":{"b":1,"c":2}}`)
	overlay := []byte(`{"a":{"c":3}}`)

	first, err := MergeJSONObjects(base, overlay)
	if err != nil {
		t.Fatalf("first merge error = %v", err)
	}

	second, err := MergeJSONObjects(first, overlay)
	if err != nil {
		t.Fatalf("second merge error = %v", err)
	}

	if string(first) != string(second) {
		t.Fatal("merge is not idempotent: second application changed the result")
	}
}
