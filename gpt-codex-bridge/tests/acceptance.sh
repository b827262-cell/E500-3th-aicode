#!/usr/bin/env bash

set -u

ROOT=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd) || exit 1
BIN="$ROOT/bin"
TMP_ROOT=$(mktemp -d "${TMPDIR:-/tmp}/gpt-codex-bridge-tests.XXXXXX") || exit 1
MOCK_PATH="$TMP_ROOT/mock-path"
mkdir -p "$MOCK_PATH"
ln -s /usr/bin/env "$MOCK_PATH/env"
ln -s /usr/bin/bash "$MOCK_PATH/bash"
UNREADABLE_XAUTH="$TMP_ROOT/unreadable-xauthority"
: >"$UNREADABLE_XAUTH"
chmod 000 "$UNREADABLE_XAUTH"
trap 'chmod 600 "$UNREADABLE_XAUTH" 2>/dev/null || true; rm -rf -- "$TMP_ROOT"' EXIT

failures=0

pgrep() {
    printf '%s\n' "${TEST_GUI_PID:?}"
}

xclip() {
    case " $* " in
        *' -i '*)
            /usr/bin/cat >"${MOCK_CLIPBOARD_FILE:?}.incoming"
            /usr/bin/mv -- "${MOCK_CLIPBOARD_FILE}.incoming" "$MOCK_CLIPBOARD_FILE"
            return 0
            ;;
        *' -o '*)
            if [[ -f ${MOCK_CLIPBOARD_FILE:-} ]]; then
                /usr/bin/cat -- "$MOCK_CLIPBOARD_FILE"
                return 0
            fi
            ;;
    esac

    case ${MOCK_XCLIP_MODE:-normal} in
        failure)
            printf 'partial clipboard'
            return 37
            ;;
        empty)
            printf ' \t\n\r'
            ;;
        utf8)
            printf '中文測試\n第二行'
            ;;
        multiline)
            printf 'line one\nline two\nline three\n'
            ;;
        *)
            printf 'acceptance clipboard'
            ;;
    esac
}

codex() {
    printf 'MOCK_CODEX_CALLED\n' >&2
    cat
}

MOCK_CLIPBOARD_FILE="$TMP_ROOT/mock.clipboard"
export MOCK_CLIPBOARD_FILE
export -f pgrep xclip codex

run_case() {
    local name=$1 command_label=$2 expected=$3 mode=$4 target=$5
    local stdout_file="$TMP_ROOT/$name.stdout"
    local stderr_file="$TMP_ROOT/$name.stderr"
    local -a env_args
    local path_value=/usr/bin:/bin
    local body rc actual pass=1

    env_args=()
    case $name in
        display_failure)
            env_args+=(-u DISPLAY XAUTHORITY=/run/user/1000/gdm/Xauthority)
            ;;
        no_xauthority)
            env_args+=(-u XAUTHORITY DISPLAY=:test)
            ;;
        xauthority_missing)
            env_args+=(DISPLAY=:test XAUTHORITY=/definitely/missing-xauthority)
            ;;
        xauthority_unreadable)
            env_args+=(DISPLAY=:test XAUTHORITY="$UNREADABLE_XAUTH")
            ;;
        xclip_missing)
            path_value=$MOCK_PATH
            env_args+=(DISPLAY=:test XAUTHORITY=/run/user/1000/gdm/Xauthority)
            ;;
        *)
            env_args+=(DISPLAY=:test XAUTHORITY=/run/user/1000/gdm/Xauthority)
            ;;
    esac
    env_args+=(PATH="$path_value" MOCK_XCLIP_MODE="$mode")

    body='TEST_GUI_PID=$$; export TEST_GUI_PID; '
    if [[ $name == xclip_missing ]]; then
        body+='unset -f xclip 2>/dev/null || true; '
    fi
    if [[ $name == preview_n ]]; then
        body+="printf '\\n' | '$target'"
    elif [[ $name == preview_y ]]; then
        body+="printf 'y\\n' | '$target'"
    else
        body+="'$target'"
    fi

    env "${env_args[@]}" /usr/bin/bash --noprofile --norc -c "$body" \
        >"$stdout_file" 2>"$stderr_file"
    rc=$?

    case $name in
        display_failure|no_xauthority|xauthority_missing|xauthority_unreadable)
            (( rc != 0 )) || pass=0
            [[ ! -s $stdout_file ]] || pass=0
            /usr/bin/grep -Eiq 'DISPLAY|XAUTHORITY' "$stderr_file" || pass=0
            ;;
        xclip_missing)
            (( rc == 127 )) || pass=0
            [[ ! -s $stdout_file ]] || pass=0
            /usr/bin/grep -Fq 'xclip' "$stderr_file" || pass=0
            ;;
        xclip_failure)
            (( rc == 37 )) || pass=0
            ! /usr/bin/grep -Fq MOCK_CODEX_CALLED "$stderr_file" || pass=0
            ;;
        empty)
            (( rc != 0 )) || pass=0
            ! /usr/bin/grep -Fq MOCK_CODEX_CALLED "$stderr_file" || pass=0
            /usr/bin/grep -Fq 'whitespace' "$stderr_file" || pass=0
            ;;
        utf8)
            (( rc == 0 )) || pass=0
            cmp -s "$stdout_file" <(printf '中文測試\n第二行') || pass=0
            ;;
        multiline)
            (( rc == 0 )) || pass=0
            cmp -s "$stdout_file" <(printf 'line one\nline two\nline three\n') || pass=0
            ;;
        preview_n)
            (( rc == 0 )) || pass=0
            /usr/bin/grep -Fq 'acceptance clipboard' "$stdout_file" || pass=0
            ! /usr/bin/grep -Fq MOCK_CODEX_CALLED "$stderr_file" || pass=0
            ;;
        preview_y)
            (( rc == 0 )) || pass=0
            /usr/bin/grep -Fq 'acceptance clipboard' "$stdout_file" || pass=0
            /usr/bin/grep -Fq MOCK_CODEX_CALLED "$stderr_file" || pass=0
            ;;
    esac

    actual="stdout=$(/usr/bin/tr '\n' ' ' <"$stdout_file") stderr=$(/usr/bin/tr '\n' ' ' <"$stderr_file")"
    printf 'COMMAND=%s\nEXPECTED=%s\nACTUAL=%s\nEXIT_CODE=%s\nRESULT=%s\n\n' \
        "$command_label" "$expected" "$actual" "$rc" "$([[ $pass -eq 1 ]] && printf PASS || printf FAIL)"
    if (( pass != 1 )); then
        failures=$((failures + 1))
    fi
}

