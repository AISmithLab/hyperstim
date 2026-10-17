#!/usr/bin/env bash
# Set up (or update) the prod instance on this server (plan 010).
#
#   sudo deploy/setup.sh
#
# Reads deploy/server.env (copy deploy/server.env.example and fill it in). Safe to run
# again at any time: it changes only what differs, and says what it changed.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$HERE")"
CONFIG="$HERE/server.env"
RELEASE_COMMAND=/usr/local/bin/hyperstim-release

say() { printf '\033[1m%s\033[0m\n' "$*"; }
fail() {
  echo "setup: $*" >&2
  exit 1
}

[ "$(id -u)" = 0 ] || fail "run it with sudo: sudo deploy/setup.sh"
[ -f "$CONFIG" ] || fail "no deploy/server.env: copy deploy/server.env.example and fill it in."
. "$CONFIG"
VARS="PROD_DIR SERVICE SERVICE_USER PORT RELEASE_GROUP RELEASERS NGINX_SITE CORS_ORIGIN
  YOUTUBE_API_KEY ANALYSIS_LIMIT_PER_IP ANALYSIS_LIMIT_PER_DAY"
for name in $VARS; do
  value="${!name:-}"
  [ -n "$value" ] || fail "$name is empty in deploy/server.env."
  case "$value" in *"<"*) fail "$name still has a placeholder in deploy/server.env." ;; esac
  export "${name?}"
done
export YTDLP_COOKIES="${YTDLP_COOKIES:-}"
[ -f "$NGINX_SITE" ] || fail "NGINX_SITE: no such file: $NGINX_SITE"

CHANGED=() # what this run changed, for the summary
as_service() { sudo -u "$SERVICE_USER" env HOME="$PROD_DIR/data" PATH="$PROD_DIR/bin:/usr/bin:/bin" "$@"; }

# install_file <template> <target> <mode> <owner:group>: render, and install only if it differs.
install_file() {
  local tmp
  tmp="$(mktemp)"
  envsubst "$(printf '${%s} ' $VARS YTDLP_COOKIES)" <"$HERE/$1" >"$tmp"
  if [ -f "$2" ] && cmp -s "$tmp" "$2"; then
    chmod "$3" "$2" && chown "$4" "$2"
    rm "$tmp"
    return 1
  fi
  install -m "$3" -o "${4%%:*}" -g "${4##*:}" "$tmp" "$2"
  rm "$tmp"
  CHANGED+=("$2")
}

# --- Tools ------------------------------------------------------------------------------

say "Tools (tools.env)"
install -d -m 755 "$PROD_DIR" "$PROD_DIR/bin"
"$ROOT/scripts/install-tools.sh" server "$PROD_DIR/bin"

# --- User, group, folders ---------------------------------------------------------------

say "User, group, folders"
if ! getent passwd "$SERVICE_USER" >/dev/null; then
  useradd --system --home-dir "$PROD_DIR/data" --no-create-home --shell /usr/sbin/nologin "$SERVICE_USER"
  CHANGED+=("user $SERVICE_USER")
fi
if ! getent group "$RELEASE_GROUP" >/dev/null; then
  groupadd --system "$RELEASE_GROUP"
  CHANGED+=("group $RELEASE_GROUP")
fi
for login in $RELEASERS; do
  id "$login" >/dev/null 2>&1 || fail "RELEASERS: no user $login on this server."
  if ! id -nG "$login" | tr ' ' '\n' | grep -qx "$RELEASE_GROUP"; then
    usermod -aG "$RELEASE_GROUP" "$login"
    CHANGED+=("$login added to $RELEASE_GROUP (log in again to use it)")
  fi
done
install -d -m 755 -o "$SERVICE_USER" -g "$SERVICE_USER" \
  "$PROD_DIR/repo" "$PROD_DIR/releases" "$PROD_DIR/uv" "$PROD_DIR/data"
install -d -m 700 -o "$SERVICE_USER" -g "$SERVICE_USER" "$PROD_DIR/data/analysis" "$PROD_DIR/data/thumbnails"
[ -e "$PROD_DIR/releases.log" ] || install -m 644 -o "$SERVICE_USER" -g "$SERVICE_USER" /dev/null "$PROD_DIR/releases.log"

