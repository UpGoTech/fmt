# Troubleshooting

Start with `fmt doctor`, `fmt list` and `fmt logs <site>`.

| Symptom | Cause and fix |
|---|---|
| `create` ends with "ping not OK yet" | Certificate not issued yet. Run `fmt ssl status <site>`. If it shows "Traefik default certificate", see the next row. |
| Traefik log: `NXDOMAIN looking up A` | Let's Encrypt did not see your DNS record yet. Check `dig +short <site> @8.8.8.8`, then `docker restart <traefik container>`. Traefik does not retry by itself. Limit: about 5 failed validations per hostname per hour. |
| Traefik log: `forbidden by policy` | Let's Encrypt refuses `example.com` and similar. Use a real domain, or `--local`. |
| Warning that the domain resolves elsewhere | Expected behind Cloudflare's proxy. Otherwise fix the A record. `--strict-dns` turns the warning into an error. |
| `No running Traefik container found` | Answer yes to the install prompt or run `fmt traefik install`. |
| Site shows 404 from Traefik | Wrong network or entrypoint names. Pass `--network` and `--resolver`, check `docker inspect <traefik>`. |
| `curl -I` returns 403 on `/api/method/ping` | HEAD is rejected by Frappe. Use `curl -s <url>` (GET). |
| Update failed, site in maintenance mode | `fmt rollback <site>` restores the last backup with the old image. |
| Port 80 or 443 already in use (macOS dev) | Stop other proxies, for example Frappe Manager's global nginx. |
| `/opt/fmt` permission denied | Run as root or set `FMT_HOME` to a writable directory. |

## Files per site

`$FMT_HOME/<site-with-dashes>/`: `compose.yaml`, `compose.traefik.yaml`, `.env` (secrets, mode 600), `apps.json`, `backups/<timestamp>/`.

## Environment

`FMT_HOME` (default `/opt/fmt`): where sites, the Traefik install and the image build cache live.
