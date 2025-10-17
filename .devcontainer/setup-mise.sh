#!/bin/sh
set -eu

#region logging setup
if [ "${MISE_DEBUG-}" = "true" ] || [ "${MISE_DEBUG-}" = "1" ]; then
  debug() {
    echo "$@" >&2
  }
else
  debug() {
    :
  }
fi

if [ "${MISE_QUIET-}" = "1" ] || [ "${MISE_QUIET-}" = "true" ]; then
  info() {
    :
  }
else
  info() {
    echo "$@" >&2
  }
fi

error() {
  echo "$@" >&2
  exit 1
}
#endregion

#region environment setup
get_os() {
  os="$(uname -s)"
  if [ "$os" = Darwin ]; then
    echo "macos"
  elif [ "$os" = Linux ]; then
    echo "linux"
  else
    error "unsupported OS: $os"
  fi
}

get_arch() {
  musl=""
  if type ldd >/dev/null 2>/dev/null; then
    libc=$(ldd /bin/ls | grep 'musl' | head -1 | cut -d ' ' -f1)
    if [ -n "$libc" ]; then
      musl="-musl"
    fi
  fi
  arch="$(uname -m)"
  if [ "$arch" = x86_64 ]; then
    echo "x64$musl"
  elif [ "$arch" = aarch64 ] || [ "$arch" = arm64 ]; then
    echo "arm64$musl"
  elif [ "$arch" = armv7l ]; then
    echo "armv7$musl"
  else
    error "unsupported architecture: $arch"
  fi
}

get_ext() {
  if [ -n "${MISE_INSTALL_EXT:-}" ]; then
    echo "$MISE_INSTALL_EXT"
  elif [ -n "${MISE_VERSION:-}" ] && echo "$MISE_VERSION" | grep -q '^v2024'; then
    # 2024 versions don't have zstd tarballs
    echo "tar.gz"
  elif tar_supports_zstd; then
    echo "tar.zst"
  elif command -v zstd >/dev/null 2>&1; then
    echo "tar.zst"
  else
    echo "tar.gz"
  fi
}

tar_supports_zstd() {
  # tar is bsdtar or version is >= 1.31
  if tar --version | grep -q 'bsdtar' && command -v zstd >/dev/null 2>&1; then
    true
  elif tar --version | grep -q '1\.(3[1-9]|[4-9][0-9]'; then
    true
  else
    false
  fi
}

shasum_bin() {
  if command -v shasum >/dev/null 2>&1; then
    echo "shasum"
  elif command -v sha256sum >/dev/null 2>&1; then
    echo "sha256sum"
  else
    error "mise install requires shasum or sha256sum but neither is installed. Aborting."
  fi
}

