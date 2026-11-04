#!/usr/bin/env bash
# =============================================================================
# erpctl — frappe-manager-style CLI for production ERPNext v16 on Docker+Traefik
#
#   erpctl create erp.example.com          # spin up a new isolated site
#   erpctl list | start | stop | restart | logs | shell | bench | backup
#   erpctl update erp.example.com [tag]    # backup -> pull image -> migrate
#   erpctl delete erp.example.com
#
# Each site = its own compose project (MariaDB, 2x Redis, gunicorn backend,
# nginx frontend, socketio, short+long workers, scheduler) joined to your
# existing Traefik network. Nothing is published on host ports.
# =============================================================================
set -Eeuo pipefail

ERP_HOME="${ERP_HOME:-/opt/erpnext-sites}"
ERP_IMAGE_DEFAULT="${ERP_IMAGE:-frappe/erpnext}"
ERP_TAG_DEFAULT="${ERP_TAG:-version-16}"       # pin to e.g. v16.x.y for strict reproducibility
DB_IMAGE_DEFAULT="${DB_IMAGE:-mariadb:11.8}"
REDIS_IMAGE_DEFAULT="${REDIS_IMAGE:-redis:7-alpine}"
BACKUP_KEEP_DAYS="${BACKUP_KEEP_DAYS:-14}"

c_red=$'\e[31m'; c_grn=$'\e[32m'; c_ylw=$'\e[33m'; c_dim=$'\e[2m'; c_off=$'\e[0m'
log()  { echo "${c_grn}==>${c_off} $*"; }
warn() { echo "${c_ylw}warn:${c_off} $*" >&2; }
die()  { echo "${c_red}error:${c_off} $*" >&2; exit 1; }

usage() {
cat <<EOF
Usage: erpctl <command> [args]

  create <site> [options]   Create + start a new ERPNext v16 site
      --admin-password PW   Administrator password (default: random)
      --image IMG           Image (default: $ERP_IMAGE_DEFAULT)
      --tag TAG             Image tag (default: $ERP_TAG_DEFAULT)
      --apps a,b            Extra apps to install (must exist in the image)
      --network NAME        Traefik docker network (default: auto-detect)
      --resolver NAME       Traefik certresolver   (default: auto-detect/letsencrypt)
  list                      Show all sites
  info <site>               URL, directory, credentials location
  start|stop|restart <site>
  logs <site> [service]     Follow logs (default: all services)
  shell <site>              bash inside the backend container
  bench <site> <args...>    Run 'bench --site <site> <args...>'
  backup <site>             DB + files backup copied to <site dir>/backups
  update <site> [tag]       Backup, pull new image, restart, migrate
  delete <site>             Destroy site, containers and volumes (asks first)

Env: ERP_HOME (default /opt/erpnext-sites), BACKUP_KEEP_DAYS (default 14)
EOF
}

# ---------- helpers ----------------------------------------------------------
preflight() {
  command -v docker >/dev/null || die "docker not found"
  docker info >/dev/null 2>&1 || die "cannot talk to docker (run as root or add yourself to the docker group)"
  docker compose version >/dev/null 2>&1 || die "docker compose v2 plugin not found"
}

