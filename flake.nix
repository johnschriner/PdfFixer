{
  description = "pdffixer reproducible dev shell";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-24.05";

  outputs = { self, nixpkgs }:
  let
    forEachSystem = f:
      builtins.listToAttrs (map (system: { name = system; value = f system; }) [ "x86_64-linux" ]);
  in {
    devShells = forEachSystem (system:
      let
        # no special config needed now that we're skipping ngrok
        pkgs = import nixpkgs { inherit system; };
        py = pkgs.python311;
        pyPkgs = py.pkgs;
      in {
        default = pkgs.mkShell {
          packages = [
            # Python & libs your app uses
            py
            pyPkgs.pip
            pyPkgs.setuptools
            pyPkgs.wheel
            pyPkgs.flask
            pyPkgs.requests
            pyPkgs.gevent
            pyPkgs.gevent-websocket
            pyPkgs.flask-socketio
            pyPkgs.flask-cors
	    pyPkgs.pymupdf
            pyPkgs.pikepdf

            # system libs/binaries needed at runtime
            pkgs.qpdf
            pkgs.libglvnd   # provides libGL for PyMuPDF
          ];

          env = {
            OLLAMA_HOST = "http://127.0.0.1:11434";
            PDFFIXER_TEXT_MODEL = "llama3.2";
            PDFFIXER_VISION_MODEL = "llama3.2-vision";
            PYTHONUNBUFFERED = "1";
          };

          shellHook = ''
            echo "🔒 Nix shell active. Python: $(python -V)"
            echo "Run your app with:  python app.py"
          '';
        };
      });
  };
}
