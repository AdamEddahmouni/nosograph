(() => {
  const graph = document.querySelector("[data-ng-graph]");
  if (!graph) return;

  const nodes = [...graph.querySelectorAll("[data-node]")];
  const edges = [...graph.querySelectorAll("[data-from][data-to]")];
  const status = graph.querySelector("[data-graph-status]");
  const labels = Object.fromEntries(nodes.map((node) => [node.dataset.node, node.dataset.label || node.dataset.node]));

  const clearState = () => {
    nodes.forEach((node) => node.classList.remove("is-active", "is-muted"));
    edges.forEach((edge) => edge.classList.remove("is-active", "is-muted"));
  };

  const focusNode = (node) => {
    const id = node.dataset.node;
    const connected = edges.filter((edge) => edge.dataset.from === id || edge.dataset.to === id);
    const connectedIds = new Set([id]);
    connected.forEach((edge) => {
      connectedIds.add(edge.dataset.from);
      connectedIds.add(edge.dataset.to);
    });

    nodes.forEach((candidate) => {
      candidate.classList.toggle("is-active", candidate === node);
      candidate.classList.toggle("is-muted", !connectedIds.has(candidate.dataset.node));
    });
    edges.forEach((edge) => {
      edge.classList.toggle("is-active", connected.includes(edge));
      edge.classList.toggle("is-muted", !connected.includes(edge));
    });

    if (status) status.textContent = `${labels[id]} focused. Connected relationships are highlighted.`;
  };

  nodes.forEach((node) => {
    node.addEventListener("mouseenter", () => focusNode(node));
    node.addEventListener("focus", () => focusNode(node));
    node.addEventListener("click", () => focusNode(node));
    node.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        focusNode(node);
      }
      if (event.key === "Escape") {
        clearState();
        if (status) status.textContent = "Graph focus cleared. Select a labeled entity to trace relationships.";
      }
    });
  });

  graph.addEventListener("mouseleave", () => {
    clearState();
    if (status) status.textContent = "Select a labeled entity to trace relationships.";
  });
})();
