#!/usr/bin/env bash

set -u

BASHRC_PATH=${BASHRC_PATH:-$HOME/.bashrc}
PATH_LINE='export PATH="$HOME/project/gpt-codex-bridge/bin:$PATH"'
LEGACY_START='# ChatGPT Web -> E500 Codex CLI Bridge Functions'
LEGACY_END='# If not running interactively, don'"'"'t do anything'

if [[ ! -f $BASHRC_PATH ]]; then
    printf '%s\n' "uninstall: $BASHRC_PATH does not exist; nothing to do"
    exit 0
fi

if grep -Fqx "$LEGACY_START" "$BASHRC_PATH" && ! grep -Fqx "$LEGACY_END" "$BASHRC_PATH"; then
    printf '%s\n' 'uninstall: legacy bridge block has no closing marker; refusing to edit' >&2
    exit 1
fi

backup_path="$BASHRC_PATH.bridge-backup.$(date +%Y%m%d-%H%M%S)"
cp -p "$BASHRC_PATH" "$backup_path" || {
    printf '%s\n' "uninstall: cannot create backup $backup_path" >&2
    exit 1
}

tmp_file=$(mktemp "${BASHRC_PATH}.tmp.XXXXXX") || {
    printf '%s\n' 'uninstall: cannot create temporary .bashrc file' >&2
    exit 1
}
trap 'rm -f -- "$tmp_file"' EXIT

awk -v path_line="$PATH_LINE" -v legacy_start="$LEGACY_START" -v legacy_end="$LEGACY_END" '
    $0 == legacy_start { in_legacy = 1; next }
    in_legacy && $0 == legacy_end { in_legacy = 0; print; next }
    in_legacy { next }
    $0 == "# gpt-codex-bridge" { next }
    $0 == path_line { next }
    { print }
' "$BASHRC_PATH" >"$tmp_file" || {
    printf '%s\n' 'uninstall: failed to transform .bashrc' >&2
    exit 1
}

chmod --reference="$BASHRC_PATH" "$tmp_file" 2>/dev/null || true
mv -- "$tmp_file" "$BASHRC_PATH" || {
    printf '%s\n' 'uninstall: failed to replace .bashrc' >&2
    exit 1
}
trap - EXIT

printf 'Removed bridge PATH entry and legacy functions from %s\n' "$BASHRC_PATH"
printf 'Backup: %s\n' "$backup_path"
printf '%s\n' 'The project directory was not deleted.'
