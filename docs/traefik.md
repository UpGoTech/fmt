# Traefik

`fmt` needs a running Traefik (v2 or v3) with the Docker provider. If none is running, `fmt create` offers to install one; you can also run `fmt traefik install --email you@example.com`.

## What fmt installs

`$FMT_HOME/traefik/compose.yaml` (container `fmt-traefik`, image `traefik:v3.6`): entrypoints `web` (:80) and `websecure` (:443), the Docker provider with `exposedbydefault=false`, a `letsencrypt` resolver using HTTP-01, and `acme.json` in `$FMT_HOME/traefik/letsencrypt`. The network is `fmt-proxy`.

## Using your own Traefik

fmt finds the container by image name and reads entrypoint and resolver names from its command-line flags. Requirements:

- Docker provider enabled, attached to a user-defined network (fmt joins sites to it; override with `--network`).
- An entrypoint on :80 and one on :443 (defaults `web` and `websecure`).
- A certificate resolver (default `letsencrypt`; override with `--resolver`) with `acme.json` on a volume.

If your Traefik is configured by a static file instead of flags, fmt falls back to the defaults above; pass `--network` and `--resolver` when yours differ. `fmt doctor` verifies the setup.

## How sites are routed

Each site gets `compose.traefik.yaml` next to its `compose.yaml` with the router labels for the `frontend` container (HTTPS router with the resolver, plus an HTTP router that redirects to HTTPS). Local sites get a single plain-HTTP router.
