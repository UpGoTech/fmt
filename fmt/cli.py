from typing import List, Optional

import typer

from fmt.compose import ComposeProject
from fmt.creator import SiteCreator
from fmt.process import FmtError
from fmt.site import Site

app = typer.Typer(help="Frappe Manager - Traefik: production Frappe sites on Docker + Traefik.",
                  no_args_is_help=True)


def load(name):
    site = Site(name).require_existing()
    return site, ComposeProject(site)


@app.command()
def create(
    name: str,
    frappe: str = typer.Option("version-16", help="Frappe branch or tag"),
    apps: str = typer.Option("erpnext", help="name[:ref],git-url[:ref],..."),
    admin_password: Optional[str] = typer.Option(None, help="Default: random"),
    network: Optional[str] = typer.Option(None, help="Traefik docker network"),
    resolver: Optional[str] = typer.Option(None, help="Traefik certresolver"),
):
    """Create and start a new site."""
    creator = SiteCreator(name, frappe, apps, admin_password, network, resolver)
    live = creator.create()
    typer.echo(f"\nURL: https://{creator.site.name}\nLogin: Administrator\n"
               f"Password: {creator.admin_password}\nDirectory: {creator.site.directory}")
    if not live:
        typer.echo("warn: HTTPS ping not OK yet; check DNS, 'fmt logs' and Traefik logs.", err=True)


@app.command("list")
def list_sites():
    """Show all sites."""
    for site in Site.all():
        running = ComposeProject(site).running_count()
        typer.echo(f"{site.name:<38} {running}/9  {site.env.read()['IMAGE']}")


@app.command()
def info(name: str):
    """Show URL, directory and image of a site."""
    site, _ = load(name)
    values = site.env.read()
    typer.echo(f"Site: https://{site.name}\nDirectory: {site.directory}\nImage: {values['IMAGE']}\n"
               f"Apps: {values['APPS']}\nInitial admin password: in {site.directory}/.env")


@app.command()
def start(name: str):
    """Start all services."""
    load(name)[1].run("up", "-d")


@app.command()
def stop(name: str):
    """Stop all services."""
    load(name)[1].run("stop")


@app.command()
def restart(name: str):
    """Restart all services."""
    load(name)[1].run("restart")


@app.command()
def logs(name: str, service: Optional[List[str]] = typer.Argument(None)):
    """Follow logs."""
    load(name)[1].run("logs", "-f", "--tail=100", *(service or []))


@app.command()
def shell(name: str):
    """Open bash in the backend container (cwd: frappe-bench)."""
    load(name)[1].run("exec", "backend", "bash")


@app.command(context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def bench(name: str, arguments: List[str] = typer.Argument(...)):
    """Run 'bench --site <name> <arguments>'."""
    load(name)[1].bench("--site", name, *arguments, tty=True)


@app.command()
def delete(name: str):
    """Destroy a site: containers, volumes and directory."""
    site, compose = load(name)
    if typer.prompt(f"Type '{site.name}' to confirm deletion") != site.name:
        raise FmtError("aborted")
    compose.run("down", "-v", "--remove-orphans")
    site.remove()


def main():
    try:
        app()
    except FmtError as error:
        typer.echo(f"error: {error}", err=True)
        raise SystemExit(1)
