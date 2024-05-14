{pkgs}: {
  deps = [
    pkgs.postgresql
    pkgs.openssl
    pkgs.rustc
    pkgs.libiconv
    pkgs.cargo
    pkgs.ffmpeg-full
    pkgs.inetutils
  ];
}
