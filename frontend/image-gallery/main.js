import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const STYLE = `
#acdev-ribbon{position:fixed;left:0;right:0;bottom:0;z-index:9999;background:#15161aee;border-top:1px solid #3a3b42;
  backdrop-filter:blur(6px);font:13px sans-serif;color:#f4f4f5;transition:transform .18s ease}
#acdev-ribbon.collapsed{transform:translateY(calc(100% - 32px))}
#acdev-ribbon header{display:flex;align-items:center;gap:8px;padding:6px 12px;height:32px;box-sizing:border-box}
#acdev-ribbon header strong{font-weight:600;font-size:12px}
#acdev-ribbon header .spacer{flex:1}
#acdev-ribbon .muted{opacity:.6}
#acdev-ribbon button{background:#202127;color:inherit;border:1px solid #4a4b52;border-radius:6px;
  padding:3px 10px;cursor:pointer;font:inherit;font-size:12px}
#acdev-ribbon button:hover{background:#2a2b33}
#acdev-ribbon button.primary{border-color:#6ea8fe;color:#cfe2ff}
#acdev-ribbon button:disabled{opacity:.4;cursor:default}
#acdev-strip{display:flex;gap:8px;overflow-x:auto;padding:0 12px 12px;scrollbar-width:thin}
#acdev-strip .empty{opacity:.6;padding:12px 2px}
#acdev-strip figure{margin:0;flex:0 0 auto;cursor:zoom-in;border-radius:6px;overflow:hidden;
  border:2px solid #3a3b42;background:#09090b;line-height:0;position:relative}
#acdev-strip figure.picked{border-color:#6ea8fe}
#acdev-strip img{height:104px;width:auto;display:block}
#acdev-strip .tick{position:absolute;top:3px;right:3px;width:17px;height:17px;border-radius:4px;
  background:#15161acc;border:1px solid #6b6c75;color:#cfe2ff;font:11px/17px sans-serif;text-align:center}
#acdev-strip figure.picked .tick{background:#6ea8fe;color:#0b0b0f;border-color:#6ea8fe}
#acdev-view{position:fixed;inset:0;z-index:10001;background:#000000e8;display:flex;flex-direction:column;
  align-items:center;justify-content:center;gap:10px;padding:18px;box-sizing:border-box}
#acdev-view img{max-width:92vw;max-height:78vh;object-fit:contain;border-radius:6px}
#acdev-view .bar{display:flex;gap:10px;align-items:center;font:13px sans-serif;color:#f4f4f5}
#acdev-view .name{max-width:46vw;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;opacity:.75}
#acdev-view button{background:#202127;color:#f4f4f5;border:1px solid #4a4b52;border-radius:6px;
  padding:5px 12px;cursor:pointer;font:inherit}
#acdev-view button.picked{background:#6ea8fe;color:#0b0b0f;border-color:#6ea8fe}
#acdev-view .nav{position:absolute;top:0;bottom:0;width:16vw;border:0;background:transparent;color:#fff;
  font-size:34px;opacity:.35;cursor:pointer}
#acdev-view .nav:hover{opacity:.9}
#acdev-view .prev{left:0} #acdev-view .next{right:0}
`;

const viewUrl = (item) => api.apiURL(`/view?${new URLSearchParams({
  filename: item.filename, subfolder: item.subfolder || "", type: item.type || "output",
}).toString()}`);
const label = (item) => `${item.subfolder ? `${item.subfolder}/` : ""}${item.filename}`;

function collect(history) {
  const out = [];
  for (const entry of Object.values(history || {})) {
    for (const output of Object.values(entry.outputs || {})) {
      for (const file of output.images || []) {
        if ((file.type || "output") === "temp") continue;
        if (!/\.(png|jpe?g|webp)$/i.test(file.filename || "")) continue;
        out.push(file);
      }
    }
  }
  return out.slice(-300).reverse();
}

function save(item) {
  const a = document.createElement("a");
  a.href = viewUrl(item); a.download = item.filename;
  document.body.append(a); a.click(); a.remove();
}

