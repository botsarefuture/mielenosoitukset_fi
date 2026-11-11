package main

import (
	"bytes"
	"context"
	"encoding/json"
	"io"
	"log"
	"math"
	"mime"
	"net"
	"net/http"
	"net/url"
	"os"
	"regexp"
	"strconv"
	"strings"
	"time"
	"unicode"
	"unicode/utf8"

	"go.mongodb.org/mongo-driver/v2/bson"
	"go.mongodb.org/mongo-driver/v2/mongo"
	"go.mongodb.org/mongo-driver/v2/mongo/options"
)

var analyticsLocation = func() *time.Location {
	location, err := time.LoadLocation("Europe/Helsinki")
	if err != nil {
		panic(err)
	}
	return location
}()

var analyticsBots = regexp.MustCompile(`(?i)bot|crawl|spider|slurp|facebookexternalhit|embedly|preview|python-requests|python-urllib|curl|wget|httpclient|okhttp|go-http|headless|lighthouse|pingdom|uptimerobot|monitor`)
var analyticsMobile = regexp.MustCompile(`(?i)iphone|ipod|android.*mobile|mobile.*android|windows phone|blackberry|bb10|opera mini|opera mobi|iemobile|webos|palm`)
var analyticsTablet = regexp.MustCompile(`(?i)ipad|kindle|silk|playbook|tablet|nexus (?:7|9|10)|sm-x`)
var analyticsDesktop = regexp.MustCompile(`(?i)windows nt|macintosh|mac os x|cros|x11|linux`)
var analyticsListing = regexp.MustCompile(`(?i)^(/city/[^/]+(/tanaan)?|/tag/[^/]+|/organization/[a-f\d]{24})$`)

type analyticsObject [][2]any

func analyticsJSONValue(decoder *json.Decoder) (any, error) {
	value, err := decoder.Token()
	if err != nil {
		return nil, err
	}
	if value == json.Delim('{') {
		object := analyticsObject{}
		for decoder.More() {
			key, err := decoder.Token()
			if err != nil {
				return nil, err
			}
			item, err := analyticsJSONValue(decoder)
			if err != nil {
				return nil, err
			}
			object = append(object, [2]any{key, item})
			for index := 0; index < len(object)-1; index++ {
				if object[index][0] == key {
					object[index][1] = item
					object = object[:len(object)-1]
					break
				}
			}
		}
		_, err = decoder.Token()
		return object, err
	}
	if value == json.Delim('[') {
		array := []any{}
		for decoder.More() {
			item, err := analyticsJSONValue(decoder)
			if err != nil {
				return nil, err
			}
			array = append(array, item)
		}
		_, err = decoder.Token()
		return array, err
	}
	return value, nil
}

func analyticsEnabledFromEnv() bool {
	return os.Getenv("SITE_ANALYTICS_ENABLED") == "true"
}

func analyticsEventHandler(next http.Handler, enabled bool, increment func(context.Context, bson.M) error) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/api/analytics/event" || r.Method != http.MethodPost {
			next.ServeHTTP(w, r)
			return
		}
		w.Header().Set("Cache-Control", "no-store")
		if enabled && r.Header.Get("DNT") != "1" {
			if key := analyticsEventKey(r, clock()); key != nil {
				ctx, cancel := context.WithTimeout(r.Context(), time.Second)
				if err := increment(ctx, key); err != nil {
					log.Print("Analytics event counter unavailable")
				}
				cancel()
			}
		}
		writeJSON(w, http.StatusOK, map[string]bool{"ok": true})
	})
}

func incrementAnalyticsEvent(db *mongo.Database) func(context.Context, bson.M) error {
	return func(ctx context.Context, key bson.M) error {
		_, err := db.Collection("site_analytics").UpdateOne(ctx, key, bson.M{"$inc": bson.M{"count": 1}}, options.UpdateOne().SetUpsert(true))
		return err
	}
}

func analyticsEventPayload(r *http.Request) map[string]any {
	mediaType, _, _ := mime.ParseMediaType(r.Header.Get("Content-Type"))
	if mediaType == "application/json" || strings.HasPrefix(mediaType, "application/") && strings.HasSuffix(mediaType, "+json") {
		body, err := io.ReadAll(r.Body)
		if err != nil || !utf8.Valid(body) {
			return nil
		}
		decoder := json.NewDecoder(bytes.NewReader(body))
		decoder.UseNumber()
		value, err := analyticsJSONValue(decoder)
		object, ok := value.(analyticsObject)
		if err != nil || !ok || decoder.Decode(new(any)) != io.EOF {
			return nil
		}
		payload := map[string]any{}
		for _, pair := range object {
			payload[pair[0].(string)] = pair[1]
		}
		return payload
	}
	if mediaType == "multipart/form-data" {
		if r.ParseMultipartForm(500<<10) != nil {
			return nil
		}
		defer r.MultipartForm.RemoveAll()
	} else if r.ParseForm() != nil {
		return nil
	}
	payload := map[string]any{}
	for key, values := range r.PostForm {
		if len(values) != 0 {
			payload[key] = values[0]
		}
	}
	return payload
}

func analyticsString(value any) string {
	switch typed := value.(type) {
	case nil:
		return ""
	case bool:
		if typed {
			return "True"
		}
		return ""
	case string:
		return typed
	case json.Number:
		if number, _ := typed.Float64(); number == 0 {
			return ""
		}
		return analyticsNumber(typed)
	case []any:
		if len(typed) == 0 {
			return ""
		}
		values := make([]string, len(typed))
		for index, item := range typed {
			values[index] = analyticsRepr(item)
		}
		return "[" + strings.Join(values, ", ") + "]"
	case analyticsObject:
		if len(typed) == 0 {
			return ""
		}
		values := make([]string, len(typed))
		for index, pair := range typed {
			values[index] = analyticsRepr(pair[0]) + ": " + analyticsRepr(pair[1])
		}
		return "{" + strings.Join(values, ", ") + "}"
	default:
		return ""
	}
}

