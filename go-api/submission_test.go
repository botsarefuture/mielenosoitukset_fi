package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"mime/multipart"
	"net"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"

	"go.mongodb.org/mongo-driver/v2/bson"
	"go.mongodb.org/mongo-driver/v2/mongo"
	"go.mongodb.org/mongo-driver/v2/mongo/options"
)

func submissionRequest(token, title string, overrides ...map[string]string) *http.Request {
	var body bytes.Buffer
	form := multipart.NewWriter(&body)
	fields := map[string]string{"submission_token": token, "title": title, "tags": "test", "date": "2099-01-01", "start_time": "12:00", "city": "Helsinki", "address": "Kauppatori", "type": "paikallaan", "submitter_name": "Example", "submitter_email": "example@example.test", "submitter_role": "organizer", "accept_terms": "1", "description": `<p>Hello <strong>world</strong><script>alert(1)</script><a href="javascript:alert(1)">link</a></p>`, "approved": "true"}
	for _, values := range overrides {
		for key, value := range values {
			fields[key] = value
		}
	}
	for key, value := range fields {
		_ = form.WriteField(key, value)
	}
	form.Close()
	r := httptest.NewRequest("POST", "https://mielenosoitukset.fi/api/submissions", &body)
	r.Header.Set("Content-Type", form.FormDataContentType())
	r.Header.Set("Origin", "https://mielenosoitukset.fi")
	r.Header.Set("X-Requested-With", "XMLHttpRequest")
	return r
}

func TestSubmissionValidationAndSanitizing(t *testing.T) {
	for _, locale := range []string{"en", "sv"} {
		input, err := readSubmission(httptest.NewRecorder(), submissionRequest("0123456789abcdef0123456789abcdef", "Title", map[string]string{"default_language": locale}), map[string]bool{"fi": true, "en": true, "sv": true})
		if err != nil || input.Event["default_language"] != locale {
			t.Fatal("configured content language rejected", locale, err)
		}
	}
	r := submissionRequest("0123456789abcdef0123456789abcdef", "Title")
	input, err := readSubmission(httptest.NewRecorder(), r, map[string]bool{"fi": true})
	if err != nil {
		t.Fatal(err)
	}
	if input.Event["approved"] != false || strings.Contains(submissionString(input.Event["description"]), "script") || strings.Contains(submissionString(input.Event["description"]), "alert") {
		t.Fatal(input.Event)
	}
	if !strings.Contains(submissionString(input.Event["description"]), "<strong>world</strong>") {
		t.Fatal("formatting lost")
	}
	for _, value := range []string{"2026-02-30", "2026-1-1", "<script>"} {
		r = submissionRequest("0123456789abcdef0123456789abcdef", "Title")
		r.ParseMultipartForm(1 << 20)
		r.MultipartForm.Value["date"] = []string{value}
		r.Form.Set("date", value)
		if _, err := readSubmission(httptest.NewRecorder(), r, map[string]bool{"fi": true}); err == nil {
			t.Fatal("invalid date accepted", value)
		}
	}
	if similarSubmission(bson.M{"title": "Other", "address": "Elsewhere"}, "Something", "Location") {
		t.Fatal("false duplicate")
	}
	if !similarSubmission(bson.M{"title": "Tasa-arvo ja oikeudet kaikille"}, "Oikeudet kaikille nyt", "") {
		t.Fatal("word duplicate missed")
	}
}

