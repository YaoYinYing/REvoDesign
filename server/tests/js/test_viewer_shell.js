/* REvoCompute — contract tests for the sandboxed Mol* viewer shell */
/* SPDX-License-Identifier: GPL-3.0-only */
/* Run: node server/tests/js/test_viewer_shell.js */

"use strict";

var fs = require("fs");
var path = require("path");

function fakeNode(tag) {
  return {
    tagName: tag,
    hidden: false,
    textContent: "",
    children: [],
    dataset: {},
    appendChild: function (child) { this.children.push(child); return child; },
    replaceChildren: function () { this.children = []; },
    addEventListener: function () {}
  };
}

async function main() {
  var stateNode = fakeNode("div");
  stateNode.textContent = "Waiting for structure data…";
  var host = fakeNode("div");
  host.hidden = true;
  var reports = [];
  var listeners = {};
  var loadedStructure = null;
  var loadedStructureCount = 0;
  var viewerCreateCount = 0;
  var canvasBackground = null;
  var layoutShowControls = null;
  var viewerPlugin = null;
  var colorUpdates = [];
  var componentA = { id: "component-a" };
  var componentB = { id: "component-b" };
  var parentWindow = {
    origin: "https://revocompute.example",
    postMessage: function (payload, targetOrigin) { reports.push({ payload: payload, targetOrigin: targetOrigin }); }
  };
  var document = {
    head: fakeNode("head"),
    documentElement: { dataset: {} },
    getElementById: function (id) { return id === "shellState" ? stateNode : host; },
    querySelector: function () { return null; },
    createElement: function (tag) { return fakeNode(tag); }
  };
  var selectionChanged = [];
  var selectedStructure = {
    units: [
      {
        kind: 0,
        chain: "A",
        elements: [5],
        residues: { 5: { auth: 163, label: 163 } }
      }
    ]
  };
  var window = {
    parent: parentWindow,
    addEventListener: function (type, listener) { listeners[type] = listener; },
    molstar: {
      Viewer: {
        create: async function (_id, options) {
          viewerCreateCount += 1;
          layoutShowControls = options.layoutShowControls;
          viewerPlugin = {
            clear: async function () {},
            dispose: function () {},
            canvas3d: {
              setProps: function (props) { canvasBackground = props.renderer.backgroundColor; }
            },
            managers: {
              structure: {
                hierarchy: {
                  currentComponentGroups: [[componentA], [componentB]],
                  current: {
                    structures: [{ cell: { obj: { data: selectedStructure } } }]
                  }
                },
                component: {
                  updateRepresentationsTheme: async function (components, theme) {
                    colorUpdates.push({ components: components, theme: theme });
                  }
                },
                selection: {
                  events: {
                    changed: {
                      subscribe: function (handler) { selectionChanged.push(handler); return { unsubscribe: function () {} }; }
                    }
                  },
                  getLoci: function (structure) {
                    if (structure !== selectedStructure) return undefined;
                    return {
                      structure: selectedStructure,
                      elements: [{ unit: selectedStructure.units[0], indices: [0] }]
                    };
                  }
                }
              }
            }
          };
          return {
            plugin: viewerPlugin,
            loadStructureFromData: async function (text, format, options) {
              loadedStructureCount += 1;
              loadedStructure = { text: text, format: format, options: options };
            }
          };
        }
      },
      lib: {
        structure: {
          StructureElement: {
            Loci: {
              forEachLocation: function (loci, callback) {
                loci.elements.forEach(function (group) {
                  group.indices.forEach(function (index) {
                    callback({
                      _chain: group.unit.chain,
                      _residue: group.unit.residues[group.unit.elements[index]],
                      unit: group.unit
                    });
                  });
                });
              }
            },
            Location: {
              create: function (_structure, unit, elementIndex) {
                return { _chain: unit.chain, _residue: unit.residues[elementIndex] };
              }
            }
          },
          StructureProperties: {
            chain: {
              auth_asym_id: function (location) { return location._chain; },
              label_asym_id: function () { return undefined; }
            },
            residue: {
              auth_seq_id: function (location) { return location._residue.auth; },
              label_seq_id: function (location) { return location._residue.label; }
            }
          }
        }
      }
    }
  };
  var source = fs.readFileSync(
    path.resolve(__dirname, "../../revocompute/static/js/viewer-shell.js"),
    "utf8"
  );
  new Function("window", "document", source)(window, document);

  if (!reports.some(function (entry) { return entry.payload.type === "shell-ready"; })) {
    throw new Error("shell did not report readiness");
  }
  listeners.message({
    source: parentWindow,
    origin: "https://revocompute.example",
    data: {
      type: "structure",
      text: "ATOM",
      format: "pdb",
      label: "probe",
      requestId: "probe-1",
      theme: "dark",
      colorMode: "plddt",
      selectionEnabled: true
    }
  });
  await new Promise(function (resolve) { setTimeout(resolve, 0); });

  if (!loadedStructure || loadedStructure.text !== "ATOM" || loadedStructure.format !== "pdb") {
    throw new Error("shell did not load the posted structure");
  }
  if (!stateNode.hidden || host.hidden || host.children.length !== 1) {
    throw new Error("shell did not reveal the mounted viewer");
  }
  if (document.documentElement.dataset.theme !== "dark") {
    throw new Error("shell did not apply the parent theme");
  }
  if (canvasBackground !== 0x111318) {
    throw new Error("shell did not apply the dark canvas color");
  }
  if (colorUpdates.length !== 1 || colorUpdates[0].theme.color !== "plddt-confidence") {
    throw new Error("shell did not apply the initial pLDDT theme");
  }
  if (colorUpdates[0].components[0] !== componentA || colorUpdates[0].components[1] !== componentB) {
    throw new Error("shell did not pass flattened structure components to Mol*");
  }
  if (layoutShowControls !== false) {
    throw new Error("result viewer must hide the right-side controls by default");
  }
  if (!viewerPlugin.selectionMode) {
    throw new Error("selection-enabled viewer must enter Mol* selection mode");
  }
  listeners.message({
    source: parentWindow,
    origin: "https://revocompute.example",
    data: { type: "color", mode: "chain" }
  });
  listeners.message({
    source: parentWindow,
    origin: "https://revocompute.example",
    data: { type: "color", mode: "rainbow" }
  });
  await new Promise(function (resolve) { setTimeout(resolve, 0); });
  if (colorUpdates[1].theme.color !== "chain-id" || colorUpdates[2].theme.color !== "sequence-id") {
    throw new Error("shell did not map the Chain and Rainbow themes");
  }
  listeners.message({
    source: parentWindow,
    origin: "https://revocompute.example",
    data: { type: "theme", theme: "light" }
  });
  if (canvasBackground !== 0xf8faf7) {
    throw new Error("shell did not restore the light canvas color");
  }
  if (!reports.some(function (entry) {
    return entry.payload.type === "ready" && entry.payload.requestId === "probe-1";
  })) {
    throw new Error("shell did not report structure readiness");
  }
  if (selectionChanged.length !== 1) {
    throw new Error("shell did not subscribe to selection changes");
  }
  selectionChanged[0]();
  await new Promise(function (resolve) { setTimeout(resolve, 0); });
  var selectionReports = reports.filter(function (entry) { return entry.payload.type === "selection"; });
  if (selectionReports.length !== 1) {
    throw new Error("shell did not report the selection change");
  }
  var residues = selectionReports[0].payload.residues;
  if (residues.length !== 1 || residues[0].chain !== "A" || residues[0].residue !== 163) {
    throw new Error("shell reported wrong selected residues: " + JSON.stringify(residues));
  }
  // Warm reuse: a second structure message must reuse the booted plugin —
  // Viewer.create exactly once, loadStructureFromData twice.
  listeners.message({
    source: parentWindow,
    origin: "https://revocompute.example",
    data: {
      type: "structure",
      text: "ATOM2",
      format: "pdb",
      label: "probe-2",
      requestId: "probe-2",
      theme: "dark",
      colorMode: "plddt",
      selectionEnabled: false
    }
  });
  await new Promise(function (resolve) { setTimeout(resolve, 0); });
  if (loadedStructureCount !== 2 || loadedStructure.text !== "ATOM2") {
    throw new Error("warm shell did not load the second structure");
  }
  if (viewerCreateCount !== 1) {
    throw new Error("warm shell recreated the viewer instead of reusing it");
  }
  if (!reports.some(function (entry) { return entry.payload.type === "ready" && entry.payload.requestId === "probe-2"; })) {
    throw new Error("warm shell did not report readiness for the second structure");
  }
  console.log("viewer shell message contract passed");
}

main().catch(function (error) {
  console.error(error.stack || error);
  process.exit(1);
});
