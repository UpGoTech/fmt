<div align="center">

# Frappe Manager - Traefik (`fmt`)

Create and run production Frappe, ERPNext and HRMS sites on a VPS with Docker and Traefik, one command per site.

</div>

`fmt` is modelled on [Frappe Manager](https://github.com/rtCamp/Frappe-Manager) but uses **Traefik** instead of nginx as the reverse proxy and the **official images and layout of [frappe_docker](https://github.com/frappe/frappe_docker)** instead of a custom image.

## Install

Requires Linux or macOS with Docker (Compose v2), git and openssl.

```bash
curl -fsSL https://raw.githubusercontent.com/UpGoTech/fmt/develop/install.sh | bash
fmt doctor
```

Or manually: `uv tool install git+https://github.com/UpGoTech/fmt@develop`. Update with `uv tool upgrade frappe-manager-traefik`.

## Quick start

```bash
fmt create erp.example.com                                   # official frappe/erpnext:version-16
fmt create hr.example.com --apps erpnext,hrms                # builds an image with HRMS
fmt create old.example.com --frappe version-15 --apps erpnext,hrms
fmt create demo.localhost                                    # local dev: HTTP only, no DNS or certificate
```

If no Traefik is running, `fmt` offers to download and start one (`fmt traefik install`).
Sites live in `/opt/fmt/<site>` (override with `FMT_HOME`).

## Commands

| Command | Purpose |
|---|---|
| `create <site> [--frappe REF] [--apps ...] [--local] [--strict-dns]` | New site |
| `list`, `info <site>` | Status (`Active (n/9)`), paths, image, apps |
| `start`, `stop`, `restart`, `logs [service]` | Lifecycle |
| `shell <site>` | bash in the backend container, then use `bench` freely |
| `bench <site> <args>` | `bench --site <site> <args>` |
| `apps list\|add\|remove <site> ...` | Manage apps (rebuilds the image) |
| `backup`, `restore`, `clone <source> <new>` | Data safety and staging copies |
| `update <site> [--frappe REF] [--app name:ref]`, `rollback` | Upgrades, see [docs/upgrading.md](docs/upgrading.md) |
| `ssl status <site>`, `doctor` | Certificates and environment checks, see [docs/ssl.md](docs/ssl.md) |
| `traefik install` | Download and start Traefik |
| `delete <site>` | Remove containers, volumes and files |

`--apps` takes `name[:ref]` (apps from github.com/frappe) or `git-url[:ref]`. See [docs/apps.md](docs/apps.md).

## Docs

- [Apps and versions](docs/apps.md)
- [SSL and renewal](docs/ssl.md)
- [Backups and upgrades](docs/upgrading.md)
- [Local development](docs/local.md)

## Differences from Frappe Manager

Production focus: no dev containers, VS Code attach, mailpit or adminer. Traefik instead of nginx. Official images, with apps baked in by a frappe_docker layered build.

## Development

```bash
uv sync && uv run pytest
```
