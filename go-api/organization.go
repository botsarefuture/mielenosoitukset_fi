package main

import (
	"context"
	"errors"
	"log"
	"net/http"
	"net/url"
	"strings"
	"time"
	"unicode"

	"go.mongodb.org/mongo-driver/v2/bson"
	"go.mongodb.org/mongo-driver/v2/mongo"
	"go.mongodb.org/mongo-driver/v2/mongo/options"
)

type organizationProfile struct {
	ID          string            `json:"_id"`
	Name        string            `json:"name"`
	Description string            `json:"description"`
	Email       string            `json:"email"`
	Website     string            `json:"website"`
	Logo        string            `json:"logo"`
	Socials     map[string]string `json:"social_media_links"`
	Verified    bool              `json:"verified"`
}

type organizationStore interface {
	FindOrganization(context.Context, bson.ObjectID) (organizationProfile, error)
}

func organizationProjection() bson.M {
	return bson.M{"_id": 1, "name": 1, "description": 1, "email": 1,
		"website": 1, "logo": 1, "social_media_links": 1, "verified": 1}
}

func organizationText(value any) string {
	text, _ := value.(string)
	return strings.TrimSpace(text)
}

func organizationURL(value any) string {
	text := organizationText(value)
	if text == "" || strings.Contains(text, "\\") || strings.IndexFunc(text, unicode.IsControl) >= 0 {
		return ""
	}
	parsed, err := url.Parse(text)
	if err != nil || parsed.User != nil {
		return ""
	}
	if parsed.Scheme == "" {
		if strings.HasPrefix(text, "/") && !strings.HasPrefix(text, "//") && parsed.Host == "" {
			return text
		}
		return ""
	}
	if (strings.EqualFold(parsed.Scheme, "http") || strings.EqualFold(parsed.Scheme, "https")) && parsed.Hostname() != "" {
		return text
	}
	return ""
}

func publicOrganization(id bson.ObjectID, doc bson.M) organizationProfile {
	profile := organizationProfile{ID: id.Hex(), Name: organizationText(doc["name"]),
		Description: organizationText(doc["description"]), Email: organizationText(doc["email"]),
		Website: organizationURL(doc["website"]), Logo: organizationURL(doc["logo"]),
		Socials: map[string]string{}, Verified: doc["verified"] == true}
	if strings.IndexFunc(profile.Email, unicode.IsControl) >= 0 {
		profile.Email = ""
	}
	for platform, value := range object(doc["social_media_links"]) {
		if href := organizationURL(value); href != "" {
			profile.Socials[platform] = href
		}
	}
	return profile
}

func (s mongoStore) FindOrganization(ctx context.Context, id bson.ObjectID) (organizationProfile, error) {
	var doc bson.M
	err := s.collection.Database().Collection("organizations").FindOne(ctx, bson.M{"_id": id},
		options.FindOne().SetProjection(organizationProjection())).Decode(&doc)
	if err != nil {
		return organizationProfile{}, err
	}
	return publicOrganization(id, doc), nil
}

func (a *API) getOrganization(w http.ResponseWriter, r *http.Request) {
	id, err := bson.ObjectIDFromHex(r.PathValue("id"))
	if err != nil || id.IsZero() {
		writeError(w, 404, "organization not found")
		return
	}
	if len(r.URL.RawQuery) > 512 {
		writeError(w, 400, "invalid query parameters")
		return
	}
	if _, err := parseQuery(r.URL.RawQuery); err != nil {
		writeError(w, 400, "invalid query parameters")
		return
	}
	var readErr error
	if source, ok := a.store.(interface {
		FindOrganizationJSON(context.Context, bson.ObjectID) ([]byte, error)
	}); ok {
		data, err := source.FindOrganizationJSON(r.Context(), id)
		readErr = err
		if err == nil {
			w.Header().Set("Cache-Control", "public, max-age=30, s-maxage=60")
			writeJSONBytes(w, 200, data)
			return
		}
		if errors.Is(err, mongo.ErrNoDocuments) {
			writeError(w, 404, "organization not found")
			return
		}
	} else if source, ok := a.store.(organizationStore); ok {
		ctx, cancel := context.WithTimeout(r.Context(), 3*time.Second)
		defer cancel()
		profile, err := source.FindOrganization(ctx, id)
		readErr = err
		if err == nil {
			w.Header().Set("Cache-Control", "public, max-age=30, s-maxage=60")
			writeJSON(w, 200, profile)
			return
		}
		if errors.Is(err, mongo.ErrNoDocuments) {
			writeError(w, 404, "organization not found")
			return
		}
	}
	log.Printf("Organization database read failed (%s)", dbErrorKind(readErr))
	writeError(w, 503, "service unavailable")
}
