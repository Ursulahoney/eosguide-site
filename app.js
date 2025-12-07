let ALL_ROWS = [];
let CURRENT_STATE = "MT";
let CURRENT_CATEGORY = "All";

const priorityOrder = { high: 0, medium: 1, low: 2 };
const speedOrder = { Fast: 0, Medium: 1, Slow: 2 };

// Categories that feel like "money you might be owed or can claim"
const MONEY_FIRST_CATEGORIES = new Set([
  "Unclaimed money & refunds",
  "Legal settlements & enforcement",
  "Tax & property relief",
  "Utilities & energy",
  "Health & medical debt",
  "Veterans",
  "Tribal programs",
  "Education & student help",
  "Agriculture & rural",
  "Business & jobs"
]);

// Help / assistance style categories (shown later / separate)
const ASSISTANCE_CATEGORIES = new Set([
  "Social services & safety net",
  "Other"
]);

// Category display order for sorting within groups
const CATEGORY_PRIORITY = {
  "Unclaimed money & refunds": 1,
  "Legal settlements & enforcement": 2,
  "Tax & property relief": 3,
  "Utilities & energy": 4,
  "Health & medical debt": 5,
  "Veterans": 6,
  "Tribal programs": 7,
  "Education & student help": 8,
  "Agriculture & rural": 9,
  "Business & jobs": 10,
  "Social services & safety net": 11,
  "Other": 12
};

document.addEventListener("DOMContentLoaded", () => {
  loadData();
  setupFilterListeners();
});

function loadData() {
  Papa.parse("opportunities_tagged_with_state.csv", {
    header: true,
    skipEmptyLines: true,
    download: true,
    complete: (results) => {
      ALL_ROWS = results.data || [];
      initStateSelector();
      initCategoryChips();
      renderAll();
    },
    error: (err) => {
      console.error("Error loading CSV:", err);
    }
  });
}

function setupFilterListeners() {
  const searchInput = document.getElementById("search-input");
  const speedSelect = document.getElementById("speed-select");
  const difficultySelect = document.getElementById("difficulty-select");
  const proofSelect = document.getElementById("proof-select");
  const stateSelect = document.getElementById("state-select");
  const clearFiltersButton = document.getElementById("clear-filters-button");

  // OPTION A: search overrides category
  searchInput.addEventListener(
    "input",
    debounce(() => {
      const value = searchInput.value;

      // When user is typing anything, reset category to All
      if (value.trim() !== "") {
        CURRENT_CATEGORY = "All";

        const chips = document.querySelectorAll("#category-chips .chip");
        chips.forEach((el) => el.classList.remove("chip-active"));

        const firstChip = document.querySelector("#category-chips .chip");
        if (firstChip) {
          firstChip.classList.add("chip-active");
        }
      }

      renderAll();
    }, 250)
  );

  speedSelect.addEventListener("change", renderAll);
  difficultySelect.addEventListener("change", renderAll);
  proofSelect.addEventListener("change", renderAll);

  stateSelect.addEventListener("change", () => {
    CURRENT_STATE = stateSelect.value;
    renderAll();
  });

  clearFiltersButton.addEventListener("click", () => {
    resetFilters();
    renderAll();
  });
}

function resetFilters() {
  document.getElementById("search-input").value = "";
  document.getElementById("speed-select").value = "";
  document.getElementById("difficulty-select").value = "";
  document.getElementById("proof-select").value = "";
  CURRENT_CATEGORY = "All";

  document
    .querySelectorAll("#category-chips .chip")
    .forEach((chip) => chip.classList.remove("chip-active"));

  const firstChip = document.querySelector("#category-chips .chip");
  if (firstChip) {
    firstChip.classList.add("chip-active");
  }
}

function initStateSelector() {
  const stateSelect = document.getElementById("state-select");
  const states = Array.from(
    new Set(ALL_ROWS.map((row) => (row.state || "").trim()).filter(Boolean))
  ).sort();

  stateSelect.innerHTML = "";
  states.forEach((state) => {
    const opt = document.createElement("option");
    opt.value = state;
    opt.textContent = state;
    stateSelect.appendChild(opt);
  });

  if (states.includes("MT")) {
    stateSelect.value = "MT";
    CURRENT_STATE = "MT";
  } else if (states.length > 0) {
    stateSelect.value = states[0];
    CURRENT_STATE = states[0];
  }
}

