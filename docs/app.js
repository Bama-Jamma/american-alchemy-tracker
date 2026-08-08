const SUBCATEGORY_GLYPHS = {
  government_document: "🗂️",
  testimony: "🎙️",
  news_media: "📰",
  legal_personal_record: "⚖️",
  scientific_data: "🧪",
  essay_paper: "📜",
};

let allData = null;
let activeTab = "episodes";
const manuallyExpanded = new Set();

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

function episodeUrl(videoId) {
  return `https://www.youtube.com/watch?v=${videoId}`;
}

// ---------- Filters ----------

function getFilters() {
  return {
    search: document.getElementById("search-input").value.trim().toLowerCase(),
    type: document.getElementById("filter-type").value,
    subcategory: document.getElementById("filter-subcategory").value,
    episode: document.getElementById("filter-episode").value,
  };
}

function filtersActive(filters) {
  return filters.search !== "" || filters.type !== "all" || filters.subcategory !== "all" || filters.episode !== "all";
}

function matchesSearch(searchText, episodeTitle, itemTitle, itemAuthorOrSource) {
  if (!searchText) return true;
  const haystack = `${itemTitle} ${itemAuthorOrSource || ""} ${episodeTitle}`.toLowerCase();
  return haystack.includes(searchText);
}

// ---------- Shared entry renderers ----------

function renderBookEntry(book, { showEpisode = false } = {}) {
  const episodeTag = showEpisode
    ? `<div class="entry-episode-tag">from <a href="${escapeHtml(episodeUrl(book.video_id))}" target="_blank" rel="noopener">${escapeHtml(book.episode_title)}</a> (${formatDate(book.upload_date)})</div>`
    : "";
  return `
    <div class="entry">
      <div class="entry-glyph">📕</div>
      <div>
        <div class="entry-title"><a href="${escapeHtml(book.amazon_url)}" target="_blank" rel="noopener">${escapeHtml(book.title)}</a></div>
        ${book.author ? `<div class="entry-meta">${escapeHtml(book.author)}</div>` : ""}
        ${book.context ? `<div class="entry-context">${escapeHtml(book.context)}</div>` : ""}
        ${episodeTag}
        <span class="entry-link-hint">search on amazon ↗</span>
      </div>
    </div>`;
}

function renderBookCard(book) {
  return `
    <div class="book-card">
      <div class="entry-glyph">📕</div>
      <div class="entry-title"><a href="${escapeHtml(book.amazon_url)}" target="_blank" rel="noopener">${escapeHtml(book.title)}</a></div>
      ${book.author ? `<div class="entry-meta">${escapeHtml(book.author)}</div>` : ""}
      ${book.context ? `<div class="entry-context">${escapeHtml(book.context)}</div>` : ""}
      <div class="entry-episode-tag">from <a href="${escapeHtml(episodeUrl(book.video_id))}" target="_blank" rel="noopener">${escapeHtml(book.episode_title)}</a></div>
    </div>`;
}

function documentSourceHint(accessType) {
  if (accessType === "direct") return `<span class="entry-link-hint">view document ↗</span>`;
  if (accessType === "request") return `<span class="entry-link-hint entry-link-hint-request">request via FOIA ↗</span>`;
  return "";
}

function renderDocumentEntry(doc, { showEpisode = false } = {}) {
  const episodeTag = showEpisode
    ? `<div class="entry-episode-tag">from <a href="${escapeHtml(episodeUrl(doc.video_id))}" target="_blank" rel="noopener">${escapeHtml(doc.episode_title)}</a> (${formatDate(doc.upload_date)})</div>`
    : "";
  const titleHtml = doc.source_url
    ? `<a href="${escapeHtml(doc.source_url)}" target="_blank" rel="noopener">${escapeHtml(doc.title)}</a>`
    : escapeHtml(doc.title);
  return `
    <div class="entry">
      <div class="entry-glyph">📄</div>
      <div>
        <div class="entry-title">${titleHtml}</div>
        ${doc.source ? `<div class="entry-meta">${escapeHtml(doc.source)}</div>` : ""}
        ${doc.context ? `<div class="entry-context">${escapeHtml(doc.context)}</div>` : ""}
        ${episodeTag}
        ${documentSourceHint(doc.access_type)}
      </div>
    </div>`;
}

// ---------- Tab: By Episode ----------

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

