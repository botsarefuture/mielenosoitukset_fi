package main

import (
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
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

func TestFundraisingAccountHiddenUntilHelsinkiOpening(t *testing.T) {
	file := filepath.Join(t.TempDir(), "f.json")
	content := `{"start_date":"2026-11-16","organizer":"Org","iban":"FI00","bic":"B","recipient":"R","reference":"1","payment_url":"https://x.test","mobilepay_links":[{"url":"https://m.test"}]}`
	if err := os.WriteFile(file, []byte(content), 0o600); err != nil {
		t.Fatal(err)
	}
	defer func(old func() time.Time) { fundraisingNow = old }(fundraisingNow)
	helsinki, _ := time.LoadLocation("Europe/Helsinki")
	cases := []struct {
		at   time.Time
		open bool
	}{
		{time.Date(2026, 11, 15, 23, 59, 59, 0, helsinki), false},
		{time.Date(2026, 11, 16, 0, 0, 0, 0, helsinki), true},
		{time.Date(2026, 11, 15, 22, 0, 0, 0, time.UTC), true}, // 00:00 in Helsinki (UTC+2)
		{time.Date(2026, 11, 15, 21, 59, 59, 0, time.UTC), false},
	}
	for _, c := range cases {
		fundraisingNow = func() time.Time { return c.at }
		body := serveFundraising(t, file, "GET", fundraisingDetailsPath).Body.String()
		if got := strings.Contains(body, "FI00"); got != c.open {
			t.Fatalf("%v: account present=%v want %v: %s", c.at, got, c.open, body)
		}
		if !strings.Contains(body, `"organizer":"Org"`) {
			t.Fatalf("%v: other fields must stay: %s", c.at, body)
		}
		if !c.open && (strings.Contains(body, "bic") || strings.Contains(body, "m.test") || strings.Contains(body, "x.test")) {
			t.Fatalf("%v: payment fields leaked: %s", c.at, body)
		}
	}
}
