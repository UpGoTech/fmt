import time

import typer

from fmt.apps import FRAPPE_ORGANIZATION_URL, AppSpec, ImageBuilder, ImageResolver, parse_apps
from fmt.backup import STATE_FILE, BackupStore
from fmt.compose import ComposeProject
from fmt.process import FmtError, run
from fmt.site import EnvFile, fmt_home

BENCH_ASSETS = "/home/frappe/frappe-bench/sites/assets/."


def compatibility_warnings(frappe_ref, apps):
    return [
        f"{app.name}@{app.ref} may not match frappe@{frappe_ref}; Frappe apps should share a version"
        for app in apps
        if app.url.startswith(FRAPPE_ORGANIZATION_URL)
        and app.ref.startswith("version-") and frappe_ref.startswith("version-")
        and app.ref != frappe_ref
    ]


def sync_assets(site, image):
    """The sites volume hides the image's built assets; copy the new ones over."""
    volume = f"{site.slug}_sites"
    script = f"mkdir -p /mnt/sites/assets && cp -a {BENCH_ASSETS} /mnt/sites/assets/"
    run(["docker", "run", "--rm", "-v", f"{volume}:/mnt/sites", image, "bash", "-c", script],
        check=False, capture=True)


class Upgrader:
    """Backup, rebuild, migrate, switch. Used by update and apps add/remove."""

    def __init__(self, site):
        self.site, self.compose = site, ComposeProject(site)
        self.backups = BackupStore(site, self.compose)

    def target(self, frappe_ref=None, changes=(), removals=()):
        values = self.site.env.read()
        old_ref = values["FRAPPE_REF"]
        new_ref = frappe_ref or old_ref
        current = parse_apps(values["APPS"], old_ref)
        followed = [AppSpec(a.name, a.url, new_ref if a.ref == old_ref else a.ref) for a in current]
        changed = {app.name: app for app in changes}
        kept = [changed.pop(a.name, a) for a in followed if a.name not in removals]
        return new_ref, kept + list(changed.values())

    def run(self, frappe_ref=None, changes=(), removals=(), fresh=False):
        values = self.site.env.read()
        previous = {a.name for a in parse_apps(values["APPS"], values["FRAPPE_REF"])}
        new_ref, apps = self.target(frappe_ref, changes, removals)
        for warning in compatibility_warnings(new_ref, apps):
            typer.echo(f"warn: {warning}", err=True)
        resolver = ImageResolver(self.site.slug, new_ref, apps)
        typer.echo(f"Backing up {self.site.name}")
        self.backups.create()
        ImageBuilder(fmt_home() / ".cache").ensure(resolver, fresh=fresh)
        try:
            self._switch(resolver, new_ref, apps, previous, removals)
        except FmtError:
            typer.echo(f"Update failed; site left in maintenance mode. Roll back: fmt rollback {self.site.name}",
                       err=True)
            raise

    def _bench(self, *arguments):
        self.compose.bench("--site", self.site.name, *arguments)

    def _switch(self, resolver, frappe_ref, apps, previous, removals):
        self._bench("set-maintenance-mode", "on")
        self.compose.run("stop", "queue-short", "queue-long", "scheduler")
        for name in removals:
            self._bench("uninstall-app", name, "--yes", "--no-backup")
        self.apply_settings(resolver, frappe_ref, apps)
        self.compose.run("up", "-d", "--remove-orphans")
        self.wait_for_backend()
        sync_assets(self.site, resolver.image)
        self._bench("migrate")
        for app in apps:
            if app.name not in previous:
                self._bench("install-app", app.name)
        self._bench("set-maintenance-mode", "off")

    def apply_settings(self, resolver, frappe_ref, apps):
        self.site.env.update(
            IMAGE=resolver.image, FRAPPE_REF=frappe_ref, APPS=",".join(a.serialize() for a in apps))
        (self.site.directory / "apps.json").write_text(resolver.apps_json)

    def wait_for_backend(self, attempts=30):
        for _ in range(attempts):
            if self.compose.bench("--version", check=False).returncode == 0:
                return
            time.sleep(2)
        raise FmtError("backend did not become ready")

    def rollback(self, folder=None):
        folder = folder or self.backups.latest()
        state = EnvFile(folder / STATE_FILE).read()
        resolver = ImageResolver(self.site.slug, state["FRAPPE_REF"],
                                 parse_apps(state["APPS"], state["FRAPPE_REF"]))
        ImageBuilder(fmt_home() / ".cache").ensure(resolver)
        self.site.env.update(**state)
        self.compose.run("up", "-d", "--remove-orphans")
        self.wait_for_backend()
        sync_assets(self.site, state["IMAGE"])
        self.backups.restore(folder)
        self._bench("set-maintenance-mode", "off")
        self.compose.run("restart")
