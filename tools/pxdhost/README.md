# PXD Host: .pxd sites and 3D assets from your own hardware

A Raspberry Pi 5 (or base2, or any Linux box) serves .pxd sites and their 3D models. All it needs is a connection and power.

- **Install:** copy `PXD-Host-Pi.pxd2` (from pxd2.github.io/vr/pxdweb/) to the Pi and run `sh PXD-Host-Pi.pxd2 pi1`, or open it from the file manager. It installs Python, Cloudflare's tunnel client and a copy of the site, and sets the host up as a service that starts at boot. It also adds **PXD Host STATUS / UPDATE / RESTART** icons to the Pi's desktop.
- **Reaching the internet:** the Pi dials out through a Cloudflare tunnel, so no router ports are opened. It works on Verizon home internet, hotspots and Starlink.
- **Being found:** with a GitHub token (fine-grained; Contents: read and write; the site repo only), the Pi writes its current address into `hosts.json`. Every PXD Browser and PXD Web then loads any name marked `"host": "pi1"` from the Pi, while the address bar stays on `name.pxd`.
- **Putting a site on the Pi:** add the site folder to the Pi's copy, then mint the name with the host set:
  `python tools/minter/pxdmint.py mint shopname --to /stores/shopname/ --title "Shop Name" --host pi1`
- **Updates:** the site copy changes only when you press UPDATE. Nothing pulls on its own.
- **Streaming:** the host serves files with HTTP Range, so 3D models and PXDZ bundles stream instead of downloading whole.
- **Limits:** today's tunnel is Cloudflare's free quick tunnel, so the address changes when the Pi restarts, and the host republishes it to `hosts.json` each time. A Cloudflare account with a named tunnel gives a fixed address.
