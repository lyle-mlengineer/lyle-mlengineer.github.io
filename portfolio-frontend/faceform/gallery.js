const ITEMS = [
  {
    id: "g01",
    name: "Audrey",
    img: "images/gallery-01.png",
    prompt: "Editorial headshot, freckles, soft window light, sage backdrop",
    ratio: "4:5",
    time: "2h ago",
    date: "Oct 30, 2026",
    seed: "8841203",
    days: 0,
  },
  {
    id: "g02",
    name: "Kenji",
    img: "images/gallery-04.png",
    prompt: "Tech founder, round glasses, warm smile, peach backdrop",
    ratio: "1:1",
    time: "5h ago",
    date: "Oct 30, 2026",
    seed: "7719904",
    days: 0,
  },
  {
    id: "g03",
    name: "Naomi",
    img: "images/gallery-02.png",
    prompt: "Beauty close-up, long box braids, glossy skin, lilac backdrop",
    ratio: "4:5",
    time: "1d ago",
    date: "Oct 29, 2026",
    seed: "6642301",
    days: 1,
  },
  {
    id: "g04",
    name: "Marcus",
    img: "images/gallery-03.png",
    prompt: "Corporate executive, grey beard, powder-blue backdrop",
    ratio: "9:16",
    time: "1d ago",
    date: "Oct 29, 2026",
    seed: "5580427",
    days: 1,
  },
  {
    id: "g05",
    name: "Priya",
    img: "images/gallery-05.png",
    prompt: "Finance lead, short dark bob, neutral expression, ivory backdrop",
    ratio: "4:5",
    time: "2d ago",
    date: "Oct 28, 2026",
    seed: "4231188",
    days: 2,
  },
  {
    id: "g06",
    name: "Ellis",
    img: "images/gallery-06.png",
    prompt: "Travel creator, curly hair, relaxed smile, olive backdrop",
    ratio: "4:5",
    time: "3d ago",
    date: "Oct 27, 2026",
    seed: "3104772",
    days: 3,
  },
  {
    id: "g07",
    name: "Ava",
    img: "images/sample-ava.png",
    prompt: "Warm portrait, dark curly hair, terracotta knit, natural light",
    ratio: "4:5",
    time: "5d ago",
    date: "Oct 25, 2026",
    seed: "2988110",
    days: 5,
  },
  {
    id: "g08",
    name: "Theo",
    img: "images/sample-theo.png",
    prompt: "Product designer, round glasses, soft studio light",
    ratio: "1:1",
    time: "6d ago",
    date: "Oct 24, 2026",
    seed: "1944203",
    days: 6,
  },
  {
    id: "g09",
    name: "Nora",
    img: "images/sample-nora.png",
    prompt: "Candid laugh, golden hour, sage studio backdrop",
    ratio: "9:16",
    time: "8d ago",
    date: "Oct 22, 2026",
    seed: "1877120",
    days: 8,
  },
];

const SIZES = {
  "4:5": "1080 × 1350",
  "1:1": "1080 × 1080",
  "9:16": "1080 × 1920",
};

const deleted = new Set(FF.store.get("gallery.deleted", []));
const favourites = new Set(FF.store.get("gallery.favs", ["g01", "g04"]));
let items = ITEMS.filter((item) => !deleted.has(item.id));

const galleryEl = document.getElementById("userGallery");
const countEl = document.getElementById("galleryCount");
const searchEl = document.getElementById("gallerySearch");
const sortEl = document.getElementById("gallerySort");
const filterEl = document.getElementById("galleryFilters");
const lightbox = document.getElementById("lightbox");

let filter = "all";
let query = "";
let currentId = null;

function saveFavourites() {
  FF.store.set("gallery.favs", [...favourites]);
}

function visibleItems() {
  const filtered = items.filter((item) => {
    const matchesQuery =
      !query ||
      item.name.toLowerCase().includes(query) ||
      item.prompt.toLowerCase().includes(query);

    if (!matchesQuery) return false;
    if (filter === "favourites") return favourites.has(item.id);
    if (filter === "week") return item.days <= 7;
    if (["4:5", "1:1", "9:16"].includes(filter)) return item.ratio === filter;
    return true;
  });

  return filtered.sort((a, b) =>
    sortEl.value === "oldest" ? b.days - a.days : a.days - b.days
  );
}

function starSvg() {
  return `<svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true">
    <path d="m12 3 2.7 5.6 6.1.9-4.4 4.3 1 6.1-5.4-2.9-5.4 2.9 1-6.1L3.2 9.5l6.1-.9L12 3z"
      fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" />
  </svg>`;
}