func TestMongoSubmissionTokenOutlivesFingerprintWindow(t *testing.T) {
	uri := os.Getenv("TEST_MONGODB_URI")
	if uri == "" {
		t.Skip("set TEST_MONGODB_URI for submission integration")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancel()
	client, err := mongo.Connect(options.Client().ApplyURI(uri))
	if err != nil {
		t.Fatal(err)
	}
	defer client.Disconnect(context.Background())
	db := client.Database("moso_go_submission_lifetime_" + bson.NewObjectID().Hex())
	defer db.Drop(context.Background())
	_, err = db.Collection("demo_submission_tokens").Indexes().CreateOne(ctx, mongo.IndexModel{Keys: bson.D{{Key: "token", Value: 1}}, Options: options.Index().SetUnique(true)})
	if err != nil {
		t.Fatal(err)
	}
	handler := publicSubmissionHandler(http.NotFoundHandler(), db, submissionConfig{Origin: "https://mielenosoitukset.fi", Secret: strings.Repeat("s", 32), Locales: map[string]bool{"fi": true}})
	submit := func(token, title string) (int, string) {
		w := httptest.NewRecorder()
		handler.ServeHTTP(w, submissionRequest(token, title))
		var response struct {
			ID string `json:"demo_id"`
		}
		if err := json.Unmarshal(w.Body.Bytes(), &response); err != nil {
			t.Fatal(err)
		}
		return w.Code, response.ID
	}
	status, original := submit("original-form-token-0123456789", "Lifetime event")
	if status != 200 || original == "" {
		t.Fatal(status, original)
	}
	_, err = db.Collection("demo_submission_tokens").UpdateMany(ctx, bson.M{"status": "completed"}, bson.M{"$set": bson.M{"created_at": time.Now().Add(-13 * time.Hour)}})
	if err != nil {
		t.Fatal(err)
	}
	status, retried := submit("original-form-token-0123456789", "Lifetime event")
	if status != 200 || retried != original {
		t.Fatal("same form created a different event after 12h", status, original, retried)
	}
	status, fresh := submit("fresh-form-token-0123456789", "Lifetime event")
	if status != 200 || fresh == original || fresh == "" {
		t.Fatal("fresh form did not retain the 12h fingerprint policy", status, fresh)
	}
	status, _ = submit("original-form-token-0123456789", "Changed content")
	if status != 409 {
		t.Fatal("completed token changed content", status)
	}
	for _, collection := range []string{"demonstrations", "submitters", "demo_notifications_queue"} {
		count, err := db.Collection(collection).CountDocuments(ctx, bson.M{})
		if err != nil || count != 2 {
			t.Fatal(collection, count, err)
		}
	}
}

func TestSubmissionSessionUsesExistingFlaskAuthority(t *testing.T) {
	directory, err := os.MkdirTemp("/tmp", "moso-session-")
	if err != nil {
		t.Fatal(err)
	}
	defer os.RemoveAll(directory)
	listener, err := net.Listen("unix", filepath.Join(directory, "session.sock"))
	if err != nil {
		t.Fatal(err)
	}
	id := bson.NewObjectID()
	server := &http.Server{Handler: http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/api/session" || r.Header.Get("X-Forwarded-Proto") != "https" {
			t.Error("incorrect bridge request")
		}
		if r.Header.Get("Cookie") == "session=valid" {
			fmt.Fprintf(w, `{"authenticated":true,"actor_id":%q}`, id.Hex())
		} else {
			fmt.Fprint(w, `{"authenticated":false}`)
		}
	})}
	go server.Serve(listener)
	defer server.Close()
	config := submissionConfig{Origin: "https://mielenosoitukset.fi", SessionSocket: listener.Addr().String()}
	for _, cookie := range []string{"", "session=expired", "session=valid"} {
		r := httptest.NewRequest("POST", "/api/submissions", nil)
		r.Header.Set("Cookie", cookie)
		actor, err := submissionActor(context.Background(), r, config)
		if err != nil || (cookie == "session=valid" && actor != id) || (cookie != "session=valid" && !actor.IsZero()) {
			t.Fatal(cookie, actor, err)
		}
	}
}

func TestSubmissionClientTrustBoundary(t *testing.T) {
	r := httptest.NewRequest("POST", "/api/submissions", nil)
	r.RemoteAddr = "127.0.0.1:1234"
	r.Header.Set("X-Forwarded-For", "1.2.3.4, 173.245.48.1")
	r.Header.Set("CF-Connecting-IP", "203.0.113.7")
	if submissionClientAddress(r) != "203.0.113.7" {
		t.Fatal("Cloudflare visitors collapsed into edge address")
	}
	r.Header.Set("CF-Connecting-IPv6", "2001:db8::1")
	if submissionClientAddress(r) != "2001:db8::1" {
		t.Fatal("IPv6 preference changed")
	}
	r.RemoteAddr = "198.51.100.1:1234"
	if submissionClientAddress(r) != "198.51.100.1" {
		t.Fatal("untrusted proxy headers spoofed client")
	}
	r.RemoteAddr = "127.0.0.1:1234"
	r.Header.Set("X-Forwarded-For", "203.0.113.2")
	if submissionClientAddress(r) != "203.0.113.2" {
		t.Fatal("untrusted Cloudflare header accepted")
	}
}

func TestSubmissionOriginMatchesBothProductionHosts(t *testing.T) {
	primary := "https://mielenosoitukset.fi"
	for _, origin := range []string{primary, "https://www.mielenosoitukset.fi"} {
		if !submissionOriginAllowed(origin, primary) {
			t.Fatal("supported site hostname rejected", origin)
		}
	}
	for _, origin := range []string{"", "null", "http://www.mielenosoitukset.fi", "https://evil.mielenosoitukset.fi", "https://www.mielenosoitukset.fi.evil.test", primary + ":444", primary + "/", "https://www.example.test"} {
		if submissionOriginAllowed(origin, primary) {
			t.Fatal("untrusted origin accepted", origin)
		}
	}
	if submissionOriginAllowed("https://www.example.test", "https://example.test") {
		t.Fatal("custom deployments gained an implicit alias")
	}
}

