from rich import box
from rich.console import Console
from rich.table import Table

console = Console()
STATUS_STYLES = {True: ("Active", "green"), False: ("Inactive", "dim")}


def _table(**options):
    return Table(box=box.SQUARE, show_lines=True, border_style="white", **options)


def sites_table(rows):
    """rows: iterable of (name, active, path)."""
    table = _table(header_style="bold")
    for column in ("Site", "Status", "Path"):
        table.add_column(column)
    for name, active, path in rows:
        label, style = STATUS_STYLES[active]
        table.add_row(f"[{style}]{name}[/]", f"[{style}]{label}[/]", f"[magenta]{path}[/]")
    return table


def details_table(pairs):
    table = _table(show_header=False)
    table.add_column(style="bold")
    table.add_column(overflow="fold")
    for key, value in pairs:
        table.add_row(key, str(value))
    return table
