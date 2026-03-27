{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  packages = [
    pkgs.git
    pkgs.nodejs_22
    pkgs.python3
  ];

  shellHook = ''
    export PATH="$PWD/.venv/bin:$PWD/node_modules/.bin:$PATH"
    echo "control dev shell ready: node $(node -v)"
  '';
}
