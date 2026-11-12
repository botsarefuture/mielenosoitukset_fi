package main

import (
	"container/list"
	"context"
	"encoding/json"
	"errors"
	"sync"
	"time"

	"go.mongodb.org/mongo-driver/v2/bson"
	"golang.org/x/sync/singleflight"
)

const (
	organizationTTL      = 60 * time.Second
	organizationMaxItems = 128
	organizationMaxBytes = 2 << 20
)

type organizationEntry struct {
	id        bson.ObjectID
	data      []byte
	expiresAt time.Time
}

type organizationCache struct {
	source organizationStore
	base   context.Context
	now    func() time.Time
	mu     sync.Mutex
	items  map[bson.ObjectID]*list.Element
	order  *list.List
	bytes  int
	group  singleflight.Group
	sem    chan struct{}
	queue  chan struct{}
}

func newOrganizationCache(source organizationStore, base context.Context) *organizationCache {
	return &organizationCache{source: source, base: base, now: time.Now,
		items: map[bson.ObjectID]*list.Element{}, order: list.New(),
		sem: make(chan struct{}, 4), queue: make(chan struct{}, 16)}
}

func (c *organizationCache) remove(element *list.Element) {
	entry := element.Value.(*organizationEntry)
	delete(c.items, entry.id)
	c.bytes -= len(entry.id) + len(entry.data)
	c.order.Remove(element)
}

func (c *organizationCache) read(id bson.ObjectID) ([]byte, bool) {
	c.mu.Lock()
	defer c.mu.Unlock()
	element := c.items[id]
	if element == nil {
		return nil, false
	}
	entry := element.Value.(*organizationEntry)
	if !c.now().Before(entry.expiresAt) {
		c.remove(element)
		return nil, false
	}
	c.order.MoveToFront(element)
	return entry.data, true
}

func (c *organizationCache) put(id bson.ObjectID, data []byte) {
	if len(id)+len(data) > 64<<10 {
		return
	}
	c.mu.Lock()
	defer c.mu.Unlock()
	if old := c.items[id]; old != nil {
		c.remove(old)
	}
	c.items[id] = c.order.PushFront(&organizationEntry{id, data, c.now().Add(organizationTTL)})
	c.bytes += len(id) + len(data)
	for len(c.items) > organizationMaxItems || c.bytes > organizationMaxBytes {
		c.remove(c.order.Back())
	}
}

func (c *organizationCache) get(ctx context.Context, id bson.ObjectID) ([]byte, error) {
	if data, ok := c.read(id); ok {
		return data, nil
	}
	result := c.group.DoChan(id.Hex(), func() (any, error) {
		if data, ok := c.read(id); ok {
			return data, nil
		}
		select {
		case c.queue <- struct{}{}:
			defer func() { <-c.queue }()
		default:
			return nil, errors.New("organization queue full")
		}
		loadCtx, cancel := context.WithTimeout(c.base, 3*time.Second)
		defer cancel()
		select {
		case c.sem <- struct{}{}:
			defer func() { <-c.sem }()
		case <-loadCtx.Done():
			return nil, loadCtx.Err()
		}
		profile, err := c.source.FindOrganization(loadCtx, id)
		if err != nil {
			return nil, err
		}
		data, err := json.Marshal(profile)
		if err != nil {
			return nil, err
		}
		data = append(data, '\n')
		c.put(id, data)
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

func (s *cachedDetailStore) FindOrganizationJSON(ctx context.Context, id bson.ObjectID) ([]byte, error) {
	if s.organization == nil {
		return nil, errors.New("organization store unavailable")
	}
	return s.organization.get(ctx, id)
}
