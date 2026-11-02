package main

import "go.mongodb.org/mongo-driver/v2/bson"

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
