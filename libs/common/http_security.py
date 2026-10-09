"""Protection des services ML réservés au poste local, sans session métier."""

from urllib.parse import urlsplit


def same_origin_request(request) -> bool:
    origin = request.headers.get("origin")
    if origin:
        try:

            def normalized(value):
                parsed = urlsplit(value)
                if (
                    parsed.scheme not in ("http", "https")
                    or not parsed.hostname
                    or parsed.username
                    or parsed.password
                ):
                    return None
                return (
                    parsed.scheme,
                    parsed.hostname,
                    parsed.port or (443 if parsed.scheme == "https" else 80),
                )

            incoming = normalized(origin)
            return incoming is not None and incoming == normalized(
                str(request.base_url)
            )
        except ValueError:
            return False
    return request.headers.get("sec-fetch-site") in (None, "same-origin", "none")
