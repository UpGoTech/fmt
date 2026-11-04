import time
import urllib.request

import typer

from fmt.apps import ImageBuilder, ImageResolver, parse_apps
from fmt.compose import ComposeProject
from fmt.dns import check_dns
from fmt.process import FmtError
from fmt.routing import SiteRouting, is_local_domain
from fmt.site import Site, fmt_home, validate_domain

NEW_SITE_SCRIPT = """set -e
bench new-site --mariadb-user-host-login-scope='%' \
  --db-root-username root --db-root-password "$DB_ROOT_PASSWORD" \
  --admin-password "$ADMIN_PASSWORD" --set-default "$SITE" $INSTALL_FLAGS
bench --site "$SITE" set-config host_name "$SITE_URL"
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
    def __init__(self, name, frappe_ref, apps_text, admin_password, traefik,
                 local=None, strict_dns=False):
        self.site = Site(validate_domain(name))
        self.local = is_local_domain(self.site.name) if local is None else local
        self.strict_dns = strict_dns
        self.frappe_ref = frappe_ref
        self.apps = parse_apps(apps_text, frappe_ref)
        self.admin_password = admin_password or Site.new_secret(6)
        self.traefik = traefik
        self.image = ImageResolver(self.site.slug, frappe_ref, self.apps)

    @property
    def url(self):
        return f"{'http' if self.local else 'https'}://{self.site.name}"

    def settings(self):
        return {
            "SITE": self.site.name, "SLUG": self.site.slug, "IMAGE": self.image.image,
            "SSL": "false" if self.local else "true",
            "FRAPPE_REF": self.frappe_ref,
            "APPS": ",".join(app.serialize() for app in self.apps),
            "DB_IMAGE": "mariadb:11.8", "REDIS_IMAGE": "redis:7-alpine",
            "DB_ROOT_PASSWORD": Site.new_secret(), "ADMIN_PASSWORD": self.admin_password,
            "DB_BUFFER_POOL": f"{buffer_pool_megabytes()}M",
        }

    def create(self):
        self._check_dns()
        ImageBuilder(fmt_home() / ".cache").ensure(self.image)
        self.site.initialize(self.settings())
        self._write_routing()
        self._provision(ComposeProject(self.site))
        return self._wait_until_live()

    def _check_dns(self):
        warning = None if self.local else check_dns(self.site.name)
        if warning and self.strict_dns:
            raise FmtError(f"{warning} Fix DNS or drop --strict-dns.")
        if warning:
            typer.echo(f"warn: {warning}", err=True)

    def _write_routing(self):
        routing = SiteRouting(self.site.name, self.site.slug, self.traefik, self.local)
        self.site.routing_path.write_text(routing.render())
        (self.site.directory / "apps.json").write_text(self.image.apps_json)

    def _provision(self, compose):
        compose.run("up", "-d", "--wait", "db", "redis-cache", "redis-queue")
        compose.run("run", "--rm", "-T", "configurator")
        flags = " ".join(f"--install-app {app.name}" for app in self.apps)
        compose.one_off(
            NEW_SITE_SCRIPT, SITE=self.site.name, SITE_URL=self.url,
            ADMIN_PASSWORD=self.admin_password, INSTALL_FLAGS=flags,
            DB_ROOT_PASSWORD=self.site.env.read()["DB_ROOT_PASSWORD"],
        )
        compose.run("up", "-d")

    def _request(self):
        if not self.local:
            return urllib.request.Request(f"{self.url}/api/method/ping")
        return urllib.request.Request("http://127.0.0.1/api/method/ping",
                                      headers={"Host": self.site.name})

    def _wait_until_live(self, attempts=40):
        self.last_error = None
        for _ in range(attempts):
            try:
                if urllib.request.urlopen(self._request(), timeout=5).status == 200:
                    return True
            except OSError as error:
                self.last_error = error
            time.sleep(4)
        return False
