from typing import List, Optional

import typer

from fmt.compose import ComposeProject
from fmt.creator import SiteCreator
from fmt.display import STATUS_STYLES, console, details_table, sites_table
from fmt.process import FmtError
from fmt.routing import is_local_domain
from fmt.site import Site, fmt_home
from fmt.traefik import TraefikDetector, TraefikNotFound
from fmt.traefik_install import TraefikInstaller

app = typer.Typer(help="Frappe Manager - Traefik: production Frappe sites on Docker + Traefik.",
                  no_args_is_help=True)


def load(name):
    site = Site(name).require_existing()
    return site, ComposeProject(site)


def install_traefik(email, local):
    if email is None:
        email = typer.prompt("Let's Encrypt email (blank for HTTP-only local use)", default="") \
            if local else typer.prompt("Let's Encrypt email")
    typer.echo("Installing Traefik (docker image traefik:v3.6)...")
    TraefikInstaller(fmt_home() / "traefik").install(email)


def locate_traefik(network, resolver, local, assume_yes, email):
    detector = TraefikDetector()
    try:
        return detector.detect(network, resolver)
    except TraefikNotFound:
        if not (assume_yes or typer.confirm("No running Traefik found. Download and install it now?")):
            raise FmtError("Traefik is required. Install it yourself or run 'fmt traefik install'.")
    install_traefik(email, local)
    return detector.detect(network, resolver)


@app.command()
def create(
    name: str,
    frappe: str = typer.Option("version-16", help="Frappe branch or tag"),
    apps: str = typer.Option("erpnext", help="name[:ref],git-url[:ref],..."),
    admin_password: Optional[str] = typer.Option(None, help="Default: random"),
    network: Optional[str] = typer.Option(None, help="Traefik docker network"),
    resolver: Optional[str] = typer.Option(None, help="Traefik certresolver"),
    local: Optional[bool] = typer.Option(
        None, "--local/--no-local",
        help="HTTP only, no DNS or certificate. Default: on for .localhost/.test/.local domains"),
    strict_dns: bool = typer.Option(False, help="Abort when DNS does not point to this server"),
    install_traefik_if_missing: bool = typer.Option(
        False, "--install-traefik", help="Install Traefik without asking when none is running"),
    acme_email: Optional[str] = typer.Option(None, help="Let's Encrypt email for a new Traefik"),
):
    """Create and start a new site."""
    is_local = is_local_domain(name.lower()) if local is None else local
    traefik = locate_traefik(network, resolver, is_local, install_traefik_if_missing, acme_email)
    creator = SiteCreator(name, frappe, apps, admin_password, traefik, is_local, strict_dns)
    live = creator.create()
    console.print(details_table([
        ("URL", creator.url), ("Login", "Administrator"),
        ("Password", creator.admin_password), ("Directory", creator.site.directory),
    ]))
    if is_local:
        typer.echo(f"Add to /etc/hosts if the name does not resolve: 127.0.0.1 {creator.site.name}")
    if not live:
        typer.echo("warn: ping not OK yet; check DNS, 'fmt logs' and Traefik logs.", err=True)


traefik_app = typer.Typer(help="Manage the Traefik reverse proxy.")
app.add_typer(traefik_app, name="traefik")


@traefik_app.command("install")
def traefik_install(email: Optional[str] = typer.Option(None, help="Let's Encrypt email")):
    """Download and start Traefik (ports 80/443)."""
    install_traefik(email, local=False)


@app.command("list")
def list_sites():
    """Show all sites."""
    rows = [(site.name, ComposeProject(site).running_count() > 0, site.directory)
            for site in Site.all()]
    console.print(sites_table(rows))


@app.command()
def info(name: str):
    """Show URL, directory, image and apps of a site."""
    site, compose = load(name)
    values = site.env.read()
    active = compose.running_count() > 0
    console.print(details_table([
        ("Site", site.url), ("Status", STATUS_STYLES[active][0]), ("Directory", site.directory),
        ("Image", values["IMAGE"]), ("Apps", values["APPS"].replace(",", ", ")),
        ("Admin password", f"initial one is in {site.directory}/.env"),
    ]))


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
