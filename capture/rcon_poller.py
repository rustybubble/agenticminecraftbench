#!/usr/bin/env python3
"""Record a real gameplay log from a Minecraft 1.16.5 server over RCON (stdlib only).

Writes events.jsonl in the rmalde/minecraft-agent style that splitcheck reads:
  {"time": ISO-8601, "type": "start" | "position_sample" | "nether_entered" | "nether_exited" |
   "end_entered" | "death_suspected" | "stop", ...}
Each position_sample carries:
  player, position [x,y,z], dimension, inventory {item: count}, health, food (0-20),
  selected_item (item id held in the main hand, or null), feet_block and head_block
  ("water" | "lava" | "other", tested at floor(pos) and floor(pos)+1 in the player's dimension),
  eye_block (same kinds, at floor(y + 1.62) = standing eye height; the evaluator uses it for the
  1.16.5 underwater dig penalty, which applies only when the eyes are submerged),
  start also carries difficulty (from the RCON `difficulty` query, e.g. "peaceful"),
  poll_ms (wall time this sample took to collect).

Usage (server.properties: enable-rcon=true, rcon.port=25575, rcon.password=<pw>):
  python3 capture/rcon_poller.py --player <name> --password <pw> --out runs/human-01/events.jsonl [--hz 2]
Stop with Ctrl-C. Needs the player to be online.

Read-only: it runs only `data get entity ...`, `seed`, and `execute in <dim> if block ...` tests.
`execute if block` only tests a block and changes nothing in the world.

Cost per sample: 6 `data get` commands (+1 sentinel round trip for Inventory, whose reply can span
several RCON packets) and 2-12 `execute if block` tests (feet and head: water, then lava, then the
water plants kelp/kelp_plant/seagrass/tall_seagrass/bubble_column, stopping at the first hit; dry land
costs the most). That is 9-19 RCON round trips; on a local server each is ~0.5-2 ms, so a sample is
typically 10-40 ms and 2 Hz (500 ms budget) keeps a >10x margin. poll_ms is logged so the actual
rate can be checked; a warning is printed if a sample exceeds the 1/hz budget.
"""
import argparse, json, math, re, socket, struct, sys, time, datetime, os

SENTINEL_TYPE = 100   # unknown packet type: vanilla answers "Unknown request ..." with the same id


class Rcon:
    def __init__(self, host, port, password):
        self.s = socket.create_connection((host, port), timeout=5)
        self.rid = 0
        rid, _ = self._send(3, password)
        if rid == -1:
            sys.exit("RCON auth failed: check rcon.password")

    def _write(self, kind, body):
        self.rid += 1
        data = body.encode() + b"\x00\x00"
        self.s.sendall(struct.pack("<iii", len(data) + 8, self.rid, kind) + data)
        return self.rid

    def _packet(self):
        size = struct.unpack("<i", self._read(4))[0]
        pkt = self._read(size)
        rid, _ = struct.unpack("<ii", pkt[:8])
        return rid, pkt[8:-2].decode(errors="replace")

    def _send(self, kind, body):
        self._write(kind, body)
        return self._packet()

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

    def cmd_long(self, c):
        """For replies that may exceed one 4096-byte RCON packet: send the command, then a sentinel
        packet, and concatenate every reply packet until the sentinel's answer arrives."""
        want = self._write(2, c)
        stop = self._write(SENTINEL_TYPE, "")
        parts = []
        while True:
            rid, body = self._packet()
            if rid == stop:
                return "".join(parts)
            if rid == want:
                parts.append(body)


NUM = r"-?\d+(?:\.\d+)?(?:E-?\d+)?"


def parse_pos(txt):
    m = re.findall(r"(" + NUM + r")d", txt)
    return [round(float(v), 3) for v in m[:3]] if len(m) >= 3 else None


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


def parse_int_data(txt):
    """'<player> has the following entity data: 17' -> 17 (foodLevel is an int tag, no suffix)."""
    m = re.search(r"entity data: (-?\d+)\s*$", txt.strip())
    return int(m.group(1)) if m else None


