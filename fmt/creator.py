import time
import urllib.request

import typer

from fmt.apps import ImageBuilder, ImageResolver, parse_apps
from fmt.compose import ComposeProject
from fmt.dns import check_dns
from fmt.site import Site, fmt_home, validate_domain
from fmt.traefik import TraefikDetector

NEW_SITE_SCRIPT = """set -e
bench new-site --mariadb-user-host-login-scope='%' \
  --db-root-username root --db-root-password "$DB_ROOT_PASSWORD" \
  --admin-password "$ADMIN_PASSWORD" --set-default "$SITE" $INSTALL_FLAGS
bench --site "$SITE" set-config host_name "https://$SITE"
bench --site "$SITE" enable-scheduler
bench --site "$SITE" set-maintenance-mode off
"""


def buffer_pool_megabytes():
    try:
        with open("/proc/meminfo") as meminfo:
            kilobytes = int(meminfo.readline().split()[1])
    except (OSError, ValueError, IndexError):
        return 1024
    return min(max(kilobytes // 1024 // 4, 256), 4096)


class SiteCreator:
    def __init__(self, name, frappe_ref, apps_text, admin_password, network=None, resolver=None):
        self.site = Site(validate_domain(name))
        self.frappe_ref = frappe_ref
        self.apps = parse_apps(apps_text, frappe_ref)
        self.admin_password = admin_password or Site.new_secret(6)
        self.traefik = TraefikDetector().detect(network, resolver)
        self.image = ImageResolver(self.site.slug, frappe_ref, self.apps)

    def settings(self):
        return {
            "SITE": self.site.name, "SLUG": self.site.slug, "IMAGE": self.image.image,
            "FRAPPE_REF": self.frappe_ref,
            "APPS": ",".join(app.serialize() for app in self.apps),
            "DB_IMAGE": "mariadb:11.8", "REDIS_IMAGE": "redis:7-alpine",
            "DB_ROOT_PASSWORD": Site.new_secret(), "ADMIN_PASSWORD": self.admin_password,
            "DB_BUFFER_POOL": f"{buffer_pool_megabytes()}M",
            "TRAEFIK_NETWORK": self.traefik.network,
            "TRAEFIK_ENTRYPOINT_WEB": self.traefik.entrypoint_web,
            "TRAEFIK_ENTRYPOINT_SECURE": self.traefik.entrypoint_secure,
            "TRAEFIK_CERTRESOLVER": self.traefik.certresolver,
        }

    def create(self):
        warning = check_dns(self.site.name)
        if warning:
            typer.echo(f"warn: {warning}", err=True)
        ImageBuilder(fmt_home() / ".cache").ensure(self.image)
        self.site.initialize(self.settings())
        (self.site.directory / "apps.json").write_text(self.image.apps_json)
        self._provision(ComposeProject(self.site))
        return self._wait_until_live()

    def _provision(self, compose):
        compose.run("up", "-d", "--wait", "db", "redis-cache", "redis-queue")
        compose.run("run", "--rm", "-T", "configurator")
        flags = " ".join(f"--install-app {app.name}" for app in self.apps)
        compose.one_off(
            NEW_SITE_SCRIPT, SITE=self.site.name, ADMIN_PASSWORD=self.admin_password,
            DB_ROOT_PASSWORD=self.site.env.read()["DB_ROOT_PASSWORD"], INSTALL_FLAGS=flags,
        )
        compose.run("up", "-d")

    def _wait_until_live(self, attempts=40):
        url = f"https://{self.site.name}/api/method/ping"
        for _ in range(attempts):
            try:
                if urllib.request.urlopen(url, timeout=5).status == 200:
                    return True
            except OSError:
                time.sleep(4)
        return False
