/* REvoCompute — local capability plugin registry and lifecycle host */
/* SPDX-License-Identifier: GPL-3.0-only */

(function (global) {
  "use strict";

  function PluginRegistry(kind) {
    this.kind = kind;
    this.plugins = new Map();
  }

  PluginRegistry.prototype.register = function (plugin) {
    if (!plugin || typeof plugin.id !== "string" || !plugin.id) {
      throw new TypeError(this.kind + " plugin requires a non-empty id");
    }
    if (this.plugins.has(plugin.id)) {
      throw new Error("Duplicate " + this.kind + " plugin: " + plugin.id);
    }
    if (typeof plugin.mount !== "function" && typeof plugin.render !== "function") {
      throw new TypeError(this.kind + " plugin " + plugin.id + " requires mount() or render()");
    }
    this.plugins.set(plugin.id, Object.freeze(plugin));
    return this;
  };

  PluginRegistry.prototype.get = function (id) {
    return this.plugins.get(id) || null;
  };

  PluginRegistry.prototype.resolve = function (subject, context) {
    var direct = subject && subject.plugin ? this.get(subject.plugin) : null;
    if (direct) return direct;
    var resolved = null;
    this.plugins.forEach(function (plugin) {
      if (!resolved && typeof plugin.supports === "function" && plugin.supports(subject, context)) {
        resolved = plugin;
      }
    });
    return resolved;
  };

  function PluginHost(registry, root, services) {
    this.registry = registry;
    this.root = root;
    this.services = services || {};
    this.instances = [];
  }

  PluginHost.prototype.mount = function (definitions, context) {
    this.destroy();
    var host = this;
    (definitions || []).forEach(function (definition) {
      var plugin = host.registry.resolve(definition, context);
      if (!plugin) {
        if (host.services.onUnsupported) host.services.onUnsupported(definition);
        return;
      }
      var target = host.services.createTarget
        ? host.services.createTarget(definition, plugin)
        : host.root;
      var instance = plugin.mount(target, definition, context, host.services) || {};
      host.instances.push({ definition: definition, plugin: plugin, instance: instance, target: target });
    });
    return this.instances;
  };

  PluginHost.prototype.collect = function () {
    var values = {};
    this.instances.forEach(function (mounted) {
      if (typeof mounted.instance.readValue !== "function") return;
      try { values[mounted.definition.id] = mounted.instance.readValue(); }
      catch (error) { values[mounted.definition.id] = null; }
    });
    return values;
  };

  PluginHost.prototype.validate = function () {
    var errors = [];
    this.instances.forEach(function (mounted) {
      if (typeof mounted.instance.validate !== "function") return;
      try {
        var result = mounted.instance.validate();
        if (Array.isArray(result)) errors.push.apply(errors, result);
        else if (result) errors.push(result);
      } catch (error) { errors.push(mounted.plugin.id + ": " + error.message); }
    });
    return errors;
  };

  PluginHost.prototype.refresh = function () {
    this.instances.forEach(function (mounted) {
      if (typeof mounted.instance.refresh === "function") mounted.instance.refresh();
    });
  };

  PluginHost.prototype.destroy = function () {
    this.instances.slice().reverse().forEach(function (mounted) {
      if (typeof mounted.instance.destroy === "function") mounted.instance.destroy();
    });
    this.instances = [];
    if (this.root && this.services.clearRoot !== false) this.root.replaceChildren();
  };

  global.REvoComputePlugins = Object.freeze({
    PluginRegistry: PluginRegistry,
    PluginHost: PluginHost
  });
})(window);
