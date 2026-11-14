package main

import (
	"context"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"go.mongodb.org/mongo-driver/v2/bson"
	"go.mongodb.org/mongo-driver/v2/mongo"
	"go.mongodb.org/mongo-driver/v2/mongo/options"
)

func TestCleanBannerText(t *testing.T) {
	if got, ok := cleanBannerText("  Aino \x00 \t ", 60, false); !ok || got != "Aino" {
		t.Fatalf("control characters kept: %q %v", got, ok)
	}
	if got, ok := cleanBannerText("a\r\nb\tc", 500, true); !ok || got != "a\nb c" {
		t.Fatalf("note whitespace: %q %v", got, ok)
	}
	if got, _ := cleanBannerText("A\u202eino\u200b", 60, false); got != "Aino" {
		t.Fatalf("format characters kept: %q", got)
	}
	if got, _ := cleanBannerText("a\nb", 60, false); got != "ab" {
		t.Fatalf("single-line text kept a line break: %q", got)
	}
	if _, ok := cleanBannerText(strings.Repeat("ä", 61), 60, false); ok {
		t.Fatal("over-long text accepted")
	}
	if _, ok := cleanBannerText(strings.Repeat("ä", 60), 60, false); !ok {
		t.Fatal("limit counts characters, not bytes")
	}
	if _, ok := cleanBannerText("bad\xff", 60, false); ok {
		t.Fatal("invalid UTF-8 accepted")
	}
}

