# ---
# summary: the unMirror SERVICE -- a read-only MCP server over the corpus estate, so a codex
#   (or any MCP-speaking) endpoint grounds its writing in the mirrors instead of in priors.
#   Four tools: list_corpora, query_mirror, fetch_page, verify_estate. No write tool exists.
# operator: artificer
# agent(s): scrivener.Hammerlocke
# origin: LAB 162 - unMirror, 2026-10-24, on the operator's word: a codex
#   service-instance-endpoint runs on GUTS and needs a textMirror stack of its own. The
#   SERVICE layer carries the whole point, since codex speaks MCP rather than slashes.
# location: LAB 162 - unMirror/CODE/unmirror_mcp.py  (marker deck8unmirror_root)
# tags: [unmirror, mcp, service, readonly, lab162]
# release_status: released
# version: 1
# lineage: transport shape and the funnel/allowed_hosts handling follow
#   lab3120_mcp_server.py v2 (LAB 134), which already carries the tunnel scars.
# ---
"""
unmirror-mcp -- the corpus estate as MCP tools.

  python unmirror_mcp.py                 stdio (local attach, the default)
  python unmirror_mcp.py --http [port]   streamable-http (a served endpoint)

READ-ONLY by construction. Minting, retiring and verifying-with-intent belong to
unmirror_intake.py on the serving node; nothing here writes a byte. A connected model
can read the estate and quote it, and can change nothing.

Every path, port and allowed host comes off unmirror.yaml. The code carries no default
worth editing.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import unmirror_registry as reg  # noqa: E402

from mcp.server import MCPServer  # noqa: E402

SAFE_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\-]{0,80}$")

try:
    CFG = reg.config()
except reg.RegistryBlind as e:
    # The server stands up and CONFESSES rather than serving a silently empty estate.
    CFG = {"__blind__": str(e)}

QCFG = CFG.get("query", {}) if "__blind__" not in CFG else {}
SCFG = CFG.get("service", {}) if "__blind__" not in CFG else {}

# fetch_page returns a WINDOW. One rendered page here reaches millions of characters
# (measured 2026-10-24: neon/llms-full.txt, 5,716,883 chars), which no caller holds.
FETCH_LINES = int(QCFG.get("fetch_lines", 400))
FETCH_CHARS = int(QCFG.get("fetch_chars", 60000))

mcp = MCPServer(
    name=SCFG.get("name", "unmirror"), version="1",
    description="Read-only access to the estate's text mirrors: rendered plain-text "
                "twins of documentation corpora, so an answer rests on the corpus "
                "rather than on training priors.")


def tool(fn):
    mcp.add_tool(fn)
    return fn


def _blind():
    return {"error": "BLIND", "note": CFG.get("__blind__")} if "__blind__" in CFG else None


def _visible():
    """Live, non-blind rows carrying a mirror path."""
    out = {}
    for k, v in reg.rows(CFG).items():
        if k.startswith("__blind__") or v.get("status") == "BLIND":
            continue
        out[k] = v
    return out


@tool
def list_corpora() -> dict:
    """Every text mirror this server can see, keyed by corpus. Each row names its
    human label, its status (live or retired), how many text files it holds, when it
    got stamped, and whether unMirror minted it or inherits it read-only from another
    registry. Call this first: a query needs an exact corpus key."""
    b = _blind()
    if b:
        return b
    rows = reg.rows(CFG)
    blind = [{"registry": v.get("registry_file"), "note": v.get("label")}
             for k, v in rows.items() if v.get("status") == "BLIND"]
    corpora = [{"key": k, "label": v.get("label"), "status": v.get("status", "live"),
                "files": v.get("files", v.get("pages")), "stamped": v.get("stamped"),
                "origin": v.get("origin"), "labels": v.get("labels")}
               for k, v in sorted(rows.items()) if not k.startswith("__blind__")]
    out = {"count": len(corpora), "corpora": corpora}
    if blind:
        # An instrument confesses its blindness. A registry it could not open gets
        # NAMED, so a short list never reads as a complete estate.
        out["blind_registries"] = blind
        out["reading"] = "DEGRADED"
    else:
        out["reading"] = "COMPLETE"
    return out


@tool
def query_mirror(corpus: str, pattern: str, case_sensitive: bool = False,
                 max_passages: int = 0) -> dict:
    """Search one text mirror and get readable passages back with file and line.

    Pass a corpus key from list_corpora and a regular-expression pattern. Returns the
    hit count, then up to max_passages passages with surrounding context, naming how
    many it dropped. An empty result answers a question about the MIRROR, never about
    the world: the mirror may lag its source, so the corpus stamp comes back with it."""
    b = _blind()
    if b:
        return b
    if not SAFE_KEY.match(corpus):
        return {"error": "bad corpus key"}
    row = _visible().get(corpus)
    if not row:
        return {"error": "no such corpus", "known": sorted(_visible())}
    mirror = row.get("mirror")
    if not mirror or not os.path.isdir(mirror):
        return {"error": "mirror absent from disk", "corpus": corpus, "mirror": mirror,
                "status": row.get("status", "live")}
    cs = case_sensitive or QCFG.get("case_sensitive", False)
    try:
        rx = re.compile(pattern if cs else "(?i)" + pattern)
    except re.error as e:
        return {"error": "bad pattern", "note": str(e)}

    before = int(QCFG.get("context_before", 2))
    after = int(QCFG.get("context_after", 6))
    cap = int(max_passages or QCFG.get("max_passages", 5))

    hits, passages = 0, []
    for dirpath, _, files in os.walk(mirror):
        for fn in sorted(files):
            if not fn.endswith(".txt"):
                continue
            p = os.path.join(dirpath, fn)
            try:
                lines = open(p, encoding="utf-8", errors="ignore").read().splitlines()
            except OSError:
                continue
            for i, ln in enumerate(lines):
                if not rx.search(ln):
                    continue
                hits += 1
                if len(passages) < cap:
                    lo, hi = max(0, i - before), min(len(lines), i + after + 1)
                    passages.append({
                        "file": os.path.relpath(p, mirror).replace("\\", "/"),
                        "line": i + 1,
                        "text": "\n".join(lines[lo:hi]).strip()})
    return {"corpus": corpus, "pattern": pattern, "hits": hits,
            "showing": len(passages), "dropped": max(0, hits - len(passages)),
            "stamped": row.get("stamped"), "status": row.get("status", "live"),
            "passages": passages,
            "note": ("0 hits names what the mirror holds, never what the source holds; "
                     "this mirror carries the %s stamp" % row.get("stamped"))
                    if hits == 0 else None}


@tool
def fetch_page(corpus: str, path: str, start_line: int = 1, max_lines: int = 0) -> dict:
    """Read a rendered page out of a mirror, by line window. Pass a corpus key and the
    file path exactly as query_mirror reported it, plus the line query_mirror gave you
    as start_line. Use this after a query when the passage context runs too short.

    A window, never the whole file: one rendered page in this estate reaches millions
    of characters (measured: neon/llms-full.txt, 5.7M), which no caller can hold. The
    reply names total_lines and has_more so a reader walks the file in windows."""
    b = _blind()
    if b:
        return b
    if not SAFE_KEY.match(corpus):
        return {"error": "bad corpus key"}
    row = _visible().get(corpus)
    if not row:
        return {"error": "no such corpus", "known": sorted(_visible())}
    mirror = row.get("mirror") or ""
    target = os.path.normpath(os.path.join(mirror, path))
    # Containment check: a page request never escapes its own mirror root.
    if not os.path.normpath(target).startswith(os.path.normpath(mirror) + os.sep):
        return {"error": "path escapes the mirror root"}
    if not os.path.isfile(target):
        return {"error": "no such page", "corpus": corpus, "path": path}

    cap = int(max_lines or FETCH_LINES)
    lo = max(0, int(start_line) - 1)
    lines = open(target, encoding="utf-8", errors="ignore").read().splitlines()
    window = lines[lo:lo + cap]
    text = "\n".join(window)
    if len(text) > FETCH_CHARS:
        text = text[:FETCH_CHARS]
        truncated = True
    else:
        truncated = False
    return {"corpus": corpus, "path": path, "stamped": row.get("stamped"),
            "start_line": lo + 1, "end_line": lo + len(window),
            "total_lines": len(lines), "chars": len(text),
            "char_truncated": truncated,
            "has_more": lo + len(window) < len(lines),
            "text": text}


@tool
def verify_estate() -> dict:
    """Join every registry row against what sits on disk and report the disagreements
    in buckets: ok, count_drift, mirror_missing, orphan_retired, blind. Read-only:
    it reports drift and repairs nothing. Use it before trusting a quiet answer."""
    b = _blind()
    if b:
        return b
    import argparse
    import unmirror_intake as intake
    ns = argparse.Namespace(name=None)
    out = intake.cmd_verify(ns)
    out["note"] = "read-only reading; repair runs through unmirror_intake on the serving node"
    return out


if __name__ == "__main__":
    if "--http" in sys.argv:
        i = sys.argv.index("--http")
        port = int(sys.argv[i + 1]) if len(sys.argv) > i + 1 else int(
            SCFG.get("http_port", 8162))
        from mcp.server.transport_security import TransportSecuritySettings
        # Mount at "/" rather than the default /mcp: a tailscale funnel strips its
        # --set-path prefix, so a public /mcp arrives here as "/". LAB 134 wears that scar.
        sec = TransportSecuritySettings(
            allowed_hosts=list(SCFG.get("allowed_hosts") or
                               ["127.0.0.1", "127.0.0.1:*", "localhost", "localhost:*"]))
        mcp.run(transport="streamable-http", host=SCFG.get("http_host", "127.0.0.1"),
                port=port, streamable_http_path="/", transport_security=sec)
    else:
        mcp.run()  # stdio
