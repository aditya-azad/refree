{
  config,
  lib,
  pkgs,
  ...
}:
let
  cfg = config.services.refree;
in
{
  options.services.refree = {
    enable = lib.mkEnableOption "refree - self-hosted reference manager";

    package = lib.mkOption {
      type = lib.types.package;
      default = pkgs.refree or (throw "refree package not found; add refree.overlays.default to nixpkgs.overlays");
      defaultText = lib.literalExpression "pkgs.refree";
      description = "The refree package to use.";
    };

    host = lib.mkOption {
      type = lib.types.str;
      default = "127.0.0.1";
      description = "Host address to bind to.";
    };

    port = lib.mkOption {
      type = lib.types.port;
      default = 23119;
      description = "Port to bind to.";
    };

    dataDir = lib.mkOption {
      type = lib.types.path;
      default = "/var/lib/refree";
      description = "Directory for the SQLite database and stored PDFs.";
    };

    user = lib.mkOption {
      type = lib.types.str;
      default = "refree";
      description = "User to run the service as.";
    };

    group = lib.mkOption {
      type = lib.types.str;
      default = "refree";
      description = "Group to run the service as.";
    };
  };

  config = lib.mkIf cfg.enable {
    users.users.${cfg.user} = {
      isSystemUser = true;
      group = cfg.group;
      home = cfg.dataDir;
      createHome = true;
    };

    users.groups.${cfg.group} = { };

    environment.etc."refree/config.yaml".text = ''
      refree_dir: "${cfg.dataDir}"
      app_host: "${cfg.host}"
      app_port: ${toString cfg.port}
    '';

    environment.systemPackages = [ cfg.package ];

    systemd.services.refree = {
      description = "refree - self-hosted reference manager";
      after = [ "network.target" ];
      wantedBy = [ "multi-user.target" ];

      environment = {
        REFREE_CONFIG_FILE = "/etc/refree/config.yaml";
      };

      serviceConfig = {
        Type = "simple";
        User = cfg.user;
        Group = cfg.group;
        WorkingDirectory = cfg.dataDir;
        ExecStart = "${cfg.package}/bin/refree";
        Restart = "on-failure";
        RestartSec = 5;
        StateDirectory = "refree";
      };
    };
  };
}