func TestBannerHandlerGuardsBeforeTouchingTheDatabase(t *testing.T) {
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
		prideBannerHandler(next, nil, config, state).ServeHTTP(recorder, request)
		return recorder
	}
	same := map[string]string{"Origin": "https://mielenosoitukset.fi"}
	checks := []struct {
		name   string
		code   int
		result *httptest.ResponseRecorder
	}{
		{"other paths pass through", 299, run(on, "POST", reminderPath, nil)},
		{"flag off: signup does not exist", 404, run(&reminderState{}, "POST", bannerPath, same)},
		{"flag off: unsubscribe does not exist", 404, run(nil, "POST", bannerUnsubscribePath, nil)},
		{"signup is POST only", 405, run(on, "GET", bannerPath, same)},
		{"unsubscribe is POST only (scanners)", 405, run(on, "GET", bannerUnsubscribePath, nil)},
		{"foreign origin", 403, run(on, "POST", bannerPath, map[string]string{"Origin": "https://evil.example"})},
		{"missing origin on confirm", 403, run(on, "POST", bannerConfirmPath, nil)},
		{"cross-site", 403, run(on, "POST", bannerPath, map[string]string{"Origin": "https://mielenosoitukset.fi", "Sec-Fetch-Site": "cross-site"})},
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

func bannerTestDB(t *testing.T) *mongo.Database {
	t.Helper()
	db := reminderTestDB(t)
	if _, err := db.Collection(bannerCollection).Indexes().CreateOne(context.Background(), mongo.IndexModel{
		Keys: bson.D{{Key: "email", Value: 1}}, Options: options.Index().SetUnique(true)}); err != nil {
		t.Fatal(err)
	}
	return db
}

func bannerHandlerFor(db *mongo.Database) http.Handler {
	config := submissionConfig{Origin: "https://mielenosoitukset.fi", Secret: strings.Repeat("s", 32), Locales: map[string]bool{"fi": true}}
	on := &reminderState{}
	on.available.Store(true)
	return prideBannerHandler(http.NotFoundHandler(), db, config, on)
}

func TestBannerSignupThroughTheHandler(t *testing.T) {
	db := bannerTestDB(t)
	ctx := context.Background()
	rows := db.Collection(bannerCollection)
	handler := bannerHandlerFor(db)
	body := `{"name":" Aino ","email":"Aino@Example.TEST","city":"Oulu","pride":"Oulun Pride","unsure":false,"note":"Sopii viikonloppu","consent":true,"locale":"fi","website":""}`

	first := reminderCall(t, handler, bannerPath, body)
	if first.Code != 202 {
		t.Fatalf("signup = %d %s", first.Code, first.Body.String())
	}
	var row bson.M
	if err := rows.FindOne(ctx, bson.M{"email": "aino@example.test"}).Decode(&row); err != nil {
		t.Fatal(err)
	}
	if row["name"] != "Aino" || row["status"] != "pending" || row["consent_version"] != bannerConsentVersion {
		t.Fatalf("stored row wrong: %v", row)
	}
	for _, key := range []string{"phone", "address", "ip", "user_agent"} {
		if _, has := row[key]; has {
			t.Fatalf("unexpected field %s stored", key)
		}
	}
	// A repeat answers the same text, creates no second row and keeps the first answers.
	again := reminderCall(t, handler, bannerPath, strings.Replace(body, "Oulun Pride", "Muu Pride", 1))
	if again.Code != 202 || again.Body.String() != first.Body.String() {
		t.Fatalf("repeat answered differently: %d %s", again.Code, again.Body.String())
	}
	if n, _ := rows.CountDocuments(ctx, bson.M{}); n != 1 {
		t.Fatalf("%d rows after repeat", n)
	}
	// A confirmed address gets the very same answer and stays untouched.
	_, _ = rows.UpdateOne(ctx, bson.M{"email": "aino@example.test"}, bson.M{"$set": bson.M{"status": "confirmed"}})
	confirmed := reminderCall(t, handler, bannerPath, body)
	if confirmed.Code != 202 || confirmed.Body.String() != first.Body.String() {
		t.Fatalf("confirmed address answered differently: %d %s", confirmed.Code, confirmed.Body.String())
	}
	// "En tiedä vielä" clears the Pride text.
	reminderCall(t, handler, bannerPath, `{"name":"Bo","email":"bo@example.test","pride":"x","unsure":true,"consent":true}`)
	var bo bson.M
	_ = rows.FindOne(ctx, bson.M{"email": "bo@example.test"}).Decode(&bo)
	if bo["pride"] != "" || bo["unsure"] != true {
		t.Fatalf("unsure row: %v", bo)
	}
}

func TestBannerSignupRejectsBadInputWithoutStoring(t *testing.T) {
	db := bannerTestDB(t)
	handler := bannerHandlerFor(db)
	cases := map[string]struct {
		body string
		code int
	}{
		"no consent":      {`{"name":"A","email":"a@example.test","consent":false}`, 400},
		"no name":         {`{"name":"  ","email":"a@example.test","consent":true}`, 400},
		"bad email":       {`{"name":"A","email":"a@b","consent":true}`, 400},
		"long note":       {`{"name":"A","email":"a@example.test","consent":true,"note":"` + strings.Repeat("x", 501) + `"}`, 400},
		"unknown field":   {`{"name":"A","email":"a@example.test","consent":true,"phone":"040"}`, 400},
		"two documents":   {`{"name":"A","email":"a@example.test","consent":true}{}`, 400},
		"honeypot filled": {`{"name":"A","email":"a@example.test","consent":true,"website":"x"}`, 202},
	}
	for name, c := range cases {
		// Each case is its own visitor: the per-IP limit has its own test.
		_, _ = db.Collection("demo_submission_tokens").DeleteMany(context.Background(), bson.M{})
		if got := reminderCall(t, handler, bannerPath, c.body).Code; got != c.code {
			t.Fatalf("%s: %d, want %d", name, got, c.code)
		}
	}
	if n, _ := db.Collection(bannerCollection).CountDocuments(context.Background(), bson.M{}); n != 0 {
		t.Fatalf("%d rows stored from bad input", n)
	}
}

func TestBannerConfirmAndUnsubscribeUseTheirOwnCollection(t *testing.T) {
	db := bannerTestDB(t)
	ctx := context.Background()
	banner, reminder := db.Collection(bannerCollection), db.Collection(reminderCollection)
	handler := bannerHandlerFor(db)
	good, unsub := strings.Repeat("g", 43), strings.Repeat("u", 43)
	_, _ = banner.InsertOne(ctx, bson.M{"email": "g@example.test", "status": "pending", "confirm_hash": tokenHash(good),
		"confirm_expires_at": time.Now().Add(time.Hour), "unsubscribe_hashes": bson.A{tokenHash(unsub)}})
	// The same hashes in the other list must be untouched by banner links.
	_, _ = reminder.InsertOne(ctx, bson.M{"email": "r@example.test", "status": "pending", "confirm_hash": tokenHash(good),
		"confirm_expires_at": time.Now().Add(time.Hour), "unsubscribe_hashes": bson.A{tokenHash(unsub)}})
	if got := reminderCall(t, handler, bannerConfirmPath, `{"token":"`+good+`"}`).Code; got != 200 {
		t.Fatalf("confirm = %d", got)
	}
	if got := reminderCall(t, handler, bannerConfirmPath, `{"token":"`+good+`"}`).Code; got != 410 {
		t.Fatalf("replayed confirm = %d, want 410", got)
	}
	if got := reminderCall(t, handler, bannerUnsubscribePath, `{"token":"`+unsub+`"}`).Code; got != 200 {
		t.Fatalf("unsubscribe = %d", got)
	}
	if got := reminderCall(t, handler, bannerUnsubscribePath, `{"token":"`+unsub+`"}`).Code; got != 200 {
		t.Fatalf("second unsubscribe = %d, want the same answer", got)
	}
	if n, _ := banner.CountDocuments(ctx, bson.M{}); n != 0 {
		t.Fatal("banner row survived unsubscribe")
	}
	var other struct {
		Status string `bson:"status"`
	}
	if err := reminder.FindOne(ctx, bson.M{"email": "r@example.test"}).Decode(&other); err != nil || other.Status != "pending" {
		t.Fatal("a banner link touched the fundraising reminder list")
	}
}

func TestBannerSignupIsRateLimitedPerVisitor(t *testing.T) {
	db := bannerTestDB(t)
	handler := bannerHandlerFor(db)
	limited := false
	for i := 0; i < 8; i++ {
		body := `{"name":"A","email":"a` + strings.Repeat("x", i) + `@example.test","consent":true}`
		if reminderCall(t, handler, bannerPath, body).Code == 429 {
			limited = true
		}
	}
	if !limited {
		t.Fatal("eight signups in a minute from one visitor were not limited")
	}
}
