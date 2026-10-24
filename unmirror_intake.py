# ---
# summary: the unMirror INTAKE -- one door for a received source of any shape, plus the two
#   legs LAB 110's stack never grew. C mints a mirror and its row; D retires a corpus
#   (directory parked, row flipped, nothing deleted); V joins registry rows against disk and
#   reports disagreements in buckets. Shape routing carried forward from mirror_intake.py v2.
# operator: artificer
# agent(s): scrivener.Hammerlocke
# origin: LAB 162 - unMirror, 2026-10-24. The D and V legs answer a gap measured that day:
#   no verb anywhere in the LAB 110 stack clears a mirror, and register() leaves a standing
#   row alone, so a corpus key once written left by no mechanism.
# location: LAB 162 - unMirror/CODE/unmirror_intake.py  (marker deck8unmirror_root)
# tags: [unmirror, intake, crudvb, lab162]
# release_status: released
# version: 1
# ---
"""
unmirror_intake -- receive, render, register, retire, verify.

  python unmirror_intake.py mint   --source <tree|file.pdf|file.zip|dir> --name <key> [--out <dir>]
  python unmirror_intake.py retire --name <key> [--note "why"] [--dry]
  python unmirror_intake.py verify [--name <key>]
  python unmirror_intake.py list

CRUD-VB, as far as this container carries it:
  C  mint     render a source into a mirror and append its registry row
  R  list     the corpus estate, own rows and inherited ones alike
  D  retire   park the mirror directory, flip the row to retired. CAN reads as DEAD,
              never as GONE: nothing gets deleted and the row keeps its place.
  V  verify   join rows against disk, report in buckets

U (re-mint in place) and B (slice the registry off-node) stay unbuilt. Named here so a
later reader sees the gap rather than assuming the set complete.
"""
import argparse
import json
import os
import shutil
import sys
import time
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import unmirror_registry as reg  # noqa: E402
from unmirror import to_text, SOURCE_EXT  # noqa: E402

ENGINE = os.path.join(HERE, "unmirror.py")


# ---------------------------------------------------------------- render helpers

def txt_count(root):
    n = 0
    for _, _, files in os.walk(root):
        n += sum(1 for f in files if f.endswith(".txt"))
    return n


def mirror_tree(src, out):
    import subprocess
    r = subprocess.run([sys.executable, ENGINE, "--src", src, "--out", out],
                       capture_output=True, text=True)
    sys.stdout.write(r.stdout)
    if r.returncode != 0:
        sys.stderr.write(r.stderr)
        raise SystemExit("engine failed on tree: %s" % src)


def mirror_pdf(pdf, out):
    """One PDF -> one .txt carrying per-page separators.

    KNOWN SHAPE, carried forward deliberately and measured 2026-10-24: a PDF corpus
    renders as ONE text file however long the book runs, so the registry's file count
    reads 1 for a PDF. LAB 110's rows turing1950 and trustingtrust both carry that.
    The field now reads `files` rather than `pages`, which names what it counts.
    """
    from pypdf import PdfReader
    name = os.path.splitext(os.path.basename(pdf))[0]
    reader = PdfReader(pdf)
    os.makedirs(out, exist_ok=True)
    dst = os.path.join(out, name + ".txt")
    parts = ["# mirror :: %s\n# source: %s\n" % (name, os.path.basename(pdf))]
    for i, page in enumerate(reader.pages, 1):
        text = (page.extract_text() or "").strip()
        parts.append("\n--- page %d ---\n%s\n" % (i, text))
    with open(dst, "w", encoding="utf-8", newline="\n") as f:
        f.write("".join(parts))
    print("PDF     %-40s -> %s  (%d pages)" % (os.path.basename(pdf), dst, len(reader.pages)))


def mirror_file(src, out):
    """One text-shaped file -> one .txt, through the engine's own renderer."""
    if not src.lower().endswith(SOURCE_EXT):
        raise SystemExit("unhandled file type: %s (want one of %s)"
                         % (src, ", ".join(SOURCE_EXT)))
    name = os.path.splitext(os.path.basename(src))[0]
    os.makedirs(out, exist_ok=True)
    dst = os.path.join(out, name + ".txt")
    raw = open(src, encoding="utf-8", errors="ignore").read()
    with open(dst, "w", encoding="utf-8", newline="\n") as f:
        f.write("# mirror :: %s\n# source: %s\n\n%s\n"
                % (name, os.path.basename(src), to_text(raw)))
    print("FILE    %-40s -> %s" % (os.path.basename(src), dst))


