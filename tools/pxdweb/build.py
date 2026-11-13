"""Build the PXD Web downloads into /vr/pxdweb/ on the site:
  PXD-Web-Windows.zip       unzip, double-click "Install PXD Web.bat"
  PXD-Web-Linux.pxd2        one self-installing file (sh PXD-Web-Linux.pxd2, or mark it executable and open it)
Each carries the root server, the signature checker, the PXD authority's public key (once it exists) and a
snapshot of names.json for when the machine is offline. Run after names or the root change:
    python tools/pxdweb/build.py
"""
import io, os, tarfile, zipfile, base64, time

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(SITE, "vr", "pxdweb")

COMMON = [("tools/pxd2root/pxd2root.py", None), ("tools/pxdz/pxdsign.py", None), ("names.json", None),
          ("names.json.sig", "optional"), ("pxd/authority.json", "optional")]


def files(platform_dir):
    for rel, opt in COMMON:
        p = os.path.join(SITE, rel)
        if os.path.exists(p):
            yield rel, p
        elif not opt:
            raise SystemExit(f"missing {rel}")
    d = os.path.join(HERE, platform_dir)
    for f in sorted(os.listdir(d)):
        yield f"{platform_dir}/{f}", os.path.join(d, f)


def main():
    os.makedirs(OUT, exist_ok=True)
    zp = os.path.join(OUT, "PXD-Web-Windows.zip")
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        for rel, p in files("windows"):
            z.write(p, "PXD Web/" + rel)
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as t:
        for rel, p in files("linux"):
            ti = t.gettarinfo(p, rel); ti.uid = ti.gid = 0; ti.uname = ti.gname = "root"
            ti.mode = 0o755 if rel.endswith(".sh") else 0o644
            with open(p, "rb") as fh:
                t.addfile(ti, fh)
    head = (
        "#!/bin/sh\n"
        "# PXD Web for Linux (.pxd2 installer). Run:  sh PXD-Web-Linux.pxd2\n"
        "# Unpacks to a temporary folder, installs to /opt/pxd-web, adds PXD Web ON / OFF / STATUS to the desktop, turns it on.\n"
        "set -e\nT=$(mktemp -d)\n"
        "sed '1,/^__PXD2_PAYLOAD__$/d' \"$0\" | base64 -d | tar -xz -C \"$T\"\n"
        "sh \"$T/linux/pxdweb.sh\" install \"$(id -un)\"\n"
        "rm -rf \"$T\"\nexit 0\n__PXD2_PAYLOAD__\n")
    lp = os.path.join(OUT, "PXD-Web-Linux.pxd2")
    with open(lp, "w", newline="\n") as f:
        f.write(head + base64.encodebytes(buf.getvalue()).decode())
    os.chmod(lp, 0o755)
    # PXD Host for a Raspberry Pi (or any Debian/Ubuntu box): one self-installing file
    hb = io.BytesIO()
    with tarfile.open(fileobj=hb, mode="w:gz") as t:
        for rel, src in (("pxdhost-install.sh", "tools/pxdhost/linux/pxdhost-install.sh"), ("pxdhost.py", "tools/pxdhost/pxdhost.py")):
            ti = t.gettarinfo(os.path.join(SITE, src), rel); ti.uid = ti.gid = 0; ti.uname = ti.gname = "root"; ti.mode = 0o755
            with open(os.path.join(SITE, src), "rb") as fh:
                t.addfile(ti, fh)
    hp = os.path.join(OUT, "PXD-Host-Pi.pxd2")
    with open(hp, "w", newline="\n") as f:
        f.write("#!/bin/sh\n# PXD Host (.pxd2 installer) for a Raspberry Pi 5 or any Debian/Ubuntu box. Run:  sh PXD-Host-Pi.pxd2 [host-id]\n"
                "set -e\nT=$(mktemp -d)\nsed '1,/^__PXD2_PAYLOAD__$/d' \"$0\" | base64 -d | tar -xz -C \"$T\"\n"
                "sh \"$T/pxdhost-install.sh\" \"${1:-pi1}\"\nrm -rf \"$T\"\nexit 0\n__PXD2_PAYLOAD__\n" + base64.encodebytes(hb.getvalue()).decode())
    os.chmod(hp, 0o755)
    for p in (zp, lp, hp):
        print(f"{os.path.relpath(p, SITE)}  {os.path.getsize(p) // 1024} KB")


if __name__ == "__main__":
    main()
