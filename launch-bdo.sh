#!/bin/bash
set -uo pipefail

# Both programs use Proton 11.0 and one Wine prefix, so they share a wineserver.
STEAM_ROOT="/home/aqalaqyl/.steam/debian-installation"
PROTON_DIR="${STEAM_ROOT}/steamapps/common/Proton 11.0"
COMPAT="${STEAM_ROOT}/steamapps/compatdata/3549432507"
WINEPREFIX="${COMPAT}/pfx"
FIRST_EXE="/home/aqalaqyl/BDO/540q4bn.exe"
GAME_EXE="${WINEPREFIX}/drive_c/Pearlabyss/BlackDesert/BlackDesertLauncher.exe"
PROTON="${PROTON_DIR}/proton"

if [[ ! -d "$PROTON_DIR" || ! -f "$PROTON" ]]; then
    echo "error: Proton 11.0 not found: $PROTON" >&2
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

# Let Proton start wineserver. Calling files/bin/wineserver directly fails
# because Proton 11.0 expects its own library path and Steam Linux Runtime.
export WINEPREFIX
export STEAM_COMPAT_DATA_PATH="$COMPAT"
export STEAM_COMPAT_CLIENT_INSTALL_PATH="$STEAM_ROOT"
STEAM_COMPAT_APP_ID="$(basename "$COMPAT")"
export STEAM_COMPAT_APP_ID
export SteamAppId="$STEAM_COMPAT_APP_ID"
export SteamGameId="$STEAM_COMPAT_APP_ID"
unset WINESERVER WINELOADER LD_LIBRARY_PATH WINEDLLPATH || true

to_win_path() {
    local unix_path="$1"
    printf 'Z:%s\n' "${unix_path//\//\\}"
}

SLR=""
for candidate in \
    "${STEAM_ROOT}/steamapps/common/SteamLinuxRuntime_4" \
    "${HOME}/.local/share/Steam/steamapps/common/SteamLinuxRuntime_4" \
    "${HOME}/.steam/steam/steamapps/common/SteamLinuxRuntime_4"
do
    if [[ -x "$candidate/run" ]]; then
        SLR="$candidate"
        break
    fi
done

first_win="$(to_win_path "$FIRST_EXE")"
first_dir_win="$(to_win_path "$(dirname "$FIRST_EXE")")"
game_win="$(to_win_path "$GAME_EXE")"
# One Proton session starts both programs, so they share its wineserver.
launch_cmd="start \"\" /D \"${first_dir_win}\" \"${first_win}\" & \"${game_win}\""

proton_cmd=()
if [[ -x "$PROTON" ]]; then
    proton_cmd=("$PROTON")
else
    proton_cmd=(python3 "$PROTON")
fi

echo "proton: $PROTON_DIR"
if [[ -f "$PROTON_DIR/version" ]]; then
    IFS= read -r proton_version < "$PROTON_DIR/version"
    echo "version: $proton_version"
fi
echo "prefix: $WINEPREFIX"
if [[ -n "$SLR" ]]; then
    echo "runtime: $SLR"
fi
echo "start:  $FIRST_EXE"
echo "start:  $GAME_EXE"

pushd "$(dirname "$GAME_EXE")" >/dev/null || exit 1
if [[ -n "$SLR" ]]; then
    "$SLR/run" -- "${proton_cmd[@]}" runinprefix cmd.exe /c "$launch_cmd"
else
    "${proton_cmd[@]}" runinprefix cmd.exe /c "$launch_cmd"
fi
status=$?
popd >/dev/null || true
exit "$status"