def parse_selected(txt):
    m = re.search(r'id: "minecraft:([a-z0-9_]+)"', txt)
    return m.group(1) if m else None   # "Found no elements matching SelectedItem" -> empty hand


WATERY = ("water", "kelp", "kelp_plant", "seagrass", "tall_seagrass", "bubble_column")


def block_kind(r, dim, x, y, z):
    """'water' | 'lava' | 'other' for the block at (x, y, z) in dimension dim (read-only test)."""
    where = f"execute in minecraft:{dim or 'overworld'} if block {x} {y} {z} minecraft:"
    if "passed" in r.cmd(where + "water"):
        return "water"
    if "passed" in r.cmd(where + "lava"):
        return "lava"
    for b in WATERY[1:]:   # water plants are always water-filled in 1.16
        if "passed" in r.cmd(where + b):
            return "water"
    return "other"


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
    try:  # "The difficulty is Peaceful" -> "peaceful" (evaluator uses it for the food rule)
        diff = (r.cmd("difficulty").strip().rsplit(" ", 1)[-1] or "").lower() or None
    except Exception:
        diff = None
    out = open(a.out, "a", buffering=1)

    def log(kind, **data):
        out.write(json.dumps({"time": now(), "type": kind, **data}) + "\n")

    log("start", player=a.player, seed=seed.strip(), difficulty=diff, source="rcon_poller", hz=a.hz,
        fields=["position", "dimension", "inventory", "health", "food", "selected_item",
                "feet_block", "head_block", "eye_block", "poll_ms"])
    last_dim, last_health = None, None
    budget = 1 / a.hz
    print(f"logging {a.player} -> {a.out} (Ctrl-C to stop)")
    try:
        while True:
            t0 = time.time()
            pos_t = r.cmd(f"data get entity {a.player} Pos")
            if "No entity was found" in pos_t:
                time.sleep(1); continue
            pos = parse_pos(pos_t)
            dim = parse_dim(r.cmd(f"data get entity {a.player} Dimension"))
            inv = parse_inventory(r.cmd_long(f"data get entity {a.player} Inventory"))
            hp = parse_health(r.cmd(f"data get entity {a.player} Health"))
            food = parse_int_data(r.cmd(f"data get entity {a.player} foodLevel"))
            sel = parse_selected(r.cmd(f"data get entity {a.player} SelectedItem"))
            feet = head = eye = None
            if pos:
                bx, by, bz = (math.floor(v) for v in pos)
                feet = block_kind(r, dim, bx, by, bz)
                head = block_kind(r, dim, bx, by + 1, bz)
                ey = math.floor(pos[1] + 1.62)  # standing eye height (swimming: y + 0.4)
                eye = head if ey == by + 1 else block_kind(r, dim, bx, ey, bz)
            poll_ms = round((time.time() - t0) * 1000, 1)
            log("position_sample", player=a.player, position=pos, dimension=dim, inventory=inv,
                health=hp, food=food, selected_item=sel, feet_block=feet, head_block=head, eye_block=eye,
                poll_ms=poll_ms)
            if poll_ms > budget * 1000:
                print(f"warning: sample took {poll_ms} ms (> {budget * 1000:.0f} ms budget)", file=sys.stderr)
            if last_dim and dim != last_dim:
                if dim == "the_nether": log("nether_entered", position=pos)
                elif last_dim == "the_nether" and dim == "overworld": log("nether_exited", position=pos)
                elif dim == "the_end": log("end_entered", position=pos)
            if last_health is not None and hp is not None and last_health > 0 and hp >= 20 and last_health < 6:
                log("death_suspected", note="health jumped from low to full (respawn)")
            last_dim, last_health = dim, hp
            time.sleep(max(0, budget - (time.time() - t0)))
    except KeyboardInterrupt:
        log("stop")
        print("stopped")


if __name__ == "__main__":
    main()
