# Home Manager module for refree.
#
# Installs refree as a *user* systemd service — the closest Nix analog to what
# scripts/install.sh wrote under ~/.config/systemd/user.

# The config file install.sh wrote to ~/.refree/config.yaml is generated
# declaratively here and fed to the service via REFREE_CONFIG_FILE, so the
# service does not mutate the user's home directory.
{
  config,
  lib,
  pkgs,
  ...
}:
let
  cfg = config.services.refree;

  configFile = pkgs.writeText "refree-config.yaml" (
    lib.generators.toYAML { } {
      refree_dir = cfg.dataDir;
      app_host = cfg.host;
      app_port = cfg.port;
    }
  );
in
{
  options.services.refree = {
    enable = lib.mkEnableOption "refree, a self-hosted reference manager";

    package = lib.mkOption {
      type = lib.types.package;
      description = "refree derivation to run.";
    };

    host = lib.mkOption {
      type = lib.types.str;
      default = "127.0.0.1";
      description = "Address to bind the HTTP server to.";
    };

    port = lib.mkOption {
      type = lib.types.port;
      default = 23119;
      description = "Port to bind the HTTP server to.";
    };

    dataDir = lib.mkOption {
      type = lib.types.path;
      default = "${config.home.homeDirectory}/.refree/data";
      defaultText = lib.literalExpression "\${config.home.homeDirectory}/.refree/data";
      description = "Where refree stores its database and PDFs.";
    };
  };

  config = lib.mkIf cfg.enable {
    systemd.user.services.refree = {
      Unit = {
        Description = "refree - self-hosted reference manager";
        After = [ "network.target" ];
      };

      Service = {
        Type = "simple";
        ExecStart = "${cfg.package}/bin/refree";
        Restart = "on-failure";
        RestartSec = 5;
        Environment = [
          "REFREE_CONFIG_FILE=${configFile}"
          "REFREE_HOST=${cfg.host}"
          "REFREE_PORT=${toString cfg.port}"
        ];
      };

      Install = {
        WantedBy = [ "default.target" ];
      };
    };
  };
}
