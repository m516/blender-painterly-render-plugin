# Vendored Cycles (third_party/cycles)

Verbatim files from Blender's Cycles renderer, pinned to upstream commits and checked by sha256.
The manifest is `VENDORED.toml`; the only tool that writes these files is `tools/vendor_sync.py` (T3.1).

## Licence and provenance

- **Apache-2.0**: Blender v5.2.2 `intern/cycles` (tag `v5.2.2`, commit
  `d13f752e3b9c4f8c261cda552b1021f8bcc0382c`). This covers the whole tree except `sse2neon/`.
- **MIT**: `sse2neon/` from DLTcollab/sse2neon at commit `227cc413fb2d50b2a10073087be96b59d5364aea`.
  Its licence text is `sse2neon/LICENSE`, which T3.2 vendors.

## Rules

- Never hand-edit a vendored file. To change one, change the pin in `VENDORED.toml` or add a patch in
  `patches/`, then run `tools/vendor_sync.py sync`.
- Patches apply in lexical order with `git apply`. A patched file carries the comment
  `Modified by the Painterly project` inside its patch.
- `patches/` holds only `*.patch` files.

## Commands

| Command | Does |
|---|---|
| `tools/vendor_sync.py fetch` | check out each upstream at its pinned commit under `.cache/vendor/` |
| `tools/vendor_sync.py sync` | regenerate the files from the checkouts and patches, rewrite `VENDORED.toml` |
| `tools/vendor_sync.py check [--upstream]` | verify the tree against the manifest; `--upstream` re-derives every file |
| `tools/vendor_sync.py add [--upstream NAME] PATH... [--dest-prefix P]` | vendor upstream files, then sync |
| `tools/vendor_sync.py remove DEST...` | drop vendored files and their entries, then sync |
| `tools/vendor_sync.py closure HEADER...` | print the `#include "..."` closure inside the Cycles root |

`make vendor-check` runs `check` without network access; it is part of `make check`.
