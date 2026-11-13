package main

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"strings"
	"testing"
	"time"

	"go.mongodb.org/mongo-driver/v2/bson"
	"go.mongodb.org/mongo-driver/v2/mongo"
	"go.mongodb.org/mongo-driver/v2/mongo/options"
)

type fakeDeveloperStore struct {
	enabled bool
	err     error
	owner   bson.ObjectID
	apps    []developerApp
	asked   []bson.ObjectID
}

func (f *fakeDeveloperStore) AccessEnabled(_ context.Context, user bson.ObjectID) (bool, error) {
	f.asked = append(f.asked, user)
	return f.enabled, f.err
}
func (f *fakeDeveloperStore) Apps(context.Context, bson.ObjectID) ([]developerApp, error) {
	return f.apps, f.err
}
func (f *fakeDeveloperStore) App(_ context.Context, owner, id bson.ObjectID) (*developerApp, error) {
	for _, a := range f.apps {
		if a.ID == id.Hex() && owner == f.owner {
			return &a, nil
		}
	}
	return nil, nil
}
func (f *fakeDeveloperStore) Tokens(context.Context, bson.ObjectID, bson.ObjectID) ([]developerToken, error) {
	return []developerToken{{ID: testOrg, Type: "short", Scopes: []string{"read"}}}, f.err
}

func developerRig(t *testing.T, store *fakeDeveloperStore) http.Handler {
	config, _ := fakeFlask(t, flaskAnswer)
	resolver, _ := newSessionResolver(config)
	return developerHandler(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { w.WriteHeader(299) }), store, resolver)
}

func TestDeveloperRoutesRequireSignIn(t *testing.T) {
	h := developerRig(t, &fakeDeveloperStore{enabled: true})
	for _, cookie := range []string{"", "session=guest"} {
		if w := get(h, developerOverviewPath, cookie); w.Code != 401 {
			t.Errorf("cookie %q: got %d", cookie, w.Code)
		}
	}
	if w := get(h, developerOverviewPath, "session=error"); w.Code != 503 {
		t.Fatalf("session failure must fail closed, got %d", w.Code)
	}
	if w := get(h, "/other", ""); w.Code != 299 {
		t.Fatal("other paths pass through")
	}
}

func TestDeveloperLockedAccountGetsNoData(t *testing.T) {
	h := developerRig(t, &fakeDeveloperStore{enabled: false, apps: []developerApp{{ID: testOrg, Name: "secret app"}}})
	w := get(h, developerOverviewPath, "session=member")
	if w.Code != 200 || strings.TrimSpace(w.Body.String()) != `{"access":false}` {
		t.Fatal(w.Code, w.Body.String())
	}
}

func TestDeveloperOverviewUsesTheBridgeActorAndNoSecrets(t *testing.T) {
	store := &fakeDeveloperStore{enabled: true, apps: []developerApp{{ID: testOrg, Name: "Sovellus", ClientID: "cid", AllowedScopes: []string{"read"}}}}
	h := developerRig(t, store)
	w := get(h, developerOverviewPath, "session=member")
	body := w.Body.String()
	if w.Code != 200 || !strings.Contains(body, `"Sovellus"`) || !strings.Contains(body, `"client_id":"cid"`) {
		t.Fatal(w.Code, body)
	}
	for _, leak := range []string{"secret", "token_hash", `"token"`} {
		if strings.Contains(body, leak) {
			t.Fatalf("leaks %q: %s", leak, body)
		}
	}
	if len(store.asked) != 1 || store.asked[0].Hex() != testActor {
		t.Fatalf("must read the signed-in account only, asked %v", store.asked)
	}
	if w.Header().Get("Cache-Control") != "no-store" || !strings.Contains(w.Header().Get("Vary"), "Cookie") {
		t.Fatal("must be uncacheable and vary by cookie")
	}
}

