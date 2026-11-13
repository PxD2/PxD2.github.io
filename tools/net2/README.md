# PXD Net2

The clean second web that `.pxd` grows into. Everyone downloads three things once: a **personal kit** (your own encrypt/decrypt keys), the **PXD dictionary**, and the **cards** of the people they deal with. After that, the wire carries only what the other side doesn't already have, sealed so only they can read it.

**Double-click `Make My Net2 Kit.bat`** to make your kit and card in Documents\PXD Net2. Your kit is locked with your passphrase and stays with you. Your card is the public half: give it to anyone.

## Layers, and what each saves
| Layer | Saves | Where |
|---|---|---|
| `.pxd` names | a lookup goes to PXD's signed registry, not a .com registrar | `tools/minter`, `tools/pxd2root`, `tools/pxdweb` |
| Lit | a file seen once anywhere nearby is never fetched from the origin again | `tools/lit` |
| COG books | a sentence travels as `meaning.variant` ids | `tools/pxdz` |
| Net2 dictionary | the common shape of PXD pages and data is never sent | `tools/net2/dicts` (numbered, hash-published, never changed) |
| Net2 live link | after one handshake, each message carries only what changed since the last | `net2.Session` |

## Security
- Each kit has two keys: an X25519 key to receive and an Ed25519 key to sign. It's locked with scrypt and ChaCha20-Poly1305.
- **One-off messages (`seal`):** encrypted to one person and provably from the sender. Each message gets a fresh key, so a stolen kit can't open old traffic. A changed byte, the wrong sender or the wrong recipient are all refused.
- **Live links (`Session`):** both sides prove who they are in the handshake and get a separate key for each direction. Frames are numbered, and a replayed or reordered frame is refused.
- **Dictionaries:** each is checked against its published SHA-256. A swapped dictionary is refused.

## Measured (`python tools/net2/net2.py bench`, 2026-11-13; on 278 site files the dictionaries were not built from)
| | raw | gzip | Net2, sealed |
|---|---:|---:|---:|
| live link, 200 order updates | 22,061 B | 19,159 B | **5,721 B** (26% of raw, 30% of gzip) |
| client site page (6.9 KB) | 6,971 | 2,573 | **1,680** (65% of gzip) |
| engineering case JSON | 1,378 | 738 | **433** (59% of gzip) |
| a repeated live message | | | **21 B** per frame |
| one short chat line, one-off | 61 | 67 | 107 (header + tag cost 60 B: send chatter over a live link) |
| all of it | 233,811 | 95,559 | **70,850** (30% of raw, 74% of gzip) |

What's already shared never travels. What's genuinely new costs what it costs: a new photo or model is already compressed. Lit's job is to send that once per neighborhood.

## Commands
```
python tools/net2/net2.py kit --out me.n2kit --name Chad
python tools/net2/net2.py seal me.n2kit --to angie.n2card file -o file.n2
python tools/net2/net2.py open me.n2kit --from chad.n2card file.n2 -o file
python tools/net2/net2.py dict-build        # adds new numbered dictionaries; old ones stay so old messages still open
python tools/net2/net2.py bench
```
