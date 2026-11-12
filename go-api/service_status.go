package main

import (
	"context"
	"net/http"
	"sync"
	"time"
)

type statusService struct {
	Name    string `json:"name"`
	Status  string `json:"status"`
	Message string `json:"message"`
}

type serviceStatus struct {
	OverallOK bool            `json:"overall_ok"`
	Services  []statusService `json:"services"`
	UpdatedAt string          `json:"updated_at"`
	LatencyMS int64           `json:"latency_ms"`
}

func serviceStatusHandler(ping func(context.Context) error) http.Handler {
	var mutex sync.Mutex
	var checked time.Time
	var service statusService
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Cache-Control", "no-store")
		w.Header().Set("X-Robots-Tag", "noindex")
		started := time.Now()
		mutex.Lock()
		if checked.IsZero() || clock().Sub(checked) >= time.Minute {
			ctx, cancel := context.WithTimeout(context.Background(), time.Second)
			err := ping(ctx)
			cancel()
			service = statusService{"Tietokanta", "ok", "Yhteys kunnossa"}
			if err != nil {
				service.Status, service.Message = "err", "Ei vastaa"
			}
			checked = clock()
		}
		current := service
		mutex.Unlock()
		result := serviceStatus{current.Status == "ok", []statusService{current},
			time.Now().UTC().Format("02.01.2006 15:04:05 UTC"), time.Since(started).Milliseconds()}
		if r.Method == http.MethodHead {
			w.Header().Set("Content-Type", "application/json; charset=utf-8")
			w.WriteHeader(http.StatusOK)
			return
		}
		writeJSON(w, http.StatusOK, result)
	})
}
