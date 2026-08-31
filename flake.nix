{
  description = "Production-grade, token-optimized FastMCP SQLite Server";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        python = pkgs.python312;
      in
      {
        packages.default = python.pkgs.buildPythonApplication {
          pname = "fastmcp-sqlite";
          version = "1.0.0";
          pyproject = true;
          src = ./.;

          nativeBuildInputs = [ python.pkgs.hatchling ];
          propagatedBuildInputs = [ python.pkgs.mcp ];

          doCheck = false;
        };

        apps.default = {
          type = "app";
          program = "${self.packages.${system}.default}/bin/fastmcp-sqlite";
        };
      });
}