# --- The clone --------------------------------------------------------------------------

say "Clone"
url="https://github.com/$(git -C "$ROOT" remote get-url origin | sed -E 's#^.*github\.com[:/]##; s#\.git$##').git"
if [ ! -e "$PROD_DIR/repo/.git" ]; then
  as_service git clone --quiet --no-checkout "$url" "$PROD_DIR/repo" ||
    fail "couldn't clone $url (the repo must be public)."
  CHANGED+=("clone of $url")
elif [ "$(as_service git -C "$PROD_DIR/repo" remote get-url origin)" != "$url" ]; then
  as_service git -C "$PROD_DIR/repo" remote set-url origin "$url"
  CHANGED+=("clone's origin set to $url")
fi

# --- Settings and the service -----------------------------------------------------------

say "Settings and systemd"
restart=0
install_file env.template "$PROD_DIR/env" 640 "root:$SERVICE_USER" && restart=1
install_file instance.env.template "$PROD_DIR/instance.env" 644 root:root || true
if install_file service.template "$PROD_DIR/$SERVICE.service" 644 root:root; then
  systemctl daemon-reload
  restart=1
fi
[ -L "/etc/systemd/system/$SERVICE.service" ] || systemctl link --quiet "$PROD_DIR/$SERVICE.service"
systemctl is-enabled --quiet "$SERVICE" || systemctl enable --quiet "$SERVICE"
if [ "$restart" = 1 ] && systemctl is-active --quiet "$SERVICE"; then
  systemctl restart "$SERVICE"
  CHANGED+=("restarted $SERVICE")
fi

# --- Releasing --------------------------------------------------------------------------

say "Release command and sudo rule"
install_file release-command.template "$RELEASE_COMMAND" 755 root:root || true
tmp="$(mktemp)"
envsubst "$(printf '${%s} ' $VARS)" <"$HERE/sudoers.template" >"$tmp"
visudo -cqf "$tmp" || fail "the rendered sudoers rule doesn't parse."
if ! cmp -s "$tmp" "/etc/sudoers.d/$SERVICE"; then
  install -m 440 -o root -g root "$tmp" "/etc/sudoers.d/$SERVICE"
  CHANGED+=("/etc/sudoers.d/$SERVICE")
fi
rm "$tmp"

# --- nginx ------------------------------------------------------------------------------

say "nginx"
nginx_changed=0
for f in nginx-http nginx-locations nginx-proxy; do
  install_file "$f.conf.template" "$PROD_DIR/$f.conf" 644 root:root && nginx_changed=1
done
if [ ! -L "/etc/nginx/conf.d/$SERVICE.conf" ]; then
  ln -s "$PROD_DIR/nginx-http.conf" "/etc/nginx/conf.d/$SERVICE.conf"
  nginx_changed=1
fi
include="include $PROD_DIR/nginx-locations.conf;"
backup=""
if ! grep -qF "$include" "$NGINX_SITE"; then
  # Into the TLS server block: just before its `listen 443` line.
  grep -q "listen 443" "$NGINX_SITE" || fail "NGINX_SITE has no 'listen 443' line to add the API next to."
  backup="$PROD_DIR/$(basename "$NGINX_SITE").before-setup"
  cp -p "$NGINX_SITE" "$backup"
  sed -i "0,/listen 443/s||# The website's API under /v2/ (deploy/setup.sh)\n    $include\n\n    &|" "$NGINX_SITE"
  CHANGED+=("$NGINX_SITE (backup: $backup)")
  nginx_changed=1
fi
if [ "$nginx_changed" = 1 ]; then
  if ! nginx -t -q; then
    [ -n "$backup" ] && cp -p "$backup" "$NGINX_SITE"
    fail "nginx -t failed; the site file is restored. Fix the templates and run again."
  fi
  systemctl reload nginx
fi

# --- Summary ----------------------------------------------------------------------------

if [ "${#CHANGED[@]}" = 0 ]; then
  say "Nothing to change: the server matches deploy/server.env."
else
  say "Changed:"
  printf '  %s\n' "${CHANGED[@]}"
fi
[ -e "$PROD_DIR/releases/current" ] || say "Next: the first release, with hyperstim-release (see the root README)."
