import socket
import urllib.request


def public_address():
    try:
        return urllib.request.urlopen("https://ifconfig.me/ip", timeout=5).read().decode().strip()
    except OSError:
        return None


def check_dns(domain):
    """Return a warning message when the domain does not point at this server, else None."""
    server = public_address()
    try:
        resolved = socket.gethostbyname(domain)
    except OSError:
        return f"{domain} does not resolve yet; certificate issuance fails until DNS points to {server or 'this server'}."
    if server and resolved != server:
        return f"{domain} resolves to {resolved} but this server is {server} (fine behind a proxy such as Cloudflare)."
    return None
