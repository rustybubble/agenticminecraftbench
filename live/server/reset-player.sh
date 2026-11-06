#!/usr/bin/env bash
# Clear a player to a clean survival start on the live server (console FIFO).
# usage: ./reset-player.sh [name] [x y z]
set -euo pipefail
cd "$(dirname "$0")"
NAME="${1:-SplitAgent}"
X="${2:--181}"; Y="${3:-70}"; Z="${4:-214}"
{
  echo "gamemode survival $NAME"
  echo "clear $NAME"
  echo "effect clear $NAME"
  echo "experience set $NAME 0"
  echo "tp $NAME $X $Y $Z"
} > console.in
echo "reset $NAME -> $X $Y $Z"
