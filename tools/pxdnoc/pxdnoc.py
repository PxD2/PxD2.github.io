"""PXD NOC + PXD Link: PXD2's own network, the way BlackBerry ran one.

Every registered device's traffic for the sites you choose (Google by default) goes out through PXD2's own
machine, the NOC (a Pi 5 or base1), so those sites see PXD2's address, never the person's. The NOC only lets in
devices it knows (each has its own signing key, like a BlackBerry PIN), only carries web traffic (ports 80/443),
and never sees inside HTTPS: it moves encrypted bytes, it does not read them.

  NOC (the Pi, behind its Cloudflare tunnel; no open router ports):
    python3 pxdnoc.py noc --port 8090                 # then: cloudflared tunnel --url http://127.0.0.1:8090
    python3 pxdnoc.py allow <device card>             # register a device
  Device (Windows / Linux / Mac, next to the PXD Browser):
    python3 pxdnoc.py enroll                          # makes this device's key; prints its card to register
    python3 pxdnoc.py link --noc wss://<tunnel>/relay # local SOCKS5 on 127.0.0.1:1080 -> the NOC
  PXD Browser then uses {"exit": "socks5://127.0.0.1:1080"} in ~/.pxd/shield.json.

Wire: one secure WebSocket per connection. The NOC sends a 32-byte challenge; the device answers with its card and
an Ed25519 signature over (challenge + destination); the NOC checks the card is registered, the port is 80/443 and
the destination is not a private address, then pipes bytes both ways.
"""
import argparse, asyncio, base64, ipaddress, json, os, socket, struct, sys, time

import websockets
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature

HOME = os.path.join(os.path.expanduser("~"), ".pxd")
DEVICE_KEY = os.path.join(HOME, "pxdlink.key")
NOC_DIR = os.environ.get("PXD_NOC_DIR", "/etc/pxd-noc" if os.name != "nt" else os.path.join(HOME, "noc"))
ALLOWED = os.path.join(NOC_DIR, "allowed.json")
PORTS = {80, 443}
RAW = serialization.Encoding.Raw


def b64(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def ub64(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def log(m):
    print(time.strftime("%H:%M:%S ") + m, flush=True)


# ------------------------------------------------------------------ NOC
SITE_ALLOWED = os.environ.get("PXD_NOC_SITE_ALLOWED", "/opt/pxd-host/site/noc/allowed.json")


def load_allowed():
    """Devices registered on this NOC, plus those PXD2 published in the site repo (noc/allowed.json, public keys only)."""
    out = {}
    for f in (SITE_ALLOWED, ALLOWED):
        try:
            out.update(json.load(open(f)).get("devices", {}))
        except (OSError, ValueError):
            pass
    return out


def public_dest(host, port):
    """Refuse anything that is not a public web address (no reaching into the NOC's own network)."""
    test = os.environ.get("PXD_NOC_TEST_ALLOW_PRIVATE") == "1"      # test harness only (local web server, any port)
    if port not in PORTS and not (test and port == int(os.environ.get("PXD_NOC_TEST_PORT", "0"))):
        return False, f"port {port} is not carried (web only: 80, 443)"
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return False, "name does not resolve"
    if test:
        return True, ""
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            return False, "private address refused"
    return True, ""


async def noc_conn(ws):
    peer = "?"
    try:
        challenge = os.urandom(32)
        await ws.send(json.dumps({"pxd": "noc/1", "challenge": b64(challenge)}))
        hello = json.loads(await asyncio.wait_for(ws.recv(), 15))
        card, host, port, sig = hello["card"], hello["host"], int(hello["port"]), ub64(hello["sig"])
        devices = load_allowed()
        if card not in devices:
            await ws.close(4003, "device not registered"); log(f"refused unregistered device {card[:12]}"); return
        try:
            Ed25519PublicKey.from_public_bytes(ub64(card)).verify(sig, challenge + f"{host}:{port}".encode())
        except (InvalidSignature, ValueError):
            await ws.close(4003, "bad signature"); log(f"refused bad signature from {card[:12]}"); return
        ok, why = await asyncio.get_running_loop().run_in_executor(None, public_dest, host, port)
        if not ok:
            await ws.close(4004, why); return
        peer = devices[card].get("name", card[:12])
        reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), 15)
        await ws.send(json.dumps({"ok": True}))

        async def up():
            async for msg in ws:
                writer.write(msg if isinstance(msg, bytes) else msg.encode()); await writer.drain()
            writer.close()

        async def down():
            while True:
                data = await reader.read(65536)
                if not data:
                    break
                await ws.send(data)
            await ws.close()
        await asyncio.gather(up(), down(), return_exceptions=True)
    except Exception as e:  # noqa: BLE001
        if not isinstance(e, (websockets.ConnectionClosed, asyncio.CancelledError)):
            log(f"{peer}: {type(e).__name__}: {e}")


async def run_noc(port):
    os.makedirs(NOC_DIR, exist_ok=True)
    log(f"PXD NOC on 127.0.0.1:{port}/relay · {len(load_allowed())} registered device(s) · web only (80/443)")
    async with websockets.serve(noc_conn, "127.0.0.1", port, max_size=2**22, compression=None,
                                process_request=lambda c, r: None if r.path == "/relay" else c.respond(404, "PXD NOC\n")):
        await asyncio.Future()


