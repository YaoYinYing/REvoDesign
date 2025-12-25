# PyMOL CLI Autocompletion for `cmd.extend` Commands (Shortcut / `cmd.auto_arg`)

This document describes PyMOL’s autocompletion mechanism for extended commands, centered around the **`Shortcut`** object and the **`cmd.auto_arg`** registry. It is written to be practical: you should be able to copy patterns from here and implement reliable autocomplete for multi-argument `cmd.extend()` commands.

---

## What problem this solves

When you add a new command with `cmd.extend("name", func)`, PyMOL does **not** automatically know how to autocomplete that command’s arguments. PyMOL’s CLI completion system is driven by a registry called **`cmd.auto_arg`**, where each command argument position can be associated with a *provider* that returns a `Shortcut` instance (often via a lambda).

---

## Key concepts

### 1) `cmd.extend`

Registers a new command name in the PyMOL command interpreter:

```python
cmd.extend("real_sc", shortcut_real_sc)
```

Autocomplete can only be added meaningfully **after** the command exists (i.e., after `cmd.extend`).

---

### 2) `Shortcut`

A `Shortcut` is (conceptually) “a set of legal tokens” that the CLI completion system can suggest and match.

Typical usage:

```python
lambda: Shortcut(keywords=["0", "1"])
```

* You usually return a `Shortcut` from a **callable** (often a `lambda`) so completions can be generated dynamically at runtime.
* Keywords can be static (`["0", "1"]`) or computed on demand (e.g., from current objects/selections).

---

### 3) `cmd.auto_arg`

`cmd.auto_arg` is a list indexed by argument position groups. The details vary internally, but the core usage pattern is stable:

* You assign autocomplete behavior per **argument index** of your extended command.
* Argument index is **0-based**: arg0, arg1, arg2, ...

The general assignment format is:

```python
cmd.auto_arg[<arg_id>]["<command_name>"] = [
    <shortcut_factory>,   # callable returning a Shortcut
    "<label>",            # displayed label in completion UI
    "<postfix>",          # appended after inserting the completion
]
```

Where:

* `<arg_id>`: which argument you are defining completion for (0-based)
* `<command_name>`: your `cmd.extend` name
* `<shortcut_factory>`: typically a `lambda` returning a `Shortcut`, or reused from another command
* `"<label>"`: hints what the argument represents (e.g., `"selection"`)
* `"<postfix>"`: appended after the inserted token (commonly `' '` or `''`)

---

## Borrowing existing completion providers vs. creating new ones

You have two standard approaches:

### Approach A — Borrow an existing provider

This is the fastest path and usually the most consistent with PyMOL’s UX.

Example: reuse the completion provider already defined for `select` or `show`.

```python
cmd.auto_arg[0]["real_sc"] = [cmd.auto_arg[1]["select"][0], "selection", " "]
cmd.auto_arg[1]["real_sc"] = [cmd.auto_arg[0]["show"][0], "representation", " "]
```

Notes:

* `cmd.auto_arg[...]["select"][0]` is the *provider* callable from the existing spec.
* You can borrow providers from any built-in or previously-registered command that has a suitable completion behavior.

Use this when:

* Your argument semantics match an existing category (selection, object, representation, color name, setting name, etc.).
* You want consistent behavior with built-in commands.

---

### Approach B — Create a new provider

Use this when your argument tokens are domain-specific (e.g., flags `0/1`, custom modes, named presets).

```python
cmd.auto_arg[2]["color_by_mutation"] = [lambda: Shortcut(keywords=["0", "1"]), "waters", ""]
cmd.auto_arg[3]["color_by_mutation"] = [lambda: Shortcut(keywords=["0", "1"]), "labels", ""]
```

Use this when:

* The valid tokens are a small closed set (enums, flags, modes).
* The tokens should be computed dynamically from session state (objects, selections, states, maps, etc.).

---

## Worked examples

### Example 1: `real_sc` (two arguments, both borrowed)

```python
cmd.extend("real_sc", shortcut_real_sc)
cmd.auto_arg[0]["real_sc"] = [cmd.auto_arg[1]["select"][0], "selection", " "]
cmd.auto_arg[1]["real_sc"] = [cmd.auto_arg[0]["show"][0], "representation", " "]
```

Interpretation:

* `real_sc arg0` is a **selection** → reuse `select`’s selection completion provider
* `real_sc arg1` is a **representation** → reuse `show`’s representation completion provider
* Both append a space after completion insertion (`" "`), which makes interactive entry smoother.

