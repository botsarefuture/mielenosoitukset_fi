package main

import (
	"regexp"

	"go.mongodb.org/mongo-driver/v2/bson"
)

// publicDatedFilter is shared by homepage and listing reads. Scalar types
// prevent malformed array values from matching the public date range.
func publicDatedFilter() bson.M {
	filter := publicVisibility()
	expression := object(filter["$expr"])
	expression["$and"] = append(expression["$and"].(bson.A),
		bson.M{"$eq": bson.A{bson.M{"$type": "$date"}, "string"}},
		bson.M{"$eq": bson.A{bson.M{"$type": "$_id"}, "objectId"}})
	return filter
}

// User searches are literal text, never executable regular expressions.
func literalMatch(value string, exact bool) bson.Regex {
	pattern := regexp.QuoteMeta(value)
	if exact {
		pattern = "^" + pattern + "$"
	}
	return bson.Regex{Pattern: pattern, Options: "i"}
}

func appendTranslatedMatch(and bson.A, fields []string, value string, exact bool) bson.A {
	if value == "" {
		return and
	}
	or := bson.A{}
	for _, field := range fields {
		or = append(or, bson.M{field: literalMatch(value, exact)})
		if field == "title" || field == "description" || field == "tags" {
			for _, lang := range []string{"fi", "en", "sv"} {
				or = append(or, bson.M{"translations." + lang + "." + field: literalMatch(value, exact)})
			}
		}
	}
	return append(and, bson.M{"$or": or})
}
