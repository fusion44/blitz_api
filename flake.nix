{
  description = "A management backend for the RaspiBlitz project written in Python / FastAPI";

  inputs = {
    flake-utils.url = "github:numtide/flake-utils";
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    poetry2nix = {
      url = "github:nix-community/poetry2nix";
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
        nativeBuildInputs = with pkgs; [
          poetry
          poetryDev
          pyright
          alejandra
        ];
      };
    });

    overlays.overlays = {
      default = final: prev: {
        ${name} = self.packages.${prev.stdenv.hostPlatform.system}.${name};
      };
    };
  in
    systems // overlays;
}
