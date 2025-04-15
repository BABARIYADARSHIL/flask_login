{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  buildInputs = with pkgs; [
    cmake
    gcc
    boost
    pkg-config
    libffi
    zlib
    libjpeg
    libpng
    python310
    python310Packages.pip
    python310Packages.setuptools
    python310Packages.wheel
  ];
}