function initCategoryChips() {
  const container = document.getElementById("category-chips");
  container.innerHTML = "";

  const categories = Array.from(
    new Set(
      ALL_ROWS.map((row) => (row.category || "").trim()).filter(Boolean)
    )
  ).sort((a, b) => {
    const aRank = CATEGORY_PRIORITY[a] ?? 999;
    const bRank = CATEGORY_PRIORITY[b] ?? 999;
    return aRank - bRank;
  });

  const allChip = createChipElement("All");
  allChip.classList.add("chip-active");
  container.appendChild(allChip);

  categories.forEach((cat) => {
    const chip = createChipElement(cat);
    container.appendChild(chip);
  });
}

function createChipElement(label) {
  const chip = document.createElement("button");
  chip.type = "button";
  chip.className = "chip";
  chip.textContent = label;
  chip.dataset.category = label;

  chip.addEventListener("click", () => {
    CURRENT_CATEGORY = label;
    document
      .querySelectorAll("#category-chips .chip")
      .forEach((el) => el.classList.remove("chip-active"));
    chip.classList.add("chip-active");
    renderAll();
  });

  return chip;
}

function renderAll() {
  const filtered = applyFilters();
  renderSpotlight(filtered);
  renderGroupedResults(filtered);
}

function applyFilters() {
  const searchValue = document
    .getElementById("search-input")
    .value.trim()
    .toLowerCase();
  const speedValue = document.getElementById("speed-select").value;
  const difficultyValue = document.getElementById("difficulty-select").value;
  const proofValue = document.getElementById("proof-select").value;

  let rows = ALL_ROWS.filter((row) => {
    if (CURRENT_STATE && (row.state || "").trim() !== CURRENT_STATE) {
      return false;
    }

    if (CURRENT_CATEGORY && CURRENT_CATEGORY !== "All") {
      if ((row.category || "").trim() !== CURRENT_CATEGORY) return false;
    }

    if (speedValue && (row.money_speed || "").trim() !== speedValue) {
      return false;
    }

    if (
      difficultyValue &&
      (row.difficulty || "").trim() !== difficultyValue
    ) {
      return false;
    }

    if (proofValue && (row.proof_simple || "").trim() !== proofValue) {
      return false;
    }

    if (searchValue) {
      const haystack =
        (row.title || "") +
        " " +
        (row.description_short || "") +
        " " +
        (row.company_or_agency || "");
      if (!haystack.toLowerCase().includes(searchValue)) {
        return false;
      }
    }

    return true;
  });

  rows.sort((a, b) => {
    const catA = a.category || "";
    const catB = b.category || "";
    const catRankA = CATEGORY_PRIORITY[catA] ?? 999;
    const catRankB = CATEGORY_PRIORITY[catB] ?? 999;
    if (catRankA !== catRankB) return catRankA - catRankB;

    const prA = (a.priority_for_user || "").toLowerCase();
    const prB = (b.priority_for_user || "").toLowerCase();
    const prScoreA = priorityOrder[prA] ?? 99;
    const prScoreB = priorityOrder[prB] ?? 99;
    if (prScoreA !== prScoreB) return prScoreA - prScoreB;

    const spA = a.money_speed || "";
    const spB = b.money_speed || "";
    const spScoreA = speedOrder[spA] ?? 99;
    const spScoreB = speedOrder[spB] ?? 99;
    if (spScoreA !== spScoreB) return spScoreA - spScoreB;

    const dA = a.date_found || "";
    const dB = b.date_found || "";
    if (dA > dB) return -1;
    if (dA < dB) return 1;
    return 0;
  });

  return rows;
}

