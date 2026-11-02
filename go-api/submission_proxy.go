package main

import (
	_ "embed"
	"encoding/json"
	"net"
	"net/http"
	"strings"
)

//go:generate python3 ../scripts/generate_proxy_networks.py
//go:embed cloudflare_networks.json
var submissionProxyJSON []byte

func submissionCloudflarePeer(value string) bool {
	address := net.ParseIP(value)
	for _, network := range submissionProxyNetworks {
		if network.Contains(address) {
			return true
		}
	}
	return false
}

var submissionProxyNetworks = func() []*net.IPNet {
	var values []string
	if json.Unmarshal(submissionProxyJSON, &values) != nil {
		panic("invalid generated proxy data")
	}
	networks := []*net.IPNet{}
	for _, value := range values {
		_, network, err := net.ParseCIDR(value)
		if err != nil {
			panic("invalid generated proxy network")
		}
		networks = append(networks, network)
	}
	return networks
}()

// Match Flask's Cloudflare trust policy after the trusted local Apache hop.
func submissionVisitorAddress(r *http.Request, proxy string) string {
	if submissionCloudflarePeer(proxy) {
		for _, header := range []string{"CF-Connecting-IPv6", "CF-Connecting-IP"} {
			if address := net.ParseIP(strings.TrimSpace(r.Header.Get(header))); address != nil {
				return address.String()
			}
		}
	}
	return proxy
}
