package main

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"net/http"
	"strconv"
	"strings"
	"time"
)

// publicResponseCache is the outer shared tier. Existing in-process caches
// remain the fallback when Redis is disabled, unavailable, or missing a key.
// It never stores errors, private responses, oversized bodies or stale listing
// fallbacks. Redis hits carry Age so a CDN cannot restart their freshness TTL.
func publicResponseCache(next http.Handler, cache responseCache) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		policy, eligible := publicResponsePolicy(r, time.Now())
		if !eligible {
			next.ServeHTTP(w, r)
			return
		}
		if cache != nil {
			if value, found := cache.get(r.Context(), policy.key); found && validCachedResponse(value, policy) {
				w.Header().Set("X-Public-Cache", "HIT")
				writeCachedResponse(w, r, value)
				return
			}
		}
		// A HEAD miss must still generate the full GET representation for a shared
		// key, but neither cached nor uncached HEAD sends a response body.
		request := r.Clone(r.Context())
		request.Method = http.MethodGet
		buffer := &responseBuffer{destination: w, header: make(http.Header), head: r.Method == http.MethodHead}
		next.ServeHTTP(buffer, request)
		if buffer.streaming {
			return
		}
		if !buffer.cacheable(policy) {
			if buffer.status != http.StatusOK || buffer.header.Get("Set-Cookie") != "" {
				buffer.header.Set("Cache-Control", "no-store")
			}
			buffer.flush()
			return
		}
		now := time.Now()
		value := cachedResponse{Body: buffer.body.Bytes(), Stored: now.Unix(), Lifetime: responseLifetime(policy, now)}
		w.Header().Set("X-Public-Cache", "BYPASS")
		if cache != nil {
			cache.put(r.Context(), policy.key, value)
			w.Header().Set("X-Public-Cache", "MISS")
		}
		writeCachedResponse(w, r, value)
	})
}

func validCachedResponse(value cachedResponse, policy responsePolicy) bool {
	age := time.Now().Unix() - value.Stored
	return age >= 0 && value.Lifetime > 0 && value.Lifetime <= int64(policy.ttl/time.Second) && age < value.Lifetime && json.Valid(value.Body)
}

func writeCachedResponse(w http.ResponseWriter, r *http.Request, value cachedResponse) {
	hash := sha256.Sum256(value.Body)
	etag := `"` + hex.EncodeToString(hash[:]) + `"`
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.Header().Set("Access-Control-Allow-Origin", "*")
	w.Header().Set("X-Content-Type-Options", "nosniff")
	w.Header().Set("Cache-Control", "public, max-age="+strconv.FormatInt(min(value.Lifetime, 60), 10)+", s-maxage="+strconv.FormatInt(value.Lifetime, 10))
	w.Header().Set("Age", strconv.FormatInt(max(time.Now().Unix()-value.Stored, 0), 10))
	w.Header().Set("ETag", etag)
	for _, candidate := range strings.Split(r.Header.Get("If-None-Match"), ",") {
		candidate = strings.TrimPrefix(strings.TrimSpace(candidate), "W/")
		if candidate == etag || candidate == "*" {
			w.WriteHeader(http.StatusNotModified)
			return
		}
	}
	w.WriteHeader(http.StatusOK)
	if r.Method != http.MethodHead {
		_, _ = w.Write(value.Body)
	}
}

// Buffer only small API responses. Larger responses stream through unchanged
// instead of doubling an unbounded amount of memory just to populate Redis.
type responseBuffer struct {
	destination     http.ResponseWriter
	header          http.Header
	status          int
	body            bytes.Buffer
	streaming, head bool
}

func (b *responseBuffer) Header() http.Header { return b.header }
func (b *responseBuffer) WriteHeader(status int) {
	if b.status == 0 {
		b.status = status
	}
}
func (b *responseBuffer) Write(data []byte) (int, error) {
	if b.status == 0 {
		b.status = http.StatusOK
	}
	if !b.streaming && b.body.Len()+len(data) > responseMaxBytes {
		b.header.Set("Cache-Control", "no-store")
		b.flush()
		b.streaming = true
	}
	if b.streaming {
		if b.head {
			return len(data), nil
		}
		return b.destination.Write(data)
	}
	return b.body.Write(data)
}

func (b *responseBuffer) cacheable(policy responsePolicy) bool {
	control := strings.ToLower(b.header.Get("Cache-Control"))
	return b.status == http.StatusOK && b.header.Get("Set-Cookie") == "" &&
		b.header.Get("Vary") == "" && !strings.Contains(control, "private") && !strings.Contains(control, "no-cache") &&
		strings.HasPrefix(b.header.Get("Content-Type"), "application/json") && json.Valid(b.body.Bytes()) &&
		(policy.series || !strings.Contains(control, "no-store"))
}

func (b *responseBuffer) flush() {
	for key, values := range b.header {
		b.destination.Header()[key] = values
	}
	status := b.status
	if status == 0 {
		status = http.StatusOK
	}
	b.destination.WriteHeader(status)
	if !b.head {
		_, _ = b.destination.Write(b.body.Bytes())
	}
	b.body.Reset()
}
