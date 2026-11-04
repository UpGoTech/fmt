import base64
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from fmt.process import run

FRAPPE_ORGANIZATION_URL = "https://github.com/frappe"
FRAPPE_DOCKER_URL = "https://github.com/frappe/frappe_docker"
OFFICIAL_IMAGE = "frappe/erpnext"


@dataclass(frozen=True)
class AppSpec:
    name: str
    url: str
    ref: str

    @classmethod
    def parse(cls, text, default_ref):
        source, ref = cls._split_ref(text.strip())
        if "/" in source or "@" in source:
            name = source.rstrip("/").rsplit("/", 1)[-1].removesuffix(".git")
            return cls(name, source, ref or default_ref)
        return cls(source, f"{FRAPPE_ORGANIZATION_URL}/{source}", ref or default_ref)

    @staticmethod
    def _split_ref(text):
        head, separator, tail = text.rpartition(":")
        if separator and tail and "/" not in tail:
            return head, tail
        return text, None

    def serialize(self):
        is_frappe_app = self.url == f"{FRAPPE_ORGANIZATION_URL}/{self.name}"
        return f"{self.name if is_frappe_app else self.url}:{self.ref}"


def parse_apps(text, default_ref):
    items = [item for item in (text or "erpnext").split(",") if item.strip()]
    return [AppSpec.parse(item, default_ref) for item in items]


class ImageResolver:
    """Official image when only erpnext at the frappe ref is requested, else a layered build."""

    def __init__(self, slug, frappe_ref, apps):
        self.slug, self.frappe_ref, self.apps = slug, frappe_ref, apps

    @property
    def is_official(self):
        return all(a.name == "erpnext" and a.ref == self.frappe_ref for a in self.apps)

    @property
    def apps_json(self):
        return json.dumps([{"url": a.url, "branch": a.ref} for a in self.apps], indent=2)

    @property
    def image(self):
        if self.is_official:
            return f"{OFFICIAL_IMAGE}:{self.frappe_ref}"
        digest = hashlib.sha256(f"{self.frappe_ref}{self.apps_json}".encode()).hexdigest()[:12]
        return f"fmt/{self.slug}:{digest}"


class ImageBuilder:
    def __init__(self, cache_directory):
        self.repository = Path(cache_directory) / "frappe_docker"

    def ensure(self, resolver, fresh=False):
        if resolver.is_official:
            run(["docker", "pull", resolver.image])
        elif fresh or not self._exists(resolver.image):
            self._build(resolver, fresh)

    def _exists(self, image):
        return run(["docker", "image", "inspect", image], check=False, capture=True).returncode == 0

    def _build(self, resolver, fresh=False):
        self._update_repository()
        encoded = base64.b64encode(resolver.apps_json.encode()).decode()
        run(self._build_command(resolver, encoded, fresh))

    def _build_command(self, resolver, encoded, fresh=False):
        return [
            "docker", "build", *(["--no-cache", "--pull"] if fresh else []), "--file", str(self.repository / "images/layered/Containerfile"),
            "--build-arg", f"FRAPPE_BRANCH={resolver.frappe_ref}",
            "--build-arg", f"APPS_JSON_BASE64={encoded}",
            "--tag", resolver.image, str(self.repository),
        ]

    def _update_repository(self):
        if (self.repository / ".git").exists():
            run(["git", "-C", str(self.repository), "pull", "--ff-only", "-q"], check=False)
            return
        self.repository.parent.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", "--depth", "1", FRAPPE_DOCKER_URL, str(self.repository)])

