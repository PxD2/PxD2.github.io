# PXD NOC + PXD Link: PXD2's own network

This works the way BlackBerry did. Registered devices send their Google traffic out through PXD2's own machine, the NOC, so Google sees PXD2's address and never the person's.

| Part | Runs on | Does |
|---|---|---|
| **PXD NOC** | the Pi (PXD Host starts it) | takes encrypted links from registered devices and carries their web traffic out |
| **PXD Link** | each person's computer (the PXD Browser starts it) | the device's encrypted line to the NOC, offered locally as SOCKS5 on 127.0.0.1:1080 |
| **Google · Shield** | the PXD Browser | the real google.com, memory-only, trackers blocked, sent through PXD Link |

- **Registered devices only.** Each device has its own signing key, like a BlackBerry PIN. The NOC checks a fresh signed challenge on every connection.
- **Web traffic only.** Ports 80 and 443; private and local addresses are refused, so nobody can use the NOC for spam or to reach your home network.
- **The NOC never reads HTTPS.** It moves encrypted bytes; Google's TLS runs end to end between the browser and Google.
- **No open router ports.** The NOC sits behind its own Cloudflare tunnel, and the Pi publishes the NOC's current address in `hosts.json`, which PXD Link reads.

## Setting up a device
1. `python tools/pxdnoc/pxdnoc.py enroll` prints the device's card.
2. Register it: on the Pi run `python3 /opt/pxd-host/site/tools/pxdnoc/pxdnoc.py allow <card> --name "Chad laptop"`, or add it to `noc/allowed.json` in the site repo so every PXD NOC accepts it.
3. Put `{"link": true}` in `%USERPROFILE%\.pxd\shield.json`. The PXD Browser starts PXD Link and routes Google · Shield through the NOC from then on.

Tested 2026-11-13: a registered device's traffic got through the NOC, including a 10 MB file intact. An unregistered device was refused, and so was a non-web port.
