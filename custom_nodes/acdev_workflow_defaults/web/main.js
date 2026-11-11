import { app } from "../../scripts/app.js";

const MODES = ["randomize", "fixed", "increment", "decrement"];
function isSeed(node, widget) {
  const input = node.inputs?.find(input => input.name === widget.name);
  return /(^|_)seed(?:_\d+)?$/.test(widget.name) ||
    Object.hasOwn(node.properties?.acdevSeedModes || {}, widget.name) || /\bseed\b/i.test(input?.label || widget.label || "") ||
    (/PrimitiveInt|PrimitiveNode/.test(node.type || "") && (/seed/i.test(node.title || "") || node.properties?.acdevSeedDriver) && widget.name === "value");
}
function linkSource(graph, input) {
  const link = graph.links?.get?.(input.link) ?? graph.links?.[input.link];
  return link && graph.getNodeById?.(link.origin_id);
}
function seedWidgets(graph) {
  const result = new Map();
  const add = (node, widget) => {
    if (widget && typeof widget.value === "number") {
      if (!result.has(node)) result.set(node, new Set());
      result.get(node).add(widget);
    }
  };
  for (const node of graph._nodes || graph.nodes || []) {
    for (const widget of node.widgets || []) {
      if (!isSeed(node, widget)) continue;
      const input = node.inputs?.find(input => input.name === widget.name);
      if (input?.link != null) {
        // A linked upstream value wins over the sampler's local widget.
        const source = linkSource(graph, input);
        if (/PrimitiveInt|PrimitiveNode/.test(source?.type || "")) {
          add(source, source.widgets?.find(widget => widget.name === "value"));
        }
      } else add(node, widget);
    }
  }
  return result;
}
function nativeControl(node, seed) {
  const next = node.widgets[node.widgets.indexOf(seed) + 1];
  if (next && /control_after_generate/.test(next.name)) return next;
  const controls = node.widgets.filter(widget => /control_after_generate/.test(widget.name));
  const seeds = node.widgets.filter(widget => typeof widget.value === "number" && isSeed(node, widget));
  return controls.length === 1 && seeds.length === 1 ? controls[0] : null;
}
function modeControl(node, seed) {
  const native = nativeControl(node, seed);
  if (native && /control_after_generate/.test(native.name) && MODES.includes(native.value)) return native;
  node.properties ||= {};
  const modes = node.properties.acdevSeedModes ||= {};
  modes[seed.name] ||= "randomize";
  const name = `${seed.name} mode`;
  let control = node.widgets.find(widget => widget.name === name);
  if (!control && node.addWidget) {
    control = node.addWidget("combo", name, modes[seed.name], value => {
      modes[seed.name] = value;
    }, { values: MODES, serialize: false });
    // Mode is persisted by name in properties, never inserted into seed widget values.
    control.serialize = false;
  }
  if (control) control.value = modes[seed.name];
  return control || { value: modes[seed.name] };
}
export function prepareSeeds(graph, execute = false, seen = new Set(), widgetsSeen = new Set()) {
  if (!graph || seen.has(graph)) return;
  seen.add(graph);
  for (const [node, widgets] of seedWidgets(graph)) {
    for (const seed of widgets) {
      if (widgetsSeen.has(seed)) continue;
      widgetsSeen.add(seed);
      const mode = modeControl(node, seed).value;
      if (!execute || mode === "fixed") continue;
      // Native increment/decrement controls already update after generation.
      const hasNative = Boolean(nativeControl(node, seed));
      const min = Math.max(0, seed.options?.min ?? 0);
      const max = Math.min(Number.MAX_SAFE_INTEGER, seed.options?.max ?? Number.MAX_SAFE_INTEGER);
      if (mode === "randomize") {
        let low = Math.max(min, 100000000000000);
        let high = Math.min(max, 999999999999999);
        if (low > high) { low = min; high = max; }
        const words = new Uint32Array(2);
        globalThis.crypto.getRandomValues(words);
        seed.value = low + Math.floor(((words[0] * 2097152 + (words[1] >>> 11)) /
          9007199254740992) * (high - low + 1));
      } else if (!hasNative) {
        seed.value = Math.min(max, Math.max(min, seed.value + (mode === "increment" ? 1 : -1)));
      }
      seed.callback?.(seed.value);
    }
  }
  for (const node of graph._nodes || graph.nodes || []) {
    prepareSeeds(node.subgraph, execute, seen, widgetsSeen);
  }
}
app.registerExtension({
  name: "ACDEV.WorkflowSeedDefaults",
  nodeCreated(node) { queueMicrotask(() => prepareSeeds(node.graph)); },
  loadedGraphNode(node) { prepareSeeds(node.graph); },
  setup() {
    const graphToPrompt = app.graphToPrompt;
    app.graphToPrompt = function (...args) {
      prepareSeeds(args[0] || this.rootGraph || this.graph, true);
      return graphToPrompt.apply(this, args);
    };
  },
});
