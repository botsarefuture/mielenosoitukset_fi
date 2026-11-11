package main

import (
	"testing"

	"go.mongodb.org/mongo-driver/v2/bson"
)

func TestCardImagePrefersUploadedPicture(t *testing.T) {
	const preview = "https://cdn.example/DEM/demo_preview-10.jpg"
	const oldPreview = "https://cdn.example/DEM/demo_preview-3.jpg"
	cases := []struct {
		name string
		doc  bson.M
		want string
	}{
		{"uploaded cover beats preview",
			bson.M{"cover_picture": "https://cdn.example/DEM/demo_pics-7.jpg", "preview_image": preview},
			"https://cdn.example/DEM/demo_pics-7.jpg"},
		{"gallery comes first",
			bson.M{"gallery_images": bson.A{"https://cdn.example/g1.jpg"}, "img": "https://cdn.example/i.jpg", "preview_image": preview},
			"https://cdn.example/g1.jpg"},
		{"stale generated cover falls through to current preview",
			bson.M{"cover_picture": oldPreview, "img": oldPreview, "preview_image": preview},
			preview},
		{"legacy static preview is generated too",
			bson.M{"cover_picture": "/static/demo_preview/abc.png", "preview_image": preview},
			preview},
		{"only an old generated image remains",
			bson.M{"cover_picture": oldPreview},
			oldPreview},
		{"nothing", bson.M{}, ""},
	}
	for _, tc := range cases {
		if got := cardImage(tc.doc); got != tc.want {
			t.Errorf("%s: cardImage = %q, want %q", tc.name, got, tc.want)
		}
	}
}

func TestListingAndHomeCardsUseCardImage(t *testing.T) {
	id := bson.NewObjectID()
	doc := bson.M{"_id": id, "title": "Mielenosoitus", "date": "2026-12-01",
		"cover_picture": "https://cdn.example/DEM/demo_preview-3.jpg",
		"img":           "https://cdn.example/DEM/demo_pics-9.jpg",
		"preview_image": "https://cdn.example/DEM/demo_preview-10.jpg"}
	if got := listingCard(doc, "fi")["cover_image"]; got != "https://cdn.example/DEM/demo_pics-9.jpg" {
		t.Fatalf("listing cover_image = %v", got)
	}
	cards := homeCards([]bson.M{doc}, "fi")
	if len(cards) != 1 || cards[0]["cover_image"] != "https://cdn.example/DEM/demo_pics-9.jpg" {
		t.Fatalf("home cards = %v", cards)
	}
}
