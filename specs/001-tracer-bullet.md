# Spec 001: Frappe Manager - Traefik (fmt)

Production Frappe/ERPNext/HRMS sites on a VPS with an existing Traefik, using official frappe_docker images and method. Clone of rtCamp Frappe-Manager (production lifecycle only).

## Principles
- Official `frappe/erpnext` images when only erpnext is requested; otherwise layered build from frappe_docker `images/layered/Containerfile` on the VPS.
- Traefik owns TLS issuance and renewal; fmt only emits labels.
- One site = one compose project in `$FMT_HOME/<site-slug>` (default `/opt/fmt`).

## Phases (tracer bullet)
1. **create**: Traefik detection, compose render, db/redis up, configurator, new-site, ping.
2. **lifecycle**: list, info, start, stop, restart, logs, shell, bench, delete.
3. **apps**: `--apps name[:ref]|url[:ref]`, `--frappe REF`, apps.json, layered build, `fmt apps add|remove|list`.
4. **backup/update**: backup, restore, update (backup, build, maintenance, migrate, switch), rollback, clone.
5. **ssl/doctor**: `ssl status`, `doctor`.
6. **install/docs**: `install.sh`, README, docs/, CI.

## Apps spec syntax
`name[:ref]` resolves to `https://github.com/frappe/<name>` (ref defaults to the frappe branch). `url[:ref]` is any git URL. `ref` is a branch or tag.

## Upgrade sequence
Backup -> build/pull new image -> maintenance on, stop workers -> `bench migrate` in one-off container -> recreate services -> maintenance off -> ping. On failure `fmt rollback` restores the backup with the previous image. Migrations are never reverted.

## SSL
Router labels with `tls.certresolver`; HTTP router redirects to HTTPS and serves ACME HTTP-01. `ssl status` reads the live certificate expiry; `doctor` checks Traefik, resolver and port reachability.
