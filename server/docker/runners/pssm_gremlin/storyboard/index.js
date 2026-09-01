/* GREMLIN scientific result composition; generic file rendering stays in the server. */
export default {
  mount(host, context) {
    const title = document.createElement("h2");
    title.textContent = "GREMLIN Coevolution Analysis";
    const summary = document.createElement("p");
    summary.textContent = "Inspect the filtered alignment, position-specific scoring matrix, and coupling matrix produced for this sequence.";
    const list = document.createElement("div");
    [["alignment", "Filtered multiple-sequence alignment"], ["pssm", "Position-specific scoring matrix"], ["coupling_matrix", "GREMLIN coupling matrix"]].forEach(([id, label]) => {
      const file = context.files.get(id);
      const button = document.createElement("button");
      button.type = "button";
      button.className = "btn btn-soft";
      button.textContent = file ? `Inspect ${label}` : `${label} unavailable`;
      button.disabled = !file;
      if (file) button.addEventListener("click", () => context.services.openFile(file));
      list.appendChild(button);
    });
    host.replaceChildren(title, summary, list);
  },
  destroy() {}
};
