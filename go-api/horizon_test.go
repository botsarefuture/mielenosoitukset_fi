package main

import "testing"

func TestListingDatesStopOpenEndedUpcomingReadsAtTheHorizon(t *testing.T) {
	open := listingDates(listingQuery{Day: "2026-11-10"})
	if open["$gte"] != "2026-11-10" || open["$lte"] != "2028-11-09" {
		t.Fatalf("open-ended upcoming read = %v", open)
	}
	explicit := listingDates(listingQuery{Day: "2026-11-10", End: "2031-01-01"})
	if explicit["$lte"] != "2031-01-01" {
		t.Fatalf("explicit end date must be honoured, got %v", explicit)
	}
	window := listingDates(listingQuery{Day: "2026-11-10", MaxDays: 60})
	if window["$lte"] != "2027-01-09" {
		t.Fatalf("max_days_till window changed: %v", window)
	}
	past := listingDates(listingQuery{Day: "2026-11-10", InPast: true})
	if _, lower := past["$gte"]; lower || past["$lte"] != "2028-11-09" {
		t.Fatalf("in_past reads keep the past but stop at the horizon, got %v", past)
	}
	today := listingDates(listingQuery{Day: "2026-11-10", Today: true})
	if today["$eq"] != "2026-11-10" || len(today) != 1 {
		t.Fatalf("today read changed: %v", today)
	}
}
