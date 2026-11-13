# PXD2 Game Test

PXD2's own playtest and beta system. Invited people play PXD2 games; the code stays on PXD2's machines.

Public page: **pxd2gametest.pxd** (pxd2.github.io/playtest/). It shows whether a test is open and links to the live gate.

## How the code stays secured

| Layer | What it does |
|---|---|
| **Stream mode (default)** | The game runs on base1 / base2 with Unreal Pixel Streaming (NVENC on the RTX GPU). Testers get video out and send input back. No executable, paks or source ever leave the machine. |
| **The gate** | Every request to the game stream needs a signed, 12-hour session cookie (HttpOnly, Secure, SameSite=Strict). If there is no session, the request is sent to the sign-in page. Ordinary requests are re-checked one by one; the live game socket takes up one of the play seats. |
| **Tester passes** | One-time invite codes (expire after 14 days by default) turn into a personal pass. Only a SHA-256 hash of the pass is stored. `revoke` stops the pass and closes a stream already in progress within 5 seconds. |
| **Download mode** | This mode is optional and set per build. The file is served from your machine, never from GitHub, only to a signed-in tester, and every download is logged against that tester. Ship download builds only as Shipping with pak encryption and signing (below). |
| **Private data** | Testers, sessions, feedback, screenshots and crash reports go in `keys/playtest/`, which is gitignored and never pushed. |

## Run a test on base1 (one click each)

1. Start the game for streaming:
   - Signalling server (Wilbur, ships with the Pixel Streaming plugin under `Engine/Plugins/Media/PixelStreaming*/Resources/WebServers/`): player port **80**, streamer port **8888**. Run it without the HTTPS redirect. The gate connects to it on the same machine.
   - Packaged game: `Game.exe -PixelStreamingURL=ws://127.0.0.1:8888 -RenderOffScreen -ResX=1920 -ResY=1080`
2. **Run PXD2 Game Test.bat**: starts the gate and a Cloudflare tunnel, and publishes the address so pxd2gametest.pxd shows "A test session is open". Publishing needs `keys/pxd-host.token`, the same fine-grained token the Pi uses.
3. **Invite a Tester.bat**: type a name and send them the code.
4. **Game Test Reports.bat**: testers, feedback and crashes, and opens the reports folder.

Builds shown to testers:
```
python pxdplaytest.py build add gt-alpha --title "Global Theaters alpha" --notes "Training center map"
python pxdplaytest.py build add rr-dl --title "Rouge Racer test" --mode download --file D:\Builds\RougeRacer_Test.zip
python pxdplaytest.py build hide gt-alpha      # take it off the list without deleting it
```
Seats: `--max-players 1` means one person plays at a time per running game. Run a second game and signalling server on base2 (own gate, own port) for a second seat.

## Network: one thing to set before outside testers

The tunnel carries the web page and signalling. The video itself is WebRTC, which needs a direct UDP path or a **TURN relay**. If base1's internet sits behind carrier NAT (Starlink, cellular, many home plans), outside players will sign in but the stream will not connect until you add a TURN server to Wilbur's `peer_options` (`iceServers` with your TURN URL and credentials). That can be coturn on any box with a public IP or a hosted TURN service. Test from a phone on cellular to confirm.

## Unreal settings for builds that leave the machine (download mode)

Project Settings, then:
- **Packaging**: Build Configuration **Shipping**; Use Pak File and Io Store on; **Include Debug Files off** (no PDBs); Include Prerequisites as needed.
- **Crypto**: *Generate new encryption key*, *Generate new signing key*; turn on **Encrypt Pak INI Files**, **Encrypt Pak Index**, **Encrypt UAsset Files**, **Encrypt All Assets**, and **Enable Pak Signing**.
- Keep `Config/DefaultCrypto.ini` (it holds the keys) out of any public repo.

This protects the content from casual extraction; a shipped binary can always be attacked by someone determined, which is why stream mode is the default.

## Feedback from inside the game (optional)

The game's crash reporter or a debug menu can POST a zip to `/gate/api/crash` on the same origin. In stream mode the tester's session cookie is already there. Reports land in `keys/playtest/reports/<date>/`.
