from pathlib import Path

from fmt.process import run
from fmt.traefik import PROXY_NETWORK

IMAGE = "traefik:v3.6"

COMPOSE = """services:
  traefik:
    image: {image}
    container_name: fmt-traefik
    restart: unless-stopped
    command:
      - --providers.docker=true
      - --providers.docker.exposedbydefault=false
      - --providers.docker.network={network}
      - --entrypoints.web.address=:80
      - --entrypoints.websecure.address=:443
{acme}    ports:
      - "80:80"
      - "443:443"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - ./letsencrypt:/letsencrypt
    networks: [proxy]

networks:
  proxy:
    external: true
    name: {network}
"""

ACME = """      - --certificatesresolvers.letsencrypt.acme.email={email}
      - --certificatesresolvers.letsencrypt.acme.storage=/letsencrypt/acme.json
      - --certificatesresolvers.letsencrypt.acme.httpchallenge.entrypoint=web
"""


class TraefikInstaller:
    def __init__(self, directory, network=PROXY_NETWORK):
        self.directory, self.network = Path(directory), network

    def render(self, email):
        acme = ACME.format(email=email) if email else ""
        return COMPOSE.format(image=IMAGE, network=self.network, acme=acme)

    def install(self, email=None):
        storage = self.directory / "letsencrypt"
        storage.mkdir(parents=True, exist_ok=True)
        (storage / "acme.json").touch(mode=0o600)
        (self.directory / "compose.yaml").write_text(self.render(email))
        if run(["docker", "network", "inspect", self.network], check=False, capture=True).returncode:
            run(["docker", "network", "create", self.network], capture=True)
        run(["docker", "compose", "-p", "fmt-traefik", "-f", str(self.directory / "compose.yaml"),
             "up", "-d", "--wait"])
