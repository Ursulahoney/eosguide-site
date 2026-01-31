// src/assets/app.js

function getCards() {
  return Array.from(document.querySelectorAll("#opportunitiesGrid article"));
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
