package main

import (
	"context"
	"errors"
	"log"
	"net/http"
	"sync"
	"time"

	"go.mongodb.org/mongo-driver/v2/bson"
	"go.mongodb.org/mongo-driver/v2/mongo/options"
)

// cityAdminTarget is the organisational goal of active city admins per city.
// It is shown to visitors as "recruiting", never enforced.
const cityAdminTarget = 2

const cityAdminStatusTTL = 5 * time.Minute

// nationallyManagedCities are moderated by the national admin team instead of
// local city admins (Helsinki: very high volume and a fragmented local scene),
// so they never ask visitors to become city admins. Keep in sync with
// NATIONALLY_MANAGED_CITIES in mielenosoitukset_fi/admin/admin_city_bp.py.
var nationallyManagedCities = map[string]bool{"helsinki": true}

// cityAdminStatus reduces a count to the only thing the public page needs.
// Names, user ids and exact numbers above the target are never exposed.
func cityAdminStatus(active int) string {
	switch {
	case active <= 0:
		return "none"
	case active < cityAdminTarget:
		return "single"
	default:
		return "team"
	}
}

type cityAdminStatusCache struct {
	mu      sync.Mutex
	entries map[string]cityAdminStatusEntry
}

type cityAdminStatusEntry struct {
	status  string
	expires time.Time
}

var adminStatusCache = &cityAdminStatusCache{entries: map[string]cityAdminStatusEntry{}}

func (c *cityAdminStatusCache) get(key string, now time.Time) (string, bool) {
	c.mu.Lock()
	defer c.mu.Unlock()
	entry, ok := c.entries[key]
	if !ok || now.After(entry.expires) {
		return "", false
	}
	return entry.status, true
}

func (c *cityAdminStatusCache) put(key, status string, now time.Time) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.entries[key] = cityAdminStatusEntry{status: status, expires: now.Add(cityAdminStatusTTL)}
}

// activeAccount mirrors Flask's system_teams.active_account: only accounts
// that can actually act count as coverage.
func activeAccount(doc bson.M) bool {
	if active, ok := doc["active"]; ok && active != true {
		return false
	}
	if banned, ok := doc["banned"]; ok && banned != false {
		return false
	}
	// The driver decodes nested documents as bson.D unless told otherwise.
	switch suspension := doc["security_suspension"].(type) {
	case bson.M:
		if suspension["active"] == true {
			return false
		}
	case bson.D:
		for _, field := range suspension {
			if field.Key == "active" && field.Value == true {
				return false
			}
		}
	}
	return doc["confirmed"] == true
}

// CountCityAdmins counts distinct users who can approve demonstrations in the
// city: an unrevoked grant with ACCEPT_DEMO (the rule of Flask's
// active_city_admins_for_city) held by a usable account. It reads only ids and
// status flags.
func (s mongoStore) CountCityAdmins(ctx context.Context, key string) (int, error) {
	db := s.collection.Database()
	cursor, err := db.Collection("admin_scope_grants").Find(ctx, bson.M{
		"scope_type":  "city",
		"permissions": "ACCEPT_DEMO",
		"$and": bson.A{
			bson.M{"$or": bson.A{bson.M{"scope_keys": key}, bson.M{"scope_key": key}}},
			bson.M{"$or": bson.A{bson.M{"revoked_at": bson.M{"$exists": false}}, bson.M{"revoked_at": nil}}},
		},
	}, options.Find().SetProjection(bson.M{"user_id": 1}).SetLimit(500))
	if err != nil {
		return 0, err
	}
	var grants []bson.M
	if err := cursor.All(ctx, &grants); err != nil {
		return 0, err
	}
	ids := bson.A{}
	seen := map[string]bool{}
	for _, grant := range grants {
		switch value := grant["user_id"].(type) {
		case bson.ObjectID:
			if !seen[value.Hex()] {
				seen[value.Hex()] = true
				ids = append(ids, value)
			}
		case string:
			if id, err := bson.ObjectIDFromHex(value); err == nil && !seen[id.Hex()] {
				seen[id.Hex()] = true
				ids = append(ids, id)
			}
		}
	}
	if len(ids) == 0 {
		return 0, nil
	}
	users, err := db.Collection("users").Find(ctx, bson.M{"_id": bson.M{"$in": ids}},
		options.Find().SetProjection(bson.M{"active": 1, "banned": 1, "confirmed": 1, "security_suspension": 1}))
	if err != nil {
		return 0, err
	}
	var docs []bson.M
	if err := users.All(ctx, &docs); err != nil {
		return 0, err
	}
	active := 0
	for _, doc := range docs {
		if activeAccount(doc) {
			active++
		}
	}
	return active, nil
}

// grantKeys lists the city keys a grant covers (scope_keys and the older scope_key).
func grantKeys(grant bson.M) []string {
	keys := []string{}
	switch values := grant["scope_keys"].(type) {
	case bson.A:
		for _, value := range values {
			if key, ok := value.(string); ok {
				keys = append(keys, key)
			}
		}
	}
	if key, ok := grant["scope_key"].(string); ok {
		keys = append(keys, key)
	}
	return keys
}

