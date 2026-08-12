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
        supports: function (artifact) { return artifact && artifact.preview === definition.id; },
        render: renderers[definition.id]
      });
    });
    return registry;
  }

  function ResultPreviewHost(registry, stage, services) {
    this.registry = registry; this.stage = stage; this.services = services || {}; this.active = null;
    this.generation = 0;
  }

  ResultPreviewHost.prototype.render = async function (artifact) {
    this.destroy();
    var plugin = this.registry.resolve(artifact, this.services);
    if (!plugin) throw new Error("No inline preview is available for this file type.");
    if (plugin.maxBytes && Number(artifact.size || 0) > plugin.maxBytes) {
      throw new Error("This file exceeds the safe inline preview limit. Download it instead.");
    }
    var generation = this.generation;
    var surface = document.createElement("div");
    surface.className = "result-plugin-surface";
    this.stage.appendChild(surface);
    this.active = plugin;
    await plugin.render(artifact, surface, this.services);
    if (generation !== this.generation) surface.remove();
    return plugin;
  };

  ResultPreviewHost.prototype.destroy = function () {
    this.generation += 1;
    if (this.active && typeof this.active.destroy === "function") this.active.destroy(this.services);
    if (this.services.beforeClear) this.services.beforeClear();
    this.active = null; this.stage.replaceChildren();
  };

  global.REvoComputeResultPreviews = Object.freeze({
    createRegistry: createRegistry,
    ResultPreviewHost: ResultPreviewHost
  });
})(window);
