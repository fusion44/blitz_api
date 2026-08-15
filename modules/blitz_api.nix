{
  config,
  pkgs,
  lib,
  ...
}: let
  defaultUser = "blitzapi";
  defaultGroup = defaultUser;
  name = "blitz-api";

  cfg = config.services.${name};
  nbLib = config.nix-bitcoin.lib;
  secretsDir = config.nix-bitcoin.secretsDir;
  bitcoindRpcAddress = nbLib.address bitcoind.rpc.address;

  # The ZMQ URL is always given fully qualified,
  # but the API expects the port only
  parts = strings.splitString ":" bitcoind.zmqpubrawblock;
  bitcoindZmqPort = builtins.elemAt parts 2;

  jwtSecretScript =
    if cfg.jwt.secretFile != null
    then "$(head -n1 ${lib.escapeShellArg cfg.jwt.secretFile})"
    else "$(cat /dev/urandom | tr -dc '[:alnum:]' | head -c 50)";
  loginPasswordScript =
    if cfg.passwordFile != null
    then "$(head -n1 ${lib.escapeShellArg cfg.passwordFile})"
    else "$(cat /dev/urandom | tr -dc '[:alnum:]' | head -c 50)";
  fullDotEnvPath =
    if cfg.generateDotEnvFile
    then "${cfg.dataDir}/.env"
    else if cfg.dotEnvFile != null
    then cfg.dotEnvFile
    else "${cfg.dataDir}/.env";

  inherit (lib) mkOption mkIf mkEnableOption types literalExpression strings;
  inherit (config.services) bitcoind lnd;
