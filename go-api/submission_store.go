package main

import (
	"context"
	"errors"
	"time"

	"go.mongodb.org/mongo-driver/v2/bson"
	"go.mongodb.org/mongo-driver/v2/mongo"
	"go.mongodb.org/mongo-driver/v2/mongo/options"
)

var errStaleSubmission = errors.New("submission token already used for different content")

func checkSubmissionIndexes(ctx context.Context, db *mongo.Database) error {
	cursor, err := db.Collection("demo_submission_tokens").Indexes().List(ctx)
	if err != nil {
		return err
	}
	defer cursor.Close(ctx)
	for cursor.Next(ctx) {
		var index struct {
			Key    bson.D `bson:"key"`
			Unique bool   `bson:"unique"`
		}
		if err := cursor.Decode(&index); err != nil {
			return err
		}
		if index.Unique && len(index.Key) == 1 && index.Key[0].Key == "token" {
			return nil
		}
	}
	return errors.New("existing unique submission token index required")
}

type submissionReservation struct {
	ID          bson.ObjectID `bson:"_id"`
	DemoID      bson.ObjectID `bson:"demo_id"`
	Fingerprint string        `bson:"fingerprint"`
	Created     time.Time     `bson:"created_at"`
	Event       bson.M        `bson:"pending_event"`
	Submitter   bson.M        `bson:"pending_submitter"`
	Status      string        `bson:"status"`
	Image       []byte        `bson:"pending_image"`
}

func submissionUpsert(ctx context.Context, collection *mongo.Collection, id any, fields bson.M) error {
	_, err := collection.UpdateOne(ctx, bson.M{"_id": id}, bson.M{"$setOnInsert": fields}, options.UpdateOne().SetUpsert(true))
	// Concurrent insert-only upserts can race on _id. An existing record is success.
	if mongo.IsDuplicateKeyError(err) {
		if found := collection.FindOne(ctx, bson.M{"_id": id}, options.FindOne().SetProjection(bson.M{"_id": 1})).Err(); found == nil {
			return nil
		}
	}
	return err
}

func reserveSubmission(ctx context.Context, db *mongo.Database, input submissionInput) (submissionReservation, error) {
	tokens := db.Collection("demo_submission_tokens")
	var binding struct {
		Fingerprint string `bson:"fingerprint"`
	}
	err := tokens.FindOneAndUpdate(ctx, bson.M{"token": input.Token}, bson.M{"$setOnInsert": bson.M{
		"fingerprint": input.Fingerprint, "status": "go_bound", "created_at": time.Now().UTC(),
	}}, options.FindOneAndUpdate().SetUpsert(true).SetReturnDocument(options.After)).Decode(&binding)
	if mongo.IsDuplicateKeyError(err) {
		err = tokens.FindOne(ctx, bson.M{"token": input.Token}).Decode(&binding)
	}
	if err != nil {
		return submissionReservation{}, err
	}
	if binding.Fingerprint != "" && binding.Fingerprint != input.Fingerprint {
		return submissionReservation{}, errStaleSubmission
	}
	key := "go-fingerprint:" + input.Fingerprint
	var reservation submissionReservation
	// A reservation key can be reused after the legacy twelve-hour window. Keep
	// its old _id intact because a pending delivery job may still refer to it.
	err = tokens.FindOne(ctx, bson.M{"token": key}).Decode(&reservation)
	if err != nil && !errors.Is(err, mongo.ErrNoDocuments) {
		return submissionReservation{}, err
	}
	if err == nil && reservation.Created.Before(time.Now().Add(-12*time.Hour)) && reservation.Status == "completed" {
		_, err = tokens.UpdateOne(ctx, bson.M{"_id": reservation.ID, "token": key}, bson.M{"$set": bson.M{"token": key + ":" + reservation.ID.Hex()}})
		if err != nil {
			return submissionReservation{}, err
		}
	}
	now := time.Now().UTC()
	fields := bson.M{"demo_id": bson.NewObjectID(), "fingerprint": input.Fingerprint, "created_at": now, "status": "go_preparing",
		"pending_event": input.Event, "pending_submitter": input.Submitter, "pending_image": input.Image, "go_submission": true}
	err = tokens.FindOneAndUpdate(ctx, bson.M{"token": key}, bson.M{"$setOnInsert": fields},
		options.FindOneAndUpdate().SetUpsert(true).SetReturnDocument(options.After)).Decode(&reservation)
	if mongo.IsDuplicateKeyError(err) {
		err = tokens.FindOne(ctx, bson.M{"token": key}).Decode(&reservation)
	}
	return reservation, err
}

