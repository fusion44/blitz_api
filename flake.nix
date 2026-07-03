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
      inputs = {
        pyproject-nix.follows = "pyproject-nix";
        nixpkgs.follows = "nixpkgs";
      };
    };

    pyproject-build-systems = {
      url = "github:pyproject-nix/build-system-pkgs";
      inputs = {
        pyproject-nix.follows = "pyproject-nix";
        uv2nix.follows = "uv2nix";
        nixpkgs.follows = "nixpkgs";
      };
    };
  };

  outputs = {
    self,
    nixpkgs,
    flake-utils,
    pyproject-nix,
    uv2nix,
    pyproject-build-systems,
  }: let
    name = "blitz-api";
    inherit (nixpkgs) lib;

    workspace = uv2nix.lib.workspace.loadWorkspace {workspaceRoot = ./.;};

    # Prefer prebuilt binary wheels: building grpcio & friends from
    # source is slow and needs extra native build inputs.
    overlay = workspace.mkPyprojectOverlay {
      sourcePreference = "wheel";
    };

    systems = flake-utils.lib.eachDefaultSystem (system: let
      pkgs = nixpkgs.legacyPackages.${system};
      # 3.12 to match devenv.nix; RaspiBlitz 1.12 ships 3.11
      python = pkgs.python312;

      pythonSet =
        (pkgs.callPackage pyproject-nix.build.packages {
          inherit python;
        }).overrideScope (
          lib.composeManyExtensions [
            pyproject-build-systems.overlays.default
            overlay
          ]
        );

      venv = pythonSet.mkVirtualEnv "${name}-env" workspace.deps.default;
    in {
      packages = {
        default = self.packages.${system}.${name};
        # A virtualenv with blitz_api and all of its dependencies.
        # Provides the `api` console script used by the NixOS module.
        ${name} = venv.overrideAttrs (old: {
          meta = (old.meta or {}) // {mainProgram = "api";};
        });
      };

      # Python dependencies are managed impurely via `uv sync` into
      # ./.venv, mirroring devenv.nix; this shell provides the tooling.
      devShells.default = pkgs.mkShell {
        packages = with pkgs; [
          python
          uv

          stdenv.cc.cc
          pyright
          isort
          alejandra
          statix
          ruff
          redis
          nushell
          typos
          typos-lsp
          sshpass

          bitcoind
          lnd
          clightning
        ];

        env = {
          # use the nix-provided interpreter and never download one
          UV_PYTHON = python.interpreter;
          UV_PYTHON_DOWNLOADS = "never";
        };

        shellHook = ''
          unset PYTHONPATH
          export LD_LIBRARY_PATH="$LD_LIBRARY_PATH:${
            lib.makeLibraryPath [pkgs.stdenv.cc.cc.lib]
          }"
        '';
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
