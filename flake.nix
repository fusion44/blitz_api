{
  description = "A management backend for the RaspiBlitz project written in Python / FastAPI";

  inputs = {
    flake-utils.url = "github:numtide/flake-utils";
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    poetry2nix = {
      url = "github:fusion44/poetry2nix/nb";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = {
    self,
    nixpkgs,
    flake-utils,
    poetry2nix,
  }: let
    name = "blitz-api";

    systems = flake-utils.lib.eachDefaultSystem (system: let
      pkgs = nixpkgs.legacyPackages.${system};
      inherit (poetry2nix.lib.mkPoetry2Nix {inherit pkgs;}) mkPoetryApplication overrides mkPoetryEnv;
      poetryDev = mkPoetryEnv {
        projectDir = ./.;
        preferWheels = true;
        overrides = overrides.withDefaults (final: prev: {
          ruff = prev.ruff.override {
            preferWheel = true;
          };
        });
      };
    in {
      packages = {
        default = self.packages.${system}.${name};
        ${name} = mkPoetryApplication {
          projectDir = ./.;
          meta.mainProgram = name;
        };
        poetryDev = mkPoetryEnv {
          projectDir = ./.;
          preferWheels = true;
        };
      };

      devShells.default = pkgs.mkShell {
        # TODO: dirty dirty to be able to run the app. May break other packages.
        # https://discourse.nixos.org/t/using-nix-shells-without-polluting-repositories/37362
        shellHook = ''
          export LD_LIBRARY_PATH="$LD_LIBRARY_PATH:${
            with pkgs;
              lib.makeLibraryPath [pkgs.stdenv.cc.cc.lib]
          }"
        '';
        nativeBuildInputs = with pkgs; [
          stdenv.cc.cc
          poetry
          poetryDev
          pyright
          alejandra
          statix
          ruff
          ruff-lsp
          redis
          pueue

          bitcoind
          lnd
          clightning
          pueue
        ];
      };
    });

    overlays.overlays = {
      default = final: prev: {
        ${name} = self.packages.${prev.stdenv.hostPlatform.system}.${name};
      };
    };

    module = {
      nixosModules.default = {
        pkgs,
        lib,
        config,
        ...
      }: {
        imports = [./modules/blitz_api.nix];
        nixpkgs.overlays = [self.overlays.default];
      };
    };
  in
    systems // overlays // module;
}
