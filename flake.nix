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

    # Load the uv workspace once. Pure Nix value — independent of
    # the consumer's pkgs, only depends on this repo's source tree.
    workspace = uv2nix.lib.workspace.loadWorkspace {workspaceRoot = ./.;};

    # Pyproject-nix overlay derived from pyproject.toml + uv.lock.
    # Prefer prebuilt wheels — a handful of deps (grpcio, psutil,
    # pyzmq) are painful to compile from source and wheels work
    # fine on linux/darwin. Also pkgs-independent.
    pyprojectOverlay = workspace.mkPyprojectOverlay {
      sourcePreference = "wheel";
    };

    # Build the blitz-api Python virtualenv against the CALLER's
    # pkgs. Exposed as `lib.mkBlitzApi` so consumers (NixBlitz
    # plugin, downstream embedders) can build the package using
    # their own nixpkgs — important when the consumer needs a
    # platform-specific patch that this flake's pinned
    # nixos-unstable doesn't carry yet.
    #
    # Without this, the package would be built once at THIS flake's
    # eval time using THIS flake's pinned nixpkgs, and consumer
    # overlays couldn't reach the build hook.
    mkBlitzApi = {
      pkgs,
      python ? null,
    }: let
      py =
        if python != null
        then python
        else pkgs.python312;
      pythonSet = (pkgs.callPackage pyproject-nix.build.packages {python = py;})
        .overrideScope (
        pkgs.lib.composeManyExtensions [
          pyproject-build-systems.overlays.default
          pyprojectOverlay
        ]
      );
    in
      pythonSet.mkVirtualEnv "${name}-env" workspace.deps.default;

    # Library output — what callers reach for to build the package
    # under their own pkgs.
    libOutput = {
      lib = {inherit mkBlitzApi;};
    };

    systems = flake-utils.lib.eachDefaultSystem (system: let
      pkgs = nixpkgs.legacyPackages.${system};
    in {
      packages = {
        default = self.packages.${system}.${name};
        # Convenience: a pre-built package using THIS flake's pinned
        # nixpkgs. Most consumers should use `overlays.default` or
        # `lib.mkBlitzApi` instead so the package builds against
        # their pkgs.
        ${name} = mkBlitzApi {inherit pkgs;};
      };
    });

    overlays.overlays = {
      # Re-runs `mkBlitzApi` against the consumer's `prev` pkgs so the
      # consumer's overlays (Pi 5 page-size patch, custom uv pin, etc.)
      # are in scope when the package is built.
      default = final: prev: {
        ${name} = mkBlitzApi {pkgs = prev;};
      };
    };

    module = {
      nixosModules.default = {...}: {
        imports = [./modules/blitz_api.nix];
        nixpkgs.overlays = [self.overlays.default];
      };
    };
  in
    systems // overlays // module // libOutput;
}
