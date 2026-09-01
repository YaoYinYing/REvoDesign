/* REvoCompute — manifest result preview plugin registry */
/* SPDX-License-Identifier: GPL-3.0-only */

(function (global) {
  "use strict";
  var Core = global.REvoComputePlugins;
  if (!Core) throw new Error("plugin-host.js must be loaded before result-preview-plugins.js");

  function createRegistry(renderers) {
    var registry = new Core.PluginRegistry("result preview");
    [
      { id: "structure", label: "3D structure", maxBytes: 64 * 1024 * 1024 },
      { id: "image", label: "Image", maxBytes: 32 * 1024 * 1024 },
      { id: "table", label: "Table", maxBytes: null },
      { id: "text", label: "Text", maxBytes: null }
    ].forEach(function (definition) {
      registry.register({
        id: definition.id,
        label: definition.label,
        maxBytes: definition.maxBytes,
        supports: function (artifact) { return artifact && !artifact.plugin && artifact.preview === definition.id; },
        render: renderers[definition.id]
      });
    });
    [
      "candidate-collection", "entity-table", "evidence-bundle", "alignment",
      "trajectory", "metric-series", "matrix", "scalar-summary"
    ].forEach(function (id) {
      if (typeof renderers[id] === "function") registry.register({ id: id, label: id, maxBytes: null, render: renderers[id] });
    });
    return registry;
  }

  function ResultPreviewHost(registry, stage, services) {
    this.registry = registry;
    this.stage = stage;
    this.services = services || {};
    this.active = null;
    this.controller = null;
    this.generation = 0;
  }

  ResultPreviewHost.prototype.render = async function (subject, context) {
    this.destroy();
    var plugin = this.registry.resolve(subject, context || this.services);
    if (!plugin) throw new Error("No inline preview is available for this result.");
    if (plugin.maxBytes && Number(subject.size || 0) > plugin.maxBytes) {
      throw new Error("This file exceeds the safe inline preview limit. Download it instead.");
    }
    var generation = this.generation;
    var controller = new AbortController();
    var surface = document.createElement("div");
    surface.className = "result-plugin-surface";
    this.stage.setAttribute("aria-busy", "true");
    this.stage.appendChild(surface);
    this.controller = controller;
    this.active = { plugin: plugin, instance: null };
    var services = Object.assign({}, this.services, context || {}, { signal: controller.signal });
    if (this.services.statusNode) this.services.statusNode.textContent = "Loading result…";
    try {
      var instance = await plugin.render(subject, surface, services);
      if (generation !== this.generation) {
        if (instance && typeof instance.destroy === "function") instance.destroy();
        surface.remove();
        return null;
      }
      this.active.instance = instance || null;
      if (this.services.statusNode) this.services.statusNode.textContent = "Result loaded.";
      return plugin;
    } catch (error) {
      if (generation !== this.generation || controller.signal.aborted) return null;
      throw error;
    } finally {
      if (generation === this.generation) this.stage.setAttribute("aria-busy", "false");
    }
  };

  ResultPreviewHost.prototype.destroy = function () {
    this.generation += 1;
    if (this.controller) this.controller.abort();
    if (this.active && this.active.instance && typeof this.active.instance.destroy === "function") {
      this.active.instance.destroy();
    }
    if (this.services.beforeClear) this.services.beforeClear();
    this.controller = null;
    this.active = null;
    this.stage.replaceChildren();
    this.stage.setAttribute("aria-busy", "false");
  };

  global.REvoComputeResultPreviews = Object.freeze({
    createRegistry: createRegistry,
    ResultPreviewHost: ResultPreviewHost,
    FileViewerRegistry: createRegistry,
    FileViewerHost: ResultPreviewHost
  });
})(window);
