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
    if (this.plugins.has(plugin.id)) throw new Error("Duplicate " + this.kind + " plugin: " + plugin.id);
    if (typeof plugin.mount !== "function" && typeof plugin.render !== "function") {
      throw new TypeError(this.kind + " plugin " + plugin.id + " requires mount() or render()");
    }
    this.plugins.set(plugin.id, Object.freeze(plugin));
    return this;
  };

  PluginRegistry.prototype.get = function (id) { return this.plugins.get(id) || null; };

  PluginRegistry.prototype.resolve = function (subject, context) {
    var direct = subject && subject.plugin ? this.get(subject.plugin) : null;
    if (direct) return direct;
    var resolved = null;
    this.plugins.forEach(function (plugin) {
      if (!resolved && typeof plugin.supports === "function" && plugin.supports(subject, context)) resolved = plugin;
    });
    return resolved;
  };

  function PluginHost(registry, root, services) {
    this.registry = registry;
    this.root = root;
    this.services = services || {};
    this.instances = [];
    this.faults = [];
  }

  PluginHost.prototype._fault = function (definition, plugin, phase, error, target) {
    var duplicate = this.faults.some(function (fault) {
      return fault.definition === definition && fault.phase === phase && fault.message.endsWith(error.message);
    });
    if (duplicate) return;
    var fault = {
      definition: definition,
      plugin: plugin,
      phase: phase,
      message: (plugin ? plugin.id : definition.plugin) + ": " + error.message,
      target: target
    };
    this.faults.push(fault);
    if (this.services.onError) this.services.onError(fault);
  };

  PluginHost.prototype.mount = function (definitions, context) {
    if (this.instances.length) this.destroy();
    this.faults = [];
    var host = this;
    (definitions || []).forEach(function (definition) {
      var plugin = host.registry.resolve(definition, context);
      if (!plugin) {
        if (host.services.onUnsupported) host.services.onUnsupported(definition);
        host._fault(definition, null, "mount", new Error("unsupported component"), null);
        return;
      }
      var target = host.services.createTarget ? host.services.createTarget(definition, plugin) : host.root;
      try {
        var instance = plugin.mount(target, definition, context, host.services) || {};
        host.instances.push({ definition: definition, plugin: plugin, instance: instance, target: target });
      } catch (error) { host._fault(definition, plugin, "mount", error, target); }
    });
    return this.instances;
  };

  PluginHost.prototype.collect = function () {
    var values = {};
    var host = this;
    this.instances.forEach(function (mounted) {
      if (typeof mounted.instance.readValue !== "function") return;
      try { values[mounted.definition.id] = mounted.instance.readValue(); }
      catch (error) { values[mounted.definition.id] = null; host._fault(mounted.definition, mounted.plugin, "collect", error, mounted.target); }
    });
    return values;
  };

  PluginHost.prototype.summarize = function () {
    var summaries = [];
    var host = this;
    this.instances.forEach(function (mounted) {
      if (typeof mounted.instance.summarize !== "function") return;
      try {
        var result = mounted.instance.summarize();
        if (Array.isArray(result)) summaries.push.apply(summaries, result);
        else if (result) summaries.push(result);
      } catch (error) { host._fault(mounted.definition, mounted.plugin, "summarize", error, mounted.target); }
    });
    return summaries;
  };

  PluginHost.prototype.validate = function () {
    var errors = this.faults.map(function (fault) { return fault.message; });
    var host = this;
    this.instances.forEach(function (mounted) {
      if (typeof mounted.instance.validate !== "function") return;
      try {
        var result = mounted.instance.validate();
        if (Array.isArray(result)) errors.push.apply(errors, result);
        else if (result) errors.push(result);
      } catch (error) {
        host._fault(mounted.definition, mounted.plugin, "validate", error, mounted.target);
        errors.push(mounted.plugin.id + ": " + error.message);
      }
    });
    return Array.from(new Set(errors));
  };

  PluginHost.prototype.refresh = function () {
    var host = this;
    this.instances.forEach(function (mounted) {
      if (typeof mounted.instance.refresh !== "function") return;
      try { mounted.instance.refresh(); }
      catch (error) { host._fault(mounted.definition, mounted.plugin, "refresh", error, mounted.target); }
    });
  };

  PluginHost.prototype.destroy = function () {
    var host = this;
    this.instances.slice().reverse().forEach(function (mounted) {
      if (typeof mounted.instance.destroy !== "function") return;
      try { mounted.instance.destroy(); }
      catch (error) { host._fault(mounted.definition, mounted.plugin, "destroy", error, mounted.target); }
    });
    this.instances = [];
    this.faults = [];
    if (this.root) this.root.replaceChildren();
  };

  global.REvoComputePlugins = Object.freeze({ PluginRegistry: PluginRegistry, PluginHost: PluginHost });
})(window);
