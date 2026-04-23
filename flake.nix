{
  description = "A management backend for the RaspiBlitz project written in Python / FastAPI";

  inputs = {
    flake-utils.url = "github:numtide/flake-utils";
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

    pyproject-nix = {
      url = "github:pyproject-nix/pyproject.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    uv2nix = {
      url = "github:pyproject-nix/uv2nix";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    pyproject-build-systems = {
      url = "github:pyproject-nix/build-system-pkgs";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.uv2nix.follows = "uv2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = {
    self,
    nixpkgs,
    flake-utils,
    pyproject-nix,
    uv2nix,
    pyproject-build-systems,
    ...
  }: let
    name = "blitz-api";

    # Load the uv workspace once; reused across systems.
    workspace = uv2nix.lib.workspace.loadWorkspace {workspaceRoot = ./.;};

    # Pure Nix overlay derived from pyproject.toml + uv.lock. Prefer
    # prebuilt wheels — a handful of deps (grpcio, psutil, pyzmq) are
    # painful to compile from source and wheels work fine on linux/darwin.
    overlay = workspace.mkPyprojectOverlay {
      sourcePreference = "wheel";
    };

    systems = flake-utils.lib.eachDefaultSystem (system: let
      pkgs = nixpkgs.legacyPackages.${system};
      python = pkgs.python312;

      pythonSet =
        (pkgs.callPackage pyproject-nix.build.packages {
          inherit python;
        })
        .overrideScope (
          nixpkgs.lib.composeManyExtensions [
            pyproject-build-systems.overlays.default
            overlay
          ]
        );
    in {
      packages = {
        default = self.packages.${system}.${name};
        ${name} = pythonSet.mkVirtualEnv "${name}-env" workspace.deps.default;
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