func TestDeveloperAppIsOwnerOnlyAndStrictlyParsed(t *testing.T) {
	owner, _ := bson.ObjectIDFromHex(testActor)
	store := &fakeDeveloperStore{enabled: true, owner: owner, apps: []developerApp{{ID: testOrg, Name: "Oma"}}}
	h := developerRig(t, store)
	if w := get(h, developerAppPrefix+testOrg, "session=member"); w.Code != 200 || !strings.Contains(w.Body.String(), `"Oma"`) {
		t.Fatal(w.Code, w.Body.String())
	}
	for _, id := range []string{"bad", strings.ToUpper(testOrg), "0123456789abcdef01234568"} {
		if w := get(h, developerAppPrefix+id, "session=member"); w.Code != 404 {
			t.Errorf("%s: got %d", id, w.Code)
		}
	}
	store.owner = bson.NewObjectID() // someone else's app
	if w := get(h, developerAppPrefix+testOrg, "session=member"); w.Code != 404 {
		t.Fatalf("another account's app must be 404, got %d", w.Code)
	}
}

func TestDeveloperMethodAndCrossSite(t *testing.T) {
	h := developerRig(t, &fakeDeveloperStore{enabled: true})
	if w := get(h, developerOverviewPath, "session=member", "Sec-Fetch-Site", "cross-site"); w.Code != 403 {
		t.Fatal(w.Code)
	}
}

func TestDeveloperStoreErrorIs503(t *testing.T) {
	h := developerRig(t, &fakeDeveloperStore{err: errors.New("db down")})
	if w := get(h, developerOverviewPath, "session=member"); w.Code != 503 {
		t.Fatal(w.Code)
	}
}

// Runs only when a local MongoDB answers; checks projections and decoding.
func TestMongoDeveloperStoreNeverReturnsSecrets(t *testing.T) {
	client, err := mongo.Connect(options.Client().ApplyURI("mongodb://127.0.0.1:27017").SetServerSelectionTimeout(3 * time.Second))
	if err != nil {
		t.Skip("no local MongoDB")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	if client.Ping(ctx, nil) != nil {
		t.Skip("no local MongoDB")
	}
	db := client.Database("moso_developer_test_" + bson.NewObjectID().Hex())
	defer db.Drop(context.Background())
	owner, other := bson.NewObjectID(), bson.NewObjectID()
	appID := bson.NewObjectID()
	now := bson.NewDateTimeFromTime(time.Now())
	db.Collection("users").InsertOne(ctx, bson.M{"_id": owner, "api_tokens_enabled": true})
	db.Collection("developer_apps").InsertMany(ctx, []any{
		bson.M{"_id": appID, "owner_id": owner, "name": "A", "client_id": "cid", "client_secret": "TOPSECRET", "allowed_scopes": bson.A{"read"}, "created_at": now},
		bson.M{"owner_id": other, "name": "Muiden", "client_secret": "X"}})
	db.Collection("api_tokens").InsertMany(ctx, []any{
		bson.M{"user_id": owner, "category": "user", "token": "HASH1", "type": "short", "scopes": bson.A{"read"}, "expires_at": now, "created_at": now},
		bson.M{"user_id": owner, "app_id": appID, "category": "app", "token": "HASH2", "type": "long", "scopes": bson.A{"read"}, "created_at": now}})
	store := mongoDeveloperStore{db}
	if ok, _ := store.AccessEnabled(ctx, owner); !ok {
		t.Fatal("access flag")
	}
	if ok, _ := store.AccessEnabled(ctx, other); ok {
		t.Fatal("unknown account must be locked")
	}
	apps, _ := store.Apps(ctx, owner)
	personal, _ := store.Tokens(ctx, owner, bson.NilObjectID)
	forApp, _ := store.Tokens(ctx, owner, appID)
	if len(apps) != 1 || apps[0].ClientID != "cid" || len(personal) != 1 || personal[0].Type != "short" || len(forApp) != 1 || forApp[0].Type != "long" {
		t.Fatalf("%+v %+v %+v", apps, personal, forApp)
	}
	if app, _ := store.App(ctx, other, appID); app != nil {
		t.Fatal("another owner must not read the app")
	}
	raw, _ := json.Marshal([]any{apps, personal, forApp})
	for _, leak := range []string{"TOPSECRET", "HASH1", "HASH2", "Muiden"} {
		if strings.Contains(string(raw), leak) {
			t.Fatalf("leak %s", leak)
		}
	}
}
