from typing import Optional

import typer
from rich.table import Table

from fmt.display import console, details_table
from fmt.doctor import Doctor
from fmt.loader import load
from fmt.process import FmtError
from fmt.ssl import fetch_certificate

checks = typer.Typer()
ssl_app = typer.Typer(help="Inspect site certificates.")
checks.add_typer(ssl_app, name="ssl")


@ssl_app.command("status")
def ssl_status(name: str, connect_to: Optional[str] = typer.Option(
        None, help="Connect to this address instead of the domain, e.g. 127.0.0.1")):
    """Show the live certificate expiry and issuer for a site."""
    site, _ = load(name)
    if site.env.read().get("SSL", "true") != "true":
        raise FmtError("local site: no certificate (HTTP only)")
    certificate = fetch_certificate(site.name, connect_to)
    console.print(details_table([
        ("Site", site.name), ("Issuer", certificate.issuer),
        ("Expires", certificate.expires.date()), ("Status", certificate.verdict()),
    ]))


@checks.command()
def doctor():
    """Check Docker, Traefik, certificate resolver and ports."""
    table = Table(title="fmt doctor")
    for column in ("Check", "Result", "Detail"):
        table.add_column(column)
    results = Doctor().run_all()
    for name, passed, detail in results:
        table.add_row(name, "[green]OK[/]" if passed else "[red]FAIL[/]", detail)
    console.print(table)
    if not all(passed for _, passed, _ in results):
        raise typer.Exit(1)
