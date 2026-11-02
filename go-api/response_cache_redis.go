package main

import (
	"context"
	"encoding/json"
	"errors"
	"net/url"
	"sync/atomic"
	"time"

	"github.com/redis/go-redis/v9"
)

const responseMaxBytes = 256 << 10

type cachedResponse struct {
	Body     []byte `json:"body"`
	Stored   int64  `json:"stored"`
	Lifetime int64  `json:"lifetime"`
}

type responseCache interface {
	get(context.Context, string) (cachedResponse, bool)
	put(context.Context, string, cachedResponse)
}

type redisResponseCache struct {
	client           *redis.Client
	namespace        string
	unavailableUntil atomic.Int64
}

// Sharing Redis must not mix staging and production databases with the same
// name on different MongoDB hosts. Credentials never enter the namespace.
func publicCacheSource(uri, database string) (string, error) {
	source, err := url.Parse(uri)
	if err != nil || source.Host == "" {
		return "", errors.New("invalid public cache source")
	}
	return source.Scheme + "://" + source.Host + "/" + database, nil
}

func newRedisResponseCache(rawURL, database string) (*redisResponseCache, error) {
	options, err := redis.ParseURL(rawURL)
	if err != nil {
		return nil, errors.New("invalid PUBLIC_REDIS_URL")
	}
	options.MaxRetries = -1
	options.DialTimeout = 100 * time.Millisecond
	options.ReadTimeout = 100 * time.Millisecond
	options.WriteTimeout = 100 * time.Millisecond
	options.PoolTimeout = 100 * time.Millisecond
	options.ContextTimeoutEnabled = true
	options.PoolSize = 8
	options.Protocol = 2
	return &redisResponseCache{client: redis.NewClient(options), namespace: responseKey("moso:public-api:v1", database)}, nil
}

func (c *redisResponseCache) get(ctx context.Context, key string) (cachedResponse, bool) {
	if time.Now().UnixNano() < c.unavailableUntil.Load() {
		return cachedResponse{}, false
	}
	ctx, cancel := context.WithTimeout(ctx, 100*time.Millisecond)
	defer cancel()
	data, err := c.client.Get(ctx, responseKey(c.namespace, key)).Bytes()
	if err != nil {
		if !errors.Is(err, redis.Nil) {
			c.backoff()
		}
		return cachedResponse{}, false
	}
	var value cachedResponse
	if len(data) > responseMaxBytes*2 || json.Unmarshal(data, &value) != nil || len(value.Body) > responseMaxBytes || !json.Valid(value.Body) {
		return cachedResponse{}, false
	}
	return value, true
}

// Bound this application's namespace to 256 responses (at most 64MiB of raw
// JSON), without changing Redis's global eviction settings or Flask's keys.
// The index expires too; expired response members are removed on each write.
const storePublicResponse = `
local expired = redis.call('ZRANGEBYSCORE', KEYS[1], '-inf', ARGV[1])
for _, key in ipairs(expired) do redis.call('DEL', key); redis.call('ZREM', KEYS[1], key) end
redis.call('SET', KEYS[2], ARGV[3], 'EX', ARGV[2])
redis.call('ZADD', KEYS[1], tonumber(ARGV[1])+tonumber(ARGV[2]), KEYS[2])
local excess = redis.call('ZCARD', KEYS[1]) - 256
if excess > 0 then
  local expired = redis.call('ZRANGE', KEYS[1], 0, excess-1)
  for _, key in ipairs(expired) do redis.call('DEL', key); redis.call('ZREM', KEYS[1], key) end
end
redis.call('EXPIRE', KEYS[1], 7200)
return 1
`

func (c *redisResponseCache) put(ctx context.Context, key string, value cachedResponse) {
	if len(value.Body) > responseMaxBytes || value.Lifetime <= 0 || value.Lifetime > 3600 || !json.Valid(value.Body) {
		return
	}
	if time.Now().UnixNano() < c.unavailableUntil.Load() {
		return
	}
	data, err := json.Marshal(value)
	if err != nil {
		return
	}
	ctx, cancel := context.WithTimeout(ctx, 100*time.Millisecond)
	defer cancel()
	if c.client.Eval(ctx, storePublicResponse, []string{c.namespace + ":index", responseKey(c.namespace, key)},
		value.Stored, value.Lifetime, data).Err() != nil {
		c.backoff()
	}
}

func (c *redisResponseCache) backoff() {
	c.unavailableUntil.Store(time.Now().Add(30 * time.Second).UnixNano())
}
