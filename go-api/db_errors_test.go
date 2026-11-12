package main

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"log"
	"net/http/httptest"
	"strings"
	"testing"

	"go.mongodb.org/mongo-driver/v2/bson"
	"go.mongodb.org/mongo-driver/v2/mongo"
)

func TestDBErrorKind(t *testing.T) {
	for _, tc := range []struct {
		err  error
		want string
	}{
		{context.DeadlineExceeded, "timeout"},
		{fmt.Errorf("find: %w", context.DeadlineExceeded), "timeout"},
		{context.Canceled, "canceled"},
		{mongo.CommandError{Message: "connection(95.0.0.1:27017) reset", Labels: []string{"NetworkError"}}, "network"},
		{mongo.CommandError{Message: "auth", Code: 18, Name: "AuthenticationFailed"}, "server 18"},
		{errors.New("mongodb://user:secret@host"), "other"},
	} {
		if got := dbErrorKind(tc.err); got != tc.want {
			t.Errorf("dbErrorKind(%v)=%q want %q", tc.err, got, tc.want)
		}
	}
}

// The production series 503s of November 2026 were database connection
// failures. The log has to say so, and must still never carry the driver
// message, which can include the connection string.
func TestSeriesFailureLogsClassWithoutMessage(t *testing.T) {
	var buffer bytes.Buffer
	previous := log.Writer()
	log.SetOutput(&buffer)
	defer log.SetOutput(previous)
	parent := bson.NewObjectID()
	store := &fakeSeriesStore{err: mongo.CommandError{
		Message: "connection(mongodb://user:secret@db:27017) incomplete read of message header",
		Labels:  []string{"NetworkError"},
	}}
	w := httptest.NewRecorder()
	(&API{store}).handler().ServeHTTP(w, httptest.NewRequest("GET", "/api/series/"+parent.Hex(), nil))
	if w.Code != 503 {
		t.Fatalf("status=%d", w.Code)
	}
	logged := buffer.String()
	if !strings.Contains(logged, "Series database read failed (network)") || strings.Contains(logged, "secret") {
		t.Fatalf("log=%q", logged)
	}
}
