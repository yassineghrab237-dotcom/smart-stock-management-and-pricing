import http.client
import ipaddress
import socket
import ssl
import time
from urllib.parse import urlsplit, urlunsplit, urljoin, quote

DOMAINS = {
    "Tunisianet": "tunisianet.com.tn",
    "Mytek": "mytek.tn",
    "Spacenet": "spacenet.tn",
}
USER_AGENT = "PreciosMonitor/1.0 (public product price monitoring)"


class CollectionError(ValueError):
    pass


def safe_url(retailer, url, product=True):
    if retailer not in DOMAINS:
        raise CollectionError("Enseigne inconnue.")
    if len(url) > 2000 or any(ord(c) < 33 for c in url) or "\\" in url:
        raise CollectionError("URL invalide.")
    parsed = urlsplit(url)
    host = DOMAINS[retailer]
    if (
        parsed.scheme != "https"
        or parsed.hostname not in (host, "www." + host)
        or parsed.username
        or parsed.password
        or parsed.port not in (None, 443)
    ):
        raise CollectionError("URL HTTPS de cette enseigne requise.")
    if product and (parsed.path in ("", "/") or parsed.query):
        raise CollectionError("Utilisez une URL de fiche produit sans paramètres.")
    path = quote(parsed.path or "/", safe="/%:@!$&'()*+,;=-._~")
    return urlunsplit(("https", parsed.hostname, path, parsed.query, ""))


class PublicHTTPS(http.client.HTTPSConnection):
    def connect(self):
        # Pin the connection to a checked address; retain hostname for TLS/SNI.
        addresses = socket.getaddrinfo(self.host, 443, type=socket.SOCK_STREAM)
        if not addresses or any(
            not ipaddress.ip_address(a[4][0]).is_global for a in addresses
        ):
            raise CollectionError("Adresse réseau non publique refusée.")
        raw = socket.create_connection((addresses[0][4][0], 443), timeout=self.timeout)
        try:
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except BaseException:
            raw.close()
            raise


def fetch(retailer, url, before_request=None, max_bytes=4 * 1024 * 1024):
    target = safe_url(retailer, url, product=False)
    for _ in range(4):
        parsed = urlsplit(target)
        if before_request:
            before_request(target)
        conn = PublicHTTPS(
            parsed.hostname, timeout=12, context=ssl.create_default_context()
        )
        try:
            conn.request(
                "GET",
                urlunsplit(("", "", parsed.path, parsed.query, "")),
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "text/html,text/plain,application/ld+json",
                    "Accept-Encoding": "identity",
                },
            )
            response = conn.getresponse()
            if response.status in (301, 302, 303, 307, 308):
                location = response.getheader("Location")
                if not location:
                    raise CollectionError("Redirection sans destination.")
                target = safe_url(retailer, urljoin(target, location), product=False)
                continue
            if response.status != 200:
                raise CollectionError(
                    f"Accès HTTP {response.status}. Aucun contournement ni prix enregistré."
                )
            if response.getheader("Content-Encoding", "identity").lower() not in (
                "identity",
                "",
            ):
                raise CollectionError("Encodage compressé inattendu ; lecture refusée.")
            content_type = response.getheader("Content-Type", "").lower()
            if not any(
                t in content_type
                for t in (
                    "text/html",
                    "text/plain",
                    "application/xhtml+xml",
                    "application/ld+json",
                )
            ):
                raise CollectionError("Le serveur ne renvoie pas une page lisible.")
            chunks = []
            size = 0
            started = time.monotonic()
            while True:
                chunk = response.read1(min(65536, max_bytes + 1 - size))
                if not chunk:
                    break
                chunks.append(chunk)
                size += len(chunk)
                if size > max_bytes:
                    break
                if time.monotonic() - started > 30:
                    raise CollectionError("Lecture trop lente ; collecte arrêtée.")
            data = b"".join(chunks)
            if len(data) > max_bytes:
                raise CollectionError("Page trop volumineuse ; lecture arrêtée.")
            return target, data
        except (OSError, http.client.HTTPException) as exc:
            raise CollectionError("Accès réseau ou TLS indisponible.") from exc
        finally:
            conn.close()
    raise CollectionError("Trop de redirections.")
