from rich import box
from rich.console import Console
from rich.table import Table

console = Console()


def status_label(running, total):
    """Returns (text, style): Active (n/total), Inactive (0/total), yellow when partial."""
    if running == 0:
        return f"Inactive (0/{total})", "dim"
    style = "green" if running >= total else "yellow"
    return f"Active ({running}/{total})", style


def _table(**options):
    return Table(box=box.SQUARE, show_lines=True, border_style="white", **options)


def sites_table(rows):
    """rows: iterable of (name, running, total, path)."""
    table = _table(header_style="bold")
    for column in ("Site", "Status", "Path"):
        table.add_column(column)
    for name, running, total, path in rows:
        label, style = status_label(running, total)
        table.add_row(f"[{style}]{name}[/]", f"[{style}]{label}[/]", f"[magenta]{path}[/]")
    return table


def details_table(pairs):
    table = _table(show_header=False)
    table.add_column(style="bold")
    table.add_column(overflow="fold")
    for key, value in pairs:
        table.add_row(key, str(value))
    return table
