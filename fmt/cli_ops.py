import json
from pathlib import Path
from typing import List, Optional

import typer

from fmt.apps import AppSpec, parse_apps
from fmt.backup import BackupStore
from fmt.creator import SiteCreator
from fmt.display import console, details_table
from fmt.loader import load
from fmt.process import FmtError, output
from fmt.traefik import TraefikDetector
from fmt.upgrade import Upgrader

ops = typer.Typer()
apps_app = typer.Typer(help="Manage apps of a site (rebuilds the image).")
ops.add_typer(apps_app, name="apps")


@ops.command()
def backup(name: str, keep_days: int = typer.Option(14, help="Delete backups older than this")):
    """Back up database and files into <site dir>/backups."""
    site, compose = load(name)
    store = BackupStore(site, compose)
    folder = store.create()
    store.prune(keep_days)
    typer.echo(f"Saved to {folder}. Copy it off the server too (rclone, rsync, S3).")


@ops.command()
def restore(name: str, folder: Optional[str] = typer.Argument(None, help="Default: latest backup")):
    """Restore a backup folder into the site."""
    site, compose = load(name)
    store = BackupStore(site, compose)
    store.restore(folder or store.latest())
    compose.bench("--site", site.name, "migrate")
    compose.run("restart")


@ops.command()
def update(
    name: str,
    frappe: Optional[str] = typer.Option(None, help="New Frappe branch or tag; apps on the old branch follow"),
    app: Optional[List[str]] = typer.Option(None, "--app", help="name:ref or git-url:ref"),
):
    """Back up, rebuild or pull the image, migrate and switch over."""
    site, _ = load(name)
    changes = [AppSpec.parse(item, frappe or site.env.read()["FRAPPE_REF"]) for item in app or []]
    Upgrader(site).run(frappe, changes, fresh=not (frappe or app))
    typer.echo("Updated.")


@ops.command()
def rollback(name: str, folder: Optional[str] = typer.Argument(None, help="Default: latest backup")):
    """Restore the pre-update backup together with its old image."""
    site, _ = load(name)
    Upgrader(site).rollback(Path(folder) if folder else None)


@apps_app.command("list")
def apps_list(name: str):
    """Show configured apps."""
    site, _ = load(name)
    values = site.env.read()
    console.print(details_table([(app.name, app.ref) for app in parse_apps(values["APPS"], values["FRAPPE_REF"])]))


@apps_app.command("add")
def apps_add(name: str, specs: List[str] = typer.Argument(..., help="name[:ref] or git-url[:ref]")):
    """Add apps: rebuild the image, install them and migrate."""
    site, _ = load(name)
    ref = site.env.read()["FRAPPE_REF"]
    Upgrader(site).run(changes=[AppSpec.parse(item, ref) for item in specs])


@apps_app.command("remove")
def apps_remove(name: str, names: List[str] = typer.Argument(...)):
    """Uninstall apps from the site and remove them from the image."""
    site, _ = load(name)
    if "frappe" in names:
        raise FmtError("frappe is the framework and cannot be removed")
    Upgrader(site).run(removals=names)


@ops.command()
def clone(source: str, new_name: str):
    """Create new_name from a fresh backup of source (e.g. a staging copy)."""
    site, compose = load(source)
    values = site.env.read()
    folder = BackupStore(site, compose).create()
    config = output(compose.command(
        "exec", "-T", "backend", "cat", f"/home/frappe/frappe-bench/sites/{site.name}/site_config.json"))
    creator = SiteCreator(new_name, values["FRAPPE_REF"], values["APPS"], None,
                          TraefikDetector().detect(), local=values.get("SSL") == "false")
    creator.create()
    _, new_compose = load(creator.site.name)
    key = json.loads(config).get("encryption_key")
    if key:
        new_compose.bench("--site", creator.site.name, "set-config", "encryption_key", key)
    BackupStore(creator.site, new_compose).restore(folder)
    new_compose.bench("--site", creator.site.name, "migrate")
    new_compose.run("restart")
    typer.echo(f"Cloned {site.name} to {creator.url}")
