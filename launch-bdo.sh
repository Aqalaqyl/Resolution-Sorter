#!/bin/bash
set -uo pipefail

# Run both Windows executables inside the same Steam/Proton prefix.
COMPAT="${HOME}/.steam/debian-installation/steamapps/compatdata/3549432507"
WINEPREFIX_PATH="${COMPAT}/pfx"
FIRST_EXE="/home/aqalaqyl/BDO/540q4bn.exe"
GAME_EXE="/home/aqalaqyl/BDO/bin64/BlackDesert64.exe"
FIRST_EXE_DELAY="${FIRST_EXE_DELAY:-15}"

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

export WINEPREFIX="$WINEPREFIX_PATH"
export STEAM_COMPAT_DATA_PATH="$COMPAT"
export STEAM_COMPAT_CLIENT_INSTALL_PATH="${HOME}/.steam/debian-installation"
export WINEFSYNC=1
export WINEESYNC=1
if [[ -z "${WINEDEBUG:-}" ]]; then
    export WINEDEBUG=-all
fi

WINE=""
VERSION_FILE="${COMPAT}/config_info"
if [[ -f "$VERSION_FILE" ]]; then
    while IFS= read -r line; do
        [[ "$line" == */files/share/fonts/ || "$line" == */files/share/fonts ]] || continue
        root="${line%/share/fonts/}"
        root="${root%/share/fonts}"
        for bin in "$root/bin/wine64" "$root/bin/wine"; do
            if [[ -f "$bin" ]]; then
                WINE="$bin"
                break
            fi
        done
        [[ -n "$WINE" ]] && break
    done < "$VERSION_FILE"
fi

if [[ -z "$WINE" ]]; then
    for candidate in \
        "${HOME}/.local/share/Steam/compatibilitytools.d/cachyos-10.0-20260425-slr/files/bin/wine64" \
        "${HOME}/.local/share/Steam/compatibilitytools.d/cachyos-10.0-20260425-slr/files/bin/wine" \
        "${HOME}/.local/share/Steam/compatibilitytools.d/proton-cachyos-10.0-20251126-slr-x86_64_v4/files/bin/wine64" \
        "${HOME}/.local/share/Steam/compatibilitytools.d/proton-cachyos-10.0-20251126-slr-x86_64_v4/files/bin/wine" \
        "${HOME}/.local/share/Steam/compatibilitytools.d/Proton-CachyOS Latest/files/bin/wine" \
        "${HOME}/.local/share/Steam/compatibilitytools.d/Proton-CachyOS Latest/files/bin/wine64" \
        "${HOME}/.local/share/Steam/compatibilitytools.d/Proton-CachyOS/files/bin/wine" \
        "${HOME}/.local/share/Steam/compatibilitytools.d/Proton-CachyOS/files/bin/wine64" \
        "/usr/share/steam/compatibilitytools.d/proton-cachyos/files/bin/wine" \
        "/usr/share/steam/compatibilitytools.d/proton-cachyos/files/bin/wine64"; do
        if [[ -f "$candidate" ]]; then
            WINE="$candidate"
            break
        fi
    done
fi

if [[ -z "$WINE" ]]; then
    for d in "${HOME}/.local/share/Steam/compatibilitytools.d"/GE-Proton*/files/bin/wine64; do
        [[ -f "$d" ]] && WINE="$d"
    done
fi

if [[ -z "$WINE" ]]; then
    for d in "${HOME}/.local/share/Steam/steamapps/common"/Proton*/files/bin/wine64; do
        [[ -f "$d" ]] && WINE="$d"
    done
fi

if [[ -z "$WINE" ]]; then
    for d in "${HOME}/.local/share/Steam/steamapps/common"/Proton*/files/bin/wine; do
        [[ -f "$d" ]] && WINE="$d"
    done
fi

if [[ -z "$WINE" ]]; then
    WINE="wine"
fi

# Proton's wine binary needs its own libraries on the loader path.
if [[ "$WINE" == */files/bin/wine || "$WINE" == */files/bin/wine64 ]]; then
    proton_files="$(dirname "$(dirname "$WINE")")"
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
    proton_bin="$(dirname "$WINE")"
    export PATH="${proton_bin}:${PATH}"
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

echo "prefix: $WINEPREFIX"
echo "wine:   $WINE"
launch "$FIRST_EXE" 1

echo "wait:   ${FIRST_EXE_DELAY}s"
sleep "$FIRST_EXE_DELAY"

launch "$GAME_EXE" 0