function renderEpisodeCard(episode, index, filters) {
  const { books, documents } = filterEpisode(episode, filters);
  if (!books.length && !Object.keys(documents).length) return "";

  const refNo = String(index + 1).padStart(3, "0");
  const totalCount = books.length + Object.values(documents).reduce((sum, arr) => sum + arr.length, 0);
  const isExpanded = manuallyExpanded.has(episode.video_id) || filtersActive(filters);

  const booksHtml = books.length
    ? `<div class="section-label">Books mentioned</div>${books.map((b) => renderBookEntry(b)).join("")}`
    : "";

  let documentsHtml = "";
  const subcatKeys = Object.keys(documents);
  if (subcatKeys.length) {
    documentsHtml += `<div class="section-label">Documents &amp; references</div>`;
    for (const key of subcatKeys) {
      const label = (allData.subcategory_labels && allData.subcategory_labels[key]) || key;
      const glyph = SUBCATEGORY_GLYPHS[key] || "📄";
      documentsHtml += `<div class="subcategory-label">${glyph} ${escapeHtml(label)}</div>`;
      documentsHtml += documents[key].map((d) => renderDocumentEntry(d)).join("");
    }
  }

  return `
    <div class="episode${isExpanded ? " expanded" : ""}" data-video-id="${escapeHtml(episode.video_id)}">
      <div class="episode-head">
        <div class="episode-head-main">
          <div class="episode-id">REF. ${refNo}</div>
          <div class="episode-title"><a href="${escapeHtml(episode.url)}" target="_blank" rel="noopener">${escapeHtml(episode.title)}</a></div>
        </div>
        <div class="episode-head-right">
          <span class="count-badge">${books.length} books · ${totalCount - books.length} docs</span>
          <span class="episode-date">${formatDate(episode.upload_date)}</span>
          <span class="expand-chevron">▶</span>
        </div>
      </div>
      <div class="episode-body">${booksHtml}${documentsHtml}</div>
    </div>`;
}

function renderEpisodesTab(filters) {
  const html = allData.episodes.map((ep, i) => renderEpisodeCard(ep, i, filters)).filter(Boolean).join("");
  return html || `<p class="loading">No matching entries.</p>`;
}

// ---------- Tab: Most Referenced ----------

function renderMentionItem(group) {
  const glyph = group.type === "book" ? "📕" : SUBCATEGORY_GLYPHS[group.subcategory] || "📄";
  const episodeLinks = group.episodes
    .map((e) => `<a href="${escapeHtml(episodeUrl(e.video_id))}" target="_blank" rel="noopener">${escapeHtml(e.episode_title)}</a>`)
    .join(" · ");

  const linkUrl = group.type === "book" ? group.amazon_url : group.source_url;
  const titleHtml = linkUrl
    ? `<a href="${escapeHtml(linkUrl)}" target="_blank" rel="noopener">${escapeHtml(group.title)}</a>`
    : escapeHtml(group.title);
  const hint = group.type === "book" ? `<span class="entry-link-hint">search on amazon ↗</span>` : documentSourceHint(group.access_type);

  return `
    <div class="mention-item">
      <div class="entry-glyph">${glyph}</div>
      <div>
        <div class="entry-title">${titleHtml}</div>
        ${group.author_or_source ? `<div class="entry-meta">${escapeHtml(group.author_or_source)}</div>` : ""}
        <div class="mention-episode-list">${episodeLinks}</div>
        ${hint}
      </div>
      <div class="mention-count">${group.episodes.length}×</div>
    </div>`;
}

function renderMostReferencedTab(filters) {
  const items = allData.most_referenced.filter((g) =>
    matchesSearch(filters.search, "", g.title, g.author_or_source)
  );
  if (!items.length) return `<p class="loading">No matching entries.</p>`;
  return `<div class="flat-list">${items.map(renderMentionItem).join("")}</div>`;
}

// ---------- Tab: Books ----------

function renderBooksTab(filters) {
  const items = allData.all_books.filter((b) => {
    if (filters.episode !== "all" && filters.episode !== b.video_id) return false;
    return matchesSearch(filters.search, b.episode_title, b.title, b.author);
  });
  if (!items.length) return `<p class="loading">No matching entries.</p>`;
  return `<div class="books-grid">${items.map(renderBookCard).join("")}</div>`;
}

