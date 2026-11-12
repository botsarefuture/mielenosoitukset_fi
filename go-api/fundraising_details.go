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
func fundraisingDetails(next http.Handler, path string) http.Handler {
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
		w.Header().Set("Content-Type", "application/json; charset=utf-8")
		w.WriteHeader(http.StatusOK)
		if r.Method == http.MethodGet {
			_, _ = w.Write(current)
		}
	})
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
