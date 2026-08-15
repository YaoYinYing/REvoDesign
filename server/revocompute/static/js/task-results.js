/* REvoCompute — dedicated manifest-first task result workspace */
/* SPDX-License-Identifier: GPL-3.0-only */

(function () {
  "use strict";
  var A = window.REvoDesignAuth;
  var T = window.REvoDesignTheme;
  var task = JSON.parse(document.getElementById("result-task-data").textContent);
  var artifacts = [];
  var activeArtifact = null;
  var activeMolstar = null;
  var thumbnailUrls = [];
  var previewRegistry = null;
  var previewHost = null;
  var MOLSTAR_THEME_COOKIE = "revodesign-molstar-theme";
  // Mol* runs inside the isolated /compute/viewer-shell iframe (its bundle
  // needs new Function, which only that shell's CSP permits). All constants
  // and the asset loader live in viewer-shell.js.;

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

  // The shell iframe is sandboxed without allow-same-origin, so its origin
  // is opaque ("null") — postMessages must target the frame's own serialized
  // origin, never the parent's.
  function postToShell(frame, payload) {
    var targetOrigin = "*";
    try { targetOrigin = frame.contentWindow.origin || "*"; } catch (e) { /* frame gone */ }
    frame.contentWindow.postMessage(payload, targetOrigin);
  }

  function readMolstarTheme() {
    var prefix = MOLSTAR_THEME_COOKIE + "=";
    var value = document.cookie.split(";").map(function (part) { return part.trim(); }).find(function (part) {
      return part.startsWith(prefix);
    });
    return value && value.slice(prefix.length) === "dark" ? "dark" : "light";
  }

  function setMolstarTheme(theme) {
    var resolved = theme === "dark" ? "dark" : "light";
    var secure = location.protocol === "https:" ? "; Secure" : "";
    document.cookie = MOLSTAR_THEME_COOKIE + "=" + resolved + "; Path=/; Max-Age=31536000; SameSite=Lax" + secure;
    var frame = activeMolstar ? activeMolstar.frame : document.querySelector("iframe.artifact-molstar-preview");
    if (frame) postToShell(frame, { type: "theme", theme: resolved });
    document.querySelectorAll(".molstar-theme-toggle").forEach(function (button) {
      button.textContent = resolved === "dark" ? "☾" : "☀";
      button.setAttribute("aria-label", resolved === "dark" ? "Use light Mol* theme" : "Use dark Mol* theme");
      button.title = button.getAttribute("aria-label");
      button.setAttribute("aria-pressed", resolved === "dark" ? "true" : "false");
    });
  }

  function disposeActiveViewer() {
    if (activeMolstar) {
      try { postToShell(activeMolstar.frame, { type: "dispose" }); } catch (e) { /* frame gone */ }
      activeMolstar.frame.remove();
      activeMolstar = null;
    }
  }

  function structureFormat(path) {
    var lower = String(path).toLowerCase();
    return lower.endsWith(".cif") || lower.endsWith(".mmcif") ? "mmcif" : "pdb";
  }

  // Single-flight guard: every async render captures the host generation at
  // start and re-checks it after each await. A viewer toggle, artifact
  // switch, or destroy bumps the generation, so a stale Mol*/py2Dmol
  // continuation can never mount or load a file after its surface is gone —
  // the two viewers are never in flight for the same stage simultaneously.
  function isStale(generation) {
    return previewHost && previewHost.generation !== generation;
  }

  async function renderPy2DmolFallback(structureText, artifact, stage, generation, molstarError) {
    try {
      await window.REvoDesignPy2Dmol.renderAlphaTrace(
        stage,
        structureText,
        structureFormat(artifact.path),
        artifact.path,
        [Math.max(320, Math.min(stage.clientWidth - 220, 900)), 560],
        function () { return isStale(generation); }
      );
      if (isStale(generation)) return;
    } catch (error) {
      if (isStale(generation)) return;
      throw molstarError;
    }
    var note = document.createElement("p");
    note.className = "preview-message py2dmol-note";
    note.textContent = "Mol* was unavailable; showing the interactive py2Dmol alpha-trace fallback.";
    stage.appendChild(note);
  }

  // ponytail: current viewer choice per artifact — kept simple (no global
  // preference store).  Resets when the user selects a different artifact.
  var structureViewer = "molstar";

  var activeColorMode = "plddt";

  function setStructureColor(mode) {
    activeColorMode = mode;
    // Mol* backend — forward the mode into the isolated viewer shell
    if (activeMolstar) {
      try { postToShell(activeMolstar.frame, { type: "color", mode: mode }); } catch (e) { /* frame gone */ }
    }
    // py2Dmol backend — drive the existing color select in its right panel
    var colorSelect = document.querySelector(".py2dmol-fallback #colorSelect");
    if (colorSelect) {
      colorSelect.value = mode;
      colorSelect.dispatchEvent(new Event("change", { bubbles: true }));
    }
    // Highlight active color toggle
    document.querySelectorAll(".color-toggle").forEach(function (btn) {
      btn.classList.toggle("active", btn.dataset.mode === mode);
      btn.setAttribute("aria-pressed", btn.dataset.mode === mode ? "true" : "false");
    });
  }

  function structureViewerBar(artifact) {
    var bar = document.createElement("div");
    bar.className = "structure-viewer-bar";
    bar.setAttribute("role", "toolbar");
    bar.setAttribute("aria-label", "Structure viewer controls");
    var makeBtn = function (label, viewer) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "viewer-toggle" + (structureViewer === viewer ? " active" : "");
      btn.textContent = label;
      btn.setAttribute("aria-pressed", structureViewer === viewer ? "true" : "false");
      btn.addEventListener("click", function () { structureViewer = viewer; previewArtifact(artifact); });
      return btn;
    };
    bar.append(makeBtn("Mol* (full)", "molstar"), makeBtn("py2Dmol (alpha)", "py2dmol"));
    var colorBar = document.createElement("div");
    colorBar.className = "structure-color-bar";
    colorBar.setAttribute("role", "group");
    colorBar.setAttribute("aria-label", "Structure color theme");
    [{ mode: "plddt", label: "pLDDT" }, { mode: "chain", label: "Chain" }, { mode: "rainbow", label: "Rainbow" }].forEach(function (c) {
      var btn = document.createElement("button");
      btn.type = "button"; btn.className = "color-toggle"; btn.textContent = c.label; btn.dataset.mode = c.mode;
      if (activeColorMode === c.mode) btn.classList.add("active");
      btn.setAttribute("aria-pressed", activeColorMode === c.mode ? "true" : "false");
      btn.addEventListener("click", function () { setStructureColor(c.mode); });
    colorBar.appendChild(btn);
    });
    bar.appendChild(colorBar);
    var themeButton = document.createElement("button");
    themeButton.type = "button";
    themeButton.className = "molstar-theme-toggle";
    themeButton.addEventListener("click", function () {
      setMolstarTheme(readMolstarTheme() === "dark" ? "light" : "dark");
    });
    bar.appendChild(themeButton);
    setTimeout(function () { setMolstarTheme(readMolstarTheme()); }, 0);
    return bar;
  }

  async function renderMolstar(structureText, artifact, stage, generation) {
    var requestId = "mol-" + Math.random().toString(36).slice(2);
    var frame = document.createElement("iframe");
    frame.className = "artifact-molstar-preview";
    frame.sandbox = "allow-scripts";
    frame.title = "Mol* structure viewer";
    // Register the handshake listener before the iframe starts loading so
    // the shell's "shell-ready" can never be missed.
    var handshake = new Promise(function (resolve, reject) {
      var settled = false;
      var timer = setTimeout(function () {
        if (settled) return;
        settled = true;
        window.removeEventListener("message", onMessage);
        reject(new Error("Mol* timed out"));
      }, 45000);
      function onMessage(event) {
        // The sandboxed shell has an opaque origin, so its messages carry
        // origin "null" — the source check against our own frame is the
        // real gate.
        if ((event.origin !== location.origin && event.origin !== "null") || event.source !== frame.contentWindow || !event.data) return;
        if (event.data.type === "shell-ready") {
          postToShell(frame, {
            type: "structure",
            text: structureText,
            format: structureFormat(artifact.path),
            label: artifact.path,
            requestId: requestId,
            theme: readMolstarTheme(),
            colorMode: activeColorMode
          });
        } else if (event.data.type === "ready" && event.data.requestId === requestId) {
          if (settled) return;
          settled = true;
          clearTimeout(timer);
          window.removeEventListener("message", onMessage);
          resolve(frame);
        } else if (event.data.type === "error" && event.data.requestId === requestId) {
          if (settled) return;
          settled = true;
          clearTimeout(timer);
          window.removeEventListener("message", onMessage);
          reject(new Error(event.data.message));
        }
      }
      window.addEventListener("message", onMessage);
    });
    stage.appendChild(frame);
    frame.src = "/compute/viewer-shell";
    if (isStale(generation)) { frame.remove(); return; }
    await handshake;
    if (isStale(generation)) { frame.remove(); return; }
    activeMolstar = { frame: frame };
  }

  async function previewStructure(artifact, stage) {
    var generation = previewHost.generation;
    var response = await A.authFetch(artifact.url);
    if (isStale(generation)) return;
    if (!response.ok) throw new Error("Structure download failed (HTTP " + response.status + ")");
    var structureText = await response.text();
    if (isStale(generation)) return;
    stage.appendChild(structureViewerBar(artifact));

    if (structureViewer === "py2dmol") {
      try {
        await renderPy2DmolFallback(structureText, artifact, stage, generation, new Error("User selected alpha-trace viewer"));
        if (isStale(generation)) return;
        setTimeout(function () { if (!isStale(generation)) setStructureColor(activeColorMode); }, 100);
      }
      catch (e) {
        if (isStale(generation)) return;
        var unavailableMsg = document.createElement("p");
        unavailableMsg.className = "preview-message";
        unavailableMsg.textContent = "py2Dmol unavailable. Download the structure file to inspect it locally.";
        stage.appendChild(unavailableMsg);
      }
      return;
    }

    try { await renderMolstar(structureText, artifact, stage, generation); }
    catch (error) {
      if (isStale(generation)) return;
      stage.replaceChildren();
      stage.appendChild(structureViewerBar(artifact));
      var msg = document.createElement("p");
      msg.className = "preview-message";
      msg.textContent = "Mol* could not be loaded: " + (error.message || error);
      var br = document.createElement("br");
      var retry = document.createElement("button");
      retry.type = "button";
      retry.className = "btn btn-soft btn-small";
      retry.textContent = "Open with py2Dmol (alpha-trace)";
      retry.type = "button";
      retry.addEventListener("click", function () { structureViewer = "py2dmol"; previewArtifact(artifact); });
      msg.append(br, retry);
      stage.appendChild(msg);
      console.warn("Mol* error:", error);
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

  function artifactFolder(directory, children) {
    var folder = document.createElement("details");
    folder.className = "artifact-folder";
    folder.open = true;
    var summary = document.createElement("summary");
    summary.className = "artifact-folder-name";
    summary.textContent = directory + "/";
    folder.appendChild(summary);
    var inner = document.createElement("div");
    inner.className = "artifact-folder-children";
    children.forEach(function (child) { inner.appendChild(child); });
    folder.appendChild(inner);
    return folder;
  }

  function buildArtifactTree() {
    var root = { folders: {}, files: [] };
    artifacts.forEach(function (artifact) {
      var node = root;
      artifact.path.split("/").slice(0, -1).forEach(function (segment) {
        node.folders[segment] = node.folders[segment] || { folders: {}, files: [] };
        node = node.folders[segment];
      });
      node.files.push(artifact);
    });
    function renderNode(node) {
      var entries = [];
      Object.keys(node.folders).sort().forEach(function (name) {
        entries.push(artifactFolder(name, renderNode(node.folders[name])));
      });
      node.files.slice().sort(function (a, b) { return a.path < b.path ? -1 : 1; })
        .forEach(function (artifact) { entries.push(artifactButton(artifact)); });
      return entries;
    }
    return renderNode(root);
  }

  function renderArtifacts(query) {
    var normalized = String(query || "").trim().toLowerCase();
    var list = document.getElementById("artifactList");
    list.replaceChildren();
    if (normalized) {
      // Search shows a flat result list — a collapsed tree would hide matches.
      artifacts.filter(function (artifact) { return artifact.path.toLowerCase().includes(normalized); })
        .forEach(function (artifact) { list.appendChild(artifactButton(artifact)); });
      return;
    }
    buildArtifactTree().forEach(function (node) { list.appendChild(node); });
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