# ---------------------------------------------------------------- C: mint

def cmd_mint(args):
    cfg = reg.config()
    src = os.path.abspath(args.source)
    if not os.path.exists(src):
        return {"ok": False, "verdict": "NO_SUCH_SOURCE", "source": src}

    standing = reg.get(args.name, cfg)
    if standing:
        return {"ok": False, "verdict": "KEY_STANDS", "key": args.name,
                "origin": standing.get("origin"),
                "note": "retire it first, or pick another key"}

    base = os.path.dirname(src if os.path.isfile(src) else src.rstrip("\\/"))
    out = (os.path.abspath(args.out) if args.out
           else os.path.join(base, args.name.upper() + "-TEXT"))

    low = src.lower()
    if os.path.isfile(src) and low.endswith(".zip"):
        unpacked = os.path.join(base, args.name.upper() + "-UNPACKED")
        with zipfile.ZipFile(src) as z:
            z.extractall(unpacked)
        print("ZIP unpacked -> %s" % unpacked)
        pdfs = [os.path.join(dp, f) for dp, _, fs in os.walk(unpacked)
                for f in fs if f.lower().endswith(".pdf")]
        mirror_tree(unpacked, out)
        for p in pdfs:
            mirror_pdf(p, out)
    elif os.path.isfile(src) and low.endswith(".pdf"):
        mirror_pdf(src, out)
    elif os.path.isfile(src):
        mirror_file(src, out)
    elif os.path.isdir(src):
        pdfs = [os.path.join(src, f) for f in os.listdir(src) if f.lower().endswith(".pdf")]
        textish = any(f.lower().endswith((".htm", ".html", ".xml", ".rst", ".md"))
                      for f in os.listdir(src))
        if pdfs and not textish:
            for p in pdfs:
                mirror_pdf(p, out)
        else:
            mirror_tree(src, out)
    else:
        return {"ok": False, "verdict": "UNHANDLED_SHAPE", "source": src}

    n = txt_count(out)
    row = reg.add(args.name, args.label or args.name, src, out, n,
                  engine_version=1, cfg=cfg)
    row.update({"mirror": out, "files": n})
    return row


# ---------------------------------------------------------------- D: retire

def cmd_retire(args):
    """Park the mirror directory, flip the row. NOTHING gets deleted.

    The operator's standing reading: CAN means DEAD, not GONE. So the directory moves
    to the configured can_root (or sits beside itself under a RETIRED- prefix where no
    can_root exists), and the registry row stays in place carrying status: retired.
    A retired corpus still answers "what did we once mirror and where did it go".
    """
    cfg = reg.config()
    row = reg.get(args.name, cfg)
    if not row:
        return {"ok": False, "verdict": "NO_SUCH_KEY", "key": args.name,
                "known": sorted(k for k in reg.rows(cfg) if not k.startswith("__blind__"))}
    if row.get("origin") != "own":
        return {"ok": False, "verdict": "INHERITED_READ_ONLY", "key": args.name,
                "registry": row.get("registry_file"),
                "note": "retire it where it lives; unMirror borrows this registry"}
    if str(row.get("status", "live")).lower() == str(
            cfg.get("retire", {}).get("status", "retired")).lower():
        return {"ok": True, "verdict": "ALREADY_RETIRED", "key": args.name}

    mirror = row.get("mirror")
    can_root = cfg.get("retire", {}).get("can_root")
    status = cfg.get("retire", {}).get("status", "retired")
    stamp = time.strftime("%Y%m%d")
    if mirror and os.path.isdir(mirror):
        if can_root:
            os.makedirs(can_root, exist_ok=True)
            dest = os.path.join(can_root, "%s-%s" % (os.path.basename(mirror), stamp))
        else:
            dest = os.path.join(os.path.dirname(mirror),
                                "RETIRED-%s-%s" % (os.path.basename(mirror), stamp))
        if args.dry:
            return {"ok": True, "verdict": "DRY", "key": args.name,
                    "would_move": mirror, "to": dest, "would_set_status": status}
        if os.path.exists(dest):
            return {"ok": False, "verdict": "PARK_OCCUPIED", "key": args.name, "dest": dest}
        shutil.move(mirror, dest)
    else:
        dest = None
        if args.dry:
            return {"ok": True, "verdict": "DRY", "key": args.name,
                    "would_move": None, "note": "no mirror directory on disk",
                    "would_set_status": status}

    out = reg.set_status(args.name, status,
                         note=args.note or "retired %s" % time.strftime("%Y-%m-%d"), cfg=cfg)
    out.update({"verdict": "RETIRED", "key": args.name, "parked": dest,
                "deleted": False,
                "note": "directory parked and row flipped. Nothing deleted; "
                        "a retired corpus still answers where it went."})
    return out


