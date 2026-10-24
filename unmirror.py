# ---
# summary: the unMirror ENGINE -- render a document corpus into a plain-text twin, one .txt
#   per source page, so ordinary search returns readable prose instead of markup. Carried
#   forward whole from textmirror.py v3 (LAB 110) so unMirror runs SELF-CONTAINED on a node
#   that never mounts the decks tree. Source-agnostic: point it at any tree of
#   .htm/.html/.xml/.rst/.md/.txt and name an output root.
# operator: artificer
# agent(s): scrivener.Hammerlocke
# origin: LAB 162 - unMirror, 2026-10-24, on the operator's word: a codex
#   service-instance-endpoint runs on GUTS and "they really need a textMirror stack. We can
#   call it unMirror."
# location: LAB 162 - unMirror/CODE/unmirror.py  (resolve by marker deck8unmirror_root)
# tags: [unmirror, engine, lab162]
# release_status: released
# version: 1
# lineage: textmirror.py v3, brick.Stefan, LAB 110 - TEXTMIRRORS. Carried, not imported:
#   unMirror must run where LAB 110 does not reach.
# ---
"""
unmirror -- the reusable render half of unMIRRORING.

  python unmirror.py --src <tree> --out <dir>
  python unmirror.py --src <tree> --out <dir> --label v2
  python unmirror.py --src <a> --label v1 --src <b> --label v2 --out <dir>

Writes one .txt per source page, mirroring the source tree's own directory shape.
Each output file carries a header naming its source path, so a search hit traces back.

Idempotent: it overwrites and holds no state, so a re-run after a `git pull` refreshes
the whole mirror. Never writes inside the source tree -- the clone stays pristine.
"""
import argparse
import html
import os
import re
import sys

SOURCE_EXT = (".htm", ".html", ".xml", ".rst", ".md", ".txt")
SKIP_DIRS = {".git", ".github", "static", "images", "img", "assets",
             "node_modules", "__pycache__", ".venv", "dist", "build"}

# Strip script/style wholesale -- their contents read as noise in a prose search.
DROP = re.compile(r"<(script|style)\b.*?</\1>", re.S | re.I)
# Close-tags of block elements become newlines, so paragraphs survive as paragraphs.
BLOCK = re.compile(r"</(p|div|h[1-6]|li|tr|pre|table|section|article|blockquote|dt|dd)>", re.I)
BREAK = re.compile(r"<br\s*/?>", re.I)
TAG = re.compile(r"<[^>]+>")


def to_text(raw):
    """Markup in, readable prose out. Order matters: drop, then break, then strip."""
    s = DROP.sub(" ", raw)
    s = BLOCK.sub("\n", s)
    s = BREAK.sub("\n", s)
    s = TAG.sub(" ", s)
    s = html.unescape(s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n\s*\n\s*\n+", "\n\n", s)
    return s.strip()


def mirror(src_root, out_root, label):
    if not os.path.isdir(src_root):
        print("SKIP %-6s no such tree: %s" % (label or "-", src_root))
        return 0, 1
    rendered, failed = 0, 0
    dest_base = os.path.join(out_root, label) if label else out_root
    for dirpath, dirs, files in os.walk(src_root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fn in files:
            if not fn.lower().endswith(SOURCE_EXT):
                continue
            src = os.path.join(dirpath, fn)
            rel = os.path.relpath(src, src_root)
            dst = os.path.join(dest_base, os.path.splitext(rel)[0] + ".txt")
            try:
                raw = open(src, encoding="utf-8", errors="ignore").read()
            except OSError as e:
                print("READ FAIL %s -- %s" % (src, e))
                failed += 1
                continue
            body = to_text(raw)
            try:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                with open(dst, "w", encoding="utf-8", newline="\n") as f:
                    f.write("# %s :: %s\n# source: %s\n\n%s\n"
                            % (label or "mirror", os.path.splitext(rel)[0],
                               rel.replace("\\", "/"), body))
            except OSError as e:
                print("WRITE FAIL %s -- %s" % (dst, e))
                failed += 1
                continue
            rendered += 1
    print("%-6s %d pages rendered%s" % (label or "mirror", rendered,
                                        ", %d FAILED" % failed if failed else ""))
    return rendered, failed


def main():
    ap = argparse.ArgumentParser(description="Render a document corpus into a plain-text twin.")
    ap.add_argument("--src", action="append", required=True,
                    help="source tree; repeat for several (pair each with its own --label)")
    ap.add_argument("--label", action="append", default=[],
                    help="subdirectory name for the matching --src (e.g. v1, v2); optional")
    ap.add_argument("--out", required=True, help="output root for the mirror")
    args = ap.parse_args()

    if len(args.label) > len(args.src):
        print("more --label than --src", file=sys.stderr)
        return 2
    labels = args.label + [""] * (len(args.src) - len(args.label))

    total, failures = 0, 0
    for src, label in zip(args.src, labels):
        r, f = mirror(os.path.abspath(src), os.path.abspath(args.out), label)
        total += r
        failures += f
    print("TOTAL: %d pages" % total)
    if failures:
        print("FAILURES: %d -- mirror INCOMPLETE" % failures)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
