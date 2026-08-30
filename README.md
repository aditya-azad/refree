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

## Getting started

```bash
# 1. Create the virtualenv and install dependencies (uv, never pip)
uv sync

# 2. Configure
# put the config above in ~/.refree/config.yaml

# 3. Run the dev server (zellij layout: editor + fastapi panes)
./scripts/dev.sh
#   or, without zellij:
#   fastapi dev --host 127.0.0.1 --port 23119 app/main:app
```

Open the UI at `http://127.0.0.1:23119/` and check health at
`http://127.0.0.1:23119/heartbeat`.

## Nix / NixOS

refree ships with a Nix flake that provides the system-level build
environment (Python 3.13, `uv`, `zellij`, `libsqlite3`) while `uv` continues
to manage all Python packages from `pyproject.toml` / `uv.lock`.

### Development shell

```bash
nix develop          # enters a shell with Python 3.13, uv, zellij, sqlite
uv sync              # create .venv (first time only)
./scripts/dev.sh     # zellij layout: editor + fastapi panes (auto-enters nix develop)
```

`scripts/dev.sh` automatically enters the Nix dev shell if `nix` is available,
so it works both inside and outside `nix develop`.

### Run directly

```bash
nix run --impure              # uses the local .venv if present
```

The `--impure` flag lets the build read the local `.venv/` (created by
`uv sync` in the dev shell) so the Nix sandbox doesn't need network access.
A default `~/.refree/config.yaml` is created on first run if none exists.

### Build

```bash
nix build --impure            # uses the local .venv; patches ELF binaries
./result/bin/refree           # starts the server
```

The build copies the `.venv/` created by `uv sync` (in the dev shell) into the
Nix store and runs `autoPatchelfHook` to patch all native `.so` files
(`uvloop`, `httptools`, `watchfiles`, `pydantic-core`, etc.) to use Nix store
paths. This makes the resulting package self-contained — no `nix-ld` or
`--no-sandbox` needed at runtime.

If no `.venv/` exists, the build falls back to `uv sync --frozen --no-dev`,
which requires network access (`--no-sandbox`).

### Install on NixOS

Add the flake as an input and import the NixOS module. The module creates a
system service (`services.refree`) with a dedicated user, generated config,
and automatic startup at boot:

```nix
# flake.nix
{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    refree.url = "github:azada/refree";
  };

  outputs = { self, nixpkgs, refree, ... }: {
    nixosConfigurations.myhost = nixpkgs.lib.nixosSystem {
      system = "x86_64-linux";
      modules = [
        ./hardware-configuration.nix
        ./configuration.nix
        refree.nixosModules.default
        {
          nixpkgs.overlays = [ refree.overlays.default ];
          services.refree.enable = true;
          # Optional overrides:
          # services.refree.port = 23119;          # default
          # services.refree.host = "127.0.0.1";     # default
          # services.refree.dataDir = "/var/lib/refree";  # default
        }
      ];
    };
  };
}
```

Rebuild and the service starts automatically at boot:

```bash
sudo nixos-rebuild switch

# Verify:
systemctl status refree
curl http://127.0.0.1:23119/heartbeat
```

The NixOS build uses the flake's `packages.default` via the overlay. If the
build machine has a local `.venv/` (from `uv sync`), pass `--impure` so the
Nix sandbox can read it; otherwise the build falls back to `uv sync` which
needs `--no-sandbox` for network access.

The service runs as a system user `refree` with data in `/var/lib/refree`
(SQLite database + PDFs). Config is generated at `/etc/refree/config.yaml`
from the module options.

| Option | Default | Description |
|--------|---------|-------------|
| `services.refree.enable` | `false` | Enable the service |
| `services.refree.host` | `127.0.0.1` | Bind host |
| `services.refree.port` | `23119` | Bind port |
| `services.refree.dataDir` | `/var/lib/refree` | SQLite + PDFs directory |
| `services.refree.user` | `refree` | System user |
| `services.refree.group` | `refree` | System group |
| `services.refree.package` | `pkgs.refree` | Package (via overlay) |

## Install & autostart (Linux)

`scripts/install.sh` is a one-shot bash script that installs refree into a
`.venv` with `uv`, writes a default `~/.refree/config.yaml` if none exists, and
registers a **systemd user service** so refree starts automatically at boot:

```bash
./scripts/install.sh
```

It is idempotent — re-run it after pulling updates to reinstall dependencies
and refresh the service unit. The script:

1. installs `uv` if missing, then runs `uv sync`;
2. writes a default config (`refree_dir`, `app_host`, `app_port: 23119`) only if
   `~/.refree/config.yaml` does not already exist;
3. reads `app_host`/`app_port` from the config and writes
   `~/.config/systemd/user/refree.service` pointing at the project's
   `.venv/bin/fastapi run`;
4. enables lingering (`loginctl enable-linger`) so user services start at boot
   even before login, then enables and (re)starts `refree.service`.

After install:

```bash
systemctl --user status refree        # check status
journalctl --user -u refree -f        # follow logs
systemctl --user stop refree          # stop
systemctl --user disable refree        # stop autostart at boot
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


## Development

```bash
# lint, type-check, format, run tests, and audit linter suppressions
./scripts/lint.sh
```

Tests live in `tests/` and run with pytest (`pythonpath = ["."]` is set in
`pyproject.toml`).
