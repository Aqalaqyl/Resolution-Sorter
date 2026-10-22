#!/bin/bash
set -uo pipefail

# Both programs use Proton 11.0 and one Wine prefix, so they share a wineserver.
STEAM_ROOT="/home/aqalaqyl/.steam/debian-installation"
PROTON_DIR="${STEAM_ROOT}/steamapps/common/Proton 11.0"
COMPAT="${STEAM_ROOT}/steamapps/compatdata/3549432507"
WINEPREFIX="${COMPAT}/pfx"
FIRST_EXE="/home/aqalaqyl/BDO/540q4bn.exe"
GAME_EXE="${WINEPREFIX}/drive_c/Pearlabyss/BlackDesert/BlackDesertLauncher.exe"

WINE="${PROTON_DIR}/files/bin/wine"
WINESERVER="${PROTON_DIR}/files/bin/wineserver"

if [[ ! -d "$PROTON_DIR" ]]; then
    echo "error: Proton 11.0 not found: $PROTON_DIR" >&2
    exit 1
fi
if [[ ! -x "$WINE" || ! -x "$WINESERVER" ]]; then
    echo "error: Proton 11.0 wine not found in $PROTON_DIR/files/bin" >&2
    exit 1
fi
if [[ ! -d "$WINEPREFIX" ]]; then
    echo "error: Proton prefix not found: $WINEPREFIX" >&2
    exit 1
fi
for exe in "$FIRST_EXE" "$GAME_EXE"; do
    if [[ ! -f "$exe" ]]; then
        echo "error: executable not found: $exe" >&2
        exit 1
    fi
done

export WINEPREFIX
export WINELOADER="$WINE"
export WINESERVER
export STEAM_COMPAT_DATA_PATH="$COMPAT"
export STEAM_COMPAT_CLIENT_INSTALL_PATH="$STEAM_ROOT"
STEAM_COMPAT_APP_ID="$(basename "$COMPAT")"
export STEAM_COMPAT_APP_ID
export SteamAppId="$STEAM_COMPAT_APP_ID"
export SteamGameId="$STEAM_COMPAT_APP_ID"
export WINEFSYNC=1
export WINEESYNC=1
if [[ -z "${WINEDEBUG:-}" ]]; then
    export WINEDEBUG=-all
fi

# Proton's wine has to see its own libraries, and both programs must use them.
proton_files="${PROTON_DIR}/files"
export PATH="${proton_files}/bin:${PATH}"
lib_path=""
dll_path=""
for libdir in "$proton_files/lib64" "$proton_files/lib"; do
    if [[ -d "$libdir" ]]; then
        lib_path="${lib_path:+$lib_path:}$libdir"
    fi
    if [[ -d "$libdir/wine" ]]; then
        dll_path="${dll_path:+$dll_path:}$libdir/wine"
    fi
done
if [[ -n "$lib_path" ]]; then
    export LD_LIBRARY_PATH="${lib_path}${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
fi
if [[ -n "$dll_path" ]]; then
    export WINEDLLPATH="${dll_path}${WINEDLLPATH:+:$WINEDLLPATH}"
fi

# One persistent wineserver for this prefix. The second program joins it.
if ! "$WINESERVER" -p; then
    echo "error: could not start the Proton 11.0 wineserver for $WINEPREFIX" >&2
    exit 1
fi

launch() {
    local exe="$1"
    local background="${2:-0}"
    local status=0
    echo "start:  $exe"
    pushd "$(dirname "$exe")" >/dev/null || return 1
    if [[ "$background" == "1" ]]; then
        if [[ "${WINE_VERBOSE:-0}" = "1" ]]; then
            "$WINE" "$exe" &
        else
            "$WINE" "$exe" >/dev/null 2>&1 &
        fi
        local pid=$!
        disown "$pid" 2>/dev/null || true
        echo "pid:    $pid"
    elif [[ "${WINE_VERBOSE:-0}" = "1" ]]; then
        "$WINE" "$exe"
        status=$?
    else
        "$WINE" "$exe" >/dev/null 2>&1
        status=$?
    fi
    popd >/dev/null || true
    return "$status"
}

echo "proton: $PROTON_DIR"
if [[ -f "$PROTON_DIR/version" ]]; then
    IFS= read -r proton_version < "$PROTON_DIR/version"
    echo "version: $proton_version"
fi
echo "prefix: $WINEPREFIX"
echo "server: $WINESERVER"
launch "$FIRST_EXE" 1
launch "$GAME_EXE" 0
