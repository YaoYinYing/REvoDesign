/* REvoCompute — shared py2Dmol alpha-trace preview (dashboard + results) */
/* SPDX-License-Identifier: GPL-3.0-only */

/* Lazy py2Dmol asset loading and alpha-trace rendering, shared by the
   dashboard task cards (structure input snapshot) and the results page.
   The viewer library is loaded once per page on first use, from a pinned
   CDN commit with SRI. */

(function () {
  "use strict";

  var PY2DMOL_COMMIT = "8c95fd9efae6007e124e143cd276244d89228c66";
  var PY2DMOL_SCRIPT = "https://cdn.jsdelivr.net/gh/sokrypton/py2Dmol@" + PY2DMOL_COMMIT + "/py2Dmol/resources/viewer-mol.js";
  var PY2DMOL_SCRIPT_INTEGRITY = "sha384-D1ju7xD5hbkOLM/oKtegpq8TrkqDFUXPce3GrP3xoELqjLtbfi1CMMbWtx7PDfZH";
  var assetsPromise = null;

  function ensureAssets() {
    if (window.initializePy2DmolViewer) return Promise.resolve();
    if (assetsPromise) return assetsPromise;
    assetsPromise = new Promise(function (resolve, reject) {
      var script = document.createElement("script");
      script.src = PY2DMOL_SCRIPT;
      script.integrity = PY2DMOL_SCRIPT_INTEGRITY;
      script.crossOrigin = "anonymous";
      script.dataset.py2dmolScript = PY2DMOL_COMMIT;
      script.addEventListener("load", function () {
        if (window.initializePy2DmolViewer) resolve();
        else reject(new Error("py2Dmol did not initialize"));
      }, { once: true });
      script.addEventListener("error", function () { reject(new Error("py2Dmol could not be loaded")); }, { once: true });
      document.head.appendChild(script);
    }).catch(function (error) { assetsPromise = null; throw error; });
    return assetsPromise;
  }

  function parsePdbAlphaCarbons(text) {
    var frame = { coords: [], chains: [], position_types: [], plddts: [], position_names: [], residue_numbers: [] };
    String(text).split(/\r?\n/).forEach(function (line) {
      if (!line.startsWith("ATOM  ") || line.slice(12, 16).trim() !== "CA") return;
      var x = Number(line.slice(30, 38)); var y = Number(line.slice(38, 46)); var z = Number(line.slice(46, 54));
      if (![x, y, z].every(Number.isFinite)) return;
      frame.coords.push([x, y, z]);
      frame.chains.push(line.slice(21, 22).trim() || "_");
      frame.position_types.push("P");
      frame.plddts.push(Number(line.slice(60, 66)) || 0);
      frame.position_names.push(line.slice(17, 20).trim() || "UNK");
      frame.residue_numbers.push(Number(line.slice(22, 26)) || frame.coords.length);
    });
    return frame;
  }

  function cifTokens(line) {
    return String(line).match(/'(?:[^']*)'|"(?:[^"]*)"|\S+/g) || [];
  }

  function parseCifAlphaCarbons(text) {
    var lines = String(text).split(/\r?\n/);
    var frame = { coords: [], chains: [], position_types: [], plddts: [], position_names: [], residue_numbers: [] };
    for (var start = 0; start < lines.length; start += 1) {
      if (lines[start].trim() !== "loop_") continue;
      var headers = []; var rowStart = start + 1;
      while (rowStart < lines.length && lines[rowStart].trim().startsWith("_")) {
        headers.push(lines[rowStart].trim().split(/\s+/, 1)[0]); rowStart += 1;
      }
      var xIndex = headers.indexOf("_atom_site.Cartn_x");
      if (xIndex < 0) continue;
      function indexOfAny(names) {
        for (var index = 0; index < names.length; index += 1) {
          var found = headers.indexOf(names[index]); if (found >= 0) return found;
        }
        return -1;
      }
      var yIndex = headers.indexOf("_atom_site.Cartn_y");
      var zIndex = headers.indexOf("_atom_site.Cartn_z");
      var atomIndex = indexOfAny(["_atom_site.auth_atom_id", "_atom_site.label_atom_id"]);
      var groupIndex = headers.indexOf("_atom_site.group_PDB");
      var chainIndex = indexOfAny(["_atom_site.auth_asym_id", "_atom_site.label_asym_id"]);
      var residueIndex = indexOfAny(["_atom_site.auth_seq_id", "_atom_site.label_seq_id"]);
      var nameIndex = indexOfAny(["_atom_site.auth_comp_id", "_atom_site.label_comp_id"]);
      var bIndex = headers.indexOf("_atom_site.B_iso_or_equiv");
      for (var row = rowStart; row < lines.length; row += 1) {
        var trimmed = lines[row].trim();
        if (!trimmed || trimmed === "#") break;
        if (trimmed === "loop_" || trimmed.startsWith("_") || trimmed.startsWith("data_")) break;
        var values = cifTokens(trimmed).map(function (value) { return value.replace(/^['"]|['"]$/g, ""); });
        if (values.length < headers.length || values[atomIndex] !== "CA") continue;
        if (groupIndex >= 0 && values[groupIndex] !== "ATOM") continue;
        var x = Number(values[xIndex]); var y = Number(values[yIndex]); var z = Number(values[zIndex]);
        if (![x, y, z].every(Number.isFinite)) continue;
        frame.coords.push([x, y, z]);
        frame.chains.push(chainIndex >= 0 ? values[chainIndex] : "_");
        frame.position_types.push("P");
        frame.plddts.push(bIndex >= 0 ? Number(values[bIndex]) || 0 : 0);
        frame.position_names.push(nameIndex >= 0 ? values[nameIndex] : "UNK");
        frame.residue_numbers.push(residueIndex >= 0 ? Number(values[residueIndex]) || frame.coords.length : frame.coords.length);
      }
      if (frame.coords.length) return frame;
    }
    return frame;
  }

  function py2DmolMarkup() {
    return '<div id="viewerWrapper"><div id="canvasContainer"><canvas id="canvas"></canvas></div>' +
      '<div id="controlsContainer"><button id="playButton">▶</button><button id="recordButton">●</button>' +
      '<input type="range" id="frameSlider" min="0" max="0" value="0"><span id="frameCounter">0 / 0</span>' +
      '<button id="speedButton">1x</button><button id="overlayButton">⧉</button></div></div>' +
      '<div id="paeContainer"><canvas id="paeCanvas"></canvas></div><div id="scatterContainer"><canvas id="scatterCanvas"></canvas></div>' +
      '<div id="rightPanelContainer"><select id="objectSelect"></select><label>Color <select id="colorSelect"><option value="auto">Auto</option><option value="plddt">pLDDT</option><option value="rainbow">Rainbow</option><option value="chain">Chain</option></select></label>' +
      '<label>Outline <select id="outlineModeSelect"><option value="none">None</option><option value="partial">Partial</option><option value="full" selected>Full</option></select></label>' +
      '<label><input type="checkbox" id="shadowEnabledCheckbox" checked> Shadow</label><label><input type="checkbox" id="colorblindCheckbox"> Colorblind</label>' +
      '<label>Width <input type="range" id="lineWidthSlider" min="2" max="4.7" value="3" step="0.1"></label>' +
      '<label>Ortho <input type="range" id="orthoSlider" min="0" max="1" value="1" step="0.01"></label>' +
      '<label><input type="checkbox" id="rotationCheckbox"> Rotate</label><button id="saveSvgButton">Save SVG</button></div>';
  }

  async function renderAlphaTrace(container, structureText, format, label, size, isStale) {
    await ensureAssets();
    // A render can go stale while the CDN asset loads (artifact/viewer
    // switch): bail before any DOM work or viewer state is created.
    if (isStale && isStale()) return;
    var frame = format === "mmcif" ? parseCifAlphaCarbons(structureText) : parsePdbAlphaCarbons(structureText);
    if (frame.coords.length < 2) throw new Error("Structure has fewer than two C-alpha atoms");
    var viewerId = "py2dmol-" + Math.random().toString(36).slice(2);
    var inner = document.createElement("div");
    inner.id = viewerId;
    inner.className = "py2dmol-fallback";
    inner.innerHTML = py2DmolMarkup();
    container.appendChild(inner);
    window.py2dmol_staticData = window.py2dmol_staticData || {};
    window.py2dmol_configs = window.py2dmol_configs || {};
    window.py2dmol_staticData[viewerId] = [{ name: label || "structure", frames: [frame], chains: frame.chains, position_types: frame.position_types }];
    window.py2dmol_configs[viewerId] = {
      viewer_id: viewerId,
      display: { size: size, rotate: false, autoplay: false, controls: true, box: true },
      rendering: { shadow: true, outline: "full", width: 3, ortho: 1, detect_cyclic: true },
      color: { mode: "auto", colorblind: false }, pae: { enabled: false }, scatter: { enabled: false }, overlay: { enabled: false }
    };
    window.initializePy2DmolViewer(inner, viewerId);
  }

  window.REvoDesignPy2Dmol = {
    ensureAssets: ensureAssets,
    renderAlphaTrace: renderAlphaTrace,
    parsePdbAlphaCarbons: parsePdbAlphaCarbons,
    parseCifAlphaCarbons: parseCifAlphaCarbons
  };
})();