get_checksum() {
  version=$1
  os=$2
  arch=$3
  ext=$4
  url="https://github.com/jdx/mise/releases/download/v${version}/SHASUMS256.txt"

  # For current version use static checksum otherwise
  # use checksum from releases
  if [ "$version" = "v2025.8.16" ]; then
    checksum_linux_x86_64="c453f592e95e66d13b3fd9a7c049a86ee71261d812ceacec036be6841fb88805  ./mise-v2025.8.16-linux-x64.tar.gz"
    checksum_linux_x86_64_musl="be127271afe4914654122abf17d49eeca57356c1b6818e7e81c8b26af398988a  ./mise-v2025.8.16-linux-x64-musl.tar.gz"
    checksum_linux_arm64="30ba858664e5b90826f36dc9eea8290b02eaf4e7d0c2751dedbd33b6b9046066  ./mise-v2025.8.16-linux-arm64.tar.gz"
    checksum_linux_arm64_musl="3faab17d8273f69dcacb2add0cb47e25b7d3cdeb91e992bd0981c3e48ec8c8e2  ./mise-v2025.8.16-linux-arm64-musl.tar.gz"
    checksum_linux_armv7="57d6becee0c6a68148dcea2794e49407eca08de88307d506a04a7adee06e4aa3  ./mise-v2025.8.16-linux-armv7.tar.gz"
    checksum_linux_armv7_musl="7156d6b0dab497eea6d1f3da17e997aede739f0f2b8226f759c1d32e56b1d4a5  ./mise-v2025.8.16-linux-armv7-musl.tar.gz"
    checksum_macos_x86_64="e15e8eee69643c289aa760e5e28df07875260a44e86f792f1be56e0a37144dd7  ./mise-v2025.8.16-macos-x64.tar.gz"
    checksum_macos_arm64="f5aa1c53165cee31a37a569af88ad15049568a1a91372acd5ca388401383ac35  ./mise-v2025.8.16-macos-arm64.tar.gz"
    checksum_linux_x86_64_zstd="fa64a12902dc21b24743f89e0445b41b456b042550417bbddde60aac465caa6b  ./mise-v2025.8.16-linux-x64.tar.zst"
    checksum_linux_x86_64_musl_zstd="9feb535ebc4d07ea67fc2c5874884f0f34b2c4e9a5d7ad7680cca67be87a558f  ./mise-v2025.8.16-linux-x64-musl.tar.zst"
    checksum_linux_arm64_zstd="b9d9529797539283e1f367d7e4b24bd5f41fcaa03dcf7db6f90649565a1c882d  ./mise-v2025.8.16-linux-arm64.tar.zst"
    checksum_linux_arm64_musl_zstd="74ab809fc21b43c0fb742b458a0a0bafd74d9242cf8a4262bcf7bdae154e4ced  ./mise-v2025.8.16-linux-arm64-musl.tar.zst"
    checksum_linux_armv7_zstd="97ad4b84369ccbca4c83feca45ef02e88a2b0b9c460ae121571f2162be6802a1  ./mise-v2025.8.16-linux-armv7.tar.zst"
    checksum_linux_armv7_musl_zstd="28b9d07150fcd8685670a110fb7b51a355ab21e3bf8c017a784e719a5aa68bdc  ./mise-v2025.8.16-linux-armv7-musl.tar.zst"
    checksum_macos_x86_64_zstd="8a93d3bf948ded9da18aeb3985e2c7386494b9470ab52a06caf64e4c89b2037f  ./mise-v2025.8.16-macos-x64.tar.zst"
    checksum_macos_arm64_zstd="4f583fa1e7451461fee2daffdc094e69ee0d1c5515e411957f38780a88f3322f  ./mise-v2025.8.16-macos-arm64.tar.zst"

    # TODO: refactor this, it's a bit messy
    if [ "$ext" = "tar.zst" ]; then
      if [ "$os" = "linux" ]; then
        if [ "$arch" = "x64" ]; then
          echo "$checksum_linux_x86_64_zstd"
        elif [ "$arch" = "x64-musl" ]; then
          echo "$checksum_linux_x86_64_musl_zstd"
        elif [ "$arch" = "arm64" ]; then
          echo "$checksum_linux_arm64_zstd"
        elif [ "$arch" = "arm64-musl" ]; then
          echo "$checksum_linux_arm64_musl_zstd"
        elif [ "$arch" = "armv7" ]; then
          echo "$checksum_linux_armv7_zstd"
        elif [ "$arch" = "armv7-musl" ]; then
          echo "$checksum_linux_armv7_musl_zstd"
        else
          warn "no checksum for $os-$arch"
        fi
      elif [ "$os" = "macos" ]; then
        if [ "$arch" = "x64" ]; then
          echo "$checksum_macos_x86_64_zstd"
        elif [ "$arch" = "arm64" ]; then
          echo "$checksum_macos_arm64_zstd"
        else
          warn "no checksum for $os-$arch"
        fi
      else
        warn "no checksum for $os-$arch"
      fi
    else
      if [ "$os" = "linux" ]; then
        if [ "$arch" = "x64" ]; then
          echo "$checksum_linux_x86_64"
        elif [ "$arch" = "x64-musl" ]; then
          echo "$checksum_linux_x86_64_musl"
        elif [ "$arch" = "arm64" ]; then
          echo "$checksum_linux_arm64"
        elif [ "$arch" = "arm64-musl" ]; then
          echo "$checksum_linux_arm64_musl"
        elif [ "$arch" = "armv7" ]; then
          echo "$checksum_linux_armv7"
        elif [ "$arch" = "armv7-musl" ]; then
          echo "$checksum_linux_armv7_musl"
        else
          warn "no checksum for $os-$arch"
        fi
      elif [ "$os" = "macos" ]; then
        if [ "$arch" = "x64" ]; then
          echo "$checksum_macos_x86_64"
        elif [ "$arch" = "arm64" ]; then
          echo "$checksum_macos_arm64"
        else
          warn "no checksum for $os-$arch"
        fi
      else
        warn "no checksum for $os-$arch"
      fi
    fi
  else
    if command -v curl >/dev/null 2>&1; then
      debug ">" curl -fsSL "$url"
      checksums="$(curl --compressed -fsSL "$url")"
    else
      if command -v wget >/dev/null 2>&1; then
        debug ">" wget -qO - "$url"
        stderr=$(mktemp)
        checksums="$(wget -qO - "$url")"
      else
        error "mise standalone install specific version requires curl or wget but neither is installed. Aborting."
      fi
    fi
    # TODO: verify with minisign or gpg if available

    checksum="$(echo "$checksums" | grep "$os-$arch.$ext")"
    if ! echo "$checksum" | grep -Eq "^([0-9a-f]{32}|[0-9a-f]{64})"; then
      warn "no checksum for mise $version and $os-$arch"
    else
      echo "$checksum"
    fi
  fi
}

#endregion

