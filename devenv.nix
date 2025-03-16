{
  pkgs,
  lib,
  config,
  inputs,
  ...
}: let
  # Datadir is different for testing and local development
  # Datadir is cleared for each test run, but not for development
  dataDir =
    if !config.devenv.isTesting
    then "$(pwd)/test_env_data"
    else "/tmp/bapi_test_env";

  setupString =
    if !config.devenv.isTesting
    # if we are not testing, execute setup
    then ''
      if [ ! -d ${dataDir} ]; then
        echo "Setup Script: Creating directory ${bitcoinDataDir}"
        mkdir -p ${bitcoinDataDir}
        echo "Setup Script: Creating directory ${lndDataDir}"
        mkdir -p ${lndDataDir}
        echo "Setup Script: Creating directory ${clnDataDir}"
        mkdir -p ${clnDataDir}
      fi

      if [ -f ${bitcoinConfFilePath} ]; then
        echo "Setup Script: Deleting ${bitcoinConfFilePath}"
        rm ${bitcoinConfFilePath}
      fi
    ''
    # if we are testing, clear the temp data
    else ''
      if [ -d ${dataDir} ]; then
        echo "Setup Script: Deleting contents of ${dataDir}"

        # check if path starts with /tmp/bapi, just to make sure
        if [[ ${dataDir} == /tmp/bapi* ]]; then
          echo "Setup Script: Deleting contents of ${dataDir}"
          rm -rf ${dataDir}/*
          echo "Setup Script: Creating directory ${bitcoinDataDir}"
          mkdir -p ${bitcoinDataDir}
          echo "Setup Script: Creating directory ${lndDataDir}"
          mkdir -p ${lndDataDir}
          echo "Setup Script: Creating directory ${clnDataDir}"
          mkdir -p ${clnDataDir}
        else
          echo "Setup Script: Skipping deletion as ${dataDir} does not start with /tmp/bapi"
        fi
      fi
    '';

  bitcoinConfigText = builtins.readFile ./scripts/bitcoin_regtest.conf;
  bitcoinDataDir = "${dataDir}/bitcoin";
  bitcoinConfFilePath = "${bitcoinDataDir}/bitcoin.conf";
  lndDataDir = "${dataDir}/lnd";
  clnDataDir = "${dataDir}/cln";

  pkgs-unstable = import inputs.nixpkgs-unstable {system = pkgs.stdenv.system;};
in {
  # https://devenv.sh/basics/
  env.GREET = "devenv";

  languages = {
    python = {
      enable = true;
      poetry = {
        enable = true;
        activate.enable = true;
      };
    };
  };

  # https://devenv.sh/packages/
  packages = with pkgs-unstable; [
    stdenv.cc.cc
    pyright
    isort
    alejandra
    statix
    ruff
    ruff-lsp
    redis
    nushell
    typos
    typos-lsp

    bitcoind
    lnd
    clightning
  ];

  # blitz api uses its own .env file and is not applicable for
  # the devenv
  dotenv.disableHint = true;

  # https://devenv.sh/processes/
  processes = {
    bitcoind.exec = ''
      ${setupString}

      touch ${bitcoinConfFilePath}
      echo "${bitcoinConfigText}" >> ${bitcoinConfFilePath}
      bitcoind -regtest -datadir=${bitcoinDataDir} -conf=${bitcoinConfFilePath}
    '';
    lnd.exec = ''
      sleep 3
      lnd --lnddir=${lndDataDir} \
        --bitcoin.node=bitcoind \
        --bitcoin.regtest \
        --bitcoind.dir=${bitcoinDataDir}
    '';
    cln.exec = ''
      sleep 3
      lightningd \
        --regtest \
        --lightning-dir=${clnDataDir} \
        --bitcoin-datadir=${bitcoinDataDir}
    '';
    redis_updater.exec = ''
      sleep 3
      nu ./scripts/fake_blitz_scripts/update_redis_values.nu
    '';
  };

  # https://devenv.sh/services/
  services = {
    redis.enable = true;
  };

  # https://devenv.sh/tasks/
  # tasks = {
  #   "myproj:setup".exec = "mytool build";
  #   "devenv:enterShell".after = [ "myproj:setup" ];
  # };

  enterShell = ''
    export LD_LIBRARY_PATH="$LD_LIBRARY_PATH:${
      with pkgs-unstable;
        lib.makeLibraryPath [stdenv.cc.cc.lib]
    }"
  '';

  # https://devenv.sh/tests/
  # disable tests for now. They don't work well, yet
  # enterTest = ''
  #   echo "Running tests"
  #   wait_for_port 18443
  #   bitcoin-cli -regtest --datadir=${bitcoinDataDir} createwallet testwallet
  #   bitcoin-cli -regtest --datadir=${bitcoinDataDir} -generate 160
  #
  #   lncli --chain=bitcoin --network=regtest --lnddir=${lndDataDir} getinfo
  # '';

  # https://devenv.sh/pre-commit-hooks/
  # pre-commit.hooks.shellcheck.enable = true;

  # See full reference at https://devenv.sh/reference/options/
}
