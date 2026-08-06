const SUBCATEGORY_GLYPHS = {
  government_document: "🗂️",
  testimony: "🎙️",
  news_media: "📰",
  legal_personal_record: "⚖️",
  scientific_data: "🧪",
  essay_paper: "📜",
};

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

function setTheme(name) {
  document.body.setAttribute("data-theme", name);
  document.querySelectorAll("[data-theme-btn]").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.themeBtn === name);
  });
  localStorage.setItem("aa-theme", name);
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
        <div class="entry-title">
          <span class="redact-wrap" tabindex="0">
            <span class="redact-bar">${escapeHtml(doc.title)}</span>
          </span>
        </div>
        ${doc.source ? `<div class="entry-meta">${escapeHtml(doc.source)}</div>` : ""}
        ${doc.context ? `<div class="entry-context">${escapeHtml(doc.context)}</div>` : ""}
        <span class="redact-hint">tap / hover to declassify</span>
      </div>
    </div>`;
}

function renderEpisode(episode, index) {
  const refNo = String(index + 1).padStart(3, "0");

  const booksHtml = episode.books.length
    ? `<div class="section-label">Books mentioned</div>${episode.books.map(renderBookEntry).join("")}`
    : "";

  const subcatKeys = Object.keys(episode.documents);
  let documentsHtml = "";
  if (subcatKeys.length) {
    documentsHtml += `<div class="section-label">Documents &amp; references</div>`;
    for (const key of subcatKeys) {
      const label = (window.SUBCATEGORY_LABELS && window.SUBCATEGORY_LABELS[key]) || key;
      const glyph = SUBCATEGORY_GLYPHS[key] || "📄";
      documentsHtml += `<div class="subcategory-label">${glyph} ${escapeHtml(label)}</div>`;
      documentsHtml += episode.documents[key].map(renderDocumentEntry).join("");
    }
  }

  const bodyHtml =
    booksHtml || documentsHtml
      ? booksHtml + documentsHtml
      : `<div class="empty-note">No books or documents identified for this episode.</div>`;

  return `
    <div class="episode">
      <div class="episode-head">
        <div>
          <div class="episode-id">REF. ${refNo}</div>
          <div class="episode-title"><a href="${escapeHtml(episode.url)}" target="_blank" rel="noopener">${escapeHtml(episode.title)}</a></div>
        </div>
        <div class="episode-date">${formatDate(episode.upload_date)}</div>
      </div>
      ${bodyHtml}
    </div>`;
}

async function init() {
  const savedTheme = localStorage.getItem("aa-theme");
  if (savedTheme === "declassified" || savedTheme === "alchemist") {
    setTheme(savedTheme);
  }
  document.querySelectorAll("[data-theme-btn]").forEach((btn) => {
    btn.addEventListener("click", () => setTheme(btn.dataset.themeBtn));
  });

  const main = document.getElementById("episodes");
  const footer = document.getElementById("footer-stats");

  try {
    const response = await fetch("data.json");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();

    window.SUBCATEGORY_LABELS = data.subcategory_labels || {};

    if (!data.episodes.length) {
      main.innerHTML = `<p class="loading">No episodes indexed yet.</p>`;
    } else {
      main.innerHTML = data.episodes.map(renderEpisode).join("");
    }

    const updated = data.generated_at ? formatDate(data.generated_at.slice(0, 10)) : "unknown";
    footer.textContent = `ARCHIVE STATUS: LIVE · ${data.generated_episode_count} EPISODES INDEXED · LAST UPDATED ${updated.toUpperCase()}`;
  } catch (err) {
    main.innerHTML = `<p class="loading">Could not load archive data (${escapeHtml(err.message)}).</p>`;
  }
}

init();