function render() {
  const list = visibleItems();
  galleryEl.replaceChildren();

  countEl.textContent =
    list.length === items.length
      ? `${items.length} generation${items.length === 1 ? "" : "s"}`
      : `${list.length} of ${items.length} generations`;

  if (!list.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";

    const title = document.createElement("strong");
    title.textContent = items.length ? "No generations match those filters" : "Your gallery is empty";

    const copy = document.createElement("p");
    copy.textContent = items.length
      ? "Try a different search or framing."
      : "Generate your first face in the studio and it will show up here.";

    empty.append(title, copy);

    if (query || filter !== "all") {
      const reset = document.createElement("button");
      reset.type = "button";
      reset.className = "btn btn-outline";
      reset.textContent = "Clear filters";
      reset.addEventListener("click", () => {
        query = "";
        filter = "all";
        searchEl.value = "";
        filterEl.querySelectorAll(".chip").forEach((chip) => {
          chip.classList.toggle("is-active", chip.dataset.filter === "all");
        });
        render();
      });
      empty.append(reset);
    }

    galleryEl.append(empty);
    return;
  }

  list.forEach((item) => {
    const card = document.createElement("article");
    card.className = "ug-card";
    card.dataset.id = item.id;

    const open = document.createElement("button");
    open.type = "button";
    open.className = "ug-open";
    open.dataset.open = item.id;
    open.setAttribute("aria-label", `Preview ${item.name}`);

    const img = document.createElement("img");
    img.src = item.img;
    img.alt = `${item.name} — ${item.prompt}`;
    img.loading = "lazy";

    const ratio = document.createElement("span");
    ratio.className = "ug-ratio";
    ratio.textContent = item.ratio;
    open.append(img, ratio);

    const fav = document.createElement("button");
    fav.type = "button";
    fav.className = "fav-btn";
    fav.dataset.fav = item.id;
    fav.setAttribute("aria-pressed", String(favourites.has(item.id)));
    fav.setAttribute(
      "aria-label",
      `${favourites.has(item.id) ? "Remove" : "Add"} ${item.name} ${favourites.has(item.id) ? "from" : "to"} favourites`
    );
    fav.innerHTML = starSvg();

    const meta = document.createElement("p");
    meta.className = "ug-meta";
    const name = document.createElement("strong");
    name.textContent = item.name;
    const time = document.createElement("span");
    time.textContent = item.time;
    meta.append(name, time);

    card.append(open, fav, meta);
    galleryEl.append(card);
  });
}

function syncFavButton(id) {
  const isFav = favourites.has(id);
  document.querySelectorAll(`[data-fav="${id}"]`).forEach((btn) => {
    btn.setAttribute("aria-pressed", String(isFav));
    const item = items.find((entry) => entry.id === id);
    btn.setAttribute(
      "aria-label",
      `${isFav ? "Remove" : "Add"} ${item.name} ${isFav ? "from" : "to"} favourites`
    );
  });
}

function toggleFavourite(id) {
  const item = items.find((entry) => entry.id === id);
  if (!item) return;

  if (favourites.has(id)) {
    favourites.delete(id);
    FF.toast(`${item.name} removed from favourites`);
  } else {
    favourites.add(id);
    FF.toast(`${item.name} added to favourites`);
  }

  saveFavourites();
  syncFavButton(id);

  if (currentId === id) syncDialogFav();
  if (filter === "favourites") render();
}

function openLightbox(id) {
  const item = items.find((entry) => entry.id === id);
  if (!item) return;
  currentId = id;

  document.getElementById("lbImg").src = item.img;
  document.getElementById("lbImg").alt = `${item.name} — ${item.prompt}`;
  document.getElementById("lbName").textContent = item.name;
  document.getElementById("lbPrompt").textContent = `“${item.prompt}”`;
  document.getElementById("lbRatio").textContent = item.ratio;
  document.getElementById("lbSize").textContent = SIZES[item.ratio];
  document.getElementById("lbSeed").textContent = item.seed;
  document.getElementById("lbDate").textContent = item.date;

  const download = document.getElementById("lbDownload");
  download.href = item.img;
  download.setAttribute("download", `faceform-${item.name.toLowerCase()}.png`);

  syncDialogFav();
  lightbox.showModal();
}

function syncDialogFav() {
  const favBtn = document.getElementById("lbFav");
  const isFav = favourites.has(currentId);
  favBtn.setAttribute("aria-pressed", String(isFav));
  favBtn.textContent = isFav ? "Favourited" : "Favourite";
}

galleryEl.addEventListener("click", (event) => {
  const favBtn = event.target.closest("[data-fav]");
  if (favBtn) {
    toggleFavourite(favBtn.dataset.fav);
    return;
  }

  const open = event.target.closest("[data-open]");
  if (open) openLightbox(open.dataset.open);
});

filterEl.addEventListener("click", (event) => {
  const chip = event.target.closest(".chip");
  if (!chip) return;
  filter = chip.dataset.filter;
  filterEl.querySelectorAll(".chip").forEach((el) => {
    el.classList.toggle("is-active", el === chip);
  });
  render();
});

searchEl.addEventListener("input", () => {
  query = searchEl.value.trim().toLowerCase();
  render();
});

sortEl.addEventListener("change", render);

document.getElementById("lbClose").addEventListener("click", () => lightbox.close());

lightbox.addEventListener("click", (event) => {
  if (event.target === lightbox) lightbox.close();
});

lightbox.addEventListener("close", () => {
  currentId = null;
});

document.getElementById("lbFav").addEventListener("click", () => {
  if (currentId) toggleFavourite(currentId);
});

document.getElementById("lbDelete").addEventListener("click", () => {
  if (!currentId) return;
  const item = items.find((entry) => entry.id === currentId);
  deleted.add(currentId);
  FF.store.set("gallery.deleted", [...deleted]);
  favourites.delete(currentId);
  saveFavourites();
  items = items.filter((entry) => entry.id !== currentId);
  lightbox.close();
  render();
  FF.toast(`${item.name} deleted from your gallery`);
});

render();
