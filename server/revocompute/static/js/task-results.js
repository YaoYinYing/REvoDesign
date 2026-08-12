/* REvoCompute — dedicated manifest-first task result workspace */
/* SPDX-License-Identifier: GPL-3.0-only */

(function () {
  "use strict";
  var A = window.REvoDesignAuth;
  var T = window.REvoDesignTheme;
  var task = window.__RESULT_TASK__;
  var artifacts = [];
  var activeArtifact = null;
  var molstarAssetsPromise = null;
  var py2dmolAssetsPromise = null;
  var activeMolstar = null;
  var thumbnailUrls = [];
  var previewRegistry = null;
  var previewHost = null;
  var MOLSTAR_VERSION = "5.10.0";
  var MOLSTAR_BASE = "https://cdn.jsdelivr.net/npm/molstar@" + MOLSTAR_VERSION + "/build/viewer/";
  var MOLSTAR_SCRIPT_INTEGRITY = "sha384-wBsrlRYNnkOyq4/N6JHjLcT71I5Ig8DhryHsQpwXE91zRmy3XK6KhkxqixmT1S0n";
  var MOLSTAR_STYLE_INTEGRITY = "sha384-RIontCdJN53gEl2fmiHN+4bscIBvaUaOiCeeGktXqmFqdEBF+COnSdt9O4IKFSvq";
  var PY2DMOL_COMMIT = "8c95fd9efae6007e124e143cd276244d89228c66";
  var PY2DMOL_SCRIPT = "https://cdn.jsdelivr.net/gh/sokrypton/py2Dmol@" + PY2DMOL_COMMIT + "/py2Dmol/resources/viewer-mol.js";
  var PY2DMOL_SCRIPT_INTEGRITY = "sha384-D1ju7xD5hbkOLM/oKtegpq8TrkqDFUXPce3GrP3xoELqjLtbfi1CMMbWtx7PDfZH";

  function formatBytes(value) {
    var bytes = Number(value || 0);
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KiB";
    if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + " MiB";
    return (bytes / (1024 * 1024 * 1024)).toFixed(2) + " GiB";
  }

  function showToast(message, type) {
    var node = document.createElement("div");
    node.className = "toast " + (type || "info");
    node.textContent = message;
    document.getElementById("toastWrap").appendChild(node);
    setTimeout(function () { node.remove(); }, 3600);
  }

  function disposeActiveViewer() {
    if (activeMolstar && activeMolstar.plugin) activeMolstar.plugin.dispose();
    activeMolstar = null;
  }

  function ensureMolstarAssets() {
    if (window.molstar && window.molstar.Viewer) return Promise.resolve(window.molstar);
    if (molstarAssetsPromise) return molstarAssetsPromise;
    molstarAssetsPromise = new Promise(function (resolve, reject) {
      if (!document.querySelector("link[data-molstar-style]")) {
        var style = document.createElement("link");
        style.rel = "stylesheet";
        style.href = MOLSTAR_BASE + "molstar.css";
        style.integrity = MOLSTAR_STYLE_INTEGRITY;
        style.crossOrigin = "anonymous";
        style.dataset.molstarStyle = MOLSTAR_VERSION;
        document.head.appendChild(style);
      }
      var script = document.createElement("script");
      script.src = MOLSTAR_BASE + "molstar.js";
      script.integrity = MOLSTAR_SCRIPT_INTEGRITY;
      script.crossOrigin = "anonymous";
      script.dataset.molstarScript = MOLSTAR_VERSION;
      script.addEventListener("load", function () {
        if (window.molstar && window.molstar.Viewer) resolve(window.molstar);
        else reject(new Error("Mol* did not initialize"));
      }, { once: true });
      script.addEventListener("error", function () { reject(new Error("Mol* could not be loaded")); }, { once: true });
      document.head.appendChild(script);
    }).catch(function (error) { molstarAssetsPromise = null; throw error; });
    return molstarAssetsPromise;
  }

  function structureFormat(path) {
    var lower = String(path).toLowerCase();
    return lower.endsWith(".cif") || lower.endsWith(".mmcif") ? "mmcif" : "pdb";
  }

  function ensurePy2DmolAssets() {
    if (window.initializePy2DmolViewer) return Promise.resolve();
    if (py2dmolAssetsPromise) return py2dmolAssetsPromise;
    py2dmolAssetsPromise = new Promise(function (resolve, reject) {
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
    }).catch(function (error) { py2dmolAssetsPromise = null; throw error; });
    return py2dmolAssetsPromise;
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

  async function renderPy2DmolFallback(structureText, artifact, stage, molstarError) {
    await ensurePy2DmolAssets();
    var frame = structureFormat(artifact.path) === "mmcif" ? parseCifAlphaCarbons(structureText) : parsePdbAlphaCarbons(structureText);
    if (frame.coords.length < 2) throw molstarError;
    var viewerId = "py2dmol-result-" + Math.random().toString(36).slice(2);
    var container = document.createElement("div");
    container.id = viewerId;
    container.className = "py2dmol-fallback";
    container.innerHTML = py2DmolMarkup();
    stage.appendChild(container);
    window.py2dmol_staticData = window.py2dmol_staticData || {};
    window.py2dmol_configs = window.py2dmol_configs || {};
    window.py2dmol_staticData[viewerId] = [{ name: artifact.path, frames: [frame], chains: frame.chains, position_types: frame.position_types }];
    window.py2dmol_configs[viewerId] = {
      viewer_id: viewerId,
      display: { size: [Math.max(320, Math.min(stage.clientWidth - 220, 900)), 560], rotate: false, autoplay: false, controls: true, box: true },
      rendering: { shadow: true, outline: "full", width: 3, ortho: 1, detect_cyclic: true },
      color: { mode: "auto", colorblind: false }, pae: { enabled: false }, scatter: { enabled: false }, overlay: { enabled: false }
    };
    window.initializePy2DmolViewer(container, viewerId);
    var note = document.createElement("p");
    note.className = "preview-message py2dmol-note";
    note.textContent = "Mol* was unavailable; showing the interactive py2Dmol alpha-trace fallback.";
    stage.appendChild(note);
  }

  // ponytail: current viewer choice per artifact — kept simple (no global
  // preference store).  Resets when the user selects a different artifact.
  var structureViewer = "molstar";

  function setMolstarColor(mode) {
    if (!activeMolstar || !activeMolstar.plugin) return;
    try {
      var component = activeMolstar.plugin.managers.structure.component;
      var themes = { plddt: "b-factor", chain: "chain-id", rainbow: "residue-index" };
      var themeName = themes[mode] || mode;
      component.updateRepresentationsTheme({ color: { name: themeName, params: {} } });
    } catch (e) { /* non-critical — Mol* built-in panel has these controls */ }
  }

  function structureViewerBar(artifact) {
    var bar = document.createElement("div");
    bar.className = "structure-viewer-bar";
    var makeBtn = function (label, viewer) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "viewer-toggle" + (structureViewer === viewer ? " active" : "");
      btn.textContent = label;
      btn.addEventListener("click", function () { structureViewer = viewer; previewArtifact(artifact); });
      return btn;
    };
    bar.append(makeBtn("Mol* (full)", "molstar"), makeBtn("py2Dmol (alpha)", "py2dmol"));
    var colorBar = document.createElement("div");
    colorBar.className = "structure-color-bar";
    [{ mode: "plddt", label: "pLDDT" }, { mode: "chain", label: "Chain" }, { mode: "rainbow", label: "Rainbow" }].forEach(function (c) {
      var btn = document.createElement("button");
      btn.type = "button"; btn.className = "color-toggle"; btn.textContent = c.label;
      btn.addEventListener("click", function () { setMolstarColor(c.mode); });
      colorBar.appendChild(btn);
    });
    bar.appendChild(colorBar);
    return bar;
  }

  async function renderMolstar(structureText, artifact, stage) {
    var molstar = await ensureMolstarAssets();
    var target = document.createElement("div");
    target.className = "artifact-molstar-preview";
    target.id = "molstar-result-" + Math.random().toString(36).slice(2);
    stage.appendChild(target);
    activeMolstar = await molstar.Viewer.create(target.id, {
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
    await activeMolstar.loadStructureFromData(structureText, structureFormat(artifact.path), { label: artifact.path });
  }

  async function previewStructure(artifact, stage) {
    var response = await A.authFetch(artifact.url);
    if (!response.ok) throw new Error("Structure download failed (HTTP " + response.status + ")");
    var structureText = await response.text();
    stage.appendChild(structureViewerBar(artifact));

    if (structureViewer === "py2dmol") {
      try { await renderPy2DmolFallback(structureText, artifact, stage, new Error("User selected alpha-trace viewer")); }
      catch (e) {
        var unavailableMsg = document.createElement("p");
        unavailableMsg.className = "preview-message";
        unavailableMsg.textContent = "py2Dmol unavailable. Download the structure file to inspect it locally.";
        stage.appendChild(unavailableMsg);
      }
      return;
    }

    try { await renderMolstar(structureText, artifact, stage); }
    catch (error) {
      stage.replaceChildren();
      stage.appendChild(structureViewerBar(artifact));
      var msg = document.createElement("p");
      msg.className = "preview-message";
      msg.textContent = "Mol* could not be loaded. ";
      var retry = document.createElement("button");
      retry.type = "button";
      retry.className = "btn btn-soft btn-small";
      retry.textContent = "Open with py2Dmol (alpha-trace)";
      retry.type = "button";
      retry.addEventListener("click", function () { structureViewer = "py2dmol"; previewArtifact(artifact); });
      msg.appendChild(retry);
      stage.appendChild(msg);
    }
  }

  function parseDelimited(text, delimiter) {
    var rows = [];
    String(text).split(/\r?\n/).slice(0, 101).forEach(function (line) {
      if (line) rows.push(line.split(delimiter).slice(0, 50));
    });
    return rows;
  }

  function renderTable(text, artifact, stage) {
    var rows = parseDelimited(text, artifact.path.toLowerCase().endsWith(".tsv") ? "\t" : ",");
    if (!rows.length) { stage.innerHTML = '<p class="preview-message">This table is empty.</p>'; return; }
    var wrap = document.createElement("div");
    wrap.className = "artifact-table-wrap";
    var table = document.createElement("table");
    table.className = "artifact-table-preview";
    rows.forEach(function (row, rowIndex) {
      var tr = document.createElement("tr");
      row.forEach(function (value) {
        var cell = document.createElement(rowIndex === 0 ? "th" : "td");
        cell.textContent = value;
        tr.appendChild(cell);
      });
      table.appendChild(tr);
    });
    wrap.appendChild(table);
    stage.appendChild(wrap);
  }

  async function previewImage(artifact, stage) {
    var response = await A.authFetch(artifact.url);
    if (!response.ok) throw new Error("Image download failed");
    var objectUrl = URL.createObjectURL(await response.blob());
    var image = document.createElement("img");
    image.className = "artifact-image-preview";
    image.alt = artifact.path;
    image.src = objectUrl;
    image.addEventListener("load", function () { URL.revokeObjectURL(objectUrl); }, { once: true });
    image.addEventListener("error", function () { URL.revokeObjectURL(objectUrl); }, { once: true });
    stage.appendChild(image);
  }

  function isMsaFile(path) {
    var ext = String(path || "").toLowerCase();
    return /\.(a3m|aln|fa|faa|fasta|sto)$/.test(ext);
  }

  // Zappo/Clustal residue color scheme
  var RESIDUE_COLORS = {
    A: "#80a0f0", I: "#80a0f0", L: "#80a0f0", M: "#80a0f0", F: "#80a0f0", W: "#80a0f0", V: "#80a0f0", // hydrophobic
    K: "#f01505", R: "#f01505",                                                                         // positive
    D: "#c048c0", E: "#c048c0",                                                                         // negative
    N: "#15c015", Q: "#15c015", S: "#15c015", T: "#15c015",                                             // polar
    C: "#f08080",                                                                                       // cysteine
    G: "#f09048",                                                                                       // glycine
    P: "#c0c000",                                                                                       // proline
    H: "#15a4a4", Y: "#15a4a4",                                                                         // aromatic
    "-": "#c0c0c0", ".": "#c0c0c0"                                                                      // gap
  };

  function renderMsa(text, stage) {
    var wrapper = document.createElement("div");
    wrapper.className = "msa-viewer";
    var lines = String(text).split(/\r?\n/);
    var block = document.createElement("div");
    block.className = "msa-block";
    var lineCount = 0;
    lines.forEach(function (line) {
      if (lineCount >= 5000) return;
      var trimmed = line.trimEnd();
      if (trimmed.startsWith(">") || trimmed.startsWith("#")) {
        var headerSpan = document.createElement("span");
        headerSpan.className = "msa-header";
        headerSpan.textContent = trimmed;
        block.appendChild(headerSpan);
      } else if (trimmed) {
        var seqSpan = document.createElement("span");
        seqSpan.className = "msa-sequence";
        for (var i = 0; i < trimmed.length; i++) {
          var char = trimmed[i].toUpperCase();
          var span = document.createElement("span");
          span.textContent = trimmed[i];
          span.style.color = RESIDUE_COLORS[char] || "inherit";
          seqSpan.appendChild(span);
        }
        block.appendChild(seqSpan);
      } else {
        block.appendChild(document.createElement("br"));
      }
      lineCount += 1;
    });
    if (lines.length > 5000) block.appendChild(document.createTextNode("\n\n[Preview truncated at 5000 lines]"));
    wrapper.appendChild(block);
    stage.appendChild(wrapper);
  }

  async function previewText(artifact, stage) {
    var response = await A.authFetch(artifact.url, { headers: { Range: "bytes=0-262143" } });
    if (!response.ok && response.status !== 206) throw new Error("Text preview download failed");
    var text = await response.text();
    if (isMsaFile(artifact.path)) {
      renderMsa(text, stage);
      return;
    }
    var pre = document.createElement("pre");
    pre.textContent = text + (artifact.size > 262144 ? "\n\n[Preview truncated at 256 KiB]" : "");
    stage.appendChild(pre);
  }

  async function previewTable(artifact, stage) {
    var response = await A.authFetch(artifact.url, { headers: { Range: "bytes=0-262143" } });
    if (!response.ok && response.status !== 206) throw new Error("Table preview download failed");
    renderTable(await response.text(), artifact, stage);
  }

  previewRegistry = window.REvoComputeResultPreviews.createRegistry({
    structure: previewStructure,
    image: previewImage,
    table: previewTable,
    text: previewText
  });
  previewHost = new window.REvoComputeResultPreviews.ResultPreviewHost(
    previewRegistry,
    document.getElementById("artifactPreview"),
    { beforeClear: disposeActiveViewer }
  );

  async function previewArtifact(artifact) {
    activeArtifact = artifact;
    previewHost.destroy();
    document.getElementById("previewTitle").textContent = artifact.path;
    var download = document.getElementById("artifactDownload");
    download.hidden = false;
    download.href = artifact.url + "?download=1";
    download.download = "";
    document.querySelectorAll(".artifact-row").forEach(function (node) {
      node.classList.toggle("active", node.dataset.path === artifact.path);
    });
    var stage = document.getElementById("artifactPreview");
    var plugin = previewRegistry.resolve(artifact);
    if (!plugin) {
      stage.innerHTML = '<p class="preview-message">No inline preview is available for this file type. Download the artifact instead.</p>';
      return;
    }
    if (plugin.maxBytes && artifact.size > plugin.maxBytes) {
      stage.innerHTML = '<p class="preview-message">This file exceeds the safe inline preview limit. Download it instead.</p>';
      return;
    }
    stage.innerHTML = '<p class="preview-message">Loading preview…</p>';
    try {
      stage.replaceChildren();
      await previewHost.render(artifact);
    } catch (error) {
      stage.innerHTML = '<p class="preview-message"></p>';
      stage.firstChild.textContent = error.message || "Preview unavailable";
    }
  }

  function artifactButton(artifact) {
    var button = document.createElement("button");
    button.type = "button";
    button.className = "artifact-row";
    button.dataset.path = artifact.path;
    var name = document.createElement("span");
    name.className = "artifact-row-name";
    name.textContent = artifact.path;
    var size = document.createElement("span");
    size.className = "artifact-row-size";
    size.textContent = (artifact.role === "diagnostic" ? "Execution log · " : "") + formatBytes(artifact.size);
    button.append(name, size);
    button.addEventListener("click", function () { previewArtifact(artifact); });
    return button;
  }

  function renderArtifacts(query) {
    var normalized = String(query || "").trim().toLowerCase();
    var list = document.getElementById("artifactList");
    list.replaceChildren();
    artifacts.filter(function (artifact) { return !normalized || artifact.path.toLowerCase().includes(normalized); })
      .forEach(function (artifact) { list.appendChild(artifactButton(artifact)); });
  }

  async function loadImageThumbnail(artifact, frame) {
    if (artifact.size > 4 * 1024 * 1024) {
      frame.textContent = "IMAGE";
      return;
    }
    try {
      var response = await A.authFetch(artifact.url);
      if (!response.ok) throw new Error("Thumbnail unavailable");
      var objectUrl = URL.createObjectURL(await response.blob());
      thumbnailUrls.push(objectUrl);
      var image = document.createElement("img");
      image.alt = "Preview of " + artifact.path;
      image.loading = "lazy";
      image.src = objectUrl;
      frame.replaceChildren(image);
    } catch (error) {
      frame.textContent = "IMAGE";
    }
  }

  function renderMainResults() {
    var main = document.getElementById("mainResults");
    thumbnailUrls.forEach(function (url) { URL.revokeObjectURL(url); });
    thumbnailUrls = [];
    main.replaceChildren();
    artifacts.filter(function (artifact) {
      return Boolean(artifact.preview) && artifact.role !== "diagnostic";
    }).forEach(function (artifact) {
      var card = document.createElement("button");
      card.type = "button";
      card.className = "main-result-card main-result-" + artifact.preview;
      card.setAttribute("aria-label", "Preview " + artifact.path);
      var frame = document.createElement("span");
      frame.className = "main-result-frame";
      frame.textContent = artifact.preview === "structure" ? "3D" : artifact.preview.toUpperCase();
      var name = document.createElement("strong");
      name.textContent = artifact.path;
      var detail = document.createElement("span");
      var plugin = previewRegistry.resolve(artifact);
      detail.textContent = (plugin ? plugin.label : artifact.preview) + " · " + formatBytes(artifact.size);
      card.append(frame, name, detail);
      card.addEventListener("click", function () { previewArtifact(artifact); });
      main.appendChild(card);
      if (artifact.preview === "image") loadImageThumbnail(artifact, frame);
    });
  }

  async function loadResults() {
    var response = await A.authFetch("/compute/api/results/" + encodeURIComponent(task.md5));
    var payload = await response.json().catch(function () { return {}; });
    document.getElementById("resultStatus").textContent = payload.status || task.status;
    if (!response.ok || !Array.isArray(payload.artifacts)) {
      throw new Error(payload.message || "Results are not available yet");
    }
    artifacts = payload.artifacts;
    document.getElementById("resultFileCount").textContent = artifacts.length;
    document.getElementById("resultTotalSize").textContent = formatBytes(payload.total_size);
    var archiveButton = document.getElementById("archiveButton");
    if (payload.archive && payload.archive.ready) {
      archiveButton.textContent = "Download ZIP";
      archiveButton.dataset.downloadUrl = payload.archive.download_url;
      document.getElementById("archiveState").textContent = "The optional manifest-approved ZIP is ready.";
    }
    renderArtifacts("");
    renderMainResults();
    var first = artifacts.find(function (artifact) { return Boolean(artifact.preview); });
    if (first && !activeArtifact) previewArtifact(first);
  }

  async function archiveAction() {
    var button = document.getElementById("archiveButton");
    if (button.dataset.downloadUrl) { window.location.assign(button.dataset.downloadUrl); return; }
    button.disabled = true;
    try {
      var response = await A.authFetch("/compute/api/results/" + encodeURIComponent(task.md5) + "/archive", { method: "POST" });
      var payload = await response.json().catch(function () { return {}; });
      if (!response.ok && response.status !== 202) throw new Error(payload.error || "Archive request failed");
      document.getElementById("archiveState").textContent = "Archive generation requested. Refresh shortly to download it.";
      showToast("Archive generation requested.", "info");
    } catch (error) { showToast(error.message || "Archive request failed", "error"); }
    finally { button.disabled = false; }
  }

  document.addEventListener("DOMContentLoaded", function () {
    T.initToggle(document.getElementById("themeToggle"));
    document.getElementById("refreshResults").addEventListener("click", function () { window.location.reload(); });
    document.getElementById("artifactSearch").addEventListener("input", function (event) { renderArtifacts(event.target.value); });
    document.getElementById("archiveButton").addEventListener("click", archiveAction);

    // Space to preview (macOS Finder Quick Look), Escape to close
    document.addEventListener("keydown", function (event) {
      if (event.target.tagName === "INPUT" || event.target.tagName === "TEXTAREA") return;
      if (event.key === " " || event.code === "Space") {
        event.preventDefault();
        if (activeArtifact) { activeArtifact = null; previewHost.destroy(); return; }
        var first = artifacts.find(function (a) { return Boolean(a.preview); });
        if (first) previewArtifact(first);
      }
      if (event.key === "Escape" && activeArtifact) {
        event.preventDefault();
        activeArtifact = null;
        previewHost.destroy();
        document.getElementById("previewTitle").textContent = "";
        document.getElementById("artifactDownload").hidden = true;
        document.querySelectorAll(".artifact-row.active").forEach(function (r) { r.classList.remove("active"); });
      }
    });

    loadResults().catch(function (error) {
      document.getElementById("artifactPreview").innerHTML = '<p class="preview-message"></p>';
      document.getElementById("artifactPreview").firstChild.textContent = error.message || "Results unavailable";
    });
  });
  window.addEventListener("pagehide", function () {
    previewHost.destroy();
    thumbnailUrls.forEach(function (url) { URL.revokeObjectURL(url); });
  });
})();
