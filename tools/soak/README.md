# PXD2 Soak

Holds every `.pxd` name, and every page and file behind it, under steady load for as long as you say, then reports what broke and how the root held up.

**Double-click `Run_Soak.bat`.** It starts a private-hosting PXD root from this copy of the site on test ports (no administrator needed), soaks it for 10 minutes, stops it, and opens the report.

Each round, for every name in `names.json`:
- DNS: A over UDP, A over TCP, TXT, DoH GET, DoH POST, `/resolve`
- Web: the name's page through the root (`X-PXD-Host: pxd2-private` checked), every file the HTML and CSS load, and every file its scripts and JSON catalogs load
- Root health every 5 s: memory, threads, open files (a leak shows as a climbing line)

```
python tools/soak/pxdsoak.py --spawn                              # 10 minutes, 12 at once
python tools/soak/pxdsoak.py --spawn --minutes 30 --workers 16
python tools/soak/pxdsoak.py --root <base1 ip> --dns-port 53 --web-port 80 --pid <root pid>   # a root already running
python tools/soak/pxdsoak.py --spawn --live                       # the public pxd2.github.io pages too
python tools/soak/pxdsoak.py --live-only --minutes 5              # only the public pages
```

Reports land in `tools/soak/reports/` (kept out of git): `.html` to open, `.md` short, `.json` everything. Exit code 0 means clean.

"Named in code, not on disk" is a list, not a failure: shop photo slots waiting for photos (the page shows "Photo coming soon"), `items.json` before a shop's inventory is in, download names, CDN files.

## 2026-11-13 soak results
| | before fixes | after |
|---|---|---|
| failures | 7 DoH POST resets in 246,288 checks | 0 in 222,099 |
| p99 latency | ~1,020 ms on every web/DoH check | 47–118 ms |
| worst request | 3.07 s | 0.22 s |
| root memory over the run | 67 → 311 MB (steps up under load) | 23 → 35 MB, flat |

Fixed in `pxd2root.py`: listen queue 5 → 512 (overflow was dropping connections that retried a second later), and private hosting now streams files in 256 KB pieces instead of loading each one whole per visitor. Fixed on the site: `/hugs/` linked `book/hugs.lex.json`, which isn't on the site; it now links `book/acr.json`.
