import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone

WARN_DAYS = 14
DEFAULT_CERT_MARK = "TRAEFIK DEFAULT CERT"


@dataclass
class CertificateInfo:
    expires: datetime
    issuer: str

    @property
    def days_left(self):
        return (self.expires - datetime.now(timezone.utc)).days

    @property
    def is_traefik_default(self):
        return DEFAULT_CERT_MARK in self.issuer.upper()

    def verdict(self):
        if self.is_traefik_default:
            return "Not issued: Traefik is serving its default certificate"
        if self.days_left < 0:
            return "Expired"
        if self.days_left < WARN_DAYS:
            return f"Expiring in {self.days_left} days; Traefik should renew it, check its logs"
        return f"OK, {self.days_left} days left"


def parse_certificate(text):
    fields = dict(line.split("=", 1) for line in text.splitlines() if "=" in line)
    expires = datetime.strptime(" ".join(fields["notAfter"].split()), "%b %d %H:%M:%S %Y %Z")
    return CertificateInfo(expires.replace(tzinfo=timezone.utc), fields.get("issuer", "").strip())


def fetch_certificate(host, connect_to=None):
    target = f"{connect_to or host}:443"
    client = subprocess.run(
        ["openssl", "s_client", "-connect", target, "-servername", host],
        input="", capture_output=True, text=True, timeout=15, check=False)
    parsed = subprocess.run(
        ["openssl", "x509", "-noout", "-enddate", "-issuer"],
        input=client.stdout, capture_output=True, text=True, check=False)
    return parse_certificate(parsed.stdout)