func TestMongoSubmissionConcurrencyAndRecovery(t *testing.T) {
	uri := os.Getenv("TEST_MONGODB_URI")
	if uri == "" {
		t.Skip("set TEST_MONGODB_URI for isolated submission integration")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	client, err := mongo.Connect(options.Client().ApplyURI(uri))
	if err != nil {
		t.Fatal(err)
	}
	defer client.Disconnect(context.Background())
	db := client.Database("moso_go_submission_test_" + bson.NewObjectID().Hex())
	defer db.Drop(context.Background())
	if checkSubmissionIndexes(ctx, db) == nil {
		t.Fatal("missing unique index accepted")
	}
	_, err = db.Collection("demo_submission_tokens").Indexes().CreateOne(ctx, mongo.IndexModel{Keys: bson.D{{Key: "token", Value: 1}}, Options: options.Index().SetUnique(true)})
	if err != nil || checkSubmissionIndexes(ctx, db) != nil {
		t.Fatal(err)
	}
	input, err := readSubmission(httptest.NewRecorder(), submissionRequest("0123456789abcdef0123456789abcdef", "Saved event"), map[string]bool{"fi": true})
	if err != nil {
		t.Fatal(err)
	}
	var group sync.WaitGroup
	failures := make(chan error, 12)
	for n := range 12 {
		group.Add(1)
		go func(n int) {
			defer group.Done()
			copy := input
			copy.Token = fmt.Sprintf("client-token-%020d", n)
			item, err := reserveSubmission(ctx, db, copy)
			if err == nil {
				err = finishSubmission(ctx, db, item)
			}
			if err != nil {
				failures <- err
			}
		}(n)
	}
	group.Wait()
	close(failures)
	for err := range failures {
		t.Fatal(err)
	}
	for _, name := range []string{"demonstrations", "submitters", "demo_notifications_queue"} {
		count, err := db.Collection(name).CountDocuments(ctx, bson.M{})
		if err != nil || count != 1 {
			t.Fatal(name, count, err)
		}
	}
	var demo bson.M
	db.Collection("demonstrations").FindOne(ctx, bson.M{}).Decode(&demo)
	if demo["approved"] != false {
		t.Fatal("approval injected")
	}
	if _, exists := demo["submitter_email"]; exists {
		t.Fatal("contact leaked into public event")
	}
	// A retry after a moderator's edit must never replace the saved event.
	db.Collection("demonstrations").UpdateOne(ctx, bson.M{"_id": demo["_id"]}, bson.M{"$set": bson.M{"approved": true, "title": "Reviewed"}})
	item, err := reserveSubmission(ctx, db, input)
	if err != nil {
		t.Fatal(err)
	}
	if err := finishSubmission(ctx, db, item); err != nil {
		t.Fatal(err)
	}
	db.Collection("demonstrations").FindOne(ctx, bson.M{}).Decode(&demo)
	if demo["title"] != "Reviewed" {
		t.Fatal("moderation overwritten")
	}
	changed := input
	changed.Fingerprint = "different"
	if _, err := reserveSubmission(ctx, db, changed); err != errStaleSubmission {
		t.Fatal("stale token accepted", err)
	}
	// Crash after reservation, before the event insert: restart recovery finishes.
	input.Token = "recovery-token-0123456789"
	input.Fingerprint = "recovery-fingerprint"
	if _, err := reserveSubmission(ctx, db, input); err != nil {
		t.Fatal(err)
	}
	recoverGoSubmissions(ctx, db)
	if count, _ := db.Collection("demonstrations").CountDocuments(ctx, bson.M{}); count != 2 {
		t.Fatal("reservation not recovered", count)
	}
	handler := publicSubmissionHandler(http.NotFoundHandler(), db, submissionConfig{Origin: "https://mielenosoitukset.fi", Secret: strings.Repeat("s", 32), Locales: map[string]bool{"fi": true}})
	badOrigin := submissionRequest("origin-test-token-0123456789", "Title")
	badOrigin.Header.Set("Origin", "https://other.example")
	w := httptest.NewRecorder()
	handler.ServeHTTP(w, badOrigin)
	if w.Code != 403 || w.Header().Get("Access-Control-Allow-Origin") != "" {
		t.Fatal(w.Code, w.Header())
	}
	for n := range 6 {
		allowed, err := submissionRate(ctx, db, "rate-test")
		if err != nil || allowed != (n < 5) {
			t.Fatal("rate limit", n, allowed, err)
		}
	}
	native := submissionRequest("native-token-0123456789", "Reviewed")
	native.Header.Del("X-Requested-With")
	w = httptest.NewRecorder()
	handler.ServeHTTP(w, native)
	if w.Code != http.StatusSeeOther || w.Header().Get("Location") != "/submit?conflict=1" {
		t.Fatal("no-JavaScript duplicate feedback lost", w.Code, w.Body.String())
	}
	db.Collection("panic").InsertOne(ctx, bson.M{"name": "global", "panic": true})
	w = httptest.NewRecorder()
	handler.ServeHTTP(w, submissionRequest("panic-test-token-0123456789", "Title"))
	if w.Code != 503 {
		t.Fatal("panic bypass", w.Code)
	}
}
