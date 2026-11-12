package main

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"net"
	"net/http"
	"net/url"
	"time"

	"go.mongodb.org/mongo-driver/v2/bson"
)

// Flask remains the authority for its signed session cookies. Only the account
// ID is used for the private admin case; it grants no submission privileges.
func submissionActor(ctx context.Context, request *http.Request, config submissionConfig) (bson.ObjectID, error) {
	if request.Header.Get("Cookie") == "" {
		return bson.NilObjectID, nil
	}
	if config.SessionSocket == "" {
		return bson.NilObjectID, errors.New("session bridge unavailable")
	}
	transport := &http.Transport{DialContext: func(ctx context.Context, _, _ string) (net.Conn, error) {
		return (&net.Dialer{}).DialContext(ctx, "unix", config.SessionSocket)
	}}
	defer transport.CloseIdleConnections()
	client := &http.Client{Transport: transport, Timeout: time.Second, CheckRedirect: func(*http.Request, []*http.Request) error { return errors.New("session redirect") }}
	origin, err := url.Parse(config.Origin)
	if err != nil {
		return bson.NilObjectID, err
	}
	// Gunicorn speaks plain HTTP over its local socket, even for HTTPS visitors.
	call, err := http.NewRequestWithContext(ctx, "GET", "http://"+origin.Host+"/api/session", nil)
	if err != nil {
		return bson.NilObjectID, err
	}
	call.Header.Set("Cookie", request.Header.Get("Cookie"))
	call.Header.Set("Accept", "application/json")
	call.Header.Set("X-Forwarded-Proto", origin.Scheme)
	if address := submissionClientAddress(request); net.ParseIP(address) != nil {
		call.Header.Set("X-Forwarded-For", address)
	}
	response, err := client.Do(call)
	if err != nil {
		return bson.NilObjectID, err
	}
	defer response.Body.Close()
	if response.StatusCode != 200 {
		return bson.NilObjectID, errors.New("session read unavailable")
	}
	var summary struct {
		Authenticated *bool  `json:"authenticated"`
		ID            string `json:"actor_id"`
	}
	if err := json.NewDecoder(io.LimitReader(response.Body, 64<<10)).Decode(&summary); err != nil {
		return bson.NilObjectID, err
	}
	if summary.Authenticated == nil {
		return bson.NilObjectID, errors.New("invalid session summary")
	}
	if !*summary.Authenticated {
		return bson.NilObjectID, nil
	}
	return bson.ObjectIDFromHex(summary.ID)
}