run_pollution_case() {
    local stdout_file="$TMP_ROOT/pollution.stdout" stderr_file="$TMP_ROOT/pollution.stderr"
    local rc actual pass=1
    local body='TEST_GUI_PID=$$; export TEST_GUI_PID; before=$(/usr/bin/env | /usr/bin/grep -E "^(DISPLAY|XAUTHORITY)=" || true); '
    body+="'$BIN/gptclip' >/dev/null; rc=\$?; after=\$(/usr/bin/env | /usr/bin/grep -E \"^(DISPLAY|XAUTHORITY)=\" || true); printf \"BEFORE=%q\\nAFTER=%q\\nINNER_EXIT=%s\\n\" \"\$before\" \"\$after\" \"\$rc\""

    env PATH=/usr/bin:/bin MOCK_XCLIP_MODE=normal DISPLAY=:test \
        XAUTHORITY=/run/user/1000/gdm/Xauthority \
        /usr/bin/bash --noprofile --norc -c "$body" \
        >"$stdout_file" 2>"$stderr_file"
    rc=$?
    actual="$(/usr/bin/tr '\n' ' ' <"$stdout_file") stderr=$(/usr/bin/tr '\n' ' ' <"$stderr_file")"
    before_line=$(/usr/bin/sed -n 's/^BEFORE=//p' "$stdout_file")
    after_line=$(/usr/bin/sed -n 's/^AFTER=//p' "$stdout_file")
    [[ -n $before_line && $before_line == "$after_line" ]] || pass=0
    /usr/bin/grep -Fq 'INNER_EXIT=0' "$stdout_file" || pass=0
    (( rc == 0 )) || pass=0
    printf 'COMMAND=env before; gptclip; env after\nEXPECTED=DISPLAY/XAUTHORITY unchanged\nACTUAL=%s\nEXIT_CODE=%s\nRESULT=%s\n\n' \
        "$actual" "$rc" "$([[ $pass -eq 1 ]] && printf PASS || printf FAIL)"
    if (( pass != 1 )); then
        failures=$((failures + 1))
    fi
}

