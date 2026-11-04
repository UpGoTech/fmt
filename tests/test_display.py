from rich.console import Console

from fmt.display import details_table, sites_table


def render(table):
    console = Console(width=100, record=True, force_terminal=False)
    console.print(table)
    return console.export_text()


def test_sites_table_shows_status_and_path():
    text = render(sites_table([("a.localhost", True, "/p/a"), ("b.localhost", False, "/p/b")]))
    assert "Site" in text and "Status" in text and "Path" in text
    assert "Active" in text and "Inactive" in text and "/p/b" in text


def test_details_table_pairs():
    text = render(details_table([("Site", "https://a"), ("Apps", "erpnext")]))
    assert "https://a" in text and "erpnext" in text
