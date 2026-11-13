# PXD Web extension (Chrome, Edge, Firefox)

Type `mikevanceauto.pxd` in the address bar and the site opens in the PXD Browser at pxd2.github.io. It works whether the browser treats it as an address or turns it into a Google, Bing or DuckDuckGo search. Typing `pxd mikevanceauto` works too, and the toolbar button opens the PXD Browser.

- The extension contains no code that reads pages; the address-bar routing is four declarative rules in `rules.json`.
- Its only permission is to redirect: `*.pxd` and `*.pxd2` addresses, plus searches whose whole query is a .pxd name (like `bearwallow.pxd`). Every other search goes on to the search engine as usual.

## Install today (no store)
- **Chrome / Edge:** unzip `PXD-Web-Extension.zip`, open `chrome://extensions` (or `edge://extensions`), turn on Developer mode, click **Load unpacked**, and pick the folder.
- **Firefox:** open `about:debugging#/runtime/this-firefox`, click **Load Temporary Add-on**, and pick `manifest.json`. That lasts until Firefox restarts. For a permanent install, Mozilla has to sign it: upload the zip at addons.mozilla.org as "On your own" (unlisted) and you get a signed .xpi back.

## For everyone (one click)
Publish it under PXD2's developer accounts: the Chrome Web Store (one-time $5 developer fee) and addons.mozilla.org (free). The store listing gives people a one-click Add button.

## No install at all
Visit pxd2.github.io and add **PXD** as a search engine. Chrome lists it under Settings → Search engine → Manage → Site search; in Firefox it's "Add PXD" in the address-bar search menu. Make it the default, and a .pxd name opens its site while every other search goes on to Google.
