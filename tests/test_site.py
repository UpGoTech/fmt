import pytest

from fmt.compose import ComposeProject
from fmt.process import FmtError
from fmt.site import Site, validate_domain


def test_validate_domain():
    assert validate_domain(" ERP.Example.com ") == "erp.example.com"
    with pytest.raises(FmtError):
        validate_domain("localhost")


def test_initialize_writes_env_and_compose(tmp_path):
    site = Site("my-erp.example.com", tmp_path)
    site.initialize({"SITE": site.name, "IMAGE": "x"})
    assert site.exists() and site.env.read()["IMAGE"] == "x"
    assert oct(site.env.path.stat().st_mode)[-3:] == "600"
    assert [found.name for found in Site.all(tmp_path)] == ["my-erp.example.com"]


def test_initialize_refuses_existing(tmp_path):
    site = Site("a.example.com", tmp_path)
    site.initialize({"SITE": site.name})
    with pytest.raises(FmtError):
        site.initialize({})


def test_env_update(tmp_path):
    site = Site("a.example.com", tmp_path)
    site.initialize({"SITE": site.name, "IMAGE": "old"})
    site.env.update(IMAGE="new")
    assert site.env.read() == {"SITE": "a.example.com", "IMAGE": "new"}


def test_compose_command_targets_project(tmp_path):
    site = Site("a.example.com", tmp_path)
    command = ComposeProject(site).command("up", "-d")
    assert command[:5] == ["docker", "compose", "-p", "a-example-com", "--project-directory"]
    assert command[-2:] == ["up", "-d"]
