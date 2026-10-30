import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const STYLE = `
#acdev-ribbon{position:fixed;left:0;right:0;bottom:0;z-index:9999;background:#15161ae6;border-top:1px solid #3a3b42;
  backdrop-filter:blur(6px);font:13px sans-serif;color:#f4f4f5;transition:transform .18s ease}
#acdev-ribbon.collapsed{transform:translateY(calc(100% - 30px))}
#acdev-ribbon header{display:flex;align-items:center;gap:10px;padding:5px 12px;height:30px;box-sizing:border-box}
#acdev-ribbon header strong{font-weight:600;font-size:12px;letter-spacing:.02em}
#acdev-ribbon header .spacer{flex:1}
#acdev-ribbon button{background:#202127;color:inherit;border:1px solid #4a4b52;border-radius:6px;
  padding:3px 10px;cursor:pointer;font:inherit;font-size:12px}
#acdev-ribbon button:hover{background:#2a2b33}
#acdev-strip{display:flex;gap:8px;overflow-x:auto;padding:8px 12px 12px;scrollbar-width:thin}
#acdev-strip .empty{opacity:.6;padding:14px 2px}
#acdev-strip figure{margin:0;flex:0 0 auto;cursor:zoom-in;border-radius:6px;overflow:hidden;
  border:1px solid #3a3b42;background:#09090b;line-height:0;position:relative}
#acdev-strip img{height:104px;width:auto;display:block}
#acdev-strip figure.fresh{outline:2px solid #6ea8fe;outline-offset:-2px}
#acdev-lightbox{position:fixed;inset:0;z-index:10001;background:#000000d9;display:flex;align-items:center;
  justify-content:center;flex-direction:column;gap:12px;padding:24px;box-sizing:border-box}
#acdev-lightbox img{max-width:94vw;max-height:82vh;object-fit:contain;border-radius:6px}
#acdev-lightbox .bar{display:flex;gap:12px;align-items:center}
#acdev-lightbox a{color:#8dbdff}
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
        // Skip ComfyUI's transient previews; keep saved outputs only.
        if ((file.type || "output") === "temp") continue;
        if (!/\.(png|jpe?g|webp)$/i.test(file.filename || "")) continue;
        out.push(file);
      }
    }
  }
  return out.slice(-120).reverse();
}

app.registerExtension({
  name: "ACDEV.Studio.ImageRibbon",
  async setup() {
    document.head.append(Object.assign(document.createElement("style"), { textContent: STYLE }));

    const ribbon = document.createElement("div");
    ribbon.id = "acdev-ribbon";
    const header = document.createElement("header");
    const title = document.createElement("strong");
    title.textContent = "Recent images";
    const count = document.createElement("span");
    count.style.opacity = ".6";
    const spacer = document.createElement("div");
    spacer.className = "spacer";
    const reload = document.createElement("button");
    reload.textContent = "Refresh";
    const toggle = document.createElement("button");
    toggle.textContent = "Hide";
    header.append(title, count, spacer, reload, toggle);
    const strip = document.createElement("div");
    strip.id = "acdev-strip";
    ribbon.append(header, strip);
    document.body.append(ribbon);

    let known = new Set();
    let first = true;

    const open = (item) => {
      const box = document.createElement("div");
      box.id = "acdev-lightbox";
      const img = document.createElement("img");
      img.src = viewUrl(item);
      const bar = document.createElement("div");
      bar.className = "bar";
      const name = document.createElement("span");
      name.textContent = label(item);
      const dl = document.createElement("a");
      dl.href = img.src; dl.download = item.filename; dl.textContent = "Download original";
      const close = document.createElement("button");
      close.textContent = "Close";
      bar.append(name, dl, close);
      box.append(img, bar);
      const dismiss = (event) => { if (event.target === box || event.target === close) box.remove(); };
      box.addEventListener("click", dismiss);
      document.addEventListener("keydown", function esc(event) {
        if (event.key === "Escape") { box.remove(); document.removeEventListener("keydown", esc); }
      });
      document.body.append(box);
    };

    const refresh = async () => {
      try {
        const response = await api.fetchApi("/history?max_items=80");
        if (!response.ok) throw new Error(`history ${response.status}`);
        const items = collect(await response.json());
        count.textContent = items.length ? `(${items.length})` : "";
        if (!items.length) {
          strip.replaceChildren(Object.assign(document.createElement("div"),
            { className: "empty", textContent: "Queue a workflow and finished images appear here." }));
          return;
        }
        const frag = document.createDocumentFragment();
        for (const item of items) {
          const key = label(item);
          const fig = document.createElement("figure");
          if (!first && !known.has(key)) fig.className = "fresh";
          const img = document.createElement("img");
          img.src = viewUrl(item); img.loading = "lazy"; img.alt = key; img.title = key;
          fig.append(img);
          fig.addEventListener("click", () => open(item));
          frag.append(fig);
        }
        known = new Set(items.map(label));
        first = false;
        strip.replaceChildren(frag);
      } catch (error) {
        strip.replaceChildren(Object.assign(document.createElement("div"),
          { className: "empty", textContent: `Could not load outputs: ${error.message}` }));
      }
    };

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