in {
  imports = [
    (lib.mkRemovedOptionModule ["services" name "localCookieAuth"] ''
      Local cookie authentication has been removed: it wrote a live admin JWT
      to disk for a client that no longer consumes it.
    '')
  ];

  options = {
    services.${name} = {
      enable = mkEnableOption "${name}";

      package = mkOption {
        type = types.package;
        defaultText = literalExpression "pkgs.${name}";
        default = pkgs.${name};
        description = "The ${name} package to use.";
      };

      host = mkOption {
        type = types.str;
        default = "127.0.0.1";
        example = "127.0.0.1";
        description = "The host to bind to";
      };

      port = mkOption {
        type = types.port;
        default = 2121;
        example = 2121;
        description = "The port the ${name} will be listening on";
      };

      user = mkOption {
        type = types.str;
        default = defaultUser;
        example = "${defaultUser}";
        description = "The user to run the ${name} as";
      };

      home = mkOption {
        type = types.nullOr types.path;
        default = null;
        example = "/home/${defaultUser}";
        description = "Storage path of ${name}. This is where the cookie will be located, if enabled.";
      };

      group = mkOption {
        type = types.str;
        default = defaultGroup;
        description = "Group to run the ${name} as";
      };

      network = mkOption {
        type = types.enum ["mainnet" "testnet" "regtest"];
        default = "mainnet";
        description = "The bitcoin network type";
      };

      dataDir = mkOption {
        type = types.path;
        default = "/var/lib/blitz_api";
        description = "The data directory for ${name}.";
      };

      bitcoind = {
        rpc = {
          address = mkOption {
            type = types.str;
            default = "127.0.0.1";
            description = ''
              Address to use for the JSON-RPC connection.
            '';
          };

          port = mkOption {
            type = types.port;
            default =
              if cfg.network == "mainnet"
              then 8332
              else if cfg.network == "testnet"
              then 18332
              else 28332;
            defaultText = ''
              if cfg.network == "mainnet"
              then 8332
              else if cfg.network == "testnet"
              then 18332
              else 28332;
            '';
            description = "Port to use for the JSON-RPC connections.";
          };
        };

        zmq = {
          blockRPCType = mkOption {
            type = types.enum ["hashblock" "rawblock"];
            default = "hashblock";
            description = ''
              How the ${name} api will be notified of new blocks.
              Hashblock is a bit faster, so it should be used if possible.
            '';
          };
        };
      };

      logLevel = lib.mkOption {
        type = types.enum ["TRACE" "DEBUG" "INFO" "SUCCESS" "WARNING" "ERROR" "CRITICAL"];
        default = "INFO";
        description = "Log level for the ${name}";
        example = "DEBUG";
      };

      ln = {
        connectionType = lib.mkOption {
          type = types.enum ["none" "lnd_grpc" "cln_jrpc"];
          default = "none";
          description = "Whether lighgning is enabled and which implementation is used.";
        };

        lnd = {
          grpcHost = mkOption {
            type = types.str;
            default = "127.0.0.1";
            example = "127.0.0.1";
            description = "The host to connect to";
          };

          grpcPort = mkOption {
            type = types.port;
            default = 10009;
            description = "The port to connect to";
          };
        };
      };

      jwt = {
        algorithm = mkOption {
          type = types.str;
          example = "HS256";
          default = "HS256";
          description = "The hashing algorithm for the JWT. See PyJWT for a list of available algorithms.";
        };

        expiry = mkOption {
          type = types.int;
          example = "3600000";
          default = 3600000;
          description = "JWT expiry time in milliseconds (3600000 = 1 hour)";
        };

        secretFile = mkOption {
          type = types.nullOr types.str;
          default = null;
          example = "/run/keys/jwt_secret";
          description = "File path containing the JWT secret.";
        };
      };

      generateDotEnvFile = mkOption {
        type = types.bool;
        default = false;
        example = true;
        description = "Wheter to generate the dot env file.";
      };

      dotEnvFile = mkOption {
        type = types.nullOr types.str;
        default = null;
        example = "/var/lib/blitz_api/.env";
        description = "The path where the .env file will be live.";
      };

      passwordFile = mkOption {
        type = types.nullOr types.str;
        default = null;
        example = "/run/keys/login_password";
        description = "File path containing the password for native python to authenticate with.";
      };

      rootPath = mkOption {
        type = types.str;
        default = "/";
        example = "/api";
        description = "The root path the api will be served on. E.g. https://127.0.0.1/api if set to /api.";
      };

      nginx = {
        enable = mkEnableOption "Whether to enable nginx server for ${name}.";
        description = "This is used to generate the nginx configuration.";

        hostName = mkOption {
          type = types.str;
          example = "my.node.net";
          default = "localhost";
          description = "The hostname to use for the nginx virtual host.";
        };

        location = mkOption {
          type = types.str;
          example = "/api";
          default = "/api";
          description = "The location to serve the ${name} from from.";
        };

        openFirewall = mkOption {
          type = types.bool;
          default = false;
          description = "Whether to open the ports used by ${name} in the firewall for the server";
        };
      };

      env = mkOption {
        type = types.attrsOf types.str;
        default = {};
        description = ''
          Additional environment variables that are passed to the ${name}.
          Reference Variables: https://github.com/fusion44/blitz_api/blob/dev/.env_sample
        '';
        example = {
          BAPI_JWT_EXPIRY_TIME = 3600000;
        };
      };
    };
  };

  config = mkIf cfg.enable {
    assertions = [
      {
        assertion = lib.strings.hasPrefix "/" cfg.rootPath;
        message = ''
          <option>services.${name}.rootPath</option> needs to start with a / if set. Actual: ${cfg.rootPath}
        '';
      }
      {
        assertion = cfg.passwordFile != null -> builtins.pathExists cfg.passwordFile;
        message = "The specified password file does not exist: ${cfg.passwordFile}";
      }
    ];

    users.users = mkIf (cfg.user == defaultUser) {
      ${defaultUser} = {
        description = "${name} service";
        home = mkIf (cfg.home != null) cfg.home;
        group = cfg.group;
        isSystemUser = true;
      };
    };

    users.groups = mkIf (cfg.group == defaultGroup) {
      ${defaultGroup} = {};
    };

    systemd = {
      tmpfiles.rules = [
        "d '${cfg.dataDir}' 0770 ${cfg.user} ${cfg.group} - -"
      ];

      # This target is active when the env file have been created successfully.
      targets = {
        "${name}-env-file" = mkIf cfg.generateDotEnvFile {
          # This ensures that the secrets target is always activated when switching
          # configurations.
          # In this way `switch-to-configuration` is guaranteed to show an error
          # when activating the secrets target fails on deployment.
          wantedBy = ["multi-user.target"];
        };
        "${name}" = {
          # This ensures that the secrets target is always activated when switching
          # configurations.
          # In this way `switch-to-configuration` is guaranteed to show an error
          # when activating the secrets target fails on deployment.
          wantedBy = ["multi-user.target"];
        };
      };

      services.blitz-api-setup-env = mkIf cfg.generateDotEnvFile rec {
        wantedBy = ["multi-user.target"];
        before = ["${name}.target"];
        wants = ["nix-bitcoin-secrets.target"];
        after = wants;
        serviceConfig = {
          Type = "oneshot";
          RemainAfterExit = true;
        };
        script = ''
          mkdir -p "${cfg.dataDir}"
          cd "${cfg.dataDir}"
          chown root: .
          chmod 0700 .
          echo "BAPI_JWT_SECRET=${jwtSecretScript}" >> .env
          echo "BAPI_JWT_ALGORITHM=${cfg.jwt.algorithm}" >> .env
          echo "BAPI_JWT_EXPIRY_TIME=${toString cfg.jwt.expiry}" >> .env
          echo "BAPI_LOG_LEVEL=${cfg.logLevel}" >> .env
          echo "BAPI_ROOT_PATH=${cfg.rootPath}" >> .env
          echo "BAPI_PLATFORM=native_python" >> .env
          echo "BAPI_NETWORK=${cfg.network}" >> .env
          echo "BAPI_BITCOIND_ADDRESS=${bitcoindRpcAddress}" >> .env
          echo "BAPI_BITCOIND_PORT_RPC=${toString bitcoind.rpc.port}" >> .env
          echo "BAPI_BITCOIND_ZMQ_BLOCK_RPC=${cfg.bitcoind.zmq.blockRPCType}" >> .env
          echo "BAPI_BITCOIND_ZMQ_BLOCK_PORT=${bitcoindZmqPort}" >> .env
          echo "BAPI_BITCOIND_USER=${bitcoind.rpc.users.public.name}" >> .env
          pw=$(head -n1 ${secretsDir}/bitcoin-rpcpassword-public)
          echo "BAPI_BITCOIND_RPC_PW=$pw" >> .env
          echo "BAPI_NATIVE_LOGIN_PASSWORD=${loginPasswordScript}" >> .env
          echo "BAPI_LN_NODE=${cfg.ln.connectionType}" >> .env
          ${
            lib.strings.optionalString (cfg.ln.connectionType == "lnd_grpc") ''
              echo "BAPI_LND_MACAROON=${cfg.dataDir}/macaroons/admin.macaroon" >> .env
              echo "BAPI_LND_CERT=${cfg.dataDir}/lnd-cert" >> .env
              echo "BAPI_LND_GRPC_IP=${cfg.ln.lnd.grpcHost}" >> .env
              echo "BAPI_LND_GRPC_PORT=${toString cfg.ln.lnd.grpcPort}" >> .env
            ''
          }
          ${
            lib.strings.optionalString (cfg.ln.connectionType == "cln_grpc") ''
              echo "# CLN TODO"
            ''
          }

          chown ${cfg.user}:${cfg.group} .env
          chmod 400 .env
        '';
      };

      services.${name} = rec {
        wantedBy = ["multi-user.target"];
        requires = ["bitcoind.service" "lnd.service"];
        after = requires ++ ["blitz-api-setup-env.target" "nix-bitcoin-secrets.target"];
        description = "${name} server daemon";
        environment = lib.mkMerge [
          (lib.mkIf cfg.generateDotEnvFile {
            BAPI_ENV_PATH = "${cfg.dataDir}/.env";
          })
          cfg.env
        ];
        serviceConfig =
          # TODO: some hardenings interfere with API fuctionality
          # nbLib.defaultHardening //
          {
            ExecStart = "${cfg.package}/bin/api --port ${toString cfg.port} --host ${cfg.host} --root_path ${cfg.rootPath}";
            ExecStartPre = [
              (nbLib.rootScript "${name}-prepare-data-dir" ''
                install -D -o ${cfg.user} -g ${cfg.group} ${lnd.networkDir}/admin.macaroon \
                  '${cfg.dataDir}/macaroons/admin.macaroon'
                install -D -o ${cfg.user} -g ${cfg.group} ${lnd.certPath} \
                  '${cfg.dataDir}/lnd-cert'

                chown -R ${cfg.user}:${cfg.group} ${cfg.dataDir}
                # chmod -R 440 ${cfg.dataDir}
                chmod -R 777 ${cfg.dataDir}
              '')
            ];
            User = cfg.user;
            Group = cfg.group;
            Restart = "always";
            SyslogIdentifier = name;
            ReadWritePaths = [cfg.dataDir];
          };
      };
    };

    services.nginx = mkIf cfg.nginx.enable {
      enable = true;
      virtualHosts.${cfg.nginx.hostName} = {
        forceSSL = false;
        enableACME = false;

        locations."${cfg.nginx.location}" = {
          extraConfig = ''
            rewrite ${cfg.nginx.location}/(.*) /$1  break;
            proxy_redirect off;
          '';
          proxyPass = "http://${cfg.host}:${toString cfg.port}/";
          recommendedProxySettings = true;
        };
      };
    };

    networking.firewall = mkIf cfg.nginx.openFirewall {
      allowedTCPPorts = [80];
    };
  };
}