download_file() {
  url="$1"
  filename="$(basename "$url")"
  cache_dir="$(mktemp -d)"
  file="$cache_dir/$filename"

  info "mise: installing mise..."

  if command -v curl >/dev/null 2>&1; then
    debug ">" curl -#fLo "$file" "$url"
    curl -#fLo "$file" "$url"
  else
    if command -v wget >/dev/null 2>&1; then
      debug ">" wget -qO "$file" "$url"
      stderr=$(mktemp)
      wget -O "$file" "$url" >"$stderr" 2>&1 || error "wget failed: $(cat "$stderr")"
    else
      error "mise standalone install requires curl or wget but neither is installed. Aborting."
    fi
  fi

  echo "$file"
}

install_mise() {
  version="${MISE_VERSION:-v2025.8.16}"
  version="${version#v}"
  os="${MISE_INSTALL_OS:-$(get_os)}"
  arch="${MISE_INSTALL_ARCH:-$(get_arch)}"
  ext="${MISE_INSTALL_EXT:-$(get_ext)}"
  install_path="${MISE_INSTALL_PATH:-$HOME/.local/bin/mise}"
  install_dir="$(dirname "$install_path")"
  install_from_github="${MISE_INSTALL_FROM_GITHUB:-}"
  if [ "$version" != "v2025.8.16" ] || [ "$install_from_github" = "1" ] || [ "$install_from_github" = "true" ]; then
    tarball_url="https://github.com/jdx/mise/releases/download/v${version}/mise-v${version}-${os}-${arch}.${ext}"
  elif [ -n "${MISE_TARBALL_URL-}" ]; then
    tarball_url="$MISE_TARBALL_URL"
  else
    tarball_url="https://mise.jdx.dev/v${version}/mise-v${version}-${os}-${arch}.${ext}"
  fi

  cache_file=$(download_file "$tarball_url")
  debug "mise-setup: tarball=$cache_file"

  debug "validating checksum"
  cd "$(dirname "$cache_file")" && get_checksum "$version" "$os" "$arch" "$ext" | "$(shasum_bin)" -c >/dev/null

  # extract tarball
  mkdir -p "$install_dir"
  rm -rf "$install_path"
  cd "$(mktemp -d)"
  if [ "$ext" = "tar.zst" ] && ! tar_supports_zstd; then
    zstd -d -c "$cache_file" | tar -xf -
  else
    tar -xf "$cache_file"
  fi
  mv mise/bin/mise "$install_path"
  info "mise: installed successfully to $install_path"
}

after_finish_help() {
  case "${SHELL:-}" in
  */zsh)
    info "mise: run the following to activate mise in your shell:"
    info "echo \"eval \\\"\\\$($install_path activate zsh)\\\"\" >> \"${ZDOTDIR-$HOME}/.zshrc\""
    info ""
    info "mise: run \`mise doctor\` to verify this is setup correctly"
    ;;
  */bash)
    info "mise: run the following to activate mise in your shell:"
    info "echo \"eval \\\"\\\$($install_path activate bash)\\\"\" >> ~/.bashrc"
    info ""
    info "mise: run \`mise doctor\` to verify this is setup correctly"
    ;;
  */fish)
    info "mise: run the following to activate mise in your shell:"
    info "echo \"$install_path activate fish | source\" >> ~/.config/fish/config.fish"
    info ""
    info "mise: run \`mise doctor\` to verify this is setup correctly"
    ;;
  *)
    info "mise: run \`$install_path --help\` to get started"
    ;;
  esac
}

install_mise

# --- ensure mise auto-activates in bash and zsh ---
INSTALL_PATH="${MISE_INSTALL_PATH:-$HOME/.local/bin/mise}"

ensure_line() {
  file="$1"; line="$2"
  [ -f "$file" ] || : >"$file"
  grep -qxF "$line" "$file" || printf '%s\n' "$line" >> "$file"
}

# Bash setup
BASHRC="$HOME/.bashrc"
ensure_line "$BASHRC" 'export PATH="$HOME/.local/bin:$PATH"'
ensure_line "$BASHRC" "eval \"\$($INSTALL_PATH activate bash)\""

# Zsh setup
ZSHRC="${ZDOTDIR:-$HOME}/.zshrc"
# create zshrc if missing
[ -f "$ZSHRC" ] || : >"$ZSHRC"
ensure_line "$ZSHRC" 'export PATH="$HOME/.local/bin:$PATH"'
ensure_line "$ZSHRC" "eval \"\$($INSTALL_PATH activate zsh)\""

# Activate mise for the *current* shell (no restart needed)
if [ -x "$INSTALL_PATH" ]; then
  case "${SHELL:-}" in
    */zsh)  eval "$($INSTALL_PATH activate zsh)"  ;;
    */bash) eval "$($INSTALL_PATH activate bash)" ;;
    *)      : ;;  # unknown shell; skip
  esac
fi

# Optionally keep the help messages
if [ "${MISE_INSTALL_HELP-}" != 0 ]; then
  after_finish_help
fi