func analyticsRepr(value any) string {
	switch typed := value.(type) {
	case nil:
		return "None"
	case bool:
		if !typed {
			return "False"
		}
	case string:
		quote := "'"
		if strings.Contains(typed, "'") && !strings.Contains(typed, `"`) {
			quote = `"`
		}
		var escaped strings.Builder
		for _, character := range typed {
			switch {
			case character == '\n':
				escaped.WriteString(`\n`)
			case character == '\r':
				escaped.WriteString(`\r`)
			case character == '\t':
				escaped.WriteString(`\t`)
			case character == '\\' || string(character) == quote:
				escaped.WriteByte('\\')
				escaped.WriteRune(character)
			case unicode.IsPrint(character):
				escaped.WriteRune(character)
			default:
				width, prefix := 2, `\x`
				if character > 0xff {
					width, prefix = 4, `\u`
				}
				if character > 0xffff {
					width, prefix = 8, `\U`
				}
				hex := strconv.FormatInt(int64(character), 16)
				escaped.WriteString(prefix + strings.Repeat("0", width-len(hex)) + hex)
			}
		}
		return quote + escaped.String() + quote
	case []any:
		if len(typed) == 0 {
			return "[]"
		}
	case analyticsObject:
		if len(typed) == 0 {
			return "{}"
		}
	case json.Number:
		return analyticsNumber(typed)
	}
	return analyticsString(value)
}

func analyticsNumber(value json.Number) string {
	if !strings.ContainsAny(string(value), ".eE") {
		return string(value)
	}
	number, _ := value.Float64()
	if math.IsInf(number, 1) {
		return "inf"
	}
	if math.IsInf(number, -1) {
		return "-inf"
	}
	scientific := strconv.FormatFloat(number, 'e', -1, 64)
	parts := strings.Split(scientific, "e")
	exponent, _ := strconv.Atoi(parts[1])
	if exponent < -4 || exponent >= 16 {
		return scientific
	}
	result := strconv.FormatFloat(number, 'f', -1, 64)
	if !strings.Contains(result, ".") {
		result += ".0"
	}
	return result
}

func analyticsTrim(value string) string {
	return strings.TrimFunc(value, func(character rune) bool {
		return unicode.IsSpace(character) || character >= 0x1c && character <= 0x1f
	})
}

func analyticsEventKey(r *http.Request, now time.Time) bson.M {
	payload := analyticsEventPayload(r)
	event := analyticsTrim(analyticsString(payload["event"]))
	if event != "map_interaction" && event != "external_link" && event != "demo_search" {
		return nil
	}
	host, scheme := r.Host, "http"
	if r.TLS != nil {
		scheme = "https"
	}
	peer, _, _ := net.SplitHostPort(r.RemoteAddr)
	if address := net.ParseIP(peer); address != nil && address.IsLoopback() {
		if forwarded := r.Header.Get("X-Forwarded-Host"); forwarded != "" {
			parts := strings.Split(forwarded, ",")
			host = strings.TrimSpace(parts[len(parts)-1])
		}
		if forwarded := r.Header.Get("X-Forwarded-Proto"); forwarded != "" {
			parts := strings.Split(forwarded, ",")
			scheme = strings.TrimSpace(parts[len(parts)-1])
		}
	}
	if scheme == "https" {
		host = strings.TrimSuffix(host, ":443")
	} else if scheme == "http" {
		host = strings.TrimSuffix(host, ":80")
	}
	landing, err := url.Parse(r.Header.Get("Referer"))
	if err != nil {
		return nil
	}
	currentHost := strings.ToLower(strings.Split(host, ":")[0])
	referrerHost := strings.ToLower(landing.Hostname())
	if referrerHost != "" && referrerHost != currentHost {
		return nil
	}
	resource := []rune(analyticsTrim(analyticsString(payload["resource_id"])))
	if len(resource) > 200 {
		resource = resource[:200]
	}
	if event == "demo_search" {
		path := landing.EscapedPath()
		listing := analyticsListing.MatchString(path) || path == "/demonstrations" || path == "/cities" || path == "/mielenosoitukset-tanaan" || path == "/submit"
		if len(resource) < 2 || !listing || landing.Scheme != scheme || landing.Host != host || landing.User != nil || r.Header.Get("Sec-Fetch-Site") == "cross-site" {
			return nil
		}
	}
	userAgent := strings.TrimSpace(r.Header.Get("User-Agent"))
	if analyticsBots.MatchString(userAgent) {
		return nil
	}
	device := "other"
	switch {
	case analyticsMobile.MatchString(userAgent):
		device = "mobile"
	case analyticsTablet.MatchString(userAgent):
		device = "tablet"
	case analyticsDesktop.MatchString(userAgent):
		device = "desktop"
	}
	referrer := "direct"
	if referrerHost != "" {
		referrer = "internal"
	}
	local := now.In(analyticsLocation)
	key := bson.M{"date": local.Format("2006-01-02"), "hour": local.Hour(), "event": event, "language": "fi", "device": device, "referrer": referrer}
	if len(resource) > 0 {
		key["resource_id"] = string(resource)
	}
	return key
}
