// Renders data/deals.json. No build step, no framework.
// Path handling: on GitHub Pages the site is served from site/, so the
// data file is at ../data/deals.json; when opened from the repo root
// (or a local preview) it is at data/deals.json. Try both.
const CANDIDATE_PATHS = ["../data/deals.json", "data/deals.json", "deals.json"];

const fmt = (n) => "A$" + Number(n).toLocaleString("en-AU");

let allDeals = [];
let scannedAt = null;

async function loadDeals() {
  for (const path of CANDIDATE_PATHS) {
    try {
      const res = await fetch(path, { cache: "no-store" });
      if (!res.ok) continue;
      const data = await res.json();
      if (data && Array.isArray(data.deals) && data.deals.length) {
        return data;
      }
    } catch (e) {
      // try the next path
    }
  }
  return null;
}

function buildCategoryFilters(deals) {
  const box = document.getElementById("category-filters");
  const cats = [...new Set(deals.map((d) => d.category || "Sale"))].sort();
  box.querySelectorAll("label").forEach((el) => el.remove());
  for (const cat of cats) {
    const label = document.createElement("label");
    const input = document.createElement("input");
    input.type = "checkbox";
    input.className = "category-filter";
    input.value = cat;
    input.checked = true;
    input.addEventListener("change", render);
    label.append(input, document.createTextNode(" " + cat));
    box.appendChild(label);
  }
}

function selectedValues(selector) {
  return [...document.querySelectorAll(selector + ":checked")].map((el) => el.value);
}

function render() {
  const query = (document.getElementById("search").value || "").toLowerCase();
  const genders = selectedValues(".gender-filter");
  const categories = selectedValues(".category-filter");
  const list = document.getElementById("deals");
  list.innerHTML = "";
  const shown = allDeals.filter((d) =>
    genders.includes(d.gender) &&
    categories.includes(d.category || "Sale") &&
    (!query || d.name.toLowerCase().includes(query))
  );
  document.getElementById("empty").hidden = shown.length !== 0;
  for (const d of shown) {
    const li = document.createElement("li");
    const a = document.createElement("a");
    a.href = d.url;
    a.target = "_blank";
    a.rel = "noopener";
    a.textContent = d.name;
    const tags = document.createElement("div");
    tags.innerHTML = "";
    const genderTag = document.createElement("span");
    genderTag.className = "tag";
    genderTag.textContent = d.gender;
    const catTag = document.createElement("span");
    catTag.className = "tag";
    catTag.textContent = d.category || "Sale";
    tags.append(genderTag, catTag);
    const price = document.createElement("p");
    price.className = "price";
    const strike = document.createElement("span");
    strike.className = "strike";
    strike.textContent = fmt(d.originalPrice);
    const sale = document.createElement("span");
    sale.textContent = " → " + fmt(d.salePrice) + "  ";
    const saving = document.createElement("span");
    saving.className = "saving";
    saving.textContent = `Save ${fmt(d.saving)} (${d.discountPct}%)`;
    price.append(strike, sale, saving);
    li.append(a, tags, price);
    list.appendChild(li);
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  const data = await loadDeals();
  const meta = document.getElementById("meta");
  if (!data) {
    document.getElementById("error").hidden = false;
    meta.textContent = "No deal data available yet — the first scheduled scan has not completed.";
    return;
  }
  allDeals = data.deals;
  scannedAt = data.scannedAt;
  const when = scannedAt ? new Date(scannedAt).toLocaleString("en-AU", { timeZone: "Australia/Brisbane" }) : "unknown";
  meta.textContent = `${data.total} discounted products · last updated ${when} (Brisbane time)`;
  buildCategoryFilters(allDeals);
  document.querySelectorAll(".gender-filter").forEach((el) => el.addEventListener("change", render));
  document.getElementById("search").addEventListener("input", render);
  render();
});
