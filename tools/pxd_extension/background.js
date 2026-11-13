// PXD Web extension: the address-bar rules (rules.json) do the routing. This adds the "pxd" keyword
// (type  pxd mikevanceauto  in the address bar) and the toolbar button that opens the PXD Browser.
const api = typeof browser !== "undefined" ? browser : chrome;
const open = (q) => {
  const s = (q || "").trim();
  const name = s && !/\s/.test(s) && !/\.pxd2?(\/|$)/i.test(s) && !/\./.test(s) ? s + ".pxd" : s;
  return "https://pxd2.github.io/" + (name ? "?go=" + encodeURIComponent(name) : "");
};
api.omnibox.setDefaultSuggestion({ description: "Open %s on the .pxd web" });
api.omnibox.onInputEntered.addListener((text, disposition) => {
  const url = open(text);
  if (disposition === "currentTab") api.tabs.update({ url });
  else api.tabs.create({ url, active: disposition === "newForegroundTab" });
});
api.action.onClicked.addListener(() => api.tabs.create({ url: "https://pxd2.github.io/" }));
