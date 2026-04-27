{
  description = "Reproducible development shell for x2mdx";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-24.11";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = import nixpkgs { inherit system; };
        python = pkgs.python312;
        pythonPackages = pkgs.python312Packages;
        pythonEnv = python.withPackages (
          ps: with ps; [
            jinja2
            protobuf
            pyyaml
            pytest
          ]
        );
        x2mdx = pythonPackages.buildPythonApplication {
          pname = "x2mdx";
          version = "0.1.0";
          pyproject = true;
          src = ./.;
          nativeBuildInputs = with pythonPackages; [
            setuptools
            wheel
          ];
          propagatedBuildInputs = with pythonPackages; [
            jinja2
            protobuf
            pyyaml
          ];
          doCheck = false;
        };
      in
      {
        packages.default = x2mdx;
        apps.default = flake-utils.lib.mkApp { drv = x2mdx; };

        devShells.default = pkgs.mkShell {
          packages = [
            pkgs.git
            pkgs.nodejs_22
            pythonEnv
            x2mdx
          ];

          shellHook = ''
            export PYTHONPATH="$PWD/src''${PYTHONPATH:+:$PYTHONPATH}"
            echo "x2mdx dev shell ready: node $(node -v), python $(python --version 2>&1)"
          '';
        };
      }
    );
}
