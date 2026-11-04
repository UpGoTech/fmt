import pytest

from fmt.backup import BackupStore
from fmt.compose import ComposeProject
from fmt.process import FmtError
from fmt.site import Site
from fmt.ssl import parse_certificate
from fmt.upgrade import Upgrader, compatibility_warnings
from fmt.apps import parse_apps


def make_site(tmp_path, apps="erpnext:version-15,hrms:version-15"):
    site = Site("a.example.com", tmp_path)
    site.initialize({"SITE": site.name, "SLUG": site.slug, "IMAGE": "old", "FRAPPE_REF": "version-15",
                     "APPS": apps})
    return site


def test_target_moves_apps_on_frappe_branch(tmp_path):
    ref, apps = Upgrader(make_site(tmp_path)).target(frappe_ref="version-16")
    assert ref == "version-16" and {a.ref for a in apps} == {"version-16"}


def test_target_explicit_app_override_add_and_remove(tmp_path):
    site = make_site(tmp_path)
    changes = parse_apps("hrms:develop,https://github.com/o/shop:main", "version-15")
    _, apps = Upgrader(site).target(changes=changes, removals=["erpnext"])
    assert [(a.name, a.ref) for a in apps] == [("hrms", "develop"), ("shop", "main")]


def test_compatibility_warning_on_mismatch():
    apps = parse_apps("erpnext:version-15,hrms", "version-16")
    assert len(compatibility_warnings("version-16", apps)) == 1
    assert not compatibility_warnings("version-16", parse_apps("erpnext", "version-16"))


def test_backup_classifies_files(tmp_path):
    folder = tmp_path / "b"
    folder.mkdir()
    for name in ("1-a-database.sql.gz", "1-a-files.tar", "1-a-private-files.tar"):
        (folder / name).write_text("x")
    files = BackupStore._classify(folder)
    assert files["public"].name.endswith("-a-files.tar") and files["private"].name.endswith("private-files.tar")


def test_backup_requires_database(tmp_path):
    with pytest.raises(FmtError):
        BackupStore._classify(tmp_path)


def test_latest_backup_and_state(tmp_path):
    site = make_site(tmp_path)
    store = BackupStore(site, ComposeProject(site))
    with pytest.raises(FmtError):
        store.latest()
    (store.root / "2026-01-01_000000").mkdir()
    (store.root / "2026-02-01_000000").mkdir()
    assert store.latest().name == "2026-02-01_000000"


def test_parse_certificate_and_verdict():
    text = "notAfter=Jan  5 10:00:00 2099 GMT\nissuer=C=US, O=Let's Encrypt, CN=R11\n"
    certificate = parse_certificate(text)
    assert certificate.verdict().startswith("OK") and not certificate.is_traefik_default


def test_default_traefik_certificate_detected():
    text = "notAfter=Jan  5 10:00:00 2099 GMT\nissuer=CN=TRAEFIK DEFAULT CERT\n"
    assert parse_certificate(text).verdict().startswith("Not issued")
