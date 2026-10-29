package main

import (
	"encoding/json"
	"errors"
	"go.mongodb.org/mongo-driver/v2/bson"

	"math"
	"net/url"
	"sort"
	"strconv"
	"strings"
	"time"
)

var textFields = []string{"date", "start_time", "end_time", "city", "address", "slug", "event_type", "facebook", "img", "cover_picture", "preview_image"}

func publicProjection() bson.M {
	fields := bson.M{"_id": 1, "title": 1, "description": 1, "tags": 1, "default_language": 1, "cancelled": 1, "latitude": 1, "longitude": 1, "running_number": 1, "gallery_images": 1, "images": 1, "route": 1}
	for _, field := range textFields {
		fields[field] = 1
	}
	for _, lang := range []string{"fi", "en", "sv"} {
		for _, field := range []string{"title", "description", "tags"} {
			fields["translations."+lang+"."+field] = 1
		}
	}
	for _, field := range []string{"name", "website", "organization_id", "is_private", "show_name_public"} {
		fields["organizers."+field] = 1
	}
	return fields
}
func parseQuery(raw string) (string, error) {
	q, err := url.ParseQuery(raw)
	if err != nil {
		return "", err
	}
	for key, values := range q {
		if key != "lang" || len(values) != 1 {
			return "", errors.New("unknown or duplicate parameter")
		}
	}
	lang := strings.ToLower(strings.TrimSpace(q.Get("lang")))
	if lang != "" && lang != "fi" && lang != "en" && lang != "sv" {
		return "", errors.New("unsupported language")
	}
	return lang, nil
}
func object(value any) bson.M {
	switch v := value.(type) {
	case bson.M:
		return v
	case bson.D:
		result := bson.M{}
		for _, element := range v {
			result[element.Key] = element.Value
		}
		return result
	case map[string]any:
		return bson.M(v)
	}
	return bson.M{}
}
func array(value any) []any {
	switch v := value.(type) {
	case bson.A:
		return []any(v)
	case []any:
		return v
	case []string:
		r := []any{}
		for _, s := range v {
			if s = strings.TrimSpace(s); s != "" {
				r = append(r, s)
			}
		}
		return r
	}
	return nil
}
func text(value any) any {
	if s, ok := value.(string); ok {
		return s
	}
	return nil
}
func stringsOnly(value any) []string {
	r := []string{}
	for _, item := range array(value) {
		if s, ok := item.(string); ok && s != "" {
			if s = strings.TrimSpace(s); s != "" {
				r = append(r, s)
			}
		}
	}
	return r
}
func identifier(value any) any {
	switch v := value.(type) {
	case bson.ObjectID:
		return v.Hex()
	case string:
		if id, err := bson.ObjectIDFromHex(v); err == nil {
			return id.Hex()
		}
	}
	return nil
}
func number(value any) any {
	var n float64
	switch v := value.(type) {
	case float64:
		n = v
	case float32:
		n = float64(v)
	case int:
		n = float64(v)
	case int32:
		n = float64(v)
	case int64:
		n = float64(v)
	case string:
		var err error
		n, err = strconv.ParseFloat(v, 64)
		if err != nil {
			return nil
		}
	default:
		return nil
	}
	if math.IsNaN(n) || math.IsInf(n, 0) {
		return nil
	}
	return n
}
func publicPayload(doc bson.M, lang string) bson.M {
	defaultLang, _ := doc["default_language"].(string)
	if defaultLang != "fi" && defaultLang != "en" && defaultLang != "sv" {
		defaultLang = "fi"
	}
	if lang == "" {
		lang = defaultLang
	}
	translations := object(doc["translations"])
	localized := object(translations[lang])
	r := bson.M{"_id": identifier(doc["_id"]), "default_language": defaultLang, "resolved_language": lang}
	for _, field := range textFields {
		r[field] = text(doc[field])
	}
	switch v := doc["date"].(type) {
	case bson.DateTime:
		r["date"] = v.Time().UTC().Format("2006-01-02")
	case time.Time:
		r["date"] = v.UTC().Format("2006-01-02")
	}
	for _, field := range []string{"title", "description"} {
		value := doc[field]
		if s, ok := localized[field].(string); ok && strings.TrimSpace(s) != "" {
			value = strings.TrimSpace(s)
		}
		r[field] = text(value)
	}
	tags := stringsOnly(localized["tags"])
	if len(tags) == 0 {
		tags = stringsOnly(doc["tags"])
	}
	r["tags"] = tags
	languages := []string{defaultLang}
	for _, candidate := range []string{"fi", "en", "sv"} {
		values := object(translations[candidate])
		if candidate != defaultLang && (nonblank(values["title"]) || nonblank(values["description"]) || len(stringsOnly(values["tags"])) > 0) {
			languages = append(languages, candidate)
		}
	}
	sort.Strings(languages)
	r["available_languages"] = languages
	cancelled, _ := doc["cancelled"].(bool)
	r["cancelled"] = cancelled
	r["running_number"] = number(doc["running_number"])
	r["latitude"] = number(doc["latitude"])
	r["longitude"] = number(doc["longitude"])
	r["route"] = routeStops(doc["route"])
	gallery := galleryImages(doc["gallery_images"])
	if len(gallery) == 0 {
		gallery = galleryImages(doc["images"])
	}
	r["gallery_images"] = gallery
	organizers := []bson.M{}
	for _, item := range array(doc["organizers"]) {
		org := object(item)
		private, privateOK := org["is_private"].(bool)
		if _, exists := org["is_private"]; exists && !privateOK {
			continue
		}
		showName, _ := org["show_name_public"].(bool)
		if private && !showName {
			continue
		}
		name := text(org["name"])
		if name == nil || name == "" {
			continue
		}
		organizers = append(organizers, bson.M{"name": name, "website": text(org["website"]), "organization_id": identifier(org["organization_id"])})
	}
	r["organizers"] = organizers
	return r
}

func nonblank(value any) bool { s, ok := value.(string); return ok && strings.TrimSpace(s) != "" }
func routeStops(value any) []string {
	if s, ok := value.(string); ok {
		var stops []string
		if json.Unmarshal([]byte(s), &stops) == nil {
			return stringsOnly(stops)
		}
		return stringsOnly(strings.Split(s, ","))
	}
	return stringsOnly(value)
}
func galleryImages(value any) []string {
	result := []string{}
	seen := map[string]bool{}
	var add func(any)
	add = func(item any) {
		if s, ok := item.(string); ok {
			for _, line := range strings.Split(s, "\n") {
				line = strings.TrimSpace(line)
				if line != "" && !seen[line] {
					seen[line] = true
					result = append(result, line)
				}
			}
			return
		}
		for _, child := range array(item) {
			add(child)
		}
	}
	add(value)
	return result
}
