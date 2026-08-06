const SUBCATEGORY_GLYPHS = {
  government_document: "🗂️",
  testimony: "🎙️",
  news_media: "📰",
  legal_personal_record: "⚖️",
  scientific_data: "🧪",
  essay_paper: "📜",
};

let allData = null;

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

function formatDate(isoDate) {
  if (!isoDate) return "date unknown";
  const [year, month, day] = isoDate.split("-").map(Number);
  const date = new Date(Date.UTC(year, month - 1, day));
  return date.toLocaleDateString("en-US", { month: "short", year: "numeric", timeZone: "UTC" });
}

function renderBookEntry(book) {
  return `
    <div class="entry">
      <div class="entry-glyph">📕</div>
      <div>
        <div class="entry-title"><a href="${escapeHtml(book.amazon_url)}" target="_blank" rel="noopener">${escapeHtml(book.title)}</a></div>
        ${book.author ? `<div class="entry-meta">${escapeHtml(book.author)}</div>` : ""}
        ${book.context ? `<div class="entry-context">${escapeHtml(book.context)}</div>` : ""}
        <span class="entry-link-hint">search on amazon ↗</span>
      </div>
    </div>`;
}

function renderDocumentEntry(doc) {
  return `
    <div class="entry">
      <div class="entry-glyph">📄</div>
      <div>
        <div class="entry-title">${escapeHtml(doc.title)}</div>
        ${doc.source ? `<div class="entry-meta">${escapeHtml(doc.source)}</div>` : ""}
        ${doc.context ? `<div class="entry-context">${escapeHtml(doc.context)}</div>` : ""}
      </div>
    </div>`;
}

function getFilters() {
  return {
    search: document.getElementById("search-input").value.trim().toLowerCase(),
    type: document.getElementById("filter-type").value,
    subcategory: document.getElementById("filter-subcategory").value,
    episode: document.getElementById("filter-episode").value,
  };
}

function matchesSearch(searchText, episodeTitle, itemTitle, itemAuthorOrSource) {
  if (!searchText) return true;
  const haystack = `${itemTitle} ${itemAuthorOrSource || ""} ${episodeTitle}`.toLowerCase();
  return haystack.includes(searchText);
}

function filterEpisode(episode, filters) {
  const books =
    filters.type === "document" || filters.subcategory !== "all"
      ? []
      : episode.books.filter((b) => {
          if (filters.episode !== "all" && filters.episode !== episode.video_id) return false;
          return matchesSearch(filters.search, episode.title, b.title, b.author);
        });

  const documents = {};
  if (filters.type !== "book") {
    for (const [subcat, items] of Object.entries(episode.documents)) {
      if (filters.subcategory !== "all" && filters.subcategory !== subcat) continue;
      const matched = items.filter((d) => {
        if (filters.episode !== "all" && filters.episode !== episode.video_id) return false;
        return matchesSearch(filters.search, episode.title, d.title, d.source);
      });
      if (matched.length) documents[subcat] = matched;
    }
  }

  return { books, documents };
}

function renderEpisode(episode, index, filters) {
  const { books, documents } = filterEpisode(episode, filters);
  if (!books.length && !Object.keys(documents).length) return "";

  const refNo = String(index + 1).padStart(3, "0");

  const booksHtml = books.length
    ? `<div class="section-label">Books mentioned</div>${books.map(renderBookEntry).join("")}`
    : "";

  let documentsHtml = "";
  const subcatKeys = Object.keys(documents);
  if (subcatKeys.length) {
    documentsHtml += `<div class="section-label">Documents &amp; references</div>`;
    for (const key of subcatKeys) {
      const label = (allData.subcategory_labels && allData.subcategory_labels[key]) || key;
      const glyph = SUBCATEGORY_GLYPHS[key] || "📄";
      documentsHtml += `<div class="subcategory-label">${glyph} ${escapeHtml(label)}</div>`;
      documentsHtml += documents[key].map(renderDocumentEntry).join("");
    }
  }

  return `
    <div class="episode">
      <div class="episode-head">
        <div>
          <div class="episode-id">REF. ${refNo}</div>
          <div class="episode-title"><a href="${escapeHtml(episode.url)}" target="_blank" rel="noopener">${escapeHtml(episode.title)}</a></div>
        </div>
        <div class="episode-date">${formatDate(episode.upload_date)}</div>
      </div>
      ${booksHtml}${documentsHtml}
    </div>`;
}

function render() {
  const filters = getFilters();
  const main = document.getElementById("episodes");
  const html = allData.episodes.map((ep, i) => renderEpisode(ep, i, filters)).filter(Boolean).join("");
  main.innerHTML = html || `<p class="loading">No matching entries.</p>`;
}

function populateFilterOptions() {
  const subcategorySelect = document.getElementById("filter-subcategory");
  const seenSubcats = new Set();
  for (const episode of allData.episodes) {
    for (const key of Object.keys(episode.documents)) seenSubcats.add(key);
  }
  for (const key of Object.keys(allData.subcategory_labels || {})) {
    if (!seenSubcats.has(key)) continue;
    const opt = document.createElement("option");
    opt.value = key;
    opt.textContent = allData.subcategory_labels[key];
    subcategorySelect.appendChild(opt);
  }

  const episodeSelect = document.getElementById("filter-episode");
  for (const episode of allData.episodes) {
    const opt = document.createElement("option");
    opt.value = episode.video_id;
    opt.textContent = episode.title;
    episodeSelect.appendChild(opt);
  }
}

function wireFilterControls() {
  const typeSelect = document.getElementById("filter-type");
  const subcategorySelect = document.getElementById("filter-subcategory");

  document.getElementById("search-input").addEventListener("input", render);
  document.getElementById("filter-episode").addEventListener("change", render);
  subcategorySelect.addEventListener("change", render);

  typeSelect.addEventListener("change", () => {
    const isBookOnly = typeSelect.value === "book";
    subcategorySelect.disabled = isBookOnly;
    if (isBookOnly) subcategorySelect.value = "all";
    render();
  });
}

async function init() {
  const main = document.getElementById("episodes");
  const footer = document.getElementById("footer-stats");

  try {
    const response = await fetch("data.json");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    allData = await response.json();

    populateFilterOptions();
    wireFilterControls();
    render();

    const updated = allData.generated_at ? formatDate(allData.generated_at.slice(0, 10)) : "unknown";
    footer.textContent = `ARCHIVE STATUS: LIVE · ${allData.generated_episode_count} EPISODES INDEXED · LAST UPDATED ${updated.toUpperCase()}`;
  } catch (err) {
    main.innerHTML = `<p class="loading">Could not load archive data (${escapeHtml(err.message)}).</p>`;
  }
}

init();
