package main

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"
	"time"

	"go.mongodb.org/mongo-driver/v2/bson"
	"go.mongodb.org/mongo-driver/v2/mongo"
	"go.mongodb.org/mongo-driver/v2/mongo/options"
)

// These tests need a disposable MongoDB: set REMINDER_TEST_MONGO to its URI.
// They create and drop a database of their own.
func reminderTestDB(t *testing.T) *mongo.Database {
	t.Helper()
	uri := os.Getenv("REMINDER_TEST_MONGO")
	if uri == "" {
		t.Skip("REMINDER_TEST_MONGO not set")
	}
	client, err := mongo.Connect(options.Client().ApplyURI(uri))
	if err != nil {
		t.Fatal(err)
	}
	db := client.Database("rt_" + hex.EncodeToString([]byte(t.Name()))[:20])
	ctx := context.Background()
	_ = db.Drop(ctx)
	if _, err := db.Collection(reminderCollection).Indexes().CreateOne(ctx, mongo.IndexModel{Keys: bson.D{{Key: "email", Value: 1}}, Options: options.Index().SetUnique(true)}); err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = db.Drop(ctx); _ = client.Disconnect(ctx) })
	return db
}

func reminderCall(t *testing.T, handler http.Handler, path, body string) *httptest.ResponseRecorder {
	t.Helper()
	request := httptest.NewRequest("POST", path, strings.NewReader(body))
	request.Header.Set("Content-Type", "application/json")
	if path != reminderUnsubscribePath {
		request.Header.Set("Origin", "https://mielenosoitukset.fi")
	}
	recorder := httptest.NewRecorder()
	handler.ServeHTTP(recorder, request)
	return recorder
}

func tokenHash(token string) string {
	sum := sha256.Sum256([]byte(token))
	return hex.EncodeToString(sum[:])
}

func TestReminderStoreSignupIsIdempotentAndCapsResends(t *testing.T) {
	db := reminderTestDB(t)
	ctx := context.Background()
	rows := db.Collection(reminderCollection)
	for i := 0; i < 3; i++ {
		if err := storeReminderSignup(ctx, db, "a@example.test", "fi", false); err != nil {
			t.Fatal(err)
		}
	}
	if n, _ := rows.CountDocuments(ctx, bson.M{}); n != 1 {
		t.Fatalf("%d rows after repeat signup", n)
	}
	var row bson.M
	_ = rows.FindOne(ctx, bson.M{"email": "a@example.test"}).Decode(&row)
	if row["confirmation_sent_at"] != nil {
		t.Fatal("a repeat before the mail was sent must not change anything")
	}
	// Flask sent the mail 20 minutes ago: a repeat asks for a new one, three times at most.
	for send := 1; send <= 4; send++ {
		_, _ = rows.UpdateOne(ctx, bson.M{"email": "a@example.test"}, bson.M{"$set": bson.M{
			"confirmation_sent_at": time.Now().Add(-20 * time.Minute), "confirmation_count": send}})
		_ = storeReminderSignup(ctx, db, "a@example.test", "fi", false)
		var after struct {
			SentAt *time.Time `bson:"confirmation_sent_at"`
		}
		_ = rows.FindOne(ctx, bson.M{"email": "a@example.test"}).Decode(&after)
		if want := send < reminderMaxSends; (after.SentAt == nil) != want {
			t.Fatalf("send %d: re-requested = %v, want %v", send, after.SentAt == nil, want)
		}
	}
	// A confirmed address is never touched.
	_, _ = rows.UpdateOne(ctx, bson.M{"email": "a@example.test"}, bson.M{"$set": bson.M{"status": "confirmed", "confirmation_sent_at": time.Now().Add(-time.Hour), "confirmation_count": 1}})
	_ = storeReminderSignup(ctx, db, "a@example.test", "fi", true)
	var confirmed struct {
		SentAt *time.Time `bson:"confirmation_sent_at"`
		Result bool       `bson:"results_consent"`
	}
	_ = rows.FindOne(ctx, bson.M{"email": "a@example.test"}).Decode(&confirmed)
	if confirmed.SentAt == nil || confirmed.Result {
		t.Fatal("confirmed row was changed by a repeat signup")
	}
}

func TestReminderConfirmAndUnsubscribeThroughTheHandler(t *testing.T) {
	db := reminderTestDB(t)
	ctx := context.Background()
	rows := db.Collection(reminderCollection)
	config := submissionConfig{Origin: "https://mielenosoitukset.fi", Secret: strings.Repeat("s", 32), Locales: map[string]bool{"fi": true}}
	on := &reminderState{}
	on.available.Store(true)
	handler := fundraisingReminderHandler(http.NotFoundHandler(), db, config, on)

	good, expired, unsub := strings.Repeat("g", 43), strings.Repeat("e", 43), strings.Repeat("u", 43)
	_, _ = rows.InsertMany(ctx, []bson.M{
		{"email": "g@example.test", "status": "pending", "confirm_hash": tokenHash(good), "confirm_expires_at": time.Now().Add(time.Hour), "unsubscribe_hashes": bson.A{tokenHash(unsub)}},
		{"email": "e@example.test", "status": "pending", "confirm_hash": tokenHash(expired), "confirm_expires_at": time.Now().Add(-time.Minute)},
	})
	if got := reminderCall(t, handler, reminderConfirmPath, `{"token":"`+good+`"}`).Code; got != 200 {
		t.Fatalf("confirm = %d", got)
	}
	if got := reminderCall(t, handler, reminderConfirmPath, `{"token":"`+good+`"}`).Code; got != 410 {
		t.Fatalf("replayed confirm = %d, want 410", got)
	}
	if got := reminderCall(t, handler, reminderConfirmPath, `{"token":"`+expired+`"}`).Code; got != 410 {
		t.Fatalf("expired confirm = %d, want 410", got)
	}
	var state struct {
		Status string `bson:"status"`
	}
	_ = rows.FindOne(ctx, bson.M{"email": "e@example.test"}).Decode(&state)
	if state.Status != "pending" {
		t.Fatal("expired token confirmed the address")
	}
	// Removal works any number of times and is never rate limited: mailbox providers share servers.
	for i := 0; i < 80; i++ {
		if got := reminderCall(t, handler, reminderUnsubscribePath, `{"token":"`+unsub+`"}`).Code; got != 200 {
			t.Fatalf("unsubscribe %d = %d", i, got)
		}
	}
	if n, _ := rows.CountDocuments(ctx, bson.M{"email": "g@example.test"}); n != 0 {
		t.Fatal("row survived unsubscribe")
	}
}
