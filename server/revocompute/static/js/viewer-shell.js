/* REvoCompute — sandboxed Mol* host shell (runs inside the viewer iframe) */
/* SPDX-License-Identifier: GPL-3.0-only */

/* This page lives under its own CSP that permits 'unsafe-eval' (Mol*'s
   bundle calls new Function at load) — scoped to this shell only. All
   structure data arrives via postMessage from the authenticated parent;
   nothing is fetched here. */

(function () {
  "use strict";

  var MOLSTAR_VERSION = "5.11.0";
  var MOLSTAR_BASE = "https://cdn.jsdelivr.net/npm/molstar@" + MOLSTAR_VERSION + "/build/viewer/";
  var MOLSTAR_SCRIPT_INTEGRITY = "sha384-5Mfx4eL50NkWPky+mcH//qY0sbml4il0CLFFmrMp8uv/saB3Z6uZMHn2dUpAnH92";
  var MOLSTAR_STYLE_INTEGRITY = "sha384-RIontCdJN53gEl2fmiHN+4bscIBvaUaOiCeeGktXqmFqdEBF+COnSdt9O4IKFSvq";
  var MOLSTAR_DARK_STYLE_INTEGRITY = "sha384-LDnli0hRX1wCV3HrFyNGSy145zkcGA8P6EZPC8VyLVS6+TJO3jgsncYeD+cZuLjO";
  var MOLSTAR_COLORS = { plddt: "plddt-confidence", chain: "chain-id", rainbow: "sequence-id" };
  var MOLSTAR_CANVAS_COLORS = { light: 0xf8faf7, dark: 0x111318 };

  var stateNode = document.getElementById("shellState");
  var host = document.getElementById("viewerHost");
  var assetsPromise = null;
  var viewer = null;
  var viewerId = null;
  var activeTheme = "light";
  var selectionSubscription = null;
  var activeRequestId = null;

  function selectedResidues() {
    var residues = new Map();
    if (!viewer || !viewer.plugin || !viewer.plugin.managers.structure) return [];
    // The viewer bundle only exposes the library under window.molstar.lib.
    var lib = window.molstar.lib;
    var selection = viewer.plugin.managers.structure.selection;
    var structures = viewer.plugin.managers.structure.hierarchy.current.structures;
    var StructureElement = lib.structure.StructureElement;
    var StructureProperties = lib.structure.StructureProperties;
    if (!selection || !structures || !StructureElement || !StructureProperties) return [];
    // Canvas picks, sequence-panel clicks, and structureInteractivity all
    // funnel into structure.selection (lociSelects.sel IS this manager).
    structures.forEach(function (structureRef) {
      var structure = structureRef && structureRef.cell && structureRef.cell.obj && structureRef.cell.obj.data;
      if (!structure) return;
      var loci = selection.getLoci(structure);
      if (!loci || !loci.elements) return;
      StructureElement.Loci.forEachLocation(loci, function (location) {
        if (!location.unit || location.unit.kind !== 0) return;  // kind 0 = atomic units only
        var chain = String(StructureProperties.chain.auth_asym_id(location) || StructureProperties.chain.label_asym_id(location) || "_");
        var auth = Number(StructureProperties.residue.auth_seq_id(location));
        var label = Number(StructureProperties.residue.label_seq_id(location));
        residues.set(chain + ":" + auth + ":" + label, { chain: chain, auth_seq_id: auth, label_seq_id: label, residue: auth });
      });
    });
    return Array.from(residues.values());
  }

  function reportSelection() {
    try {
      report({ type: "selection", requestId: activeRequestId, residues: selectedResidues() });
    } catch (error) {
      report({ type: "selection-error", requestId: activeRequestId, message: error.message || String(error) });
    }
  }

  function bindSelectionEvents(enabled) {
    if (selectionSubscription) selectionSubscription.unsubscribe();
    selectionSubscription = null;
    if (!enabled || !viewer || !viewer.plugin || !viewer.plugin.managers.structure) return;
    var selection = viewer.plugin.managers.structure.selection;
    if (!selection || !selection.events || !selection.events.changed) return;
    selectionSubscription = selection.events.changed.subscribe(function () {
      setTimeout(reportSelection, 0);
    });
  }

  function selectResidue(message) {
    if (!viewer || typeof viewer.structureInteractivity !== "function") return;
    var elements = {};
    var prefix = message.numbering === "auth_seq_id" ? "auth" : "label";
    elements["beg_" + prefix + "_seq_id"] = Number(message.residue);
    elements["end_" + prefix + "_seq_id"] = Number(message.residue);
    if (message.chain) elements[prefix + "_asym_id"] = String(message.chain);
    viewer.plugin.managers.interactivity.lociSelects.deselectAll();
    viewer.structureInteractivity({ elements: elements, action: "select" });
  }

  // Surface any boot error in the shell UI instead of leaving the
  // "Waiting for structure data…" placeholder frozen forever.
  window.addEventListener("error", function (event) {
    stateNode.hidden = false;
    stateNode.dataset.state = "error";
    stateNode.textContent = "Shell error: " + (event.message || "unknown error");
  });

  function parentOrigin() {
    try { return window.parent.origin; } catch (e) { return "*"; }
  }

  function report(payload) {
    // The sandboxed frame has an opaque origin ("null") — target the
    // parent's real origin, never location.origin.
    window.parent.postMessage(payload, parentOrigin());
  }

  function fail(message) {
    stateNode.hidden = false;
    stateNode.dataset.state = "error";
    host.hidden = true;
    stateNode.textContent = "Mol* could not be loaded: " + message;
  }

  function ensureMolstarStyle() {
    if (document.querySelector("link[data-molstar-style]")) return;
    var style = document.createElement("link");
    style.rel = "stylesheet";
    style.href = MOLSTAR_BASE + "molstar.css";
    style.integrity = MOLSTAR_STYLE_INTEGRITY;
    style.crossOrigin = "anonymous";
    style.dataset.molstarStyle = MOLSTAR_VERSION;
    document.head.appendChild(style);
  }

  function applyTheme(theme) {
    var resolved = theme === "dark" ? "dark" : "light";
    activeTheme = resolved;
    document.documentElement.dataset.theme = resolved;
    ensureMolstarStyle();
    var darkStyle = document.querySelector("link[data-molstar-dark-style]");
    if (resolved === "dark" && !darkStyle) {
      darkStyle = document.createElement("link");
      darkStyle.rel = "stylesheet";
      darkStyle.href = MOLSTAR_BASE + "theme/dark.css";
      darkStyle.integrity = MOLSTAR_DARK_STYLE_INTEGRITY;
      darkStyle.crossOrigin = "anonymous";
      darkStyle.dataset.molstarDarkStyle = MOLSTAR_VERSION;
      document.head.appendChild(darkStyle);
    } else if (resolved === "light" && darkStyle) {
      darkStyle.remove();
    }
    if (viewer && viewer.plugin.canvas3d) {
      viewer.plugin.canvas3d.setProps({ renderer: { backgroundColor: MOLSTAR_CANVAS_COLORS[resolved] } });
    }
  }

  function ensureMolstarAssets() {
    if (window.molstar && window.molstar.Viewer) return Promise.resolve(window.molstar);
    if (assetsPromise) return assetsPromise;
    assetsPromise = new Promise(function (resolve, reject) {
      ensureMolstarStyle();
      // Mol* is a ~5 MB bundle: poll for the global (deferred init) for up
      // to 15 s and retry the fetch once before giving up.
      var settled = false;

      function waitForGlobal(start) {
        if (settled) return;
        if (window.molstar && window.molstar.Viewer) { settled = true; resolve(window.molstar); return; }
        if (Date.now() - start > 15000) { settled = true; reject(new Error("Mol* did not initialize")); return; }
        setTimeout(function () { waitForGlobal(start); }, 500);
      }

      var attempts = 0;
      function loadScript() {
        attempts += 1;
        var script = document.createElement("script");
        script.src = MOLSTAR_BASE + "molstar.js";
        script.integrity = MOLSTAR_SCRIPT_INTEGRITY;
        script.crossOrigin = "anonymous";
        script.dataset.molstarScript = MOLSTAR_VERSION;
        script.addEventListener("load", function () { waitForGlobal(Date.now()); }, { once: true });
        script.addEventListener("error", function () {
          if (attempts < 2) { loadScript(); return; }
          settled = true;
          reject(new Error("Mol* could not be loaded"));
        }, { once: true });
        document.head.appendChild(script);
      }
      loadScript();
    }).catch(function (error) { assetsPromise = null; throw error; });
    return assetsPromise;
  }

  async function mountStructure(message) {
    activeRequestId = message.requestId;
    applyTheme(message.theme);
    stateNode.hidden = false;
    host.hidden = true;
    stateNode.dataset.state = "loading";
    stateNode.textContent = "Preparing interactive structure…";
    try {
      await ensureMolstarAssets();
      if (viewer) { viewer.plugin.dispose(); host.replaceChildren(); }
      viewerId = "molstar-shell-" + Math.random().toString(36).slice(2);
      var target = document.createElement("div");
      target.id = viewerId;
      host.appendChild(target);
      viewer = await window.molstar.Viewer.create(target.id, {
        layoutIsExpanded: false,
        layoutShowControls: Boolean(message.showControls),
        layoutShowRemoteState: false,
        layoutShowSequence: true,
        layoutShowLog: false,
        layoutShowLeftPanel: false,
        viewportShowExpand: true,
        viewportShowSelectionMode: true,
        viewportShowAnimation: true
      });
      // Sequence-strip and canvas clicks select only while Mol* selection mode
      // is active. Input workbenches request selection explicitly; result
      // viewers retain Mol*'s ordinary focus-oriented default.
      viewer.plugin.selectionMode = Boolean(message.selectionEnabled);
      viewer.plugin.canvas3d.setProps({ renderer: { backgroundColor: MOLSTAR_CANVAS_COLORS[activeTheme] } });
      var format = message.format === "mmcif" ? "mmcif" : "pdb";
      await viewer.loadStructureFromData(message.text, format, { label: message.label || "structure" });
      await updateStructureColor(message.colorMode || "plddt");
      bindSelectionEvents(Boolean(message.selectionEnabled));
      stateNode.hidden = true;
      host.hidden = false;
      report({ type: "ready", requestId: message.requestId });
    } catch (error) {
      fail(error.message || String(error));
      report({ type: "error", requestId: message.requestId, message: error.message || String(error) });
    }
  }

  async function updateStructureColor(mode) {
    if (!viewer || !viewer.plugin) return;
    var name = MOLSTAR_COLORS[mode] || mode;
    var groups = viewer.plugin.managers.structure.hierarchy.currentComponentGroups;
    var components = [].concat.apply([], groups);
    try {
      await viewer.plugin.managers.structure.component.updateRepresentationsTheme(components, { color: name });
    } catch (e) { /* Keep the current Mol* theme when a theme is not applicable. */ }
  }

  window.addEventListener("message", function (event) {
    if (event.source !== window.parent) return;
    if (!event.data || typeof event.data !== "object") return;
    if (event.data.type === "structure") mountStructure(event.data);
    else if (event.data.type === "theme") applyTheme(event.data.theme);
    else if (event.data.type === "color") updateStructureColor(event.data.mode);
    else if (event.data.type === "select-residue") selectResidue(event.data);
    else if (event.data.type === "dispose") {
      if (selectionSubscription) selectionSubscription.unsubscribe();
      selectionSubscription = null;
      if (viewer) viewer.plugin.dispose();
      viewer = null;
      host.replaceChildren();
    }
  });

  report({ type: "shell-ready" });
})();
