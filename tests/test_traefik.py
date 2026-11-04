import json

from fmt import traefik
from fmt.traefik import TraefikDetector, parse_arguments


def test_parse_arguments_reads_names():
    arguments = ("--entrypoints.http.address=:80 --entrypoints.https.address=:443 "
                 "--certificatesresolvers.le.acme.email=a@b.c")
    assert parse_arguments(arguments) == {
        "entrypoint_web": "http", "entrypoint_secure": "https", "certresolver": "le"}


def test_parse_arguments_defaults():
    assert parse_arguments("")["entrypoint_secure"] == "websecure"


def test_detect_uses_custom_network(monkeypatch):
    info = [{"Args": [], "NetworkSettings": {"Networks": {"bridge": {}, "web": {}}},
             "HostConfig": {"NetworkMode": "web"}}]

    def fake_output(command):
        return "traefik traefik:v3" if command[1] == "ps" else json.dumps(info)

    monkeypatch.setattr(traefik, "output", fake_output)
    config = TraefikDetector().detect(certresolver="mine")
    assert (config.network, config.certresolver) == ("web", "mine")
