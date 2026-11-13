package main

import (
	"bytes"
	"encoding/json"
	"io"
	"net/http"
	"os"
	"sync"
	"time"
)

const fundraisingDetailsPath = "/api/fundraising/details"

// maxFundraisingFile bounds what is read and served; the real file is under 1 KB.
const maxFundraisingFile = 16 * 1024

// fundraisingDetails serves the raw fundraising configuration from a file, so
// the details can change without a host deploy. It validates nothing beyond
// "a JSON object": the React host applies the same rules as Flask
// (frontend/src/app/fundraising.ts), so incomplete or unconfirmed data never
// opens donations. An unset path, a missing file or invalid JSON answers 503 and
// the host falls back to the bundled copy. The file is re-read at most every
// five seconds, outside the response caches, like the campaign gate.
func fundraisingDetails(next http.Handler, path string, reminder *reminderState) http.Handler {
	var mu sync.Mutex
	var checked time.Time
	var body []byte
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != fundraisingDetailsPath {
			next.ServeHTTP(w, r)
			return
		}
		if r.Method != http.MethodGet && r.Method != http.MethodHead {
			writeError(w, http.StatusMethodNotAllowed, "method not allowed")
			return
		}
		mu.Lock()
		if time.Since(checked) >= 5*time.Second {
			body = readFundraisingFile(path)
			checked = time.Now()
		}
		current := body
		mu.Unlock()
		w.Header().Set("Cache-Control", "no-store")
		if current == nil {
			writeError(w, http.StatusServiceUnavailable, "fundraising details unavailable")
			return
		}
		current = withReminderFlag(withoutAccountBeforeOpening(current, fundraisingNow()), reminder.Enabled())
		w.Header().Set("Content-Type", "application/json; charset=utf-8")
		w.WriteHeader(http.StatusOK)
		if r.Method == http.MethodGet {
			_, _ = w.Write(current)
		}
	})
}

// fundraisingNow is the server clock; tests replace it.
var fundraisingNow = time.Now

// accountKeys are never served before the collection's first day.
var accountKeys = []string{"iban", "bic", "recipient", "reference", "payment_url", "mobilepay_links"}

// withoutAccountBeforeOpening drops the account and payment fields while the
// Helsinki date is before start_date (or planned_start_date), so the public
// endpoint does not publish them early. It switches at 00:00 Europe/Helsinki
// without a restart. Without a valid date, or if anything fails, the data is
// returned untouched: the React host also hides the account until opening.
func withoutAccountBeforeOpening(body []byte, now time.Time) []byte {
	var object map[string]any
	if json.Unmarshal(body, &object) != nil {
		return body
	}
	opens := ""
	for _, key := range []string{"start_date", "planned_start_date"} {
		if value, ok := object[key].(string); ok {
			if _, err := time.Parse("2006-01-02", value); err == nil {
				opens = value
				break
			}
		}
	}
	location, err := time.LoadLocation("Europe/Helsinki")
	if opens == "" || err != nil || now.In(location).Format("2006-01-02") >= opens {
		return body
	}
	for _, key := range accountKeys {
		delete(object, key)
	}
	redacted, err := json.Marshal(object)
	if err != nil {
		return body
	}
	return append(redacted, '\n')
}

// readFundraisingFile returns the compacted JSON object, or nil when the file
// cannot be used.
func readFundraisingFile(path string) []byte {
	if path == "" {
		return nil
	}
	file, err := os.Open(path)
	if err != nil {
		return nil
	}
	defer file.Close()
	raw, err := io.ReadAll(io.LimitReader(file, maxFundraisingFile+1))
	if err != nil || len(raw) == 0 || len(raw) > maxFundraisingFile {
		return nil
	}
	var object map[string]any
	if err := json.Unmarshal(raw, &object); err != nil || object == nil {
		return nil
	}
	var compact bytes.Buffer
	if err := json.Compact(&compact, raw); err != nil {
		return nil
	}
	compact.WriteByte('\n')
	return compact.Bytes()
}
