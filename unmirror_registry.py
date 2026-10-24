# ---
# summary: the unMirror REGISTRY layer -- loads unmirror.yaml, reads unMirror's own rows
#   plus any INHERITED registry read-through, and writes rows back to the own registry only.
#   The intake and the MCP service both go through here, so one reading of the corpus estate
#   serves both surfaces.
# operator: artificer
# agent(s): scrivener.Hammerlocke
# origin: LAB 162 - unMirror, 2026-10-24.
# location: LAB 162 - unMirror/CODE/unmirror_registry.py  (marker deck8unmirror_root)
# tags: [unmirror, registry, lab162]
# release_status: released
# version: 1
# ---
"""
unmirror_registry -- one door to the corpus estate.

  rows()                 every corpus unMirror can see, own rows first
  get(key)               one corpus row, or None
  add(key, **fields)     append a row to the OWN registry; refuses a live duplicate
  set_status(key, s)     flip a row's status in the OWN registry
  own_path()             where writes land

INHERITED registries read ONLY. A corpus minted in LAB 110 answers a query here and
never gets copied, forked or rewritten: its row carries origin='inherited' and every
write against it refuses. That keeps LAB 110's 36 standing rows authoritative where
they already live while unMirror mints its own beside them.

Config on surface: every path and policy comes from unmirror.yaml. Nothing here
carries a default worth editing.
"""
import os

try:
    import yaml
except ImportError:  # the registry degrades honestly rather than guessing
    yaml = None

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(HERE, "unmirror.yaml")


class RegistryBlind(RuntimeError):
    """The registry cannot answer. It says so rather than reporting an empty estate."""


def config(path=None):
    """Read unmirror.yaml. A missing PyYAML reads as BLIND, never as an empty config."""
    if yaml is None:
        raise RegistryBlind("PyYAML absent -- unmirror cannot read its control surface")
    p = path or CONFIG
    if not os.path.exists(p):
        raise RegistryBlind("no control surface at %s" % p)
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _resolve(p, base):
    return p if os.path.isabs(p) else os.path.join(base, p)


def own_path(cfg=None):
    cfg = cfg or config()
    return _resolve(cfg.get("registry", {}).get("own", "mirrors.yaml"), HERE)


def _load(path, missing_ok):
    """One registry file -> {key: row}.

    missing_ok distinguishes the two cases that a bare "file not there" collapses, and
    collapsing them produces a FALSE CLEAN: unMirror's OWN registry legitimately holds
    nothing before its first mint (missing_ok=True, reads EMPTY), while an INHERITED
    registry the node cannot reach reads BLIND (missing_ok=False, raises). Measured
    2026-10-24 during the build: pointing inherit at an unreachable path returned a
    one-row estate and zero blind registries, exactly the quiet answer this layer exists
    to refuse.
    """
    if not os.path.exists(path):
        if missing_ok:
            return {}
        raise OSError("registry not reachable at %s" % path)
    with open(path, encoding="utf-8") as f:
        doc = yaml.safe_load(f) or {}
    return doc.get("mirrors") or {}


def rows(cfg=None):
    """Every visible corpus. Own rows win a key collision; inherited rows carry
    origin='inherited' and refuse every write."""
    cfg = cfg or config()
    reg = cfg.get("registry", {})
    out = {}
    for src in reg.get("inherit") or []:
        p = _resolve(src, HERE)
        try:
            for k, v in _load(p, missing_ok=False).items():
                row = dict(v or {})
                row["origin"] = "inherited"
                row["registry_file"] = p
                out[k] = row
        except OSError as e:
            # An unreachable inherited registry gets NAMED, never swallowed. A node
            # that cannot see LAB 110 must read DEGRADED rather than clean-and-empty.
            out["__blind__%s" % os.path.basename(p)] = {
                "origin": "inherited", "registry_file": p,
                "status": "BLIND", "label": "unreachable: %s" % e}
    own = own_path(cfg)
    for k, v in _load(own, missing_ok=True).items():
        row = dict(v or {})
        row["origin"] = "own"
        row["registry_file"] = own
        out[k] = row
    return out


def blind(cfg=None):
    """The registries this reading could not open. An instrument confesses its blindness."""
    return {k: v for k, v in rows(cfg).items() if v.get("status") == "BLIND"}


def get(key, cfg=None):
    return rows(cfg).get(key)


def add(key, label, source, mirror, files, engine_version=1, minted_by="unmirror_intake",
        stamped=None, cfg=None):
    """Append a row to the OWN registry. Refuses a key that already stands anywhere,
    own or inherited, so one key never names two corpora."""
    import time
    cfg = cfg or config()
    existing = rows(cfg).get(key)
    if existing:
        return {"ok": False, "verdict": "KEY_STANDS", "key": key,
                "origin": existing.get("origin"),
                "note": "a row already carries this key -- retire it first, or pick another"}
    p = own_path(cfg)
    if not os.path.exists(p):
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write("# mirrors.yaml -- unMirror's OWN registry. Minted rows land here.\n"
                    "# Inherited registries read through unmirror.yaml and never get written.\n"
                    "# operator: artificer | agent: scrivener.Hammerlocke\n\nmirrors:\n")
    row = ("\n  %s:\n    label: \"%s\"\n    source: '%s'\n    mirror: '%s'\n"
           "    files: %d\n    engine_version: %d\n    status: live\n"
           "    stamped: \"%s\"\n    minted_by: %s\n"
           % (key, label, source, mirror, files, engine_version,
              stamped or time.strftime("%Y-%m-%d"), minted_by))
    with open(p, "a", encoding="utf-8", newline="\n") as f:
        f.write(row)
    return {"ok": True, "verdict": "ROW_APPENDED", "key": key, "registry": p}


def set_status(key, status, note=None, cfg=None):
    """Flip one OWN row's status in place. Refuses an inherited row: unMirror never
    writes into a registry it borrows."""
    cfg = cfg or config()
    row = rows(cfg).get(key)
    if not row:
        return {"ok": False, "verdict": "NO_SUCH_KEY", "key": key}
    if row.get("origin") != "own":
        return {"ok": False, "verdict": "INHERITED_READ_ONLY", "key": key,
                "registry": row.get("registry_file"),
                "note": "retire it where it lives; unMirror borrows this registry"}
    p = own_path(cfg)
    lines = open(p, encoding="utf-8").read().splitlines()
    marker = "  %s:" % key
    try:
        i = lines.index(marker)
    except ValueError:
        return {"ok": False, "verdict": "ROW_NOT_FOUND_IN_FILE", "key": key, "registry": p}
    j = i + 1
    wrote = False
    while j < len(lines) and (lines[j].startswith("    ") or not lines[j].strip()):
        if lines[j].strip().startswith("status:"):
            lines[j] = "    status: %s" % status
            wrote = True
        j += 1
    if not wrote:
        lines.insert(i + 1, "    status: %s" % status)
        j += 1
    if note:
        lines.insert(j, "    retire_note: \"%s\"" % note)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    return {"ok": True, "verdict": "STATUS_SET", "key": key, "status": status, "registry": p}
