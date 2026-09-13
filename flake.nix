{
  description = "refree - self-hosted reference manager";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs =
    { self, nixpkgs }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
      ];
      forAllSystems = fn: nixpkgs.lib.genAttrs systems (system: fn system);
    in
    {
      devShells = forAllSystems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
        in
        {
          default = pkgs.mkShell {
            packages = with pkgs; [
              python313
              uv
              zellij
              sqlite.out
            ];

            shellHook = ''
              export UV_PYTHON="${pkgs.python313}/bin/python3.13"
              export NIX_LD="$(cat ${pkgs.stdenv.cc}/nix-support/dynamic-linker)"
              export NIX_LD_LIBRARY_PATH="${pkgs.lib.makeLibraryPath [ pkgs.sqlite.out pkgs.stdenv.cc.cc.lib ]}''${NIX_LD_LIBRARY_PATH:+:$NIX_LD_LIBRARY_PATH}"
              export LD_LIBRARY_PATH="${pkgs.lib.makeLibraryPath [ pkgs.sqlite.out pkgs.stdenv.cc.cc.lib ]}''${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
              if [ ! -d .venv ]; then
                echo ">>> Creating virtual environment..."
                uv sync
              fi
            '';
          };
        }
      );

      packages = forAllSystems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
        in
        {
          default = let
            venvSrc =
              let
                envVenv = builtins.getEnv "REFREE_VENV";
              in
              if envVenv != "" then
                builtins.filterSource
                  (
                    path: type:
                    !(pkgs.lib.hasSuffix ".pyc" path)
                    && !(builtins.elem (baseNameOf path) [
                      "__pycache__"
                      ".gitignore"
                    ])
                  )
                  envVenv
              else if builtins.pathExists (./. + "/.venv") then
                builtins.filterSource
                  (
                    path: type:
                    !(pkgs.lib.hasSuffix ".pyc" path)
                    && !(builtins.elem (baseNameOf path) [
                      "__pycache__"
                      ".gitignore"
                    ])
                  )
                  ./.venv
              else null;
          in
          pkgs.stdenv.mkDerivation {
            pname = "refree";
            version = "0.1.0";

            src = builtins.filterSource
              (
                path: type:
                !(builtins.elem (baseNameOf path) [
                  ".venv"
                  "__pycache__"
                  ".pytest_cache"
                  ".ruff_cache"
                  "result"
                  "result-*"
                ])
                && !(pkgs.lib.hasSuffix ".pyc" path)
              )
              ./.;

            inherit venvSrc;

            nativeBuildInputs = with pkgs; [
              uv
              autoPatchelfHook
            ];

            buildInputs = with pkgs; [
              python313
              sqlite.out
              stdenv.cc.cc.lib
            ];

            installPhase = ''
              mkdir -p $out
              cp -r app $out/
              cp pyproject.toml uv.lock $out/

              if [ -n "''${venvSrc:-}" ] && [ -d "$venvSrc" ]; then
                cp -r "$venvSrc" $out/.venv
                chmod -R u+w $out/.venv
              else
                cd $out
                export HOME=$TMPDIR
                export UV_CACHE_DIR=$TMPDIR/uv-cache
                export UV_PYTHON="${pkgs.python313}/bin/python3.13"
                uv sync --frozen --no-dev
              fi

              mkdir -p $out/bin
              cat > $out/bin/refree << 'WRAPPER'
              #!/bin/sh
              SELF="$0"
              while [ -L "$SELF" ]; do
                DIR="$(cd "$(dirname "$SELF")" && pwd)"
                SELF="$(readlink "$SELF")"
                case "$SELF" in
                  /*) ;;
                  *) SELF="$DIR/$SELF" ;;
                esac
              done
              ROOT="$(cd "$(dirname "$SELF")/.." && pwd)"
              export PYTHONPATH="$ROOT:$PYTHONPATH"
              export REFREE_CONFIG_FILE="''${REFREE_CONFIG_FILE:-$HOME/.refree/config.yaml}"
              if [ ! -f "$REFREE_CONFIG_FILE" ]; then
                mkdir -p "$(dirname "$REFREE_CONFIG_FILE")"
                cat > "$REFREE_CONFIG_FILE" << 'CONF'
              refree_dir: "~/.refree/data"
              app_host: "127.0.0.1"
              app_port: 23119
              CONF
              fi
              cd "$ROOT"
              host="''${REFREE_HOST:-$(.venv/bin/python -c "from app.common.config import APP_HOST; print(APP_HOST)")}"
              port="''${REFREE_PORT:-$(.venv/bin/python -c "from app.common.config import APP_PORT; print(APP_PORT)")}"
              exec "$ROOT/.venv/bin/python" -m uvicorn app.main:app \
                --host "$host" \
                --port "$port"
              WRAPPER
              chmod +x $out/bin/refree

              cat > $out/bin/refree-mcp << 'MCPWRAPPER'
              #!/bin/sh
              SELF="$0"
              while [ -L "$SELF" ]; do
                DIR="$(cd "$(dirname "$SELF")" && pwd)"
                SELF="$(readlink "$SELF")"
                case "$SELF" in
                  /*) ;;
                  *) SELF="$DIR/$SELF" ;;
                esac
              done
              ROOT="$(cd "$(dirname "$SELF")/.." && pwd)"
              export PYTHONPATH="$ROOT:$PYTHONPATH"
              export REFREE_CONFIG_FILE="''${REFREE_CONFIG_FILE:-$HOME/.refree/config.yaml}"
              if [ ! -f "$REFREE_CONFIG_FILE" ]; then
                mkdir -p "$(dirname "$REFREE_CONFIG_FILE")"
                cat > "$REFREE_CONFIG_FILE" << 'CONF'
              refree_dir: "~/.refree/data"
              app_host: "127.0.0.1"
              app_port: 23119
              CONF
              fi
              cd "$ROOT"
              exec "$ROOT/.venv/bin/python" -m app.mcp_server
              MCPWRAPPER
              chmod +x $out/bin/refree-mcp
            '';
          };
        }
      );

      apps = forAllSystems (
        system: {
          default = {
            type = "app";
            program = "${self.packages.${system}.default}/bin/refree";
          };
        }
      );

      overlays.default = final: _prev: {
        refree = self.packages.${final.system}.default;
      };

      nixosModules.default = import ./nix/module.nix;
    };
}
