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
  var MOLSTAR_COLORS = { plddt: "b-factor", chain: "chain-id", rainbow: "residue-index" };

  var stateNode = document.getElementById("shellState");
  var host = document.getElementById("viewerHost");
  var assetsPromise = null;
  var viewer = null;
  var viewerId = null;

  function report(payload) {
    // The sandboxed frame has an opaque origin ("null") — target the
    // parent's real origin, never location.origin.
    window.parent.postMessage(payload, window.parent.origin);
  }

  function fail(message) {
    stateNode.hidden = false;
    host.hidden = true;
    stateNode.textContent = "Mol* could not be loaded: " + message;
  }

  function ensureMolstarAssets() {
    if (window.molstar && window.molstar.Viewer) return Promise.resolve(window.molstar);
    if (assetsPromise) return assetsPromise;
    assetsPromise = new Promise(function (resolve, reject) {
      if (!document.querySelector("link[data-molstar-style]")) {
        var style = document.createElement("link");
        style.rel = "stylesheet";
        style.href = MOLSTAR_BASE + "molstar.css";
        style.integrity = MOLSTAR_STYLE_INTEGRITY;
        style.crossOrigin = "anonymous";
        style.dataset.molstarStyle = MOLSTAR_VERSION;
        document.head.appendChild(style);
      }
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
    stateNode.hidden = false;
    host.hidden = true;
    stateNode.textContent = "Loading Mol*…";
    try {
      await ensureMolstarAssets();
      if (viewer) { viewer.plugin.dispose(); host.replaceChildren(); }
      viewerId = "molstar-shell-" + Math.random().toString(36).slice(2);
      var target = document.createElement("div");
      target.id = viewerId;
      host.appendChild(target);
      viewer = await window.molstar.Viewer.create(target.id, {
        layoutIsExpanded: false,
        layoutShowControls: true,
        layoutShowRemoteState: false,
        layoutShowSequence: true,
        layoutShowLog: false,
        layoutShowLeftPanel: false,
        viewportShowExpand: true,
        viewportShowSelectionMode: true,
        viewportShowAnimation: true
      });
      var format = message.format === "mmcif" ? "mmcif" : "pdb";
      await viewer.loadStructureFromData(message.text, format, { label: message.label || "structure" });
      stateNode.hidden = true;
      host.hidden = false;
      report({ type: "ready", requestId: message.requestId });
    } catch (error) {
      fail(error.message || String(error));
      report({ type: "error", requestId: message.requestId, message: error.message || String(error) });
    }
  }

  window.addEventListener("message", function (event) {
    if (event.source !== window.parent) return;
    if (!event.data || typeof event.data !== "object") return;
    if (event.data.type === "structure") mountStructure(event.data);
    else if (event.data.type === "color" && viewer && viewer.plugin) {
      var name = MOLSTAR_COLORS[event.data.mode] || event.data.mode;
      try {
        viewer.plugin.managers.structure.component.updateRepresentationsTheme({ color: { name: name, params: {} } });
      } catch (e) { /* Mol* handles this via its own panel too */ }
    } else if (event.data.type === "dispose") {
      if (viewer) viewer.plugin.dispose();
      viewer = null;
      host.replaceChildren();
    }
  });

  report({ type: "shell-ready" });
})();