// CityAdminCoverage counts active city admins for every city in one pass, for
// the application form. Callers reduce the counts to bands before sending them.
func (s mongoStore) CityAdminCoverage(ctx context.Context) (map[string]int, error) {
	db := s.collection.Database()
	cursor, err := db.Collection("admin_scope_grants").Find(ctx, bson.M{
		"scope_type":  "city",
		"permissions": "ACCEPT_DEMO",
		"$or":         bson.A{bson.M{"revoked_at": bson.M{"$exists": false}}, bson.M{"revoked_at": nil}},
	}, options.Find().SetProjection(bson.M{"user_id": 1, "scope_keys": 1, "scope_key": 1}).SetLimit(5000))
	if err != nil {
		return nil, err
	}
	var grants []bson.M
	if err := cursor.All(ctx, &grants); err != nil {
		return nil, err
	}
	cityUsers := map[string]map[bson.ObjectID]bool{}
	ids := bson.A{}
	known := map[bson.ObjectID]bool{}
	for _, grant := range grants {
		var id bson.ObjectID
		switch value := grant["user_id"].(type) {
		case bson.ObjectID:
			id = value
		case string:
			parsed, err := bson.ObjectIDFromHex(value)
			if err != nil {
				continue
			}
			id = parsed
		default:
			continue
		}
		for _, key := range grantKeys(grant) {
			if cityUsers[key] == nil {
				cityUsers[key] = map[bson.ObjectID]bool{}
			}
			cityUsers[key][id] = true
		}
		if !known[id] {
			known[id] = true
			ids = append(ids, id)
		}
	}
	counts := map[string]int{}
	if len(ids) == 0 {
		return counts, nil
	}
	users, err := db.Collection("users").Find(ctx, bson.M{"_id": bson.M{"$in": ids}},
		options.Find().SetProjection(bson.M{"active": 1, "banned": 1, "confirmed": 1, "security_suspension": 1}))
	if err != nil {
		return nil, err
	}
	var docs []bson.M
	if err := users.All(ctx, &docs); err != nil {
		return nil, err
	}
	usable := map[bson.ObjectID]bool{}
	for _, doc := range docs {
		if id, ok := doc["_id"].(bson.ObjectID); ok && activeAccount(doc) {
			usable[id] = true
		}
	}
	for key, members := range cityUsers {
		for id := range members {
			if usable[id] {
				counts[key]++
			}
		}
	}
	return counts, nil
}

// CityAdminCoverage lets the production caching wrapper pass the read through.
func (s *cachedDetailStore) CityAdminCoverage(ctx context.Context) (map[string]int, error) {
	source, ok := s.source.(interface {
		CityAdminCoverage(context.Context) (map[string]int, error)
	})
	if !ok {
		return nil, errors.New("city admin coverage unavailable")
	}
	return source.CityAdminCoverage(ctx)
}

// CountCityAdmins lets the production caching wrapper pass the read through.
func (s *cachedDetailStore) CountCityAdmins(ctx context.Context, key string) (int, error) {
	source, ok := s.source.(interface {
		CountCityAdmins(context.Context, string) (int, error)
	})
	if !ok {
		return 0, errors.New("city admin counts unavailable")
	}
	return source.CountCityAdmins(ctx, key)
}

func (a *API) getCityAdminStatus(w http.ResponseWriter, r *http.Request) {
	key := normalizeCityKey(r.PathValue("key"))
	if _, known := cityCatalog[key]; !known {
		writeError(w, 404, "unknown city")
		return
	}
	if nationallyManagedCities[key] {
		w.Header().Set("Cache-Control", "public, max-age=300")
		writeJSON(w, 200, map[string]string{"key": key, "status": "national"})
		return
	}
	now := time.Now()
	status, cached := adminStatusCache.get(key, now)
	if !cached {
		source, ok := a.store.(interface {
			CountCityAdmins(context.Context, string) (int, error)
		})
		if !ok {
			writeError(w, 503, "service unavailable")
			return
		}
		ctx, cancel := context.WithTimeout(r.Context(), 2*time.Second)
		defer cancel()
		count, err := source.CountCityAdmins(ctx, key)
		if err != nil {
			log.Print("City admin status read failed")
			writeError(w, 503, "service unavailable")
			return
		}
		status = cityAdminStatus(count)
		adminStatusCache.put(key, status, now)
	}
	w.Header().Set("Cache-Control", "public, max-age=300")
	writeJSON(w, 200, map[string]string{"key": key, "status": status})
}

var coverageCache = struct {
	mu      sync.Mutex
	bands   map[string]string
	expires time.Time
}{}

// getCityAdminCoverage serves the coverage band of every catalog city for the
// application form. Only bands are public: no names, ids or counts.
func (a *API) getCityAdminCoverage(w http.ResponseWriter, r *http.Request) {
	now := time.Now()
	coverageCache.mu.Lock()
	bands, fresh := coverageCache.bands, coverageCache.bands != nil && now.Before(coverageCache.expires)
	coverageCache.mu.Unlock()
	if !fresh {
		source, ok := a.store.(interface {
			CityAdminCoverage(context.Context) (map[string]int, error)
		})
		if !ok {
			writeError(w, 503, "service unavailable")
			return
		}
		ctx, cancel := context.WithTimeout(r.Context(), 3*time.Second)
		defer cancel()
		counts, err := source.CityAdminCoverage(ctx)
		if err != nil {
			log.Print("City admin coverage read failed")
			writeError(w, 503, "service unavailable")
			return
		}
		bands = make(map[string]string, len(cityCatalog))
		for key := range cityCatalog {
			if nationallyManagedCities[key] {
				bands[key] = "national"
			} else {
				bands[key] = cityAdminStatus(counts[key])
			}
		}
		coverageCache.mu.Lock()
		coverageCache.bands, coverageCache.expires = bands, now.Add(cityAdminStatusTTL)
		coverageCache.mu.Unlock()
	}
	w.Header().Set("Cache-Control", "public, max-age=300")
	writeJSON(w, 200, map[string]any{"cities": bands})
}
