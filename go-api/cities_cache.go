package main

import (
	"context"
	"encoding/json"
	"errors"
	"sync"
	"time"

	"golang.org/x/sync/singleflight"
)

type citiesCache struct {
	source citiesStore
	base   context.Context
	now    func() time.Time
	mu     sync.RWMutex
	day    string
	data   []byte
	loaded time.Time
	group  singleflight.Group
}

func (c *citiesCache) read(day string) []byte {
	c.mu.RLock()
	defer c.mu.RUnlock()
	if c.day == day && c.now().Sub(c.loaded) < time.Minute {
		return c.data
	}
	return nil
}

func (c *citiesCache) get(ctx context.Context) ([]byte, error) {
	day := localDay(c.now())
	if data := c.read(day); data != nil {
		return data, nil
	}
	result := c.group.DoChan(day, func() (any, error) {
		if data := c.read(day); data != nil {
			return data, nil
		}
		load, cancel := context.WithTimeout(c.base, 3*time.Second)
		defer cancel()
		payload, err := c.source.FindCities(load, day)
		if err != nil {
			return nil, err
		}
		data, err := json.Marshal(payload)
		if err != nil {
			return nil, err
		}
		data = append(data, '\n')
		c.mu.Lock()
		c.day = day
		c.data = data
		c.loaded = c.now()
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

func (s *cachedDetailStore) FindCitiesJSON(ctx context.Context) ([]byte, error) {
	if s.cities == nil {
		return nil, errors.New("city directory unavailable")
	}
	return s.cities.get(ctx)
}
