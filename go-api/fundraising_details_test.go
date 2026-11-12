package main

import (
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func serveFundraising(t *testing.T, path, method, target string) *httptest.ResponseRecorder {
	t.Helper()
	handler := fundraisingDetails(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusTeapot)
	}), path)
	w := httptest.NewRecorder()
	handler.ServeHTTP(w, httptest.NewRequest(method, target, nil))
	return w
}

func TestFundraisingDetailsServesFileAndFailsSoft(t *testing.T) {
	dir := t.TempDir()
	good := filepath.Join(dir, "good.json")
	if err := os.WriteFile(good, []byte("{\n \"organizer\": \"Org\",\n \"details_confirmed\": false\n}"), 0o600); err != nil {
		t.Fatal(err)
	}
	w := serveFundraising(t, good, "GET", fundraisingDetailsPath)
	if w.Code != 200 || w.Body.String() != "{\"organizer\":\"Org\",\"details_confirmed\":false}\n" {
		t.Fatalf("good file: %d %q", w.Code, w.Body.String())
	}
	if w.Header().Get("Cache-Control") != "no-store" || !strings.HasPrefix(w.Header().Get("Content-Type"), "application/json") {
		t.Fatalf("headers: %v", w.Header())
	}
	if head := serveFundraising(t, good, "HEAD", fundraisingDetailsPath); head.Code != 200 || head.Body.Len() != 0 {
		t.Fatalf("head: %d %q", head.Code, head.Body.String())
	}
	bad := map[string]string{"array": "[1]", "null": "null", "broken": "{", "empty": "", "huge": "{\"a\":\"" + strings.Repeat("x", maxFundraisingFile) + "\"}"}
	for name, content := range bad {
		p := filepath.Join(dir, name+".json")
		_ = os.WriteFile(p, []byte(content), 0o600)
		if w := serveFundraising(t, p, "GET", fundraisingDetailsPath); w.Code != 503 {
			t.Fatalf("%s: got %d", name, w.Code)
		}
	}
	for name, p := range map[string]string{"unset": "", "missing": filepath.Join(dir, "none.json")} {
		if w := serveFundraising(t, p, "GET", fundraisingDetailsPath); w.Code != 503 {
			t.Fatalf("%s: got %d", name, w.Code)
		}
	}
}

func TestFundraisingDetailsMethodsAndOtherPaths(t *testing.T) {
	if w := serveFundraising(t, "", "POST", fundraisingDetailsPath); w.Code != http.StatusMethodNotAllowed {
		t.Fatalf("post: %d", w.Code)
	}
	if w := serveFundraising(t, "", "GET", "/api/other"); w.Code != http.StatusTeapot {
		t.Fatalf("other path: %d", w.Code)
	}
}
