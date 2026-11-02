package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"net/http"
	"strings"
	"time"

	"go.mongodb.org/mongo-driver/v2/bson"
)

// These are shared-cache budgets, not browser lifetimes. Keep browsers short so
// a reload can pick up changes once the shared response expires.
const (
	publicListTTL         = 5 * time.Minute
	publicDetailTTL       = 15 * time.Minute
	publicOrganizationTTL = time.Hour
)

type responsePolicy struct {
	key      string
	ttl      time.Duration
	series   bool
	dayBound bool
}

// Only validated, public read routes are eligible. Normalized listing values
// make equivalent filters share a key; the Helsinki date prevents yesterday's
// upcoming list from being reused after midnight. No cookies enter the key.
func publicResponsePolicy(r *http.Request, now time.Time) (responsePolicy, bool) {
	if (r.Method != http.MethodGet && r.Method != http.MethodHead) || r.Header.Get("Authorization") != "" {
		return responsePolicy{}, false
	}
	path, raw := r.URL.Path, r.URL.RawQuery
	if path == "/api/demonstrations" {
		query, err := parseListingQuery(raw, now)
		if err != nil {
			return responsePolicy{}, false
		}
		data, _ := json.Marshal(query)
		return responsePolicy{key: path + ":" + string(data), ttl: publicListTTL, dayBound: true}, true
	}
	if len(raw) > 512 {
		return responsePolicy{}, false
	}
	lang, err := parseQuery(raw)
	if err != nil {
		return responsePolicy{}, false
	}
	if path == "/api/home" {
		if lang == "" {
			lang = "fi"
		}
		return responsePolicy{key: path + ":" + lang + ":" + localDay(now), ttl: publicListTTL, dayBound: true}, true
	}
	return resourceResponsePolicy(path, lang, now)
}

func resourceResponsePolicy(path, lang string, now time.Time) (responsePolicy, bool) {
	parts := strings.Split(path, "/")
	if len(parts) != 4 || parts[1] != "api" {
		return responsePolicy{}, false
	}
	switch parts[2] {
	case "demonstrations":
		if !validIdentifier(parts[3]) {
			return responsePolicy{}, false
		}
		// Empty language means the document's default, not necessarily Finnish.
		return responsePolicy{key: path + ":" + lang, ttl: publicDetailTTL}, true
	case "organizations", "series":
		id, err := bson.ObjectIDFromHex(parts[3])
		if err != nil || id.IsZero() {
			return responsePolicy{}, false
		}
		if parts[2] == "series" {
			return responsePolicy{key: "/api/series/" + id.Hex() + ":" + localDay(now), ttl: publicListTTL, series: true, dayBound: true}, true
		}
		return responsePolicy{key: "/api/organizations/" + id.Hex(), ttl: publicOrganizationTTL}, true
	}
	return responsePolicy{}, false
}

func responseKey(namespace, value string) string {
	hash := sha256.Sum256([]byte(value))
	return namespace + ":" + hex.EncodeToString(hash[:])
}

// A CDN uses the URL rather than our day-bearing Redis key. Cap its lifetime
// too, so an upcoming list cannot remain fresh across Helsinki midnight.
func responseLifetime(policy responsePolicy, now time.Time) int64 {
	lifetime := int64(policy.ttl / time.Second)
	if !policy.dayBound {
		return lifetime
	}
	location, err := time.LoadLocation("Europe/Helsinki")
	if err != nil {
		location = time.UTC
	}
	day := now.In(location)
	midnight := time.Date(day.Year(), day.Month(), day.Day()+1, 0, 0, 0, 0, location)
	return min(lifetime, max(midnight.Unix()-now.Unix(), 1))
}
