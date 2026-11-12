package main

import (
	"context"
	"errors"
	"strconv"

	"go.mongodb.org/mongo-driver/v2/mongo"
)

// dbErrorKind names the class of a failed database read for the service log.
// Driver messages can carry the connection string or host, so only the class
// and a server error code are logged. Without it every outage looked the same:
// the November 2026 series 503s were connection failures to the database host,
// not a data problem, and the log could not tell them apart.
func dbErrorKind(err error) string {
	var command mongo.CommandError
	switch {
	case err == nil:
		return "none"
	case errors.Is(err, context.Canceled):
		return "canceled"
	case errors.Is(err, context.DeadlineExceeded), mongo.IsTimeout(err):
		return "timeout"
	case mongo.IsNetworkError(err):
		return "network"
	case errors.As(err, &command) && command.Code != 0:
		return "server " + strconv.Itoa(int(command.Code))
	default:
		return "other"
	}
}