---

### Example 2: `color_by_mutation` (four arguments, mixed borrowed + custom)

```python
cmd.extend("color_by_mutation", shortcut_color_by_mutation)

cmd.auto_arg[0]["color_by_mutation"] = [cmd.auto_arg[0]["enable"][0], "obj1", ""]
cmd.auto_arg[1]["color_by_mutation"] = [cmd.auto_arg[0]["enable"][0], "obj2", ""]
cmd.auto_arg[2]["color_by_mutation"] = [lambda: Shortcut(keywords=["0", "1"]), "waters", ""]
cmd.auto_arg[3]["color_by_mutation"] = [lambda: Shortcut(keywords=["0", "1"]), "labels", ""]
```

Interpretation:

* `arg0` and `arg1`: objects (reusing provider from `enable` — commonly object-name completion)
* `arg2` and `arg3`: boolean-like flags (`0/1`) via custom `Shortcut`

---

## Recommended conventions

### 1) Always use a callable for the provider

Even for static keyword sets, prefer:

```python
lambda: Shortcut(keywords=["0", "1"])
```

This keeps the interface consistent and makes it trivial to evolve into dynamic completion later.

---

### 2) Use meaningful labels

Labels are not just decoration; they are often the only hint the user sees.

Good:

* `"selection"`, `"object"`, `"representation"`, `"state"`, `"color"`, `"mode"`, `"flag"`

Weak:

* `"arg0"`, `"param"`, `"x"`

---

### 3) Choose postfix deliberately

* Use `" "` when the user should naturally proceed to the next token.
* Use `""` when you do *not* want to force spacing (e.g., when completion inserts something that is immediately followed by punctuation or when the command grammar is unusual).

Most normal CLI arguments should use `" "`.

---

## Advanced patterns

### Dynamic keywords from session state

If you want completions that reflect the current session, generate the keyword list at call time.

Example sketch (exact API may vary depending on what you want to list):

```python
cmd.auto_arg[0]["mycmd"] = [
    lambda: Shortcut(keywords=cmd.get_names("objects")),
    "object",
    " ",
]
```

This pattern matters because:

* Users create/delete/rename objects constantly.
* Static lists get stale immediately.

---

### Context-sensitive completion (based on earlier args)

Sometimes arg1’s valid tokens depend on arg0. PyMOL’s `cmd.auto_arg` mechanism is simple by design; you typically handle “dependent completion” in one of these ways:

1. **Broaden** arg1 completion to all plausible tokens (fast and robust).
2. **Encode structured tokens** (e.g., `obj:state`) and parse later.
3. **Do lightweight inference** inside the callable using current command line context (only if you already have a known way to access it in your environment; don’t introduce brittle hacks).

In most plugin contexts, option (1) is the best tradeoff.

---

## Common failure modes and how to avoid them

1. **Autocomplete doesn’t show up**

* You added `cmd.auto_arg[...]` *before* `cmd.extend(...)`, or the command name is misspelled.

2. **Wrong provider index**

* Remember: your command args are 0-based (`arg0`, `arg1`, ...).
* Also, the `cmd.auto_arg[...]` *outer* index is not “your command’s arg index”; it’s selecting the completion “bucket” you’re editing. In practice, follow known working examples (like the ones above) and reuse existing providers rather than inventing new `cmd.auto_arg` bucket indices.

3. **Provider is not callable**

* `cmd.auto_arg` expects something it can call to obtain a `Shortcut`. If you pass a `Shortcut` instance directly, you’ll often get silent failure or inconsistent behavior.

---

## Minimal template you can copy

```python
from pymol.shortcut import Shortcut  # if needed in your environment

cmd.extend("mycmd", mycmd_impl)

# arg0: selection (borrow)
cmd.auto_arg[0]["mycmd"] = [cmd.auto_arg[1]["select"][0], "selection", " "]

# arg1: custom enum (new)
cmd.auto_arg[1]["mycmd"] = [lambda: Shortcut(keywords=["modeA", "modeB"]), "mode", " "]
```

---

## Reference example source

If you want a real-world plugin that uses this pattern, see the `spectrum_states.py` example:

```text
https://raw.githubusercontent.com/Pymol-Scripts/Pymol-script-repo/master/scripts/spectrum_states.py
```

(Kept as plain text to avoid ambiguity; it is not required reading to apply the patterns above.)
