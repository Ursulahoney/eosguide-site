// src/assets/app.js

function getCards() {
  return Array.from(document.querySelectorAll("#opportunitiesGrid > div"));
}

function cardText(card) {
  return (card.innerText || "").toLowerCase();
}

function cardState(card) {
  const loc = card.querySelector('[itemprop="address"]');
  return (loc?.textContent || "").trim();
}

function applyFilters() {
  const q = (document.querySelector("#searchInput")?.value || "").trim().toLowerCase();
  const state = (document.querySelector("#stateSelector")?.value || "").trim();

  getCards().forEach(card => {
    const matchesSearch = !q || cardText(card).includes(q);

    const loc = cardState(card);
    const matchesState =
      !state || state === "All" || state === "All States" || loc === "Nationwide" || loc === state;

    card.style.display = (matchesSearch && matchesState) ? "" : "none";
  });
}

document.addEventListener("DOMContentLoaded", () => {
  const searchInput = document.querySelector("#searchInput");
  const stateSelect = document.querySelector("#stateSelector");

  if (searchInput) searchInput.addEventListener("input", applyFilters);
  if (stateSelect) stateSelect.addEventListener("change", applyFilters);
});
// Compatibility wrappers for existing HTML handlers
window.filterOpportunities = applyFilters;
window.toggleCategories = function () {
  // If "Show All" just resets filters
  const searchInput = document.querySelector("#searchInput");
  const stateSelect = document.querySelector("#stateSelector");

  if (searchInput) searchInput.value = "";


  if (stateSelect) stateSelect.value = "All";

  applyFilters();
};
// --- Share button functions (global) ---
window.copyLink = async function (event) {
  if (event) event.preventDefault();
  const url = window.location.href;

  try {
    await navigator.clipboard.writeText(url);
    alert("Link copied!");
  } catch (e) {
    // Fallback for older browsers
    const tmp = document.createElement("textarea");
    tmp.value = url;
    document.body.appendChild(tmp);
    tmp.select();
    document.execCommand("copy");
    tmp.remove();
    alert("Link copied!");
  }
};

window.shareEmailPage = function (event) {
  if (event) event.preventDefault();
  const url = window.location.href;
  const subject = encodeURIComponent(document.title || "Opportunity list");
  const body = encodeURIComponent("Thought this might be useful:\n\n" + url);
  window.location.href = "mailto:?subject=" + subject + "&body=" + body;
};

window.shareTextPage = function (event) {
  if (event) event.preventDefault();
  const url = window.location.href;
  const body = encodeURIComponent("Check this out: " + url);
  // SMS links work best on phones
  window.location.href = "sms:?&body=" + body;
};

window.shareRedditPage = function (event) {
  if (event) event.preventDefault();
  const url = encodeURIComponent(window.location.href);
  const title = encodeURIComponent(document.title || "Opportunity list");
  window.open(`https://www.reddit.com/submit?url=${url}&title=${title}`, "_blank", "noopener,noreferrer");
};

window.shareFacebookPage = function (event) {
  if (event) event.preventDefault();
  const url = encodeURIComponent(window.location.href);
  window.open(`https://www.facebook.com/sharer/sharer.php?u=${url}`, "_blank", "noopener,noreferrer");
};
// ----------------------------
// Share button handlers (globals)
// ----------------------------
window.shareSmsPage = function (event) {
  if (event) event.preventDefault();
  const url = window.location.href;
  const body = encodeURIComponent("Check this out:\n" + url);
  // Works best on mobile
  window.location.href = "sms:?&body=" + body;
};

window.shareEmailPage = function (event) {
  if (event) event.preventDefault();
  const url = window.location.href;
  const subject = encodeURIComponent(document.title || "Link");
  const body = encodeURIComponent("Thought this might be useful:\n\n" + url);
  window.location.href = "mailto:?subject=" + subject + "&body=" + body;
};

window.shareFacebookPage = function (event) {
  if (event) event.preventDefault();
  const url = encodeURIComponent(window.location.href);
  window.open(
    "https://www.facebook.com/sharer/sharer.php?u=" + url,
    "_blank",
    "noopener,noreferrer"
  );
};

window.shareRedditPage = function (event) {
  if (event) event.preventDefault();
  const url = encodeURIComponent(window.location.href);
  const title = encodeURIComponent(document.title || "Link");
  window.open(
    "https://www.reddit.com/submit?url=" + url + "&title=" + title,
    "_blank",
    "noopener,noreferrer"
  );
};