lower()  { tr '[:upper:]' '[:lower:]' <<<"$1"; }
rand()   { openssl rand -hex "${1:-16}"; }
valid_domain() { [[ "$1" =~ ^([a-z0-9]([a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,}$ ]]; }

load_site() {                      # sets SITE, DIR + everything from .env
  local s; s="$(lower "${1:-}")"
  [[ -n "$s" ]] || die "site name required"
  DIR="$ERP_HOME/${s//./-}"
  [[ -f "$DIR/compose.yaml" ]] || die "site '$s' not found in $ERP_HOME"
  set -a; # shellcheck disable=SC1091
  source "$DIR/.env"; set +a
}
dc() { docker compose -p "$SLUG" --project-directory "$DIR" --env-file "$DIR/.env" -f "$DIR/compose.yaml" "$@"; }

detect_traefik() {
  local c args
  c="$(docker ps --format '{{.Names}} {{.Image}}' | awk 'tolower($2) ~ /traefik/ {print $1; exit}')"
  [[ -n "$c" ]] || die "No running Traefik container found. Start it first (or set TRAEFIK_NETWORK etc. and fix this check)."
  log "Traefik container: $c"

  if [[ -z "${TRAEFIK_NETWORK:-}" ]]; then
    TRAEFIK_NETWORK="$(docker inspect -f '{{range $k,$v := .NetworkSettings.Networks}}{{$k}}{{"\n"}}{{end}}' "$c" \
      | grep -vE '^(bridge|host|none)?$' | head -n1 || true)"
  fi
  if [[ -z "${TRAEFIK_NETWORK:-}" ]]; then
    # Host-mode Traefik (or one attached only to the default bridge) reaches containers by IP over 'bridge'.
    local mode; mode="$(docker inspect -f '{{.HostConfig.NetworkMode}}' "$c" 2>/dev/null || true)"
    TRAEFIK_NETWORK="erpctl-proxy"
    warn "No custom network on Traefik (network mode: ${mode:-unknown}); using dedicated network '$TRAEFIK_NETWORK'."
    docker network inspect "$TRAEFIK_NETWORK" >/dev/null 2>&1 || docker network create "$TRAEFIK_NETWORK" >/dev/null
    if [[ "$mode" != "host" ]]; then
      # Bridge-attached Traefik must share the network to reach the sites
      docker network connect "$TRAEFIK_NETWORK" "$c" 2>/dev/null || true
    fi
  fi
  docker network inspect "$TRAEFIK_NETWORK" >/dev/null 2>&1 || die "Docker network '$TRAEFIK_NETWORK' does not exist."

  # Best-effort detection from CLI args (won't work if Traefik uses a static file) -> sane defaults
  args="$(docker inspect -f '{{join .Args " "}}' "$c" 2>/dev/null || true)"
  TRAEFIK_ENTRYPOINT_WEB="${TRAEFIK_ENTRYPOINT_WEB:-$(grep -oP 'entrypoints\.\K[^.= ]+(?=\.address=:80( |$))' <<<"$args" | head -n1 || true)}"
  TRAEFIK_ENTRYPOINT_SECURE="${TRAEFIK_ENTRYPOINT_SECURE:-$(grep -oP 'entrypoints\.\K[^.= ]+(?=\.address=:443( |$))' <<<"$args" | head -n1 || true)}"
  TRAEFIK_CERTRESOLVER="${TRAEFIK_CERTRESOLVER:-$(grep -oP 'certificatesresolvers\.\K[^.= ]+' <<<"$args" | head -n1 || true)}"
  TRAEFIK_ENTRYPOINT_WEB="${TRAEFIK_ENTRYPOINT_WEB:-web}"
  TRAEFIK_ENTRYPOINT_SECURE="${TRAEFIK_ENTRYPOINT_SECURE:-websecure}"
  TRAEFIK_CERTRESOLVER="${TRAEFIK_CERTRESOLVER:-letsencrypt}"
  log "Network=$TRAEFIK_NETWORK  entrypoints=$TRAEFIK_ENTRYPOINT_WEB/$TRAEFIK_ENTRYPOINT_SECURE  resolver=$TRAEFIK_CERTRESOLVER"
  echo "${c_dim}    (override with env TRAEFIK_ENTRYPOINT_WEB / TRAEFIK_ENTRYPOINT_SECURE / TRAEFIK_CERTRESOLVER if wrong)${c_off}"
}

check_dns() {
  local pub dns
  pub="$(curl -fsS -4 -m 5 https://ifconfig.me 2>/dev/null || true)"
  dns="$(getent ahostsv4 "$1" 2>/dev/null | awk 'NR==1{print $1}')"
  if [[ -z "$dns" ]]; then
    warn "$1 does not resolve yet. Let's Encrypt will fail until its A record points to this server (${pub:-unknown})."
  elif [[ -n "$pub" && "$dns" != "$pub" ]]; then
    warn "$1 resolves to $dns but this server is $pub (fine if behind Cloudflare proxy; otherwise cert issuance will fail)."
  else
    log "DNS OK: $1 -> $dns"
  fi
}

write_compose() {
  # Quoted heredoc: ${VARS} are resolved by docker compose from .env, '$$' becomes '$' for the container shell.
cat > "$DIR/compose.yaml" <<'YAML'
x-erp: &erp
  image: ${ERP_IMAGE}:${ERP_TAG}
  restart: unless-stopped
  logging:
    driver: json-file
    options: { max-size: "10m", max-file: "5" }
  volumes:
    - sites:/home/frappe/frappe-bench/sites
    - logs:/home/frappe/frappe-bench/logs

x-after-configurator: &after_configurator
  depends_on:
    configurator:
      condition: service_completed_successfully

services:
  configurator:
    <<: *erp
    restart: "no"
    entrypoint: ["bash", "-c"]
    command:
      - >
        ls -1 apps > sites/apps.txt;
        bench set-config -g db_host $$DB_HOST;
        bench set-config -gp db_port $$DB_PORT;
        bench set-config -g redis_cache "redis://$$REDIS_CACHE";
        bench set-config -g redis_queue "redis://$$REDIS_QUEUE";
        bench set-config -g redis_socketio "redis://$$REDIS_QUEUE";
        bench set-config -gp socketio_port $$SOCKETIO_PORT;
    environment:
      DB_HOST: db
      DB_PORT: "3306"
      REDIS_CACHE: redis-cache:6379
      REDIS_QUEUE: redis-queue:6379
      SOCKETIO_PORT: "9000"
    depends_on: {}

  backend:
    <<: [*erp, *after_configurator]

  frontend:
    <<: [*erp, *after_configurator]
    command: nginx-entrypoint.sh
    environment:
      BACKEND: backend:8000
      SOCKETIO: websocket:9000
      FRAPPE_SITE_NAME_HEADER: ${SITE}
      UPSTREAM_REAL_IP_ADDRESS: 127.0.0.1
      UPSTREAM_REAL_IP_HEADER: X-Forwarded-For
      UPSTREAM_REAL_IP_RECURSIVE: "off"
      PROXY_READ_TIMEOUT: "120"
      CLIENT_MAX_BODY_SIZE: 50m
    depends_on:
      - backend
      - websocket
    networks: [default, proxy]
    labels:
      - traefik.enable=true
      - "traefik.docker.network=${TRAEFIK_NETWORK}"
      - "traefik.http.services.${SLUG}.loadbalancer.server.port=8080"
      # HTTPS router
      - "traefik.http.routers.${SLUG}-https.rule=Host(`${SITE}`)"
      - "traefik.http.routers.${SLUG}-https.entrypoints=${TRAEFIK_ENTRYPOINT_SECURE}"
      - "traefik.http.routers.${SLUG}-https.tls=true"
      - "traefik.http.routers.${SLUG}-https.tls.certresolver=${TRAEFIK_CERTRESOLVER}"
      - "traefik.http.routers.${SLUG}-https.service=${SLUG}"
      # HTTP -> HTTPS redirect
      - "traefik.http.routers.${SLUG}-http.rule=Host(`${SITE}`)"
      - "traefik.http.routers.${SLUG}-http.entrypoints=${TRAEFIK_ENTRYPOINT_WEB}"
      - "traefik.http.routers.${SLUG}-http.middlewares=${SLUG}-redirect"
      - "traefik.http.routers.${SLUG}-http.service=${SLUG}"
      - "traefik.http.middlewares.${SLUG}-redirect.redirectscheme.scheme=https"
      - "traefik.http.middlewares.${SLUG}-redirect.redirectscheme.permanent=true"

  websocket:
    <<: [*erp, *after_configurator]
    command: ["node", "/home/frappe/frappe-bench/apps/frappe/socketio.js"]

  queue-short:
    <<: [*erp, *after_configurator]
    command: ["bench", "worker", "--queue", "short,default"]

  queue-long:
    <<: [*erp, *after_configurator]
    command: ["bench", "worker", "--queue", "long,default,short"]

  scheduler:
    <<: [*erp, *after_configurator]
    command: ["bench", "schedule"]

  db:
    image: ${DB_IMAGE}
    restart: unless-stopped
    logging:
      driver: json-file
      options: { max-size: "10m", max-file: "3" }
    command:
      - --character-set-server=utf8mb4
      - --collation-server=utf8mb4_unicode_ci
      - --skip-character-set-client-handshake
      - --innodb-buffer-pool-size=${DB_BUFFER_POOL}
    environment:
      MARIADB_ROOT_PASSWORD: ${DB_ROOT_PASSWORD}
    healthcheck:
      test: ["CMD", "healthcheck.sh", "--connect", "--innodb_initialized"]
      interval: 5s
      timeout: 5s
      retries: 30
      start_period: 20s
    volumes:
      - db-data:/var/lib/mysql

  redis-cache:
    image: ${REDIS_IMAGE}
    restart: unless-stopped
    command: ["redis-server", "--maxmemory", "256mb", "--maxmemory-policy", "allkeys-lru", "--save", ""]
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      retries: 20

  redis-queue:
    image: ${REDIS_IMAGE}
    restart: unless-stopped
    command: ["redis-server", "--appendonly", "yes"]
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      retries: 20
    volumes:
      - redis-queue-data:/data

volumes:
  sites:
  logs:
  db-data:
  redis-queue-data:

networks:
  proxy:
    external: true
    name: ${TRAEFIK_NETWORK}
YAML
}

# ---------- commands ---------------------------------------------------------
cmd_create() {
  local site="" image="$ERP_IMAGE_DEFAULT" tag="$ERP_TAG_DEFAULT" admin_pw="" apps=""
  [[ $# -ge 1 ]] || die "usage: erpctl create <site> [options]"
  site="$(lower "$1")"; shift
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --admin-password) admin_pw="$2"; shift 2;;
      --image)    image="$2"; shift 2;;
      --tag)      tag="$2"; shift 2;;
      --apps)     apps="$2"; shift 2;;
      --network)  TRAEFIK_NETWORK="$2"; shift 2;;
      --resolver) TRAEFIK_CERTRESOLVER="$2"; shift 2;;
      *) die "unknown option: $1";;
    esac
  done
  valid_domain "$site" || die "'$site' is not a valid domain name (e.g. erp.example.com)"
  [[ -z "$admin_pw" ]] && admin_pw="$(rand 12)"

  local slug="${site//./-}"
  DIR="$ERP_HOME/$slug"
  [[ -e "$DIR" ]] && die "$DIR already exists — site already created? (erpctl info $site)"

  detect_traefik
  check_dns "$site"

  local mem_mb pool
  mem_mb="$(awk '/MemTotal/ {printf "%d", $2/1024}' /proc/meminfo)"
  pool=$(( mem_mb / 4 )); (( pool < 256 )) && pool=256; (( pool > 4096 )) && pool=4096

  log "Creating $DIR"
  umask 077
  mkdir -p "$DIR/backups"
  cat > "$DIR/.env" <<EOF
