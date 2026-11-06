#!/usr/bin/env python3
"""Record a real gameplay log from a Minecraft 1.16.5 server over RCON (stdlib only).

Writes events.jsonl in the rmalde/minecraft-agent style that splitcheck.logeval reads:
  {"time": ISO-8601, "type": "start" | "position_sample" | "nether_entered" | "nether_exited" | "end_entered" | "death_suspected" | "stop", ...}
Each position_sample carries: player, position [x,y,z], dimension, inventory {item: count}, health.

Usage (server.properties: enable-rcon=true, rcon.port=25575, rcon.password=<pw>):
  python3 capture/rcon_poller.py --player <name> --password <pw> --out runs/human-01/events.jsonl [--hz 2]
Stop with Ctrl-C. Needs the player to be online. Read-only: it only runs `data get` commands.
"""
import argparse, json, re, socket, struct, sys, time, datetime, os

class Rcon:
    def __init__(self, host, port, password):
        self.s = socket.create_connection((host, port), timeout=5)
        self.rid = 0
        if self._send(3, password)[0] == -1:
            sys.exit("RCON auth failed: check rcon.password")

    def _send(self, kind, body):
        self.rid += 1
        data = body.encode() + b"\x00\x00"
        self.s.sendall(struct.pack("<iii", len(data) + 8, self.rid, kind) + data)
        size = struct.unpack("<i", self._read(4))[0]
        pkt = self._read(size)
        rid, _ = struct.unpack("<ii", pkt[:8])
        return rid, pkt[8:-2].decode(errors="replace")

    def _read(self, n):
        buf = b""
        while len(buf) < n:
            chunk = self.s.recv(n - len(buf))
            if not chunk:
                raise ConnectionError("RCON closed")
            buf += chunk
        return buf

    def cmd(self, c):
        return self._send(2, c)[1]

NUM = r"-?\d+(?:\.\d+)?"

def parse_pos(txt):
    m = re.findall(NUM + r"d", txt)
    return [round(float(v[:-1]), 3) for v in m[:3]] if len(m) >= 3 else None

def parse_dim(txt):
    m = re.search(r'"(minecraft:[a-z_]+)"', txt)
    return m.group(1).split(":")[1] if m else None

def parse_inventory(txt):
    inv = {}
    for item, count in re.findall(r'id: "minecraft:([a-z0-9_]+)"[^}]*?Count: (\d+)b', txt):
        inv[item] = inv.get(item, 0) + int(count)
    # 1.16 prints Count before id in some entries; catch that order too
    if not inv:
        for count, item in re.findall(r'Count: (\d+)b[^}]*?id: "minecraft:([a-z0-9_]+)"', txt):
            inv[item] = inv.get(item, 0) + int(count)
    return inv

def parse_health(txt):
    m = re.search(r"(" + NUM + r")f", txt)
    return float(m.group(1)) if m else None

def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--player", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=25575)
    ap.add_argument("--out", required=True)
    ap.add_argument("--hz", type=float, default=2.0)
    a = ap.parse_args()
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    r = Rcon(a.host, a.port, a.password)
    seed = r.cmd("seed")
    out = open(a.out, "a", buffering=1)
    def log(kind, **data):
        out.write(json.dumps({"time": now(), "type": kind, **data}) + "\n")
    log("start", player=a.player, seed=seed.strip(), source="rcon_poller", hz=a.hz)
    last_dim, last_health = None, None
    print(f"logging {a.player} -> {a.out} (Ctrl-C to stop)")
    try:
        while True:
            t0 = time.time()
            pos_t = r.cmd(f"data get entity {a.player} Pos")
            if "No entity was found" in pos_t:
                time.sleep(1); continue
            dim = parse_dim(r.cmd(f"data get entity {a.player} Dimension"))
            inv = parse_inventory(r.cmd(f"data get entity {a.player} Inventory"))
            hp = parse_health(r.cmd(f"data get entity {a.player} Health"))
            log("position_sample", player=a.player, position=parse_pos(pos_t), dimension=dim, inventory=inv, health=hp)
            if last_dim and dim != last_dim:
                if dim == "the_nether": log("nether_entered", position=parse_pos(pos_t))
                elif last_dim == "the_nether" and dim == "overworld": log("nether_exited", position=parse_pos(pos_t))
                elif dim == "the_end": log("end_entered", position=parse_pos(pos_t))
            if last_health is not None and hp is not None and last_health > 0 and hp >= 20 and last_health < 6:
                log("death_suspected", note="health jumped from low to full (respawn)")
            last_dim, last_health = dim, hp
            time.sleep(max(0, 1 / a.hz - (time.time() - t0)))
    except KeyboardInterrupt:
        log("stop")
        print("stopped")

if __name__ == "__main__":
    main()