// Each write is insert-only and uses a reserved ID. A crash at any point can be
// resumed without a replica-set transaction and without reverting moderation.
func finishSubmission(ctx context.Context, db *mongo.Database, item submissionReservation) error {
	if item.Status == "completed" {
		return nil
	}
	if item.DemoID.IsZero() || item.Event == nil || item.Submitter == nil {
		return errors.New("invalid reservation")
	}
	item.Event["created_datetime"] = item.Created
	item.Event["last_modified"] = item.Created
	item.Event["submission_delivery_pending"] = true
	if err := submissionUpsert(ctx, db.Collection("demonstrations"), item.DemoID, item.Event); err != nil {
		return err
	}
	item.Submitter["demonstration_id"] = item.DemoID
	item.Submitter["submitted_at"] = item.Created
	// Imported media metadata is private preparation data, not submitter identity.
	contact := bson.M{}
	for _, key := range []string{"demonstration_id", "submitter_role", "submitter_name", "submitter_email", "accept_terms", "submitted_at"} {
		contact[key] = item.Submitter[key]
	}
	if err := submissionUpsert(ctx, db.Collection("submitters"), item.DemoID, contact); err != nil {
		return err
	}
	job := bson.M{"demo_id": item.DemoID, "status": "pending", "created_at": item.Created, "notification_type": "go_submission_prepare",
		"submission_record": item.ID, "marks_admin_contact": true, "delivery_tracking_version": 1}
	if err := submissionUpsert(ctx, db.Collection("demo_notifications_queue"), item.DemoID, job); err != nil {
		return err
	}
	_, err := db.Collection("demo_submission_tokens").UpdateOne(ctx, bson.M{"_id": item.ID}, bson.M{"$set": bson.M{"status": "completed", "completed_at": time.Now().UTC()}})
	return err
}

func legacySubmissionDuplicate(ctx context.Context, db *mongo.Database, input submissionInput) (bson.ObjectID, error) {
	var row struct {
		ID bson.ObjectID `bson:"demo_id"`
	}
	err := db.Collection("demo_submission_tokens").FindOne(ctx, bson.M{"fingerprint": input.Fingerprint, "status": "completed", "created_at": bson.M{"$gte": time.Now().Add(-12 * time.Hour)}}).Decode(&row)
	if errors.Is(err, mongo.ErrNoDocuments) {
		return bson.NilObjectID, nil
	}
	return row.ID, err
}

func resumeSubmission(ctx context.Context, db *mongo.Database, input submissionInput) (bson.ObjectID, error) {
	var item submissionReservation
	err := db.Collection("demo_submission_tokens").FindOne(ctx, bson.M{
		"token": "go-fingerprint:" + input.Fingerprint, "status": "go_preparing",
	}).Decode(&item)
	if errors.Is(err, mongo.ErrNoDocuments) {
		return bson.NilObjectID, nil
	}
	if err != nil {
		return bson.NilObjectID, err
	}
	return item.DemoID, finishSubmission(ctx, db, item)
}

func submissionConflicts(ctx context.Context, db *mongo.Database, input submissionInput) ([]bson.M, error) {
	filter := publicVisibility()
	filter["city"] = input.Event["city"]
	filter["date"] = input.Event["date"]
	filter["cancelled"] = bson.M{"$ne": true}
	cursor, err := db.Collection("demonstrations").Find(ctx, filter, options.Find().SetProjection(bson.M{"title": 1, "translations": 1, "address": 1, "date": 1}).SetLimit(501))
	if err != nil {
		return nil, err
	}
	defer cursor.Close(ctx)
	matches := []bson.M{}
	count := 0
	for cursor.Next(ctx) {
		count++
		if count > 500 {
			return nil, errors.New("duplicate search bound exceeded")
		}
		var candidate bson.M
		if err := cursor.Decode(&candidate); err != nil {
			return nil, err
		}
		if similarSubmission(candidate, submissionString(input.Event["title"]), submissionString(input.Event["address"])) && len(matches) < 10 {
			matches = append(matches, bson.M{"title": candidate["title"], "address": candidate["address"], "date": candidate["date"]})
		}
	}
	return matches, cursor.Err()
}

func recoverGoSubmissions(ctx context.Context, db *mongo.Database) {
	cursor, err := db.Collection("demo_submission_tokens").Find(ctx, bson.M{"token": bson.M{"$regex": "^go-fingerprint:"}, "status": "go_preparing"}, options.Find().SetLimit(20))
	if err != nil {
		return
	}
	defer cursor.Close(ctx)
	for cursor.Next(ctx) {
		var item submissionReservation
		if cursor.Decode(&item) == nil {
			_ = finishSubmission(ctx, db, item)
		}
	}
}
