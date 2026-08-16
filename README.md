# Refree

![Refree screenshot](assets/screenshot.png)

A simple, self-hosted reference manager. Import references from Zotero, store
and serve attached PDFs, search your library, and merge duplicates — all from a
small FastAPI service with a built-in web UI.

## Features

- **Reference library** — create, read, update, and delete bibliographic
  references (title, authors, year, DOI, URL, publication, abstract, …) stored
  in SQLite via SQLModel.
- **Citation keys** — auto-generated `authorShortTitleYear` keys with
  disambiguation suffixes, or set your own.
- **Zotero integration**
  - *Browser connector*: the unmodified Zotero browser extension can save
    items and PDFs directly into refree by pointing it at port `23119`.
  - *Bulk import*: `scripts/import_zotero.py` pulls items and PDF attachments
    from a running Zotero + Better BibTeX instance.
- **PDF storage** — attachments are written to a managed directory and linked
  back to their reference; the UI streams them back on demand.
- **Search** — weighted token matching across title, authors, and auxiliary
  fields (DOI, publication, abstract, …).
- **Duplicate detection & merge** — references are clustered by DOI or
  normalized title + year/author; review groups in the UI and merge them with
  per-field survivor selection.
- **Web UI** — Jinja2 templates for browsing, searching, viewing details,
  reading PDFs, and resolving duplicates, alongside a JSON REST API.

## Configuration

refree reads `config.yaml` from `~/.refree/` (override with the
`REFREE_CONFIG_FILE` environment variable). On startup it ensures
`refree_dir` exists and places `refree.db` (SQLite) and a `pdfs/` directory
inside it.

```yaml
# ~/.refree/config.yaml
refree_dir: "~/.refree/data"
app_host: "127.0.0.1"
# The Zotero Connector probes 127.0.0.1:23119 — set this to 23119 so the
# unmodified extension can talk to refree as if it were the Zotero desktop
# client. Caveat: a real Zotero client and refree cannot run on 23119 at once.
app_port: 23119
```

See `config.example.yaml` for a starting point.

## Development

Development uses `uv` and a `.venv` (never pip). See `AGENTS.md` for the full
conventions.

```bash
# Create the virtualenv and install dependencies
uv sync

# Run the dev server (zellij layout: editor + fastapi panes)
./scripts/dev.sh
#   or, without zellij:
#   fastapi dev --host 127.0.0.1 --port 23119 app/main:app
```

## Install & autostart (Nix)

refree is installed and run with [Nix flakes](https://nixos.wiki/wiki/Flakes).
The flake builds a hermetic runtime environment from the pinned `uv.lock` (via
[uv2nix](https://github.com/pyproject-nix/uv2nix)) and exposes a `refree`
launcher that runs the FastAPI server.

### Run ad-hoc

```bash
nix run .#refree
# extra args forward to the fastapi CLI:
nix run .#refree -- --workers 2
```

Host and port default to `127.0.0.1:23119`; override with the `REFREE_HOST`
and `REFREE_PORT` environment variables. The launcher sets `PYTHONPATH` to the
project root, so it runs from anywhere.

### Install as a user service (Home Manager)

The flake ships a Home Manager module that installs refree as a **systemd user
service** that starts automatically when you log in. Add the flake as an input
and import the module:

```nix
# flake.nix
{
  inputs.refree.url = "git+file:///home/azada/code/refree"; # or your repo URL
  # …
}

# home.nix
{
  imports = [ inputs.refree.homeManagerModules.default ];
  services.refree = {
    enable = true;
    port = 23119;            # default
    host = "127.0.0.1";      # default
    dataDir = ~/.refree/data; # where the SQLite DB and PDFs live
  };
}
```

The module generates its config declaratively (from the options above) and
feeds it to the service via `REFREE_CONFIG_FILE`, so it does **not** read or
mutate `~/.refree/config.yaml`. Set `services.refree.dataDir` to your existing
library path to keep your data in place.

```bash
home-manager switch
systemctl --user status refree        # check status
journalctl --user -u refree -f        # follow logs
systemctl --user stop refree          # stop
systemctl --user disable refree       # stop autostart at login
```

Open the UI at `http://127.0.0.1:23119/` and check health at
`http://127.0.0.1:23119/heartbeat`.

### Importing from Zotero

With Zotero running and the Better BibTeX plugin installed:

```bash
# auto-detects the Zotero storage directory; override with --zotero-storage-dir
uv run python scripts/import_zotero.py --base-url http://127.0.0.1:23119
```

This pulls all non-attachment items, resolves Better BibTeX citation keys, and
links PDF attachments from the Zotero storage directory into refree.

### Zotero browser connector

To let the unmodified Zotero browser extension save directly into refree, run
the server on port `23119` (the port the connector probes). refree implements
the `/connector/*` endpoints the extension expects (`saveItems`,
`saveAttachment`, `saveSnapshot`, `updateSession`, `delaySync`, …).

## API overview

All endpoints are tagged in the OpenAPI docs served at `/docs`.

| Method | Path                                   | Description                            |
|--------|----------------------------------------|----------------------------------------|
| GET    | `/`                                    | Web UI: paginated reference list + search |
| GET    | `/references`                          | List references (paginated)            |
| GET    | `/references/{reference_id}`           | Get a reference by UUID                |
| GET    | `/references/key/{citation_key}`       | Get a reference by citation key        |
| POST   | `/references`                          | Create a reference (upsert by key)     |
| PUT    | `/references/{reference_id}`           | Update a reference                     |
| DELETE | `/references/{reference_id}`           | Delete a reference                     |
| GET    | `/references/duplicates`               | List duplicate groups                  |
| POST   | `/references/merge`                    | Merge references into a survivor       |
| GET    | `/search?q=...`                        | Weighted search across the library     |
| GET    | `/ui/reference/{reference_id}`         | Reference detail view                  |
| GET    | `/ui/reference/{reference_id}/pdf`    | Stream the reference's PDF             |
| GET    | `/ui/duplicates`                       | Duplicate-review view                  |
| POST   | `/ui/duplicates/merge`                 | Merge duplicates from the UI           |
| GET    | `/heartbeat`                           | Health check                           |

## Testing & linting

```bash
# lint, type-check, format, run tests, and audit linter suppressions
./scripts/lint.sh
```

Tests live in `tests/` and run with pytest (`pythonpath = ["."]` is set in
`pyproject.toml`).
