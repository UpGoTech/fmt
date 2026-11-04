import json

LOCAL_SUFFIXES = (".localhost", ".test", ".local", ".internal")


def is_local_domain(name):
    return name.endswith(LOCAL_SUFFIXES)


class SiteRouting:
    """Traefik labels and proxy network for a site, written as a compose override (JSON is YAML)."""

    def __init__(self, name, slug, traefik, local):
        self.name, self.slug, self.traefik, self.local = name, slug, traefik, local

    def labels(self):
        slug, rule = self.slug, f"Host(`{self.name}`)"
        labels = [
            "traefik.enable=true",
            f"traefik.docker.network={self.traefik.network}",
            f"traefik.http.services.{slug}.loadbalancer.server.port=8080",
        ]
        return labels + (self._plain_http(rule) if self.local else self._secure_http(rule))

    def _plain_http(self, rule):
        prefix = f"traefik.http.routers.{self.slug}"
        return [
            f"{prefix}.rule={rule}",
            f"{prefix}.entrypoints={self.traefik.entrypoint_web}",
            f"{prefix}.service={self.slug}",
        ]

    def _secure_http(self, rule):
        slug, traefik = self.slug, self.traefik
        secure, plain = f"traefik.http.routers.{slug}-https", f"traefik.http.routers.{slug}-http"
        redirect = f"traefik.http.middlewares.{slug}-redirect.redirectscheme"
        return [
            f"{secure}.rule={rule}",
            f"{secure}.entrypoints={traefik.entrypoint_secure}",
            f"{secure}.tls=true",
            f"{secure}.tls.certresolver={traefik.certresolver}",
            f"{secure}.service={slug}",
            f"{plain}.rule={rule}",
            f"{plain}.entrypoints={traefik.entrypoint_web}",
            f"{plain}.middlewares={slug}-redirect",
            f"{plain}.service={slug}",
            f"{redirect}.scheme=https",
            f"{redirect}.permanent=true",
        ]

    def render(self):
        return json.dumps({
            "services": {"frontend": {"networks": ["default", "proxy"], "labels": self.labels()}},
            "networks": {"proxy": {"external": True, "name": self.traefik.network}},
        }, indent=2)