function renderSpotlight(rows) {
  const container = document.getElementById("spotlight-carousel");
  container.innerHTML = "";

  const spotlight = rows.filter((row) => {
    const cat = row.category || "";
    if (!MONEY_FIRST_CATEGORIES.has(cat)) return false;

    const pr = (row.priority_for_user || "").toLowerCase();
    const speed = row.money_speed || "";
    const status = (row.status || "").toLowerCase();
    const isHigh = pr === "high";
    const isMed = pr === "medium";
    const isFastish = speed === "Fast" || speed === "Medium";
    const isOpen = !status || status === "open";

    return isOpen && (isHigh || isMed) && isFastish;
  });

  const top = spotlight.slice(0, 8);

  if (top.length === 0) {
    const msg = document.createElement("div");
    msg.className = "empty-message";
    msg.textContent = "No spotlight programs match your filters yet.";
    container.appendChild(msg);
    return;
  }

  top.forEach((row) => {
    const card = document.createElement("article");
    card.className = "spotlight-card";

    const header = document.createElement("div");
    header.className = "spotlight-card-header";

    const title = document.createElement("h3");
    title.className = "spotlight-card-title";
    title.textContent = row.title || "Untitled opportunity";

    const desc = document.createElement("p");
    desc.className = "spotlight-card-text";
    desc.textContent =
      (row.description_short || "").slice(0, 200) ||
      "Program or refund worth checking.";

    header.appendChild(title);
    header.appendChild(desc);

    const badges = document.createElement("div");
    badges.className = "badge-row";

    const catBadge = document.createElement("span");
    catBadge.className = "badge";
    catBadge.textContent = row.category || "Other";
    badges.appendChild(catBadge);

    if (row.money_speed) {
      const sp = document.createElement("span");
      sp.className = "badge";
      sp.textContent = "Speed: " + row.money_speed;
      badges.appendChild(sp);
    }

    if (row.difficulty) {
      const diff = document.createElement("span");
      diff.className = "badge badge-outline";
      diff.textContent = "Difficulty: " + row.difficulty;
      badges.appendChild(diff);
    }

    const footer = document.createElement("div");
    footer.className = "spotlight-card-footer";

    const stateLabel = document.createElement("span");
    stateLabel.className = "section-subtitle";
    stateLabel.textContent = row.state || "";

    const actions = document.createElement("div");
    const infoUrl = (row.url_info || "").trim();
    const claimUrl = (row.url_claim || "").trim();
    const mainUrl = claimUrl || infoUrl;

    if (mainUrl) {
      const btn = document.createElement("button");
      btn.className = "link-button";
      btn.textContent = "Open official page";
      btn.addEventListener("click", () => {
        window.open(mainUrl, "_blank");
      });
      actions.appendChild(btn);
    }

    footer.appendChild(stateLabel);
    footer.appendChild(actions);

    card.appendChild(header);
    card.appendChild(badges);
    card.appendChild(footer);

    container.appendChild(card);
  });
}

function renderGroupedResults(rows) {
  const moneyList = document.getElementById("money-first-list");
  const assistList = document.getElementById("assistance-list");
  const moneyBlock = document.getElementById("money-first-block");
  const assistBlock = document.getElementById("assistance-block");
  const countLabel = document.getElementById("results-count");

  moneyList.innerHTML = "";
  assistList.innerHTML = "";

  countLabel.textContent = `${rows.length} opportunities found`;

  if (rows.length === 0) {
    moneyBlock.style.display = "none";
    assistBlock.style.display = "none";

    const empty = document.createElement("div");
    empty.className = "empty-message";
    empty.textContent =
      "No results match your filters yet. Try clearing filters or changing your search.";
    moneyList.appendChild(empty);
    return;
  }

  const moneyRows = [];
  const assistRows = [];

  rows.forEach((row) => {
    const cat = row.category || "";
    if (ASSISTANCE_CATEGORIES.has(cat)) {
      assistRows.push(row);
    } else {
      moneyRows.push(row);
    }
  });

  if (moneyRows.length > 0) {
    moneyBlock.style.display = "";
    moneyRows.forEach((row) => {
      const card = buildResultCard(row);
      moneyList.appendChild(card);
    });
  } else {
    moneyBlock.style.display = "none";
  }

  if (assistRows.length > 0) {
    assistBlock.style.display = "";
    assistRows.forEach((row) => {
      const card = buildResultCard(row);
      assistList.appendChild(card);
    });
  } else {
    assistBlock.style.display = "none";
  }
}