SITE=$site
SLUG=$slug
ERP_IMAGE=$image
ERP_TAG=$tag
DB_IMAGE=$DB_IMAGE_DEFAULT
REDIS_IMAGE=$REDIS_IMAGE_DEFAULT
DB_ROOT_PASSWORD=$(rand 16)
ADMIN_PASSWORD=$admin_pw
DB_BUFFER_POOL=${pool}M
EXTRA_APPS=$apps
TRAEFIK_NETWORK=$TRAEFIK_NETWORK
TRAEFIK_ENTRYPOINT_WEB=$TRAEFIK_ENTRYPOINT_WEB
TRAEFIK_ENTRYPOINT_SECURE=$TRAEFIK_ENTRYPOINT_SECURE
TRAEFIK_CERTRESOLVER=$TRAEFIK_CERTRESOLVER
EOF
  chmod 600 "$DIR/.env"
  write_compose

  load_site "$site"
  trap 'echo; warn "Creation failed. Inspect: cd $DIR && docker compose -p $SLUG logs   |   Clean up: erpctl delete $site"' ERR

  log "Pulling images ($image:$tag)"
  dc pull

  log "Starting database + redis"
  dc up -d --wait db redis-cache redis-queue

  log "Writing common_site_config.json"
  dc run --rm -T configurator

  log "Creating site + installing erpnext (a few minutes)"
  dc run --rm -T -e "SITE=$SITE" -e "ADMIN_PASSWORD=$ADMIN_PASSWORD" -e "DB_ROOT_PASSWORD=$DB_ROOT_PASSWORD" backend bash -c '
    set -e
    bench new-site --mariadb-user-host-login-scope="%" \
      --db-root-username root --db-root-password "$DB_ROOT_PASSWORD" \
      --admin-password "$ADMIN_PASSWORD" --install-app erpnext --set-default "$SITE"
    bench --site "$SITE" set-config host_name "https://$SITE"
    bench --site "$SITE" enable-scheduler
    bench --site "$SITE" set-maintenance-mode off
  '
  if [[ -n "$apps" ]]; then
    IFS=',' read -ra _apps <<<"$apps"
    for a in "${_apps[@]}"; do
      log "Installing app: $a"
      dc run --rm -T backend bench --site "$SITE" install-app "$a"
    done
  fi

  log "Starting all services"
  dc up -d

  log "Waiting for https://$SITE (cert issuance can take ~1 min)"
  local i ok=0
  for i in $(seq 1 40); do
    if curl -fsS -m 5 "https://$SITE/api/method/ping" >/dev/null 2>&1; then ok=1; break; fi
    sleep 4
  done
  trap - ERR

  echo
  if (( ok )); then log "Site is live."; else warn "Site started but HTTPS ping not yet OK — check DNS / 'erpctl logs $SITE' / Traefik logs."; fi
  cat <<EOF

  URL       : https://$SITE
  Login     : Administrator
  Password  : $ADMIN_PASSWORD
  Directory : $DIR   (secrets in $DIR/.env, chmod 600)

  Daily backup cron suggestion:
    0 2 * * *  root  $(readlink -f "$0") backup $SITE >> /var/log/erpctl-backup.log 2>&1