run_term2gpt_exact_case() {
    local payload_file="$TMP_ROOT/term2gpt.payload"
    local command_stdout="$TMP_ROOT/term2gpt.command.stdout"
    local command_stderr="$TMP_ROOT/term2gpt.command.stderr"
    local clipboard_file="$TMP_ROOT/term2gpt.clipboard"
    local result_file="$TMP_ROOT/term2gpt.result"
    local rc actual pass=1 body

    printf '%s\n' \
        '              total        used        free      shared  buff/cache   available' \
        'Mem:           15Gi       2.0Gi       8.0Gi       100Mi       5.0Gi        12Gi' \
        'Swap:          2.0Gi          0B       2.0Gi' >"$payload_file"

    body='TEST_GUI_PID=$$; export TEST_GUI_PID; '
    body+="'$BIN/term2gpt' <'$payload_file' >'$command_stdout'; term_rc=\$?; "
    body+="'$BIN/gptclip' >'$clipboard_file'; clip_rc=\$?; "
    body+="/usr/bin/cmp -s '$payload_file' '$clipboard_file'; compare_rc=\$?; "
    body+="printf 'TERM2GPT_EXIT=%s\\nCLIPBOARD_READ_EXIT=%s\\nBYTE_COMPARE_EXIT=%s\\n' \"\$term_rc\" \"\$clip_rc\" \"\$compare_rc\" >'$result_file'"

    env DISPLAY=:test XAUTHORITY=/run/user/1000/gdm/Xauthority \
        MOCK_XCLIP_MODE=normal PATH=/usr/bin:/bin \
        /usr/bin/bash --noprofile --norc -c "$body" \
        >"$command_stdout.outer" 2>"$command_stderr"
    rc=$?
    actual="stdout=$(/usr/bin/tr '\n' ' ' <"$command_stdout.outer") result=$(/usr/bin/tr '\n' ' ' <"$result_file") stderr=$(/usr/bin/tr '\n' ' ' <"$command_stderr")"

    (( rc == 0 )) || pass=0
    [[ ! -s $command_stdout ]] || pass=0
    /usr/bin/grep -Fq 'TERM2GPT_EXIT=0' "$result_file" || pass=0
    /usr/bin/grep -Fq 'CLIPBOARD_READ_EXIT=0' "$result_file" || pass=0
    /usr/bin/grep -Fq 'BYTE_COMPARE_EXIT=0' "$result_file" || pass=0
    [[ ! -s $command_stderr ]] || pass=0
    printf '%s\n' \
        'COMMAND=free -h | term2gpt; gptclip' \
        'EXPECTED=clipboard bytes exactly equal original stdout' \
        "ACTUAL=$actual" \
        "EXIT_CODE=$rc" \
        "RESULT=$([[ $pass -eq 1 ]] && printf PASS || printf FAIL)"
    if (( pass != 1 )); then
        failures=$((failures + 1))
    fi
}

printf 'STATIC\n'
for script in "$BIN/gptclip" "$BIN/term2gpt" "$BIN/gpt2codex" "$BIN/gpt2codex-preview" "$ROOT/install.sh" "$ROOT/uninstall.sh"; do
    bash -n "$script" || failures=$((failures + 1))
done
printf 'STATIC_RESULT=%s\n\n' "$([[ $failures -eq 0 ]] && printf PASS || printf FAIL)"

run_case display_failure 'gptclip (DISPLAY unset)' 'nonzero; DISPLAY diagnostic; no output' normal "$BIN/gptclip"
run_case no_xauthority 'gptclip (XAUTHORITY unset)' 'nonzero; XAUTHORITY diagnostic; no output' normal "$BIN/gptclip"
run_case xauthority_missing 'gptclip (XAUTHORITY missing)' 'nonzero; XAUTHORITY diagnostic; no output' normal "$BIN/gptclip"
run_case xauthority_unreadable 'gptclip (XAUTHORITY unreadable)' 'nonzero; XAUTHORITY diagnostic; no output' normal "$BIN/gptclip"
run_case xclip_missing 'gptclip (xclip absent)' '127; xclip diagnostic; no output' normal "$BIN/gptclip"
run_case xclip_failure 'gpt2codex (xclip failure)' 'nonzero; mock Codex not called' failure "$BIN/gpt2codex"
run_case empty 'gpt2codex (whitespace clipboard)' 'nonzero; mock Codex not called' empty "$BIN/gpt2codex"
run_case utf8 'gpt2codex (UTF-8 Chinese)' 'exact UTF-8 prompt' utf8 "$BIN/gpt2codex"
run_case multiline 'gpt2codex (multiline)' 'exact multiline prompt including final newline' multiline "$BIN/gpt2codex"
run_case preview_n 'gpt2codex-preview (Enter)' 'cancel; mock Codex not called' normal "$BIN/gpt2codex-preview"
run_case preview_y 'gpt2codex-preview (y)' 'preview then mock Codex' normal "$BIN/gpt2codex-preview"
run_pollution_case
run_term2gpt_exact_case

printf 'FAILURES=%s\n' "$failures"
exit "$failures"