function buildResultCard(row) {
  const card = document.createElement("article");
  card.className = "result-card";

  const header = document.createElement("div");
  header.className = "result-card-header";

  const titleRow = document.createElement("div");
  titleRow.className = "result-title-row";

  const emojiSpan = document.createElement("span");
  emojiSpan.className = "result-emoji";
  emojiSpan.textContent = getCategoryEmoji(row.category || "");

  const title = document.createElement("h3");
  title.className = "result-title";
  title.textContent = row.title || "Untitled opportunity";

  titleRow.appendChild(emojiSpan);
  titleRow.appendChild(title);

  const agency = document.createElement("div");
  agency.className = "result-agency";
  agency.textContent = row.company_or_agency || "";

  header.appendChild(titleRow);
  if (agency.textContent) header.appendChild(agency);

  const desc = document.createElement("p");
  desc.className = "result-desc";
  desc.textContent =
    (row.description_short || "").slice(0, 240) ||
    "Program or opportunity that may reduce bills or bring in money.";

  const metaRow = document.createElement("div");
  metaRow.className = "result-meta-row";

  const catPill = document.createElement("span");
  catPill.className = "pill";
  catPill.textContent = row.category || "Other";
  metaRow.appendChild(catPill);

  if (row.money_speed) {
    const sp = document.createElement("span");
    sp.className =
      "pill " + (row.money_speed === "Fast" ? "pill-fast" : "");
    sp.textContent = row.money_speed + " money";
    metaRow.appendChild(sp);
  }

  if (row.difficulty) {
    const diff = document.createElement("span");
    diff.className =
      "pill " + (row.difficulty === "Hard" ? "pill-hard" : "");
    diff.textContent = "Difficulty: " + row.difficulty;
    metaRow.appendChild(diff);
  }

  if (row.proof_simple) {
    const proof = document.createElement("span");
    proof.className = "pill";
    proof.textContent = "Paperwork: " + row.proof_simple;
    metaRow.appendChild(proof);
  }

  if (row.state) {
    const st = document.createElement("span");
    st.className = "pill";
    st.textContent = row.state;
    metaRow.appendChild(st);
  }

  const actions = document.createElement("div");
  actions.className = "result-actions";

  const infoUrl = (row.url_info || "").trim();
  const claimUrl = (row.url_claim || "").trim();

  if (claimUrl) {
    const a = document.createElement("a");
    a.href = claimUrl;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    a.className = "result-link primary-link";
    a.textContent = "Go to application / claim page";
    actions.appendChild(a);
  }

  if (infoUrl && infoUrl !== claimUrl) {
    const a2 = document.createElement("a");
    a2.href = infoUrl;
    a2.target = "_blank";
    a2.rel = "noopener noreferrer";
    a2.className = "result-link";
    a2.textContent = "Read more details";
    actions.appendChild(a2);
  }

  card.appendChild(header);
  card.appendChild(desc);
  card.appendChild(metaRow);
  card.appendChild(actions);

  return card;
}

function getCategoryEmoji(category) {
  switch (category) {
    case "Unclaimed money & refunds":
      return "💵";
    case "Legal settlements & enforcement":
      return "📝";
    case "Tax & property relief":
      return "🏡";
    case "Utilities & energy":
      return "⚡";
    case "Health & medical debt":
      return "🏥";
    case "Social services & safety net":
      return "❤️";
    case "Education & student help":
      return "🎓";
    case "Veterans":
      return "🇺🇸";
    case "Tribal programs":
      return "🪶";
    case "Agriculture & rural":
      return "🚜";
    case "Business & jobs":
      return "💼";
    default:
      return "✨";
  }
}

function debounce(fn, delay) {
  let t;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn.apply(null, args), delay);
  };
}
