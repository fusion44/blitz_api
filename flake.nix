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
        (system: f system (import nixpkgs { inherit system; overlays = [ poetry2nix.overlay self.overlays.default ]; }));
      forAllSystems = forSystems supportedSystems;
      projectName = "blitz_api";
    in
    {
      devShells = forAllSystems (system: pkgs: {
        default = pkgs.mkShell {
          buildInputs = with pkgs; [
            python39Packages.pytest
            python39Packages.coverage
            poetry
            pre-commit
            black
            isort
          ];
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
          python = pkgs.python39;
        };
      });
    };
}
