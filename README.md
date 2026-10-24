# unMirror

A text-mirror stack with an MCP front door.

unMirror renders a document corpus into a plain-text twin, registers it, and serves the
result to any MCP-speaking client as read-only tools. A model answering from a mirror
quotes the corpus instead of reaching for a training prior.

## Why a mirror

Documentation arrives as HTML, PDF, zip archives or a tree of Markdown. None of that
greps well, and none of it fits in a context window. A mirror renders the whole corpus
to plain text once, one `.txt` per source page, keeping the source tree's own shape.
After that an ordinary regex answers questions about it, and a client pulls back only
the passages it needs.

## The five pieces

| File | Layer | What it does |
|---|---|---|
| `unmirror.py` | engine | markup to prose, one `.txt` per source page, idempotent, never writes inside the source |
| `unmirror.yaml` | control surface | every path, port and policy; the scripts hold no default worth editing |
| `unmirror_registry.py` | registry | own rows plus read-through inheritance from other registries, which stay read-only |
| `unmirror_intake.py` | intake | `mint`, `list`, `retire`, `verify` |
| `unmirror_mcp.py` | service | read-only MCP server: `list_corpora`, `query_mirror`, `fetch_page`, `verify_estate` |

## Requirements

Python 3.9 or later, `PyYAML`, `mcp`, and `pypdf` for PDF sources.

```
pip install pyyaml mcp pypdf
```

## Use it

Render a corpus and register it:

```
python unmirror_intake.py mint --source ./docs --name mydocs --label "my project docs"
```

A source of any shape goes through that one door: a tree of `.htm/.html/.xml/.rst/.md/.txt`,
a `.pdf`, a `.zip`, or a directory of PDFs.

See what you hold, and check it against disk:

```
python unmirror_intake.py list
python unmirror_intake.py verify
```

Retire a corpus. The directory gets parked and the row flips to `retired`. Nothing gets
deleted, so a retired corpus still answers where it went:

```
python unmirror_intake.py retire --name mydocs --dry
python unmirror_intake.py retire --name mydocs --note "superseded by v2"
```

Serve it:

```
python unmirror_mcp.py                # stdio, for a local client attach
python unmirror_mcp.py --http 8162    # streamable-http, for a served endpoint
```

## What the service promises

**Read-only.** No write tool exists in the server. Minting, retiring and verifying with
intent all run through the intake on the serving node.

**Honest about what it cannot see.** A registry the node fails to open reads `BLIND`, and
every answer built on that reading carries `reading: DEGRADED`. An instrument that reports
a short list as a complete estate lies by omission, so this one refuses to.

**Honest about zero.** A query with no hits answers a question about the MIRROR, never
about the world: the mirror may lag its source. Every zero comes back with the corpus
stamp attached.

**Windows, not whole files.** `fetch_page` returns a line window carrying `total_lines`
and `has_more`. One rendered page in a real corpus measured 5.7 million characters, which
no client can hold.

**Contained.** A page request that tries to climb out of its mirror root gets refused.

## Operations covered

`mint` creates, `list` reads, `retire` deletes-without-deleting, `verify` reports drift in
buckets. Re-minting a corpus in place and slicing the registry off-node stay unbuilt, named
here so a reader sees the gap rather than assuming the set complete.

## Lineage

The render engine carries forward from `textmirror.py` v3, written by brick.Stefan. unMirror
carries it rather than importing it, so the stack runs on a node that reaches nothing else.
The retire and verify legs answer a gap measured in that earlier stack: no verb anywhere
cleared a mirror, and a registry row once written left by no mechanism.
