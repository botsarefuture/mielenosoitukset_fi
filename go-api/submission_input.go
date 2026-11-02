package main

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	stdhtml "html"
	"image"
	_ "image/gif"
	_ "image/jpeg"
	_ "image/png"
	"io"
	"net/http"
	"net/mail"
	"net/url"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"time"

	"go.mongodb.org/mongo-driver/v2/bson"
	_ "golang.org/x/image/webp"
	"golang.org/x/net/html"
	"golang.org/x/text/cases"
)

const submissionBodyLimit = 9 << 20
const submissionImageLimit = 8 << 20

var submissionTokenPattern = regexp.MustCompile(`^[a-zA-Z0-9_-]{16,100}$`)
var organizerFieldPattern = regexp.MustCompile(`^organizer_name_([1-9][0-9]?)$`)

func submissionString(value any) string {
	text, _ := value.(string)
	return text
}

type submissionInput struct {
	Token, Fingerprint string
	Event, Submitter   bson.M
	Image              []byte
	Force              bool
}

func submissionEmail(value string) bool {
	address, err := mail.ParseAddress(value)
	return err == nil && address.Address == value && len(value) <= 254 && strings.Contains(value, ".")
}

func safeSubmissionURL(value string) string {
	parsed, err := url.Parse(value)
	if err != nil || parsed.Hostname() == "" || parsed.User != nil || (parsed.Scheme != "https" && parsed.Scheme != "http") {
		return ""
	}
	return value
}

// Preserve the editor's small formatting vocabulary, never arbitrary HTML or attributes.
func cleanSubmissionHTML(value string) string {
	root, err := html.Parse(strings.NewReader(value))
	if err != nil {
		return stdhtml.EscapeString(value)
	}
	var output strings.Builder
	allowed := map[string]bool{"p": true, "br": true, "strong": true, "b": true, "em": true, "i": true, "blockquote": true, "ul": true, "ol": true, "li": true, "a": true}
	var walk func(*html.Node)
	walk = func(node *html.Node) {
		if node.Type == html.TextNode {
			output.WriteString(stdhtml.EscapeString(node.Data))
			return
		}
		if node.Type == html.ElementNode && (node.Data == "script" || node.Data == "style" || node.Data == "iframe" || node.Data == "svg" || node.Data == "math") {
			return
		}
		tag := allowed[node.Data] && node.Type == html.ElementNode
		if tag {
			output.WriteString("<" + node.Data)
			if node.Data == "a" {
				for _, attr := range node.Attr {
					if attr.Key == "href" && safeSubmissionURL(attr.Val) != "" {
						output.WriteString(` href="` + stdhtml.EscapeString(attr.Val) + `" rel="nofollow noopener"`)
						break
					}
				}
			}
			if node.Data == "li" {
				for _, attr := range node.Attr {
					if attr.Key == "data-list" && (attr.Val == "bullet" || attr.Val == "ordered") {
						output.WriteString(` data-list="` + attr.Val + `"`)
						break
					}
				}
			}
			output.WriteString(">")
		}
		for child := node.FirstChild; child != nil; child = child.NextSibling {
			walk(child)
		}
		if tag && node.Data != "br" {
			output.WriteString("</" + node.Data + ">")
		}
	}
	walk(root)
	return output.String()
}

func validSubmissionFields(r *http.Request) bool {
	for key, values := range r.MultipartForm.Value {
		limit := 2000
		if key == "description" {
			limit = 100_000
		}
		if len(values) != 1 || len(values[0]) > limit {
			return false
		}
	}
	get := func(key string) string { return strings.TrimSpace(r.FormValue(key)) }
	for _, key := range []string{"title", "date", "start_time", "city", "address", "submitter_role", "submitter_name", "submitter_email", "accept_terms"} {
		if get(key) == "" {
			return false
		}
	}
	date, err := time.Parse("2006-01-02", get("date"))
	if err != nil || date.Format("2006-01-02") != get("date") {
		return false
	}
	for _, key := range []string{"start_time", "end_time"} {
		if value := get(key); value != "" {
			if parsed, err := time.Parse("15:04", value); err != nil || parsed.Format("15:04") != value {
				return false
			}
		}
	}
	if !submissionEmail(get("submitter_email")) || !submissionTokenPattern.MatchString(get("submission_token")) {
		return false
	}
	return true
}