EOF
}

cmd_list() {
  printf '%-38s %-9s %s\n' SITE SERVICES IMAGE
  local d
  for d in "$ERP_HOME"/*/; do
    [[ -f "$d/compose.yaml" ]] || continue
    ( set -a; source "$d/.env"; set +a; DIR="${d%/}"
      n="$(dc ps -q --status running 2>/dev/null | wc -l)"
      printf '%-38s %-9s %s:%s\n' "$SITE" "$n/9" "$ERP_IMAGE" "$ERP_TAG" )
  done
}

cmd_info() {
  load_site "${1:-}"
  echo "Site      : https://$SITE"
  echo "Directory : $DIR"
  echo "Image     : $ERP_IMAGE:$ERP_TAG"
  echo "Admin pw  : stored in $DIR/.env (ADMIN_PASSWORD) — only the initial password; change it in the UI"
}

cmd_logs()    { load_site "${1:-}"; shift || true; dc logs -f --tail=100 "$@"; }
cmd_shell()   { load_site "${1:-}"; dc exec backend bash; }
cmd_bench()   { load_site "${1:-}"; shift; dc exec backend bench --site "$SITE" "$@"; }
cmd_start()   { load_site "${1:-}"; dc up -d; }
cmd_stop()    { load_site "${1:-}"; dc stop; }
cmd_restart() { load_site "${1:-}"; dc restart; }

cmd_backup() {
  load_site "${1:-}"
  local dest; dest="$DIR/backups/$(date +%F_%H%M)"
  log "Backing up $SITE"
  dc exec -T backend bench --site "$SITE" backup --with-files
  mkdir -p "$dest"
  dc exec -T backend bash -c "cd sites/$SITE/private/backups && tar cf - \$(find . -type f -mmin -10)" | tar xf - -C "$dest"
  find "$DIR/backups" -mindepth 1 -maxdepth 1 -type d -mtime +"$BACKUP_KEEP_DAYS" -exec rm -rf {} +
  log "Saved to $dest (keeping $BACKUP_KEEP_DAYS days). Copy off-server too (rclone/rsync/S3)."
}

cmd_update() {
  load_site "${1:-}"
  local tag="${2:-$ERP_TAG}"
  cmd_backup "$SITE"
  sed -i "s|^ERP_TAG=.*|ERP_TAG=$tag|" "$DIR/.env"
  set -a; source "$DIR/.env"; set +a
  log "Pulling $ERP_IMAGE:$ERP_TAG"
  dc pull
  dc up -d
  log "Migrating"
  dc exec -T backend bench --site "$SITE" migrate
  dc restart backend websocket queue-short queue-long scheduler
  log "Updated to $ERP_IMAGE:$ERP_TAG"
}

cmd_delete() {
  load_site "${1:-}"
  warn "This permanently deletes $SITE: containers, database, files and $DIR."
  read -r -p "Type the site name to confirm: " ans
  [[ "$ans" == "$SITE" ]] || die "aborted"
  dc down -v --remove-orphans
  rm -rf "$DIR"
  log "Deleted $SITE"
}

# ---------- main -------------------------------------------------------------
main() {
  local cmd="${1:-}"; shift || true
  case "$cmd" in
    ""|-h|--help|help) usage; return 0;;
  esac
  preflight
  mkdir -p "$ERP_HOME"
  case "$cmd" in
    create)  cmd_create "$@";;
    list|ls) cmd_list;;
    info)    cmd_info "$@";;
    start)   cmd_start "$@";;
    stop)    cmd_stop "$@";;
    restart) cmd_restart "$@";;
    logs)    cmd_logs "$@";;
    shell)   cmd_shell "$@";;
    bench)   cmd_bench "$@";;
    backup)  cmd_backup "$@";;
    update)  cmd_update "$@";;
    delete|rm) cmd_delete "$@";;
    *) usage; exit 1;;
  esac
}
main "$@"