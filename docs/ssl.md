# SSL and renewal

`fmt` only writes Traefik router labels (`tls.certresolver=<resolver>`). Traefik requests, stores and renews the certificates.

## Renewal

Let's Encrypt certificates last 90 days. Traefik renews them about 30 days before expiry as long as it runs. Requirements:

1. `acme.json` on a persistent volume (`fmt traefik install` does this: `$FMT_HOME/traefik/letsencrypt`).
2. Port 80 reachable from the internet for HTTP-01. The HTTP router that redirects to HTTPS is kept so challenges work.
3. The domain's DNS A record points to the server.

Wildcard domains and domains behind Cloudflare's proxy need a DNS-01 resolver configured in Traefik; pass it with `--resolver`.

## Commands

```bash
fmt doctor                       # Docker, Traefik, resolver, acme.json volume, ports
fmt ssl status erp.example.com   # live issuer and expiry; warns under 14 days
fmt create erp.example.com --strict-dns   # refuse to create when DNS is wrong
```

## Troubleshooting

- `ssl status` says "Traefik default certificate": issuance failed. Check `docker logs fmt-traefik`, DNS and port 80. After fixing, `docker restart fmt-traefik`.
- Let's Encrypt allows about 5 failed validations per hostname per hour. Test with a staging resolver first.
- Certificates lost after Traefik restarts: `acme.json` is not on a volume.