func readSubmission(w http.ResponseWriter, r *http.Request, locales map[string]bool) (submissionInput, error) {
	invalid := errors.New("Tarkista lomakkeen tiedot ja hyväksy käyttöehdot.")
	r.Body = http.MaxBytesReader(w, r.Body, submissionBodyLimit)
	if err := r.ParseMultipartForm(1 << 20); err != nil {
		return submissionInput{}, invalid
	}
	defer r.MultipartForm.RemoveAll()
	if !validSubmissionFields(r) {
		return submissionInput{}, invalid
	}
	get := func(key string) string { return strings.TrimSpace(r.FormValue(key)) }
	city, known := cityCatalog[normalizeCityKey(get("city"))]
	if !known {
		return submissionInput{}, invalid
	}
	locale := get("default_language")
	if locale == "" {
		locale = "fi"
	}
	if !locales[locale] {
		return submissionInput{}, invalid
	}
	types := map[string]string{"paikallaan": "STAY_STILL", "marssi": "MARCH", "muut": "OTHER"}
	eventType, known := types[get("type")]
	if !known {
		return submissionInput{}, invalid
	}
	organizers, err := submissionOrganizers(r)
	if err != nil {
		return submissionInput{}, invalid
	}
	tags := []string{}
	seen := map[string]bool{}
	for _, tag := range strings.Split(get("tags"), ",") {
		tag = strings.TrimSpace(strings.TrimLeft(strings.TrimSpace(tag), "#"))
		if tag != "" && !seen[tag] {
			tags = append(tags, tag)
			seen[tag] = true
		}
	}
	if len(tags) > 50 {
		return submissionInput{}, invalid
	}
	route := bson.A{}
	if eventType == "MARCH" {
		for _, place := range strings.Split(get("route"), ",") {
			if place = strings.TrimSpace(place); place != "" {
				route = append(route, place)
			}
		}
	}
	event := bson.M{"title": get("title"), "date": get("date"), "start_time": get("start_time"), "end_time": get("end_time"),
		"city": city.Name, "city_key": city.Key, "address": get("address"), "description": cleanSubmissionHTML(get("description")), "tags": tags,
		"default_language": locale, "translations": bson.M{}, "event_type": eventType, "route": route, "organizers": organizers,
		"facebook": safeSubmissionURL(get("facebook")), "approved": false, "hide": false, "rejected": false, "cancelled": false, "recurs": false, "in_past": false, "aliases": bson.A{}}
	contact := bson.M{"submitter_role": get("submitter_role"), "submitter_name": get("submitter_name"), "submitter_email": get("submitter_email"), "accept_terms": true}
	input := submissionInput{Token: get("submission_token"), Event: event, Submitter: contact, Force: get("force_submit") != ""}
	input.Fingerprint = submissionFingerprint(r, tags)
	facebookURL, _ := url.Parse(safeSubmissionURL(get("facebook")))
	facebookHost := facebookURL.Hostname()
	if get("facebook_imported") == "1" && (facebookHost == "facebook.com" || facebookHost == "www.facebook.com" || facebookHost == "m.facebook.com") && regexp.MustCompile(`^/events/[0-9]+/?$`).MatchString(facebookURL.Path) {
		event["facebook_import"] = bson.M{"url": event["facebook"], "importer": "apify-facebook-events-scraper", "imported_at": time.Now().UTC()}
	}
	// The worker validates imported media against its configured CDN, never fetches it.
	if get("facebook_imported") == "1" {
		contact["imported_image_url"] = get("facebook_image_url")
	}
	input.Image, err = readSubmissionImage(r)
	if err != nil {
		return submissionInput{}, err
	}
	return input, nil
}

