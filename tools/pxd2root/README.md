# PXD Root Server: the root of `.pxd`

`.pxd` (alias `.pxd2`) answers from the PXD registry on GitHub and every sub-hub registry, not from ICANN's root. Everything that isn't `.pxd` passes through to the ordinary internet, so a phone, a PC or a whole network can use a PXD root as its only DNS server and lose nothing.

| Who | How they reach it |
|---|---|
| A network (Hackspace, a shop, a restaurant's guest Wi-Fi) | router DHCP DNS → the PXD root's IP (UDP/TCP 53) |
| Android | Settings → Private DNS → the root's hostname (DNS-over-TLS, port 853, needs a certificate) |
| iPhone / iPad / Mac | open `https://<root>/pxd.mobileconfig`, install the profile (DNS-over-HTTPS) |
| Chrome, Edge, Firefox on any device | Secure DNS → custom → `https://<root>/dns-query` |
| PXD Browser | reads the registry directly; no DNS setting needed |
| Anyone else | `https://pxd2.github.io/<name>` |

## Names
- `name.pxd`: a main-hub name, or a sub-hub name the main hub doesn't use
- `name.hub.pxd`: a sub-hub name, always (`pizzaco.eats.pxd`)
- `anything.name.pxd`: subdomains follow their name
- TXT on every name carries the registry entry: `to=`, `group=`, `world=`, `hub=`, `store=`, `sig=`

## Trust: anyone can run a root, only the authority can change one
```
python tools/pxdz/pxdsign.py registry-sign names.json --authority keys/     # base1, after every change, then push
python tools/pxd2root/pxd2root.py --authority pxd/authority.json --require-signed
```
A root refuses:
- a registry that was edited after signing
- one signed by any other key
- one signed earlier than the registry it already has (a rollback)

It keeps serving the last good zone in every one of those cases. Sub-hub registries are signed the same way.

Order of work for a name change: edit `names.json` → `python tools/names_build.py` → `registry-sign` → push.

## Run
```
python pxd2root.py                                          # DNS :53 + web/DoH :80 (administrator or sudo)
python pxd2root.py --dns-port 5353 --web-port 8080          # test without admin
python pxd2root.py --tls-cert cert.pem --tls-key key.pem --public-url https://root.example   # adds DoT :853, HTTPS :443, iPhone profile
python pxd2root.py --edge-ip 203.0.113.7                    # where .pxd names point (the machine running the web redirect or gateway)
python pxd2root.py --ns-ip <base1 ip> --ns-ip <pi ip>      # list every PXD root as ns1, ns2, ...
python pxd2root.py --no-forward                             # answer .pxd only
python pxd2root.py --export-zone zones/                     # pxd.zone + pxd2.zone for BIND, Knot, PowerDNS, CoreDNS, Unbound
```
Endpoints: `/dns-query` (RFC 8484), `/resolve?name=x.pxd` (JSON entry), `/zone`, `/pxd.mobileconfig`, `/status`.

## More roots
Run the same script on base1, the Pi 5s and any partner's machine, all with `--authority --require-signed`. They read the same signed registry, so they agree without talking to each other. `--export-zone` lets an operator on standard DNS software serve `.pxd` too.

## Reaching phones away from home
Off-grid and satellite connections usually can't take incoming traffic on port 53. DNS-over-HTTPS can still go out through a tunnel:
1. Run `cloudflared tunnel --url http://localhost:80` on base1.
2. Use the https address it prints as `--public-url`.
3. Phones then use `https://that-address/dns-query`.

A Pi on a connection with a public IP can serve plain DNS and DNS-over-TLS.

Tested: UDP, TCP, DoT, DoH (GET/POST, HTTP and HTTPS), NXDOMAIN with SOA, sub-hub federation and clashes, the redirect, signed/tampered/rollback/wrong-authority registries, zone export, the iPhone profile.
