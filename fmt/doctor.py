import json

from fmt.process import FmtError, output, run
from fmt.traefik import TraefikDetector, parse_arguments


class Doctor:
    """Each check returns (passed, detail)."""

    def __init__(self):
        self.container = None
        self.info = None

    def checks(self):
        return [
            ("Docker daemon", self.docker),
            ("Docker Compose v2", self.compose),
            ("Traefik running", self.traefik),
            ("Certificate resolver", self.resolver),
            ("acme.json persisted", self.acme_storage),
            ("Ports 80 and 443", self.ports),
        ]

    def run_all(self):
        results = []
        for name, check in self.checks():
            try:
                results.append((name, *check()))
            except (FmtError, OSError) as error:
                results.append((name, False, str(error).splitlines()[0]))
        return results

    def docker(self):
        return run(["docker", "info"], check=False, capture=True).returncode == 0, "reachable"

    def compose(self):
        return True, output(["docker", "compose", "version", "--short"])

    def traefik(self):
        self.container = TraefikDetector().find_container()
        self.info = json.loads(output(["docker", "inspect", self.container]))[0]
        return True, self.container

    def resolver(self):
        found = "certificatesresolvers" in " ".join(self.info["Args"]).lower()
        name = parse_arguments(" ".join(self.info["Args"]))["certresolver"]
        return found, name if found else "none in CLI flags; fine if defined in a static file"

    def acme_storage(self):
        mounts = [m["Destination"] for m in self.info["Mounts"]]
        found = any("acme" in m or "letsencrypt" in m or "certs" in m for m in mounts)
        return found, ", ".join(mounts) or "no volumes: certificates are lost on restart"

    def ports(self):
        ports = self.info["NetworkSettings"]["Ports"] or {}
        published = {key.split("/")[0] for key, value in ports.items() if value}
        host_mode = self.info["HostConfig"]["NetworkMode"] == "host"
        return host_mode or {"80", "443"} <= published, "host network" if host_mode else ", ".join(sorted(published))
