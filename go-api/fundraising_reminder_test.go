package main

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestNormalizeReminderEmail(t *testing.T) {
	good := map[string]string{
		"  Test.User@Example.FI ": "test.user@example.fi",
		"a+b@example.com":         "a+b@example.com",
	}
	for input, want := range good {
		if got := normalizeReminderEmail(input); got != want {
			t.Fatalf("%q -> %q, want %q", input, got, want)
		}
	}
	for _, bad := range []string{
		"", "plain", "a@b", "a@@example.com", "Name <a@example.com>", "a@example.com, b@example.com",
		"a b@example.com", "ä@example.com", "a@.example.com", "a@example..com", "a@example.com.",
		"a@example.com\r\nBcc: x@example.com", strings.Repeat("a", 65) + "@example.com",
		strings.Repeat("a", 250) + "@example.com", "\"a\"@example.com",
	} {
		if got := normalizeReminderEmail(bad); got != "" {
			t.Fatalf("%q accepted as %q", bad, got)
		}
	}
}

func TestReminderTokenHash(t *testing.T) {
	if _, ok := reminderTokenHash("short"); ok {
		t.Fatal("short token accepted")
	}
	if _, ok := reminderTokenHash(strings.Repeat("a", 129)); ok {
		t.Fatal("long token accepted")
	}
	if _, ok := reminderTokenHash(strings.Repeat("a", 30) + "$"); ok {
		t.Fatal("odd characters accepted")
	}
	one, ok := reminderTokenHash(strings.Repeat("a", 40))
	two, _ := reminderTokenHash(strings.Repeat("a", 40))
	if !ok || len(one) != 64 || one != two {
		t.Fatalf("hash %q %q", one, two)
	}
}

func TestReminderHandlerGuardsBeforeTouchingTheDatabase(t *testing.T) {
	next := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { w.WriteHeader(299) })
	config := submissionConfig{Origin: "https://mielenosoitukset.fi", Secret: strings.Repeat("s", 32)}
	on := &reminderState{}
	on.available.Store(true)
	run := func(state *reminderState, method, path string, headers map[string]string) *httptest.ResponseRecorder {
		request := httptest.NewRequest(method, path, strings.NewReader("{}"))
		for key, value := range headers {
			request.Header.Set(key, value)
		}
		recorder := httptest.NewRecorder()
		// A nil database proves none of these paths reads it.
		fundraisingReminderHandler(next, nil, config, state).ServeHTTP(recorder, request)
		return recorder
	}
	same := map[string]string{"Origin": "https://mielenosoitukset.fi"}
	checks := []struct {
		name   string
		code   int
		result *httptest.ResponseRecorder
	}{
		{"other paths pass through", 299, run(on, "GET", "/api/cities", nil)},
		{"flag off: signup does not exist", 404, run(&reminderState{}, "POST", reminderPath, same)},
		{"flag off: confirm does not exist", 404, run(nil, "POST", reminderConfirmPath, same)},
		{"signup is POST only", 405, run(on, "GET", reminderPath, same)},
		{"unsubscribe is POST only (scanners)", 405, run(on, "GET", reminderUnsubscribePath, nil)},
		{"foreign origin", 403, run(on, "POST", reminderPath, map[string]string{"Origin": "https://evil.example"})},
		{"missing origin", 403, run(on, "POST", reminderConfirmPath, nil)},
		{"cross-site", 403, run(on, "POST", reminderPath, map[string]string{"Origin": "https://mielenosoitukset.fi", "Sec-Fetch-Site": "cross-site"})},
	}
	for _, check := range checks {
		if check.result.Code != check.code {
			t.Fatalf("%s: status %d, want %d", check.name, check.result.Code, check.code)
		}
		if check.code != 299 && check.result.Header().Get("Cache-Control") != "no-store" {
			t.Fatalf("%s: response may be cached", check.name)
		}
	}
}

func TestWithReminderFlagIsSetByTheServerOnly(t *testing.T) {
	on := string(withReminderFlag([]byte(`{"area":"x","reminder_signup":false}`), true))
	if !strings.Contains(on, `"reminder_signup":true`) {
		t.Fatalf("flag missing: %s", on)
	}
	off := string(withReminderFlag([]byte(`{"area":"x","reminder_signup":true}`), false))
	if strings.Contains(off, "reminder_signup") {
		t.Fatalf("file value leaked: %s", off)
	}
	if got := string(withReminderFlag([]byte("not json"), true)); got != "not json" {
		t.Fatalf("invalid body changed: %s", got)
	}
}
