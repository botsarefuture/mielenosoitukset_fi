package main

import (
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"go.mongodb.org/mongo-driver/v2/bson"
	"go.mongodb.org/mongo-driver/v2/mongo"
)

func TestDescriptionMarkdown(t *testing.T) {
	for _, example := range []struct{ html, markdown string }{
		{"", ""},
		{"  Tavallinen teksti  ", "Tavallinen teksti"},
		{"<p>Rivi<br/>Toinen<strong/><em/></p>", "Rivi\nToinen******"},
		{"<p>Ensimmainen kappale.</p><p><strong>Tarkea</strong> lisatieto.</p>", "Ensimmainen kappale.\n\n**Tarkea** lisatieto."},
		{"<blockquote>Pidetaan suunta rauhallisena.</blockquote><p>Nykyinen kuvaus.</p>", "Pidetaan suunta rauhallisena.\n\nNykyinen kuvaus."},
		{"<h2>Otsikko</h2><p><b>Lihava</b> ja <i>kursiivi</i><br>rivi &amp; &lt;teksti&gt; &#228;.</p>", "## Otsikko\n\n**Lihava** ja *kursiivi*\nrivi & <teksti> ä."},
		{"<ol><li>Yksi</li><li>Kaksi<ul><li>Sisalla</li></ul></li></ol>", "1. Yksi\n2. Kaksi\n  - Sisalla"},
		{`<p><a href="https://example.test/?a=1&amp;b=2">Linkki</a> <a href="mailto:a@example.test">Viesti</a> <a href="javascript:alert(1)">Ei</a> <a href="/relative">Suhteellinen</a></p>`, "[Linkki](https://example.test/?a=1&b=2) [Viesti](mailto:a@example.test) Ei Suhteellinen"},
	} {
		if got := descriptionMarkdown(example.html); got != example.markdown {
			t.Errorf("%q: got %q, want %q", example.html, got, example.markdown)
		}
	}
}

func TestSuggestionHTTPAndCachedRendering(t *testing.T) {
	id, _ := bson.ObjectIDFromHex(demoID)
	doc := bson.M{"_id": id, "title": "Alkuperäinen", "description": "<p><strong>Kuvaus</strong></p>"}
	for _, example := range []struct {
		err    error
		status int
	}{
		{nil, http.StatusOK}, {mongo.ErrNoDocuments, http.StatusNotFound}, {errors.New("unavailable"), http.StatusServiceUnavailable},
	} {
		response := httptest.NewRecorder()
		(&API{&fakeStore{doc: doc, err: example.err}}).handler().ServeHTTP(response,
			httptest.NewRequest(http.MethodGet, "/api/demonstrations/"+demoID, nil))
		if response.Code != example.status {
			t.Fatalf("got %d, want %d: %s", response.Code, example.status, response.Body.String())
		}
		if example.status == http.StatusOK {
			cached, err := renderDemonstration(doc, "fi")
			if err != nil || string(cached) != response.Body.String() {
				t.Fatalf("cached and uncached detail responses differ: %s / %s (%v)", cached, response.Body.String(), err)
			}
			var payload map[string]any
			if err := json.Unmarshal(cached, &payload); err != nil {
				t.Fatal(err)
			}
			if payload["suggestion"].(map[string]any)["description_markdown"] != "**Kuvaus**" {
				t.Fatal("missing Markdown prefill")
			}
		}
	}
}

func TestSuggestionPrefillsOriginalNotTranslation(t *testing.T) {
	doc := bson.M{"_id": bson.NewObjectID(), "title": "Alkuperainen", "description": "<p><strong>Kuvaus</strong></p>",
		"date": "2026-11-10", "start_time": "None", "end_time": nil, "facebook": "null", "tags": bson.A{"#rauha", " ilmasto "},
		"route": "['Keskustori', 'Hämeenkatu', 'Keskustori']", "translations": bson.M{"en": bson.M{"title": "Translation", "description": "Different", "tags": bson.A{"other"}}},
		"organizers": bson.A{bson.M{"name": "Järjestö", "email": "public@example.test", "show_email_public": true, "website": "https://example.test"}, bson.M{"name": "Toinen"}}}
	payload := demonstrationPayload(doc, "en")
	fields := payload["suggestion"].(bson.M)
	for field, expected := range map[string]string{"title": "Alkuperainen", "description_markdown": "**Kuvaus**", "date": "2026-11-10",
		"start_time": "", "end_time": "", "facebook": "", "tags": "rauha, ilmasto", "route": "Keskustori, Hämeenkatu, Keskustori",
		"organizers": "Järjestö (public@example.test, https://example.test)\nToinen"} {
		if fields[field] != expected {
			t.Errorf("%s: got %#v, want %q", field, fields[field], expected)
		}
	}
	if payload["title"] != "Translation" {
		t.Fatal("public localized detail must remain unchanged")
	}
}

func TestSuggestionDoesNotExposePrivateOrganizers(t *testing.T) {
	payload := demonstrationPayload(bson.M{"organizers": bson.A{
		bson.M{"name": "Secret Name", "website": "https://secret.test", "email": "secret@example.test", "is_private": true},
		bson.M{"name": "Public Name", "email": "unconsented@example.test"},
	}}, "fi")
	encoded, err := json.Marshal(payload["suggestion"])
	if err != nil {
		t.Fatal(err)
	}
	for _, private := range []string{"Secret Name", "secret.test", "secret@example.test", "unconsented@example.test"} {
		if strings.Contains(string(encoded), private) {
			t.Fatalf("private organizer leaked: %s", encoded)
		}
	}
	fields := payload["suggestion"].(bson.M)
	if fields["organizers"] != "" || fields["organizers_current"] != "Public Name" {
		t.Fatalf("a redacted list must not submit a lossy replacement: %v", fields)
	}
}

func TestSuggestionProjectedOrganizerRedaction(t *testing.T) {
	payload := demonstrationPayload(bson.M{"organizers": bson.A{
		bson.M{"name": "Public Name", "show_email_public": false, "suggestion_redacted": true},
	}}, "fi")
	fields := payload["suggestion"].(bson.M)
	if fields["organizers"] != "" || fields["organizers_current"] != "Public Name" {
		t.Fatalf("projection redaction must prevent replacement: %v", fields)
	}
	encoded, _ := json.Marshal(payload)
	if strings.Contains(string(encoded), "suggestion_redacted") {
		t.Fatal("internal projection flag escaped into public response")
	}
}

func TestSuggestionLegacyRoutes(t *testing.T) {
	for _, route := range []any{bson.A{"First", "Second", "First"}, `["First","Second","First"]`, "['First', 'Second', 'First']", "First\nSecond, First"} {
		if got := strings.Join(routeStops(route), ", "); got != "First, Second, First" {
			t.Errorf("%#v: %q", route, got)
		}
	}
}
