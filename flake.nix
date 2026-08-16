{
  description = "refree - self-hosted reference manager";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";

    pyproject-nix = {
      url = "github:pyproject-nix/pyproject.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    uv2nix = {
      url = "github:pyproject-nix/uv2nix";
      inputs.nixpkgs.follows = "nixpkgs";
      inputs.pyproject-nix.follows = "pyproject-nix";
    };

    pyproject-build-systems = {
      url = "github:pyproject-nix/build-system-pkgs";
      inputs.nixpkgs.follows = "nixpkgs";
      inputs.pyproject-nix.follows = "pyproject-nix";
    };
  };

  outputs =
    {
      self,
      nixpkgs,
      uv2nix,
      pyproject-nix,
      pyproject-build-systems,
    }:
    let
      inherit (nixpkgs) lib;
      forAllSystems = lib.genAttrs lib.systems.flakeExposed;
      nixpkgsFor = system: import nixpkgs { inherit system; };

      # Parse the uv workspace at the flake root.
      workspace = uv2nix.lib.workspace.loadWorkspace { workspaceRoot = ./.; };

      # Source tree of the project (read-only store path), used as --app-dir so
      # the `app` package is importable no matter the service WorkingDirectory.
      projectRoot = self;

      mkRefree =
        pkgs:
        let
          inherit (pkgs) stdenv;
          python = pkgs.python313;

          # Overlay generated from uv.lock: one derivation per locked package.
          depsOverlay = workspace.mkPyprojectOverlay {
            sourcePreference = "wheel";
          };

          # Base Python set with pyproject.nix build infrastructure.
          pythonSet =
            (pkgs.callPackage pyproject-nix.build.packages { inherit python; })
            .overrideScope (
              lib.composeManyExtensions [
                pyproject-build-systems.overlays.wheel
                depsOverlay
              ]
            );

          # Build a venv of the *runtime dependencies only*. We deliberately do
          # NOT include the local `refree` package (the project has no build
          # backend and is meant to run from the source tree, like install.sh
          # did with `fastapi run` from the project dir). mkVirtualEnv resolves
          # transitive deps from passthru metadata populated by uv2nix.
          venv = pythonSet.mkVirtualEnv "refree-env" {
            fastapi = [ "standard" ];
            jinja2 = [ ];
            httpx = [ ];
            pyyaml = [ ];
            sqlmodel = [ ];
            that-depends = [ ];
          };
        in
        stdenv.mkDerivation {
          pname = "refree";
          version = "0.1.0";
          dontUnpack = true;

          installPhase = ''
            runHook preInstall
            mkdir -p $out/bin
            cat > $out/bin/refree <<'EOF'
            #!/usr/bin/env bash
            set -euo pipefail
            # The fastapi CLI takes a path to the app entrypoint (it auto-detects
            # the import string and adds the project root to PYTHONPATH), so the
            # `app` package is importable regardless of the caller's cwd.
            exec "${venv}/bin/fastapi" run "${projectRoot}/app/main.py" \
              --host "''${REFREE_HOST:-127.0.0.1}" \
              --port "''${REFREE_PORT:-23119}" \
              "$@"
            EOF
            chmod +x $out/bin/refree
            runHook postInstall
          '';

          passthru = {
            inherit venv projectRoot;
          };
        };
    in
    {
      packages = forAllSystems (
        system:
        let
          pkgs = nixpkgsFor system;
          refree = mkRefree pkgs;
        in
        {
          inherit refree;
          default = refree;
        }
      );

      # Run anywhere: `nix run .# -- --host 0.0.0.0 --port 8000` (args append to
      # the fastapi invocation) or just `nix run .#` for defaults.
      apps = forAllSystems (system: {
        default = {
          type = "app";
          program = "${self.packages.${system}.default}/bin/refree";
        };
      });

      # Drop-in for Home Manager. Installs refree as a *user* systemd service
      # (systemd.user.services.refree) that starts automatically at login —
      # the closest Nix analog to what scripts/install.sh wrote under
      # ~/.config/systemd/user.
      homeManagerModules.default =
        { pkgs, ... }:
        {
          imports = [ ./nix/home.nix ];
          services.refree.package = lib.mkDefault self.packages.${pkgs.system}.default;
        };

      # Optional: a nix shell for hacking on the project. Dev itself still uses
      # `uv` / `.venv` per the repo rules; this just provides tooling.
      devShells = forAllSystems (
        system:
        let pkgs = nixpkgsFor system; in
        {
          default = pkgs.mkShell {
            packages = with pkgs; [
              uv
              python313
              ruff
            ];
          };
        }
      );

      formatter = forAllSystems (system: (nixpkgsFor system).nixfmt-rfc-style);
    };
}
