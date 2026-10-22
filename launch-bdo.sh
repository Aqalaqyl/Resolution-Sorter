#!/bin/bash
set -uo pipefail

# Run both Windows executables inside the same Steam prefix with Proton 11.0-2.
COMPAT="${HOME}/.steam/debian-installation/steamapps/compatdata/3549432507"
WINEPREFIX_PATH="${COMPAT}/pfx"
FIRST_EXE="/home/aqalaqyl/BDO/540q4bn.exe"
GAME_EXE="/home/aqalaqyl/BDO/bin64/BlackDesert64.exe"
FIRST_EXE_DELAY="${FIRST_EXE_DELAY:-15}"
PROTON_VERSION="11.0-2"
PROTON_DIR_NAME="Proton ${PROTON_VERSION}"

if [[ ! -d "$WINEPREFIX_PATH" ]]; then
    echo "error: Proton prefix not found: $WINEPREFIX_PATH" >&2
    exit 1
fi
for exe in "$FIRST_EXE" "$GAME_EXE"; do
    if [[ ! -f "$exe" ]]; then
        echo "error: executable not found: $exe" >&2
        exit 1
    fi
done

is_proton_1102() {
    local dir="$1"
    local line=""
    [[ -f "$dir/proton" && -f "$dir/version" ]] || return 1
    IFS= read -r line < "$dir/version" || return 1
    # Accept "11.0-2" or "proton-11.0-2", including a leading build timestamp.
    # Do not accept 11.0-20, 11.0-2RC, or any other Proton build.
    [[ "$line" =~ (^|[[:space:]])(proton-)?11\.0-2($|[[:space:]]) ]]
}

proton_dir_from_fonts() {
    local line="$1"
    case "$line" in
        */files/share/fonts/|*/files/share/fonts)
            line="${line%/files/share/fonts/}"
            line="${line%/files/share/fonts}"
            printf '%s\n' "$line"
            ;;
    esac
}

abs_dir() {
    (unset CDPATH && cd -- "$1" && pwd)
}

# compatdata/<appid> lives under <steam>/steamapps.
STEAM_ROOT="$(abs_dir "$(dirname "$(dirname "$(dirname "$COMPAT")")")")"
APP_ID="$(basename "$COMPAT")"

export WINEPREFIX="$WINEPREFIX_PATH"
export STEAM_COMPAT_DATA_PATH="$COMPAT"
export STEAM_COMPAT_CLIENT_INSTALL_PATH="$STEAM_ROOT"
export STEAM_COMPAT_APP_ID="$APP_ID"
export SteamAppId="$APP_ID"
export SteamGameId="$APP_ID"
export WINEFSYNC=1
export WINEESYNC=1
if [[ -z "${WINEDEBUG:-}" ]]; then
    export WINEDEBUG=-all
fi

declare -a PROTON_CANDIDATES=()
add_candidate() {
    local dir="$1"
    local existing
    [[ -n "$dir" ]] || return 0
    is_proton_1102 "$dir" || return 0
    for existing in "${PROTON_CANDIDATES[@]+"${PROTON_CANDIDATES[@]}"}"; do
        [[ "$existing" == "$dir" ]] && return 0
    done
    PROTON_CANDIDATES+=("$dir")
}

CONFIG_INFO="${COMPAT}/config_info"
if [[ -f "$CONFIG_INFO" ]]; then
    while IFS= read -r config_line || [[ -n "$config_line" ]]; do
        add_candidate "$(proton_dir_from_fonts "$config_line")"
    done < "$CONFIG_INFO"
fi

declare -a STEAM_ROOTS=()
add_steam_root() {
    local root="$1"
    local existing
    [[ -d "$root" ]] || return 0
    root="$(abs_dir "$root")"
    for existing in "${STEAM_ROOTS[@]+"${STEAM_ROOTS[@]}"}"; do
        [[ "$existing" == "$root" ]] && return 0
    done
    STEAM_ROOTS+=("$root")
}

add_steam_root "$STEAM_ROOT"
add_steam_root "${HOME}/.steam/debian-installation"
add_steam_root "${HOME}/.steam/steam"
add_steam_root "${HOME}/.steam/root"
add_steam_root "${HOME}/.local/share/Steam"

for steam_root in "${STEAM_ROOTS[@]}"; do
    for parent in "$steam_root/steamapps/common" "$steam_root/compatibilitytools.d"; do
        [[ -d "$parent" ]] || continue
        for tool_dir in "$parent"/*; do
            [[ -d "$tool_dir" ]] || continue
            add_candidate "$tool_dir"
        done
    done
done

PROTON_DIR=""
for tool_dir in "${PROTON_CANDIDATES[@]+"${PROTON_CANDIDATES[@]}"}"; do
    if [[ "$(basename "$tool_dir")" == "$PROTON_DIR_NAME" && "$tool_dir" == "$STEAM_ROOT"/* ]]; then
        PROTON_DIR="$tool_dir"
        break
    fi
done
if [[ -z "$PROTON_DIR" ]]; then
    for tool_dir in "${PROTON_CANDIDATES[@]+"${PROTON_CANDIDATES[@]}"}"; do
        if [[ "$(basename "$tool_dir")" == "$PROTON_DIR_NAME" ]]; then
            PROTON_DIR="$tool_dir"
            break
        fi
    done
fi
if [[ -z "$PROTON_DIR" && ${#PROTON_CANDIDATES[@]} -gt 0 ]]; then
    PROTON_DIR="${PROTON_CANDIDATES[0]}"
fi

if [[ -z "$PROTON_DIR" ]]; then
    echo "error: Proton ${PROTON_VERSION} not found." >&2
    echo "Install \"${PROTON_DIR_NAME}\" in Steam. Expected:" >&2
    echo "  ${STEAM_ROOT}/steamapps/common/${PROTON_DIR_NAME}/proton" >&2
    exit 1
fi

PROTON="${PROTON_DIR}/proton"
IFS= read -r PROTON_VERSION_LINE < "$PROTON_DIR/version"

run_proton() {
    if [[ -x "$PROTON" ]]; then
        "$PROTON" run "$@"
    else
        python3 "$PROTON" run "$@"
    fi
}

launch() {
    local exe="$1"
    local background="${2:-0}"
    local status=0
    echo "start:  $exe"
    pushd "$(dirname "$exe")" >/dev/null || return 1
    if [[ "$background" == "1" ]]; then
        if [[ "${WINE_VERBOSE:-0}" = "1" ]]; then
            run_proton "$exe" &
        else
            run_proton "$exe" >/dev/null 2>&1 &
        fi
        local pid=$!
        disown "$pid" 2>/dev/null || true
        echo "pid:    $pid"
    elif [[ "${WINE_VERBOSE:-0}" = "1" ]]; then
        run_proton "$exe"
        status=$?
    else
        run_proton "$exe" >/dev/null 2>&1
        status=$?
    fi
    popd >/dev/null || true
    return "$status"
}

echo "prefix: $WINEPREFIX"
echo "proton: $PROTON_VERSION_LINE"
echo "tool:   $PROTON"
launch "$FIRST_EXE" 1

echo "wait:   ${FIRST_EXE_DELAY}s"
sleep "$FIRST_EXE_DELAY"

launch "$GAME_EXE" 0
