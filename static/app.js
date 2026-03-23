/* ─────────────────────────────────────────────────────────────────────────────
   MoodFlix – Frontend Logic
───────────────────────────────────────────────────────────────────────────── */

const LOADING_MESSAGES = [
  "Reading your mood...",
  "Analyzing emotional nuance...",
  "Searching 10,000+ films...",
  "Curating your perfect picks...",
];

// ── State ─────────────────────────────────────────────────────────────────────
let lastText = "";
let page = 1;

// ── DOM refs ──────────────────────────────────────────────────────────────────
const input       = () => document.getElementById("mood-input");
const charCount   = () => document.getElementById("char-count");
const analyzeBtn  = () => document.getElementById("analyze-btn");
const moodCard    = () => document.getElementById("mood-card");
const loadingEl   = () => document.getElementById("loading-state");
const loadingText = () => document.getElementById("loading-text");
const loadingFill = () => document.getElementById("loading-fill");
const resultsEl   = () => document.getElementById("results-section");
const moviesGrid  = () => document.getElementById("movies-grid");

// ── Character counter ─────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  input().addEventListener("input", () => {
    const len = input().value.length;
    charCount().textContent = `${len} / 500`;
  });

  // Allow Enter+Shift for new line, Enter alone submits
  input().addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      analyzeMood();
    }
  });
});

// ── Quick mood chips ──────────────────────────────────────────────────────────
function setMood(btn) {
  input().value = btn.dataset.text;
  charCount().textContent = `${btn.dataset.text.length} / 500`;
  analyzeMood();
}

// ── Main analysis flow ────────────────────────────────────────────────────────
async function analyzeMood(refresh = false) {
  const text = refresh ? lastText : input().value.trim();
  if (!text) {
    shakeInput();
    return;
  }
  lastText = text;
  if (refresh) page++;

  // UI: hide card, show loading
  moodCard().classList.add("hidden");
  resultsEl().classList.add("hidden");
  loadingEl().classList.remove("hidden");
  analyzeBtn().disabled = true;

  // Animate loading messages
  let msgIdx = 0;
  loadingText().textContent = LOADING_MESSAGES[0];
  const fillInterval = setInterval(() => {
    msgIdx = Math.min(msgIdx + 1, LOADING_MESSAGES.length - 1);
    loadingText().textContent = LOADING_MESSAGES[msgIdx];
  }, 900);

  // Animate progress bar
  animateBar();

  try {
    const resp = await fetch("/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, page }),
    });

    if (!resp.ok) {
      const err = await resp.json();
      throw new Error(err.error || "Something went wrong. Please try again.");
    }

    const data = await resp.json();

    // Small delay so loading feels deliberate
    await sleep(400);
    clearInterval(fillInterval);
    loadingEl().classList.add("hidden");

    showResults(data);

  } catch (err) {
    clearInterval(fillInterval);
    loadingEl().classList.add("hidden");
    moodCard().classList.remove("hidden");
    analyzeBtn().disabled = false;
    showError(err.message);
  }
}

// ── Render results ────────────────────────────────────────────────────────────
function showResults(data) {
  // Mood banner
  document.getElementById("result-emoji").textContent  = data.mood_emoji;
  document.getElementById("result-label").textContent  = data.mood_label;
  document.getElementById("result-nuance").textContent = data.nuance || "";

  // Apply mood color to banner
  const banner = document.getElementById("mood-banner");
  banner.style.borderColor  = data.mood_color + "44";
  banner.style.background   = `linear-gradient(135deg, ${data.mood_color}11 0%, var(--bg-card) 60%)`;

  // Confidence arc
  const pct = Math.round((data.confidence || 0.8) * 100);
  animateConfidence(pct);

  // Movies
  const grid = moviesGrid();
  grid.innerHTML = "";
  if (!data.movies || data.movies.length === 0) {
    grid.innerHTML = `<p style="color:var(--text-muted);grid-column:1/-1;text-align:center;padding:40px 0">
      No movies found for this mood. Try rephrasing!</p>`;
  } else {
    data.movies.forEach((m, i) => {
      grid.appendChild(buildMovieCard(m, i));
    });
  }

  resultsEl().classList.remove("hidden");
  analyzeBtn().disabled = false;

  // Smooth scroll to results
  setTimeout(() => {
    resultsEl().scrollIntoView({ behavior: "smooth", block: "start" });
  }, 100);
}

