package main

import (
	"io"
	"regexp"
	"strconv"
	"strings"

	"go.mongodb.org/mongo-driver/v2/bson"
	"golang.org/x/net/html"
)

var markdownTrailingSpace = regexp.MustCompile(`[ \t]+\n`)
var markdownBlankLines = regexp.MustCompile(`\n{3,}`)

func demonstrationPayload(doc bson.M, lang string) bson.M {
	payload := publicPayload(doc, lang)
	payload["suggestion"] = suggestionFields(doc, payload)
	return payload
}

func descriptionMarkdown(value any) string {
	stored, _ := value.(string)
	parser := html.NewTokenizer(strings.NewReader(strings.TrimSpace(stored)))
	var result strings.Builder
	lists := []int{}
	links := []string{}
	newline := func(count int) {
		current := result.String()
		missing := count - len(current) + len(strings.TrimRight(current, "\n"))
		if missing > 0 {
			result.WriteString(strings.Repeat("\n", missing))
		}
	}
	for {
		kind := parser.Next()
		if kind == html.ErrorToken {
			if parser.Err() != io.EOF {
				return ""
			}
			break
		}
		if kind == html.TextToken {
			result.Write(parser.Text())
			continue
		}
		if kind != html.StartTagToken && kind != html.EndTagToken && kind != html.SelfClosingTagToken {
			continue
		}
		token := parser.Token()
		endings := []bool{kind == html.EndTagToken}
		if kind == html.SelfClosingTagToken {
			endings = append(endings, true)
		}
		for _, ending := range endings {
			switch token.Data {
			case "p", "div", "blockquote":
				newline(2)
			case "br":
				if !ending {
					newline(1)
				}
			case "strong", "b":
				result.WriteString("**")
			case "em", "i":
				result.WriteString("*")
			case "h1", "h2", "h3", "h4", "h5", "h6":
				newline(2)
				if !ending {
					level, _ := strconv.Atoi(token.Data[1:])
					result.WriteString(strings.Repeat("#", level) + " ")
				}
			case "ul", "ol":
				if ending {
					if len(lists) > 0 {
						lists = lists[:len(lists)-1]
					}
					newline(2)
				} else {
					newline(1)
					index := -1
					if token.Data == "ol" {
						index = 0
					}
					lists = append(lists, index)
				}
			case "li":
				newline(1)
				if !ending {
					marker := "- "
					if len(lists) > 0 && lists[len(lists)-1] >= 0 {
						lists[len(lists)-1]++
						marker = strconv.Itoa(lists[len(lists)-1]) + ". "
					}
					result.WriteString(strings.Repeat("  ", max(len(lists)-1, 0)) + marker)
				}
			case "a":
				if ending {
					if len(links) > 0 {
						target := links[len(links)-1]
						links = links[:len(links)-1]
						if target != "" {
							result.WriteString("](" + target + ")")
						}
					}
				} else {
					target := ""
					for _, attr := range token.Attr {
						if attr.Key == "href" {
							candidate := strings.TrimSpace(attr.Val)
							scheme, _, _ := strings.Cut(candidate, ":")
							if strings.EqualFold(scheme, "https") || strings.EqualFold(scheme, "http") || strings.EqualFold(scheme, "mailto") {
								target = candidate
							}
						}
					}
					links = append(links, target)
					if target != "" {
						result.WriteString("[")
					}
				}
			}
		}
	}
	return strings.TrimSpace(markdownBlankLines.ReplaceAllString(markdownTrailingSpace.ReplaceAllString(result.String(), "\n"), "\n\n"))
}

func suggestionText(value any) string {
	text, _ := value.(string)
	if strings.EqualFold(strings.TrimSpace(text), "none") || strings.EqualFold(strings.TrimSpace(text), "null") {
		return ""
	}
	return text
}

func legacyRouteList(value string) ([]string, bool) {
	remaining := strings.TrimSpace(value)
	if !strings.HasPrefix(remaining, "[") || !strings.HasSuffix(remaining, "]") {
		return nil, false
	}
	remaining = strings.TrimSpace(remaining[1 : len(remaining)-1])
	result := []string{}
	for remaining != "" {
		quote := remaining[0]
		if quote != '\'' && quote != '"' {
			return nil, false
		}
		remaining = remaining[1:]
		var item strings.Builder
		for remaining != "" && remaining[0] != quote {
			character, _, tail, err := strconv.UnquoteChar(remaining, quote)
			if err != nil {
				return nil, false
			}
			item.WriteRune(character)
			remaining = tail
		}
		if remaining == "" {
			return nil, false
		}
		if cleaned := strings.TrimSpace(item.String()); cleaned != "" {
			result = append(result, cleaned)
		}
		remaining = strings.TrimSpace(remaining[1:])
		if remaining != "" {
			if remaining[0] != ',' {
				return nil, false
			}
			remaining = strings.TrimSpace(remaining[1:])
		}
	}
	return result, true
}

func suggestionFields(doc bson.M, public bson.M) bson.M {
	fields := bson.M{}
	for _, field := range []string{"title", "date", "start_time", "end_time", "city", "address", "facebook"} {
		fields[field] = suggestionText(doc[field])
	}
	fields["date"] = suggestionText(public["date"])
	fields["description_markdown"] = descriptionMarkdown(doc["description"])
	tags := []string{}
	for _, tag := range stringsOnly(doc["tags"]) {
		if tag = strings.TrimSpace(strings.TrimLeft(strings.TrimSpace(tag), "#")); tag != "" {
			tags = append(tags, tag)
		}
	}
	fields["tags"] = strings.Join(tags, ", ")
	fields["route"] = strings.Join(routeStops(doc["route"]), ", ")
	organizers := []string{}
	for _, organizer := range public["organizers"].([]bson.M) {
		name := strings.TrimSpace(suggestionText(organizer["name"]))
		details := []string{}
		for _, key := range []string{"email", "website"} {
			if value := strings.TrimSpace(suggestionText(organizer[key])); value != "" {
				details = append(details, value)
			}
		}
		if len(details) > 0 {
			if name != "" {
				name += " (" + strings.Join(details, ", ") + ")"
			} else {
				name = strings.Join(details, ", ")
			}
		}
		if name != "" {
			organizers = append(organizers, name)
		}
	}
	fields["organizers"] = strings.Join(organizers, "\n")
	for _, item := range array(doc["organizers"]) {
		organizer := object(item)
		private, privateOK := organizer["is_private"].(bool)
		showName, _ := organizer["show_name_public"].(bool)
		showEmail, _ := organizer["show_email_public"].(bool)
		redacted, _ := organizer["suggestion_redacted"].(bool)
		_, hasPrivate := organizer["is_private"]
		if redacted || (private && !showName) || (hasPrivate && !privateOK) || (!showEmail && nonblank(organizer["email"])) {
			fields["organizers_current"] = fields["organizers"]
			fields["organizers"] = ""
			break
		}
	}
	return fields
}
