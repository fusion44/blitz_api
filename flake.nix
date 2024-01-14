{
  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    poetry2nix.url = "github:nix-community/poetry2nix";
  };
  outputs = { self, nixpkgs, poetry2nix }@inputs:
    let
      supportedSystems = [ "x86_64-linux" "aarch64-linux" ];
      forSystems = systems: f:
        nixpkgs.lib.genAttrs systems
        (system: f system (import nixpkgs { inherit system; overlay = [ poetry2nix.overlay self.overlays.default ]; }));
      forAllSystems = forSystems supportedSystems;
      projectName = "blitz_api";
    in
    {
      devShells = forAllSystems (system: pkgs: {
       default = pkgs.mkShell {
          buildInputs = with pkgs; [
            stdenv.cc.cc.lib
            python311Packages.pytest
            python311Packages.coverage
            python311Packages.venvShellHook
            poetry
            poetryPlugins.poetry-plugin-export
            pre-commit
            black
            isort
            ruff
            ruff-lsp
            pyright
          ];
          venvDir = "./.venv";
          src = null;
          shellHook = ''
            export LD_LIBRARY_PATH=${pkgs.lib.makeLibraryPath [
            pkgs.stdenv.cc.cc
            ]}
          '';
          postVenv = ''
            unset SOURCE_DATE_EPOCH
          '';
          postShellHook = ''
            unset SOURCE_DATE_EPOCH
            unset LD_PRELOAD

            PYTHONPATH=$PWD/$venvDir/${pkgs.python311.sitePackages}:$PYTHONPATH
          '';
        };
      });
      overlays = {
        default = final: prev: {
          ${projectName} = self.packages.${final.hostPlatform.system}.${projectName};
        };
      };
      packages = forAllSystems (system: pkgs: {
        default = self.packages.${system}.${projectName};
        ${projectName} = pkgs.poetry2nix.mkPoetryApplication {
          projectDir = ./.;
          python = pkgs.python311;
        };
      });
    };
}