# ---------------------------------------------------------------- V: verify

def cmd_verify(args):
    """Join registry rows against disk. Report in BUCKETS, never as one clean verdict.

    Buckets:
      ok              row stands, mirror directory present, file count matches
      count_drift     directory present, file count disagrees with the row
      mirror_missing  row stands, directory absent from disk
      orphan_retired  row reads retired and a directory still sits at its path
      blind           a registry this reading could not open
    """
    cfg = reg.config()
    allrows = reg.rows(cfg)
    retired_status = str(cfg.get("retire", {}).get("status", "retired")).lower()
    buckets = {"ok": [], "count_drift": [], "mirror_missing": [],
               "orphan_retired": [], "blind": []}
    keys = [args.name] if args.name else sorted(allrows)
    for k in keys:
        row = allrows.get(k)
        if row is None:
            buckets["mirror_missing"].append({"key": k, "note": "no registry row"})
            continue
        if row.get("status") == "BLIND":
            buckets["blind"].append({"registry": row.get("registry_file"),
                                     "note": row.get("label")})
            continue
        m = row.get("mirror")
        present = bool(m) and os.path.isdir(m)
        retired = str(row.get("status", "live")).lower() == retired_status
        if retired:
            if present:
                buckets["orphan_retired"].append({"key": k, "mirror": m})
            else:
                buckets["ok"].append({"key": k, "status": "retired"})
            continue
        if not present:
            buckets["mirror_missing"].append({"key": k, "mirror": m,
                                              "origin": row.get("origin")})
            continue
        on_disk = txt_count(m)
        claimed = row.get("files", row.get("pages"))
        if claimed is not None and int(claimed) != on_disk:
            buckets["count_drift"].append({"key": k, "row": int(claimed),
                                           "disk": on_disk, "mirror": m})
        else:
            buckets["ok"].append({"key": k, "files": on_disk})
    summary = {b: len(v) for b, v in buckets.items()}
    clean = all(summary[b] == 0 for b in
                ("count_drift", "mirror_missing", "orphan_retired", "blind"))
    return {"ok": True, "verdict": "PARITY" if clean else "DRIFT",
            "summary": summary, "buckets": buckets}


# ---------------------------------------------------------------- R: list

def cmd_list(args):
    cfg = reg.config()
    out = []
    for k, v in sorted(reg.rows(cfg).items()):
        if k.startswith("__blind__"):
            out.append({"key": k, "status": "BLIND", "registry": v.get("registry_file")})
            continue
        out.append({"key": k, "label": v.get("label"), "origin": v.get("origin"),
                    "status": v.get("status", "live"),
                    "files": v.get("files", v.get("pages")),
                    "mirror": v.get("mirror"), "stamped": v.get("stamped")})
    return {"ok": True, "verdict": "LISTED", "count": len(out),
            "own_registry": reg.own_path(cfg), "corpora": out}


# ---------------------------------------------------------------- CLI

def main():
    ap = argparse.ArgumentParser(description="unMirror intake: mint, retire, verify, list.")
    sub = ap.add_subparsers(dest="verb", required=True)

    m = sub.add_parser("mint", help="C -- render a source and register it")
    m.add_argument("--source", required=True)
    m.add_argument("--name", required=True, help="corpus key, lowercase")
    m.add_argument("--label", help="human line for the row; defaults to the key")
    m.add_argument("--out", help="mirror destination (default: <NAME>-TEXT beside the source)")

    r = sub.add_parser("retire", help="D -- park the mirror, flip the row, delete nothing")
    r.add_argument("--name", required=True)
    r.add_argument("--note")
    r.add_argument("--dry", action="store_true", help="print the plan, move nothing")

    v = sub.add_parser("verify", help="V -- join rows against disk, report in buckets")
    v.add_argument("--name", help="one corpus; omit for the whole estate")

    sub.add_parser("list", help="R -- the corpus estate, own and inherited")

    args = ap.parse_args()
    try:
        out = {"mint": cmd_mint, "retire": cmd_retire,
               "verify": cmd_verify, "list": cmd_list}[args.verb](args)
    except reg.RegistryBlind as e:
        out = {"ok": False, "verdict": "BLIND", "note": str(e)}
    print(json.dumps(out, indent=2, default=str))
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
