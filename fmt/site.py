import os
import re
import secrets
import shutil
from pathlib import Path

from fmt.process import FmtError

DOMAIN_PATTERN = re.compile(r"^([a-z0-9]([a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,}$")
TEMPLATE = Path(__file__).parent / "templates" / "compose.yaml"


def fmt_home():
    return Path(os.environ.get("FMT_HOME", "/opt/fmt"))


def validate_domain(name):
    name = name.strip().lower()
    if not DOMAIN_PATTERN.match(name):
        raise FmtError(f"'{name}' is not a valid domain name (e.g. erp.example.com)")
    return name


class EnvFile:
    def __init__(self, path):
        self.path = Path(path)

    def read(self):
        pairs = (line.split("=", 1) for line in self.path.read_text().splitlines() if "=" in line)
        return {key: value for key, value in pairs}

    def write(self, values):
        text = "".join(f"{key}={value}\n" for key, value in values.items())
        self.path.write_text(text)
        self.path.chmod(0o600)

    def update(self, **changes):
        self.write({**self.read(), **changes})


class Site:
    def __init__(self, name, home=None):
        self.name = name.strip().lower()
        self.home = Path(home) if home else fmt_home()

    @property
    def slug(self):
        return self.name.replace(".", "-")

    @property
    def directory(self):
        return self.home / self.slug

    @property
    def compose_path(self):
        return self.directory / "compose.yaml"

    @property
    def routing_path(self):
        return self.directory / "compose.traefik.yaml"

    @property
    def url(self):
        scheme = "https" if self.env.read().get("SSL", "true") == "true" else "http"
        return f"{scheme}://{self.name}"

    @property
    def env(self):
        return EnvFile(self.directory / ".env")

    def exists(self):
        return self.compose_path.exists()

    def require_existing(self):
        if not self.exists():
            raise FmtError(f"site '{self.name}' not found in {self.home}")
        return self

    def initialize(self, settings):
        if self.directory.exists():
            raise FmtError(f"{self.directory} already exists; try: fmt info {self.name}")
        (self.directory / "backups").mkdir(parents=True, mode=0o700)
        shutil.copy(TEMPLATE, self.compose_path)
        self.env.write(settings)

    def remove(self):
        shutil.rmtree(self.directory)

    @staticmethod
    def new_secret(length=16):
        return secrets.token_hex(length)

    @classmethod
    def all(cls, home=None):
        root = Path(home) if home else fmt_home()
        found = sorted(root.glob("*/compose.yaml")) if root.exists() else []
        return [cls(EnvFile(path.parent / ".env").read()["SITE"], root) for path in found]