// ---------- Tab: Documents ----------

function renderDocumentsTab(filters) {
  const items = allData.all_documents.filter((d) => {
    if (filters.subcategory !== "all" && filters.subcategory !== d.subcategory) return false;
    if (filters.episode !== "all" && filters.episode !== d.video_id) return false;
    return matchesSearch(filters.search, d.episode_title, d.title, d.source);
  });
  if (!items.length) return `<p class="loading">No matching entries.</p>`;

  const bySubcat = {};
  for (const d of items) {
    (bySubcat[d.subcategory] ||= []).push(d);
  }

  let html = "";
  for (const key of Object.keys(allData.subcategory_labels)) {
    if (!bySubcat[key]) continue;
    const label = allData.subcategory_labels[key];
    const glyph = SUBCATEGORY_GLYPHS[key] || "📄";
    html += `<div class="subcategory-label">${glyph} ${escapeHtml(label)}</div>`;
    html += bySubcat[key].map((d) => renderDocumentEntry(d, { showEpisode: true })).join("");
  }
  return `<div class="flat-list">${html}</div>`;
}

// ---------- Tab dispatch & filter bar visibility ----------

const TAB_RENDERERS = {
  episodes: renderEpisodesTab,
  "most-referenced": renderMostReferencedTab,
  books: renderBooksTab,
  documents: renderDocumentsTab,
};

function updateFilterBarVisibility() {
  const typeSelect = document.getElementById("filter-type");
  const subcategorySelect = document.getElementById("filter-subcategory");
  const episodeSelect = document.getElementById("filter-episode");

  typeSelect.style.display = activeTab === "episodes" ? "" : "none";
  subcategorySelect.style.display = activeTab === "episodes" || activeTab === "documents" ? "" : "none";
  episodeSelect.style.display = activeTab === "most-referenced" ? "none" : "";

  // The "book selected -> disable subcategory" rule only applies on the Episodes tab,
  // where both selects act as combined filters over the same list. On every other tab
  // subcategory is independent (or hidden), so it must never be left stuck disabled.
  subcategorySelect.disabled = activeTab === "episodes" && typeSelect.value === "book";
}

function render() {
  const filters = getFilters();
  const content = document.getElementById("content");
  content.innerHTML = TAB_RENDERERS[activeTab](filters);
}

function switchTab(tab) {
  activeTab = tab;
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    const isActive = btn.dataset.tab === tab;
    btn.classList.toggle("active", isActive);
    btn.setAttribute("aria-selected", String(isActive));
  });
  updateFilterBarVisibility();
  render();
}

// ---------- Setup ----------

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

function wireControls() {
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => switchTab(btn.dataset.tab));
  });

  const typeSelect = document.getElementById("filter-type");
  const subcategorySelect = document.getElementById("filter-subcategory");

  document.getElementById("search-input").addEventListener("input", render);
  document.getElementById("filter-episode").addEventListener("change", render);
  subcategorySelect.addEventListener("change", render);

  typeSelect.addEventListener("change", () => {
    if (typeSelect.value === "book") subcategorySelect.value = "all";
    updateFilterBarVisibility();
    render();
  });

  // Event delegation: clicking an episode header (but not a link inside it) toggles expand/collapse.
  document.getElementById("content").addEventListener("click", (e) => {
    if (e.target.closest("a")) return;
    const head = e.target.closest(".episode-head");
    if (!head) return;
    const card = head.closest(".episode");
    const videoId = card.dataset.videoId;
    if (manuallyExpanded.has(videoId)) manuallyExpanded.delete(videoId);
    else manuallyExpanded.add(videoId);
    render();
  });
}

async function init() {
  const content = document.getElementById("content");
  const footer = document.getElementById("footer-stats");

  try {
    const response = await fetch("data.json");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    allData = await response.json();

    populateFilterOptions();
    updateFilterBarVisibility();
    wireControls();
    render();

    const updated = allData.generated_at ? formatDate(allData.generated_at.slice(0, 10)) : "unknown";
    footer.textContent = `ARCHIVE STATUS: LIVE · ${allData.generated_episode_count} EPISODES INDEXED · LAST UPDATED ${updated.toUpperCase()}`;
  } catch (err) {
    content.innerHTML = `<p class="loading">Could not load archive data (${escapeHtml(err.message)}).</p>`;
  }
}

init();
