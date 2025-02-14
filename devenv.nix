{
  pkgs,
  lib,
  config,
  inputs,
  ...
}: let
  dataDir = "$(pwd)/test_env_data";
  bitcoinConfigText = builtins.readFile ./scripts/bitcoin_regtest.conf;
  bitcoinDataDir = "${dataDir}/bitcoin";
  bitcoinConfFilePath = "${bitcoinDataDir}/bitcoin.conf";
  lndDataDir = "${dataDir}/lnd";
  clnDataDir = "${dataDir}/cln";

  pkgs-unstable = import inputs.nixpkgs-unstable {system = pkgs.stdenv.system;};
in {
  # https://devenv.sh/basics/
  env.GREET = "devenv";

  # https://devenv.sh/packages/
  packages = with pkgs; [
    stdenv.cc.cc
    poetry
    pyright
    alejandra
    statix
    ruff
    ruff-lsp
    redis
    nushell

    pkgs-unstable.bitcoind
    pkgs-unstable.lnd
    pkgs-unstable.clightning
  ];

  # https://devenv.sh/processes/
  processes = {
    bitcoind.exec = ''
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

  # enterShell = ''
  #   nu -e 'source scripts/test_env.nu; init_env'
  # '';

  # https://devenv.sh/tests/
  enterTest = ''
    echo "Running tests"
    git --version | grep --color=auto "${pkgs.git.version}"
  '';

  # https://devenv.sh/pre-commit-hooks/
  # pre-commit.hooks.shellcheck.enable = true;

  # See full reference at https://devenv.sh/reference/options/
}
