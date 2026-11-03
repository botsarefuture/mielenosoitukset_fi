package main

import (
	"context"
	"encoding/json"
	"errors"
	"sync"
	"time"

	"golang.org/x/sync/singleflight"
)

type calendarEntry struct {
	data   []byte
	loaded time.Time
}
type calendarCache struct {
	source calendarStore
	base   context.Context
	mu     sync.Mutex
	items  map[calendarMonth]calendarEntry
	group  singleflight.Group
	sem    chan struct{}
}

func (c *calendarCache) read(month calendarMonth) []byte {
	c.mu.Lock()
	defer c.mu.Unlock()
	entry := c.items[month]
	if time.Since(entry.loaded) < time.Minute {
		return entry.data
	}
	return nil
}

func (c *calendarCache) get(ctx context.Context, month calendarMonth) ([]byte, error) {
	if data := c.read(month); data != nil {
		return data, nil
	}
	result := c.group.DoChan(month.key(), func() (any, error) {
		if data := c.read(month); data != nil {
			return data, nil
		}
		select {
		case c.sem <- struct{}{}:
			defer func() { <-c.sem }()
		default:
			return nil, errors.New("calendar busy")
		}
		load, cancel := context.WithTimeout(c.base, 3*time.Second)
		defer cancel()
		payload, err := c.source.FindCalendar(load, month)
		if err != nil {
			return nil, err
		}
		data, err := json.Marshal(payload)
		if err != nil {
			return nil, err
		}
		c.mu.Lock()
		if len(c.items) >= 24 {
			var oldest calendarMonth
			var at time.Time
			for key, entry := range c.items {
				if at.IsZero() || entry.loaded.Before(at) {
					oldest, at = key, entry.loaded
				}
			}
			delete(c.items, oldest)
		}
		c.items[month] = calendarEntry{data: data, loaded: time.Now()}
		c.mu.Unlock()
		return data, nil
	})
	select {
	case loaded := <-result:
		if loaded.Err != nil {
			return nil, loaded.Err
		}
		return loaded.Val.([]byte), nil
	case <-ctx.Done():
		return nil, ctx.Err()
	}
}

func (s *cachedDetailStore) FindCalendarJSON(ctx context.Context, month calendarMonth) ([]byte, error) {
	if s.calendar == nil {
		return nil, errors.New("calendar unavailable")
	}
	return s.calendar.get(ctx, month)
}
