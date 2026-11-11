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
	if suspension, ok := doc["security_suspension"].(bson.M); ok && suspension["active"] == true {
		return false
	}
	return doc["confirmed"] == true
}

// CountCityAdmins counts distinct users with an unrevoked city grant for key
// whose account is usable. It reads only ids and status flags.
func (s mongoStore) CountCityAdmins(ctx context.Context, key string) (int, error) {
	db := s.collection.Database()
	cursor, err := db.Collection("admin_scope_grants").Find(ctx, bson.M{
		"scope_type": "city",
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
