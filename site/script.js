(() => {
  let notes = [];
  let fuse = null;
  let activeLabel = null;

  const searchInput = document.getElementById("search");
  const labelsContainer = document.getElementById("labels");
  const noteList = document.getElementById("note-list");

  fetch("notes-data.json")
    .then((r) => r.json())
    .then((data) => {
      notes = data;
      fuse = new Fuse(notes, {
        keys: ["title", "preview"],
        threshold: 0.4,
      });
      renderLabels();
      renderNotes(notes);
    });

  searchInput.addEventListener("input", () => applyFilters());

  function applyFilters() {
    let results = notes;

    const query = searchInput.value.trim();
    if (query && fuse) {
      results = fuse.search(query).map((r) => r.item);
    }

    if (activeLabel) {
      results = results.filter((n) => n.labels.includes(activeLabel));
    }

    renderNotes(results);
  }

  function renderLabels() {
    const allLabels = [...new Set(notes.flatMap((n) => n.labels))].sort();
    labelsContainer.innerHTML = "";
    for (const label of allLabels) {
      const btn = document.createElement("button");
      btn.className = "label-chip";
      btn.textContent = label;
      btn.addEventListener("click", () => {
        if (activeLabel === label) {
          activeLabel = null;
          btn.classList.remove("active");
        } else {
          activeLabel = label;
          labelsContainer
            .querySelectorAll(".label-chip")
            .forEach((b) => b.classList.remove("active"));
          btn.classList.add("active");
        }
        applyFilters();
      });
      labelsContainer.appendChild(btn);
    }
  }

  function renderNotes(list) {
    noteList.innerHTML = "";
    if (list.length === 0) {
      noteList.innerHTML = "<li>No notes found.</li>";
      return;
    }
    for (const note of list) {
      const li = document.createElement("li");

      const titleLink = document.createElement("a");
      titleLink.className = "note-title";
      titleLink.href = `notes/${note.folder}/`;
      titleLink.textContent = note.title;

      const meta = document.createElement("div");
      meta.className = "note-meta";

      const labelSpans = note.labels
        .map((l) => `<span class="note-label">${l}</span>`)
        .join("");

      const date = note.timestamp
        ? new Date(note.timestamp * 1000).toLocaleDateString(undefined, {
            year: "numeric",
            month: "short",
            day: "numeric",
          })
        : "";

      meta.innerHTML = labelSpans + (date ? ` &middot; Last updated: ${date}` : "");

      li.appendChild(titleLink);
      li.appendChild(meta);
      noteList.appendChild(li);
    }
  }
})();
