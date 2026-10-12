"""Règles robots utiles aux sources, jokers et priorité de la règle précise."""

import re
from urllib.parse import quote, urlsplit
from .network import CollectionError


def normalized(value):
    value = quote(value, safe="/%?:@!$&'()*+,;=-._~")

    def octet(match):
        char = chr(int(match.group(1), 16))
        return (
            char
            if char.isascii() and (char.isalnum() or char in "-._~")
            else "%" + match.group(1).upper()
        )

    return re.sub(r"%([0-9a-fA-F]{2})", octet, value)


def rules(text, url, agent="PreciosMonitor"):
    groups = []
    agents = []
    entries = []
    started = False
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        key, value = (s.strip() for s in line.split(":", 1))
        key = key.lower()
        if key == "user-agent":
            if started:
                groups.append((agents, entries))
                agents = []
                entries = []
                started = False
            agents.append(value.lower())
        elif agents and key in ("allow", "disallow", "crawl-delay"):
            entries.append((key, value))
            started = True
    if agents:
        groups.append((agents, entries))
    explicit = [
        (names, entries)
        for names, entries in groups
        if any(n != "*" and n in agent.lower() for n in names)
    ]
    selected = explicit or [
        (names, entries) for names, entries in groups if "*" in names
    ]
    parsed = urlsplit(url)
    path = normalized(parsed.path + ("?" + parsed.query if parsed.query else ""))
    matches = []
    delay = 10.0
    for _, entries in selected:
        for key, value in entries:
            if key == "crawl-delay":
                try:
                    delay = max(delay, float(value))
                except ValueError:
                    pass
                continue
            if not value:
                continue
            pattern = normalized(value)
            terminal = pattern.endswith("$")
            pattern = pattern[:-1] if terminal else pattern
            pattern = re.sub(r"\*+", "*", pattern)
            regex = (
                "^"
                + re.escape(pattern).replace(r"\*", ".*")
                + ("$" if terminal else "")
            )
            if re.search(regex, path):
                matches.append((len(pattern.replace("*", "").encode()), key == "allow"))
    if delay > 60 or not delay < float("inf"):
        raise CollectionError(
            "Cadence robots supérieure à la fenêtre de collecte locale ; source différée."
        )
    return (max(matches)[1] if matches else True), delay