def allow(card, name, path=None):
    path = path or ALLOWED
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        d = json.load(open(path))
    except (OSError, ValueError):
        d = {"devices": {}}
    Ed25519PublicKey.from_public_bytes(ub64(card))           # must be a real key
    d["devices"][card] = {"name": name or card[:12], "added": time.strftime("%Y-%m-%d")}
    json.dump(d, open(path, "w"), indent=2)
    print(f"registered {name or card[:12]} · {len(d['devices'])} device(s)")


# ------------------------------------------------------------------ device
def device_key():
    if not os.path.exists(DEVICE_KEY):
        os.makedirs(HOME, exist_ok=True)
        k = Ed25519PrivateKey.generate()
        open(DEVICE_KEY, "wb").write(k.private_bytes(RAW, serialization.PrivateFormat.Raw, serialization.NoEncryption()))
        try:
            os.chmod(DEVICE_KEY, 0o600)
        except OSError:
            pass
    k = Ed25519PrivateKey.from_private_bytes(open(DEVICE_KEY, "rb").read())
    return k, b64(k.public_key().public_bytes(RAW, serialization.PublicFormat.Raw))


async def socks_client(reader, writer, noc, key, card):
    """Minimal SOCKS5 (no auth, CONNECT only) on localhost, each connection carried to the NOC."""
    try:
        ver, n = struct.unpack("!BB", await reader.readexactly(2)); await reader.readexactly(n)
        writer.write(b"\x05\x00"); await writer.drain()
        ver, cmd, _, atyp = struct.unpack("!BBBB", await reader.readexactly(4))
        if atyp == 1:
            host = socket.inet_ntoa(await reader.readexactly(4))
        elif atyp == 3:
            host = (await reader.readexactly((await reader.readexactly(1))[0])).decode()
        elif atyp == 4:
            host = socket.inet_ntop(socket.AF_INET6, await reader.readexactly(16))
        else:
            raise ValueError("address type")
        port = struct.unpack("!H", await reader.readexactly(2))[0]
        if cmd != 1:
            writer.write(b"\x05\x07\x00\x01" + b"\x00" * 6); return
        async with websockets.connect(noc, max_size=2**22, compression=None, open_timeout=15) as ws:
            ch = ub64(json.loads(await ws.recv())["challenge"])
            await ws.send(json.dumps({"card": card, "host": host, "port": port, "sig": b64(key.sign(ch + f"{host}:{port}".encode()))}))
            ok = json.loads(await ws.recv())
            if not ok.get("ok"):
                raise ConnectionError("NOC refused")
            writer.write(b"\x05\x00\x00\x01" + b"\x00" * 6); await writer.drain()

            async def up():
                while True:
                    data = await reader.read(65536)
                    if not data:
                        break
                    await ws.send(data)
                await ws.close()

            async def down():
                async for msg in ws:
                    writer.write(msg); await writer.drain()
            await asyncio.gather(up(), down(), return_exceptions=True)
    except Exception as e:  # noqa: BLE001
        try:
            writer.write(b"\x05\x01\x00\x01" + b"\x00" * 6); await writer.drain()
        except Exception:  # noqa: BLE001
            pass
        if not isinstance(e, (asyncio.IncompleteReadError, websockets.ConnectionClosed)):
            log(f"link: {type(e).__name__}: {e}")
    finally:
        writer.close()


def noc_from_hosts():
    """The NOC's current address, from the PXD registry's hosts.json (the Pi publishes it)."""
    import urllib.request
    try:
        with urllib.request.urlopen("https://pxd2.github.io/hosts.json", timeout=10) as r:
            for h in json.loads(r.read()).get("hosts", {}).values():
                if h.get("noc"):
                    return h["noc"]
    except Exception:  # noqa: BLE001
        pass
    return None


async def run_link(noc, port):
    key, card = device_key()
    noc = noc or noc_from_hosts()
    if not noc:
        sys.exit("no NOC address: pass --noc wss://.../relay (or let the Pi publish it to hosts.json)")
    srv = await asyncio.start_server(lambda r, w: socks_client(r, w, noc, key, card), "127.0.0.1", port)
    log(f"PXD Link: SOCKS5 127.0.0.1:{port} -> {noc} as device {card[:12]}")
    async with srv:
        await srv.serve_forever()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    n = sp.add_parser("noc"); n.add_argument("--port", type=int, default=8090)
    a = sp.add_parser("allow"); a.add_argument("card"); a.add_argument("--name", default="")
    a.add_argument("--file", help="registry file to add to (default: this NOC's own list); noc/allowed.json in the site repo publishes it to every NOC")
    sp.add_parser("enroll")
    l = sp.add_parser("link"); l.add_argument("--noc"); l.add_argument("--port", type=int, default=1080)
    x = ap.parse_args()
    if x.cmd == "noc":
        asyncio.run(run_noc(x.port))
    elif x.cmd == "allow":
        allow(x.card, x.name, x.file)
    elif x.cmd == "enroll":
        _, card = device_key()
        print(f"this device's card (register it on the NOC):\n{card}")
    else:
        asyncio.run(run_link(x.noc, x.port))


if __name__ == "__main__":
    main()
