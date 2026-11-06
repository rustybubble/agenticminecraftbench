#!/usr/bin/env bash
# Start the herobrine 1.16.5 live server (set seed 8398967436125155523) with RCON on.
# - offline mode so the Mineflayer bot can join without a Microsoft account
# - allow-flight so pathfinder/elytra-ish motion is not kicked as flying
# - RCON lets the telemetry logger read server-authoritative position/inventory
# - console.in FIFO so scripts can run commands (op, tp, gamerule) without RCON
set -euo pipefail
cd "$(dirname "$0")"

JAVA="${MC_JAVA_HOME:-/Users/ravil/Library/Application Support/PrismLauncher/java/java-runtime-gamma/jre.bundle/Contents/Home/bin/java}"
if [ ! -x "$JAVA" ]; then
  JAVA="$(command -v java)"
fi

[ -f server.jar ] || { echo "missing server.jar (Minecraft 1.16.5). Download it from Mojang." >&2; exit 1; }
[ -f eula.txt ] || echo 'eula=true' > eula.txt

[ -p console.in ] || mkfifo console.in
# hold the FIFO open for writing so the server never sees EOF on stdin
exec 3<> console.in

exec "$JAVA" -Xms1G -Xmx3G -XX:+UseG1GC -jar server.jar nogui < console.in
