import json

from fmt.routing import SiteRouting, is_local_domain
from fmt.traefik import TraefikConfig

TRAEFIK = TraefikConfig(network="proxy", certresolver="le")


def test_is_local_domain():
    assert is_local_domain("abc.localhost") and is_local_domain("shop.test")
    assert not is_local_domain("abc.example.com")


def test_secure_routing_has_resolver_and_redirect():
    labels = SiteRouting("a.example.com", "a-example-com", TRAEFIK, local=False).labels()
    assert "traefik.http.routers.a-example-com-https.tls.certresolver=le" in labels
    assert any("redirectscheme.scheme=https" in label for label in labels)


def test_local_routing_is_plain_http():
    labels = SiteRouting("a.localhost", "a-localhost", TRAEFIK, local=True).labels()
    assert not any("tls" in label or "redirect" in label for label in labels)
    assert "traefik.http.routers.a-localhost.entrypoints=web" in labels


def test_render_is_valid_compose_override():
    data = json.loads(SiteRouting("a.localhost", "a", TRAEFIK, True).render())
    assert data["networks"]["proxy"]["name"] == "proxy"
    assert "proxy" in data["services"]["frontend"]["networks"]