function buildMovieCard(movie, idx) {
  const card = document.createElement("div");
  card.className = "movie-card";
  card.setAttribute("data-id", movie.id);

  // Pick badge
  let badge = "";
  if (movie.pick_label) {
    const cls = movie.pick_label === "Top Pick" ? "top-pick"
              : movie.pick_label === "Safe Bet"  ? "safe-bet" : "unexpected";
    badge = `<div class="pick-badge ${cls}">${movie.pick_label}</div>`;
  }

  // Poster
  const posterHTML = movie.poster
    ? `<img class="movie-poster" src="${movie.poster}" alt="${escHtml(movie.title)}" loading="lazy">`
    : `<div class="poster-placeholder">🎬</div>`;

  // Rating stars
  const stars = movie.rating >= 7 ? "⭐" : movie.rating >= 5 ? "★" : "☆";

  card.innerHTML = `
    ${badge}
    <div class="poster-wrapper">
      ${posterHTML}
      <div class="card-overlay">
        <div class="play-btn">▶</div>
      </div>
    </div>
    <div class="card-body">
      <div class="movie-title">${escHtml(movie.title)}</div>
      <div class="card-meta">
        <span class="rating">${stars} ${movie.rating}</span>
        <span class="year">${movie.year || "—"}</span>
      </div>
      <p class="card-overview">${escHtml(movie.overview || "")}</p>
      <div class="card-actions">
        <button class="card-btn card-btn-trailer" onclick="playTrailer(${movie.id}, event)">▶ Trailer</button>
        <a class="card-btn card-btn-info" href="${movie.tmdb_url}" target="_blank" rel="noopener">Info ↗</a>
      </div>
    </div>`;

  return card;
}

// ── Trailer ───────────────────────────────────────────────────────────────────
async function playTrailer(movieId, e) {
  e.stopPropagation();
  const modal   = document.getElementById("trailer-modal");
  const wrapper = document.getElementById("iframe-wrapper");
  wrapper.innerHTML = `<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#666;font-size:0.9rem">Loading trailer…</div>`;
  modal.classList.remove("hidden");

  try {
    const resp = await fetch(`/trailer/${movieId}`);
    const data = await resp.json();
    if (data.trailer_key) {
      wrapper.innerHTML = `<iframe src="https://www.youtube.com/embed/${data.trailer_key}?autoplay=1" allow="autoplay; fullscreen" allowfullscreen></iframe>`;
    } else {
      wrapper.innerHTML = `<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#666;font-size:0.9rem">No trailer available</div>`;
    }
  } catch {
    wrapper.innerHTML = `<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#666;font-size:0.9rem">Could not load trailer</div>`;
  }
}

function closeTrailer() {
  document.getElementById("trailer-modal").classList.add("hidden");
  document.getElementById("iframe-wrapper").innerHTML = "";
}
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeTrailer(); });

// ── Reset ─────────────────────────────────────────────────────────────────────
function resetApp() {
  page = 1;
  resultsEl().classList.add("hidden");
  moodCard().classList.remove("hidden");
  input().value = "";
  charCount().textContent = "0 / 500";
  analyzeBtn().disabled = false;
  window.scrollTo({ top: 0, behavior: "smooth" });
}

// ── Animations ────────────────────────────────────────────────────────────────
function animateBar() {
  const fill = loadingFill();
  fill.style.width = "0%";
  let progress = 0;
  const iv = setInterval(() => {
    progress = Math.min(progress + Math.random() * 12, 90);
    fill.style.width = progress + "%";
    if (progress >= 90) clearInterval(iv);
  }, 200);
}

function animateConfidence(pct) {
  const arc = document.getElementById("confidence-arc");
  const pctEl = document.getElementById("confidence-pct");
  const circumference = 150.8;
  const target = circumference - (pct / 100) * circumference;

  arc.style.transition = "stroke-dashoffset 1s cubic-bezier(0.4,0,0.2,1)";
  arc.style.strokeDashoffset = target;

  let current = 0;
  const iv = setInterval(() => {
    current = Math.min(current + 2, pct);
    pctEl.textContent = current + "%";
    if (current >= pct) clearInterval(iv);
  }, 20);
}

function shakeInput() {
  const card = moodCard();
  card.style.animation = "none";
  card.offsetHeight; // reflow
  card.style.animation = "shake 0.4s ease";
  setTimeout(() => { card.style.animation = ""; }, 400);

  // Inject shake keyframes if not present
  if (!document.getElementById("shake-style")) {
    const s = document.createElement("style");
    s.id = "shake-style";
    s.textContent = `@keyframes shake { 0%,100%{transform:translateX(0)} 25%{transform:translateX(-8px)} 75%{transform:translateX(8px)} }`;
    document.head.appendChild(s);
  }
}

// ── Error ─────────────────────────────────────────────────────────────────────
function showError(message) {
  const existing = document.getElementById("error-toast");
  if (existing) existing.remove();

  const toast = document.createElement("div");
  toast.id = "error-toast";
  toast.style.cssText = `
    position:fixed; bottom:24px; left:50%; transform:translateX(-50%);
    background:#1a0f0f; border:1px solid rgba(239,68,68,0.4); color:#fca5a5;
    padding:12px 20px; border-radius:12px; font-size:0.88rem; z-index:200;
    box-shadow:0 8px 32px rgba(0,0,0,0.5); animation: slide-up 0.3s ease;
  `;
  toast.textContent = "⚠ " + message;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 4500);
}

// ── Helpers ───────────────────────────────────────────────────────────────────
const sleep   = (ms) => new Promise(r => setTimeout(r, ms));
const escHtml = (str) => str.replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
