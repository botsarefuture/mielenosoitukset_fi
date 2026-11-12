package main

import (
	"errors"
	"go.mongodb.org/mongo-driver/v2/mongo"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func validApplication() applicationInput {
	var input applicationInput
	input.CityKeys = []string{"Tampere", "tampere", "turku"}
	input.About = strings.Repeat("Olen järjestänyt mielenosoituksia. ", 3)
	input.Consent = true
	input.Activism.Cities = []string{"helsinki"}
	input.Activism.Experience = "some"
	return input
}

func TestValidateApplicationNormalisesAndBounds(t *testing.T) {
	fields, err := validateApplication(validApplication())
	if err != nil {
		t.Fatal(err)
	}
	if keys := fields["city_keys"].([]string); len(keys) != 2 || keys[0] != "tampere" || keys[1] != "turku" {
		t.Fatalf("city keys = %v", keys)
	}

	cases := map[string]func(*applicationInput){
		"APPLY_CONSENT":       func(i *applicationInput) { i.Consent = false },
		"APPLY_CITY_COUNT":    func(i *applicationInput) { i.CityKeys = nil },
		"APPLY_CITY":          func(i *applicationInput) { i.CityKeys = []string{"atlantis"} },
		"APPLY_NATIONAL_CITY": func(i *applicationInput) { i.CityKeys = []string{"helsinki"} },
		"APPLY_ABOUT":         func(i *applicationInput) { i.About = "liian lyhyt" },
		"APPLY_EXPERIENCE":    func(i *applicationInput) { i.Activism.Experience = "expert" },
		"APPLY_REFERENCES":    func(i *applicationInput) { i.References = strings.Repeat("x", 1001) },
	}
	for code, mutate := range cases {
		input := validApplication()
		mutate(&input)
		_, err := validateApplication(input)
		if invalid, ok := err.(applicationError); !ok || invalid.code != code {
			t.Fatalf("%s: got %v", code, err)
		}
	}
}

func TestApplicationHandlerGuardsBeforeTouchingTheDatabase(t *testing.T) {
	next := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { w.WriteHeader(299) })
	configured := submissionConfig{Origin: "https://mielenosoitukset.fi", Secret: strings.Repeat("s", 32)}
	run := func(config submissionConfig, method, path string, headers map[string]string) *httptest.ResponseRecorder {
		request := httptest.NewRequest(method, path, strings.NewReader("{}"))
		for key, value := range headers {
			request.Header.Set(key, value)
		}
		recorder := httptest.NewRecorder()
		// A nil database proves none of these paths reads it.
		cityAdminApplicationHandler(next, nil, config).ServeHTTP(recorder, request)
		return recorder
	}
	sameOrigin := map[string]string{"Origin": "https://mielenosoitukset.fi"}
	checks := []struct {
		name   string
		code   int
		result *httptest.ResponseRecorder
	}{
		{"other paths pass through", 299, run(configured, "GET", "/api/cities", nil)},
		{"unconfigured", 503, run(submissionConfig{}, "POST", applicationsPath, sameOrigin)},
		{"wrong method", 405, run(configured, "GET", applicationsPath, sameOrigin)},
		{"mine is read-only", 405, run(configured, "POST", applicationsMinePath, sameOrigin)},
		{"foreign origin", 403, run(configured, "POST", applicationsPath, map[string]string{"Origin": "https://evil.example"})},
		{"cross-site read", 403, run(configured, "GET", applicationsMinePath, map[string]string{"Sec-Fetch-Site": "cross-site"})},
		{"signed out", 401, run(configured, "POST", applicationsPath, sameOrigin)},
		{"signed out read", 401, run(configured, "GET", applicationsMinePath, nil)},
	}
	for _, check := range checks {
		if check.result.Code != check.code {
			t.Fatalf("%s: status %d, want %d", check.name, check.result.Code, check.code)
		}
		if check.code != 299 && check.result.Header().Get("Cache-Control") != "private, no-store" {
			t.Fatalf("%s: responses must never be cached", check.name)
		}
	}
}

// Applying must not depend on a city having demonstrations or being enabled:
// every catalog city except the nationally managed ones is a valid target.
func TestApplicationAcceptsEveryCatalogCityExceptNationalOnes(t *testing.T) {
	if len(cityCatalog) < 300 {
		t.Fatalf("catalog unexpectedly small: %d", len(cityCatalog))
	}
	for key := range cityCatalog {
		_, err := applicationCities([]string{key}, 1, 5, false)
		if nationallyManagedCities[key] {
			if err == nil {
				t.Fatalf("%s must be rejected", key)
			}
			continue
		}
		if err != nil {
			t.Fatalf("%s rejected: %v", key, err)
		}
	}
}

func TestApplicationInsertFailureTreatsDuplicateKeyAsOpenApplication(t *testing.T) {
	duplicate := mongo.WriteException{WriteErrors: mongo.WriteErrors{{Code: 11000, Message: "E11000 duplicate key"}}}
	status, code, _ := applicationInsertFailure(duplicate)
	if status != 409 || code != "APPLY_OPEN_EXISTS" {
		t.Fatalf("duplicate key gave %d %s", status, code)
	}
	status, code, _ = applicationInsertFailure(errors.New("network down"))
	if status != 503 || code != "APPLY_SAVE_FAILED" {
		t.Fatalf("other error gave %d %s", status, code)
	}
}
