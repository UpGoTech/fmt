import json
import re
from dataclasses import dataclass

from fmt.process import FmtError, output, run

PROXY_NETWORK = "fmt-proxy"
IGNORED_NETWORKS = {"bridge", "host", "none"}


@dataclass
class TraefikConfig:
    network: str
    entrypoint_web: str = "web"
    entrypoint_secure: str = "websecure"
    certresolver: str = "letsencrypt"


def parse_arguments(arguments):
    """Read entrypoint and resolver names from Traefik CLI flags; falls back to defaults."""
    web = re.search(r"entrypoints\.([^.= ]+)\.address=:80(?:\s|$)", arguments)
    secure = re.search(r"entrypoints\.([^.= ]+)\.address=:443(?:\s|$)", arguments)
    resolver = re.search(r"certificatesresolvers\.([^.= ]+)", arguments, re.IGNORECASE)
    return {
        "entrypoint_web": web.group(1) if web else "web",
        "entrypoint_secure": secure.group(1) if secure else "websecure",
        "certresolver": resolver.group(1) if resolver else "letsencrypt",
    }


class TraefikDetector:
    def find_container(self):
        lines = output(["docker", "ps", "--format", "{{.Names}} {{.Image}}"]).splitlines()
        for line in lines:
            name, _, image = line.partition(" ")
            if "traefik" in image.lower():
                return name
        raise FmtError("No running Traefik container found. Start Traefik first.")

    def detect(self, network=None, certresolver=None):
        container = self.find_container()
        info = json.loads(output(["docker", "inspect", container]))[0]
        settings = parse_arguments(" ".join(info["Args"]))
        if certresolver:
            settings["certresolver"] = certresolver
        network = network or self._network(container, info)
        return TraefikConfig(network=network, **settings)

    def _network(self, container, info):
        names = [n for n in info["NetworkSettings"]["Networks"] if n not in IGNORED_NETWORKS]
        if names:
            return names[0]
        self._ensure_network(PROXY_NETWORK)
        if info["HostConfig"]["NetworkMode"] != "host":
            run(["docker", "network", "connect", PROXY_NETWORK, container], check=False)
        return PROXY_NETWORK

    def _ensure_network(self, name):
        if run(["docker", "network", "inspect", name], check=False, capture=True).returncode:
            run(["docker", "network", "create", name], capture=True)