func readSubmissionImage(r *http.Request) ([]byte, error) {
	invalid := errors.New("Kuva ei kelpaa. Käytä JPEG-, PNG-, WebP- tai GIF-kuvaa, enintään 8 Mt ja 40 megapikseliä.")
	for key, files := range r.MultipartForm.File {
		if key != "image" || len(files) != 1 {
			return nil, invalid
		}
	}
	files := r.MultipartForm.File["image"]
	if len(files) > 0 && files[0].Filename != "" {
		file, err := files[0].Open()
		if err != nil {
			return nil, invalid
		}
		defer file.Close()
		data, err := io.ReadAll(io.LimitReader(file, submissionImageLimit+1))
		if err != nil || len(data) > submissionImageLimit {
			return nil, invalid
		}
		config, _, err := image.DecodeConfig(bytes.NewReader(data))
		if err != nil || config.Width < 1 || config.Height < 1 || int64(config.Width)*int64(config.Height) > 40_000_000 {
			return nil, invalid
		}
		return data, nil
	}
	return nil, nil
}

func submissionOrganizers(r *http.Request) (bson.A, error) {
	indices := []int{}
	for key := range r.MultipartForm.Value {
		if match := organizerFieldPattern.FindStringSubmatch(key); match != nil {
			index, _ := strconv.Atoi(match[1])
			indices = append(indices, index)
		}
	}
	if len(indices) > 20 {
		return nil, errors.New("too many organizers")
	}
	sort.Ints(indices)
	rows := bson.A{}
	for _, index := range indices {
		get := func(field string) string {
			return strings.TrimSpace(r.FormValue(fmt.Sprintf("organizer_%s_%d", field, index)))
		}
		if email := get("email"); email != "" && !submissionEmail(email) {
			return nil, errors.New("invalid organizer email")
		}
		rows = append(rows, bson.M{"_id": bson.NewObjectID(), "name": get("name"), "email": get("email"), "website": safeSubmissionURL(get("website")), "is_private": get("is_private") != "", "show_name_public": get("show_name") != "", "show_email_public": get("show_email") != ""})
	}
	return rows, nil
}

// Match Flask's fingerprint vocabulary so ordinary retries across rollback deduplicate.
func submissionFingerprint(r *http.Request, tags []string) string {
	parts := []string{}
	for _, key := range []string{"title", "date", "start_time", "end_time", "city", "address", "route", "submitter_email", "submitter_name", "submitter_role"} {
		value := r.FormValue(key)
		if key == "route" && r.FormValue("type") != "marssi" {
			value = ""
		}
		parts = append(parts, strings.ToLower(strings.TrimSpace(value)))
	}
	normalized := []string{}
	for _, tag := range tags {
		normalized = append(normalized, strings.ToLower(strings.TrimSpace(tag)))
	}
	sort.Strings(normalized)
	parts = append(parts, strings.Join(normalized, "|"), strings.ToLower(strings.TrimSpace(r.FormValue("description"))))
	sum := sha256.Sum256([]byte(strings.Join(parts, "||")))
	return hex.EncodeToString(sum[:])
}

var submissionWords = regexp.MustCompile(`[\pL\pN_]+`)

func similarSubmission(existing bson.M, title, address string) bool {
	fold := cases.Fold()
	title = fold.String(strings.TrimSpace(title))
	address = fold.String(strings.TrimSpace(address))
	words := map[string]bool{}
	for _, word := range submissionWords.FindAllString(title, -1) {
		if len([]rune(word)) > 3 {
			words[word] = true
		}
	}
	titles := []string{submissionString(existing["title"])}
	if translations, ok := existing["translations"].(bson.M); ok {
		for _, value := range translations {
			if row, ok := value.(bson.M); ok {
				titles = append(titles, submissionString(row["title"]))
			}
		}
	}
	for _, value := range titles {
		candidate := fold.String(value)
		if candidate == "" {
			continue
		}
		if strings.Contains(title, candidate) || strings.Contains(candidate, title) {
			return true
		}
		shared := map[string]bool{}
		for _, word := range submissionWords.FindAllString(candidate, -1) {
			if words[word] {
				shared[word] = true
			}
		}
		if len(shared) >= 2 {
			return true
		}
	}
	candidate := fold.String(submissionString(existing["address"]))
	return address != "" && candidate != "" && (strings.Contains(address, candidate) || strings.Contains(candidate, address))
}
