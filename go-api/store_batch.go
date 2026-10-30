package main

import (
	"context"
	"hash/fnv"
	"time"

	"go.mongodb.org/mongo-driver/v2/bson"
	"go.mongodb.org/mongo-driver/v2/mongo/options"
)

// versionField must change on EVERY edit of a demonstration (a timestamp or a
// revision counter). ADAPT to your schema. If it's missing on a document, that
// document is simply re-fetched on every batch (correct, just less efficient).
const versionField = "updated_at"

// publicFilterAll is publicFilter without the single-ID part: every publicly
// visible demonstration, with the same moderation rules as FindPublic.
func publicFilterAll() bson.M {
	filter := publicFilter(bson.NilObjectID)
	delete(filter, "_id")
	expr := object(filter["$expr"])
	expr["$and"] = append(expr["$and"].(bson.A),
		bson.M{"$eq": bson.A{bson.M{"$type": "$_id"}, "objectId"}},
	)
	return filter
}

// PublicVersions is ONE query returning only _id and the version field of every
// public demonstration. Note: the moderation filter uses $expr, which MongoDB
// can't answer from an index alone, so the server reads the matching documents,
// but only two small fields cross the network and it runs once per batch.
func (s mongoStore) PublicVersions(ctx context.Context) (map[bson.ObjectID]int64, error) {
	cursor, err := s.collection.Find(ctx, publicFilterAll(),
		options.Find().SetProjection(bson.M{"_id": 1, versionField: 1}))
	if err != nil {
		return nil, err
	}
	defer cursor.Close(ctx)
	versions := make(map[bson.ObjectID]int64)
	for cursor.Next(ctx) {
		var row bson.M
		if err := cursor.Decode(&row); err != nil {
			return nil, err
		}
		if id, ok := row["_id"].(bson.ObjectID); ok {
			versions[id] = versionNumber(row[versionField])
		}
	}
	return versions, cursor.Err()
}

// FindPublicMany is ONE query for many demonstrations, with the same projection
// (including the organizer email consent logic) as FindPublic.
func (s mongoStore) FindPublicMany(ctx context.Context, ids []bson.ObjectID) (map[bson.ObjectID]bson.M, error) {
	filter := publicFilterAll()
	filter["_id"] = bson.M{"$in": ids}
	cursor, err := s.collection.Find(ctx, filter, options.Find().SetProjection(publicProjection()))
	if err != nil {
		return nil, err
	}
	defer cursor.Close(ctx)
	var docs []bson.M
	if err := cursor.All(ctx, &docs); err != nil {
		return nil, err
	}
	result := make(map[bson.ObjectID]bson.M, len(docs))
	for _, doc := range docs {
		if id, ok := doc["_id"].(bson.ObjectID); ok {
			result[id] = doc
		}
	}
	return result, nil
}

// versionNumber turns the version field into a non-zero int64; 0 means "no version".
func versionNumber(value any) int64 {
	var n int64
	switch v := value.(type) {
	case bson.DateTime:
		n = int64(v)
	case time.Time:
		n = v.UnixMilli()
	case int32:
		n = int64(v)
	case int64:
		n = v
	case int:
		n = int64(v)
	case float64:
		n = int64(v)
	case string:
		if v == "" {
			return 0
		}
		h := fnv.New64a()
		_, _ = h.Write([]byte(v))
		n = int64(h.Sum64())
	default:
		return 0
	}
	if n == 0 {
		n = 1
	}
	return n
}