app.registerExtension({
  name: "ACDEV.Studio.ImageRibbon",
  async setup() {
    document.head.append(Object.assign(document.createElement("style"), { textContent: STYLE }));

    let items = [];
    const picked = new Set();

    const ribbon = document.createElement("div");
    ribbon.id = "acdev-ribbon";
    const header = document.createElement("header");
    const title = document.createElement("strong"); title.textContent = "Recent images";
    const count = document.createElement("span"); count.className = "muted";
    const spacer = document.createElement("div"); spacer.className = "spacer";
    const keepBtn = document.createElement("button"); keepBtn.className = "primary";
    const clearBtn = document.createElement("button"); clearBtn.textContent = "Clear picks";
    const reload = document.createElement("button"); reload.textContent = "Refresh";
    const toggle = document.createElement("button"); toggle.textContent = "Hide";
    header.append(title, count, spacer, keepBtn, clearBtn, reload, toggle);
    const strip = document.createElement("div"); strip.id = "acdev-strip";
    ribbon.append(header, strip);
    document.body.append(ribbon);

    const syncPickUi = () => {
      keepBtn.textContent = picked.size ? `Download ${picked.size} picked` : "Download picked";
      keepBtn.disabled = !picked.size;
      clearBtn.disabled = !picked.size;
      for (const fig of strip.querySelectorAll("figure")) {
        fig.classList.toggle("picked", picked.has(fig.dataset.key));
      }
    };
    const togglePick = (key) => { picked.has(key) ? picked.delete(key) : picked.add(key); syncPickUi(); };

    const openViewer = (index) => {
      const view = document.createElement("div"); view.id = "acdev-view";
      const img = document.createElement("img");
      const bar = document.createElement("div"); bar.className = "bar";
      const pos = document.createElement("span");
      const name = document.createElement("span"); name.className = "name";
      const pick = document.createElement("button");
      const dl = document.createElement("button"); dl.textContent = "Download";
      const close = document.createElement("button"); close.textContent = "Close";
      bar.append(pos, name, pick, dl, close);
      const prev = document.createElement("button"); prev.className = "nav prev"; prev.textContent = "‹";
      const next = document.createElement("button"); next.className = "nav next"; next.textContent = "›";
      view.append(prev, img, next, bar);

      let at = index;
      const render = () => {
        const item = items[at]; if (!item) return;
        img.src = viewUrl(item);
        pos.textContent = `${at + 1} / ${items.length}`;
        name.textContent = label(item);
        const on = picked.has(label(item));
        pick.textContent = on ? "Picked ✓" : "Pick";
        pick.classList.toggle("picked", on);
        prev.style.visibility = at > 0 ? "visible" : "hidden";
        next.style.visibility = at < items.length - 1 ? "visible" : "hidden";
      };
      const step = (delta) => { at = Math.min(items.length - 1, Math.max(0, at + delta)); render(); };
      const dismiss = () => { view.remove(); document.removeEventListener("keydown", keys); syncPickUi(); };
      const keys = (event) => {
        if (event.key === "Escape") dismiss();
        else if (event.key === "ArrowRight") step(1);
        else if (event.key === "ArrowLeft") step(-1);
        else if (event.key === " ") { event.preventDefault(); togglePick(label(items[at])); render(); }
        else if (event.key.toLowerCase() === "d") save(items[at]);
      };
      prev.onclick = () => step(-1);
      next.onclick = () => step(1);
      pick.onclick = () => { togglePick(label(items[at])); render(); };
      dl.onclick = () => save(items[at]);
      close.onclick = dismiss;
      view.addEventListener("click", (e) => { if (e.target === view) dismiss(); });
      document.addEventListener("keydown", keys);
      document.body.append(view);
      render();
    };

    const refresh = async () => {
      try {
        const response = await api.fetchApi("/history?max_items=200");
        if (!response.ok) throw new Error(`history ${response.status}`);
        items = collect(await response.json());
        count.textContent = items.length ? `(${items.length})` : "";
        if (!items.length) {
          strip.replaceChildren(Object.assign(document.createElement("div"),
            { className: "empty", textContent: "Queue a workflow and finished images appear here." }));
          syncPickUi(); return;
        }
        const frag = document.createDocumentFragment();
        items.forEach((item, index) => {
          const key = label(item);
          const fig = document.createElement("figure");
          fig.dataset.key = key;
          const img = document.createElement("img");
          img.src = viewUrl(item); img.loading = "lazy"; img.alt = key; img.title = key;
          const tick = document.createElement("span"); tick.className = "tick"; tick.textContent = "✓";
          tick.title = "Pick this image";
          tick.addEventListener("click", (e) => { e.stopPropagation(); togglePick(key); });
          fig.append(img, tick);
          fig.addEventListener("click", () => openViewer(index));
          frag.append(fig);
        });
        strip.replaceChildren(frag);
        syncPickUi();
      } catch (error) {
        strip.replaceChildren(Object.assign(document.createElement("div"),
          { className: "empty", textContent: `Could not load outputs: ${error.message}` }));
      }
    };

    keepBtn.onclick = () => {
      // Browsers throttle bursts of downloads, so space them out.
      const chosen = items.filter((item) => picked.has(label(item)));
      chosen.forEach((item, i) => setTimeout(() => save(item), i * 350));
    };
    clearBtn.onclick = () => { picked.clear(); syncPickUi(); };
    reload.onclick = refresh;
    toggle.onclick = () => {
      const hidden = ribbon.classList.toggle("collapsed");
      toggle.textContent = hidden ? "Show" : "Hide";
    };

    let timer;
    api.addEventListener("executed", () => { clearTimeout(timer); timer = setTimeout(refresh, 900); });
    await refresh();
  },
});
