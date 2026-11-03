/*==================== BLOG ====================*/
/* Shared by index.html (blog section) and articles.html (all articles).
   Content comes from js/articles.js through loadArticles(). */

const ARTICLES_PAGE = "articles.html";

function blogFormatDate(iso) {
    const d = new Date(iso + "T00:00:00");
    return d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

function blogTagsHtml(tags) {
    return `<ul class="chips">${tags.map(t => `<li>${t}</li>`).join("")}</ul>`;
}

function blogCardHtml(a) {
    return `
        <img src="${a.image}" alt="${a.imageAlt}" class="blog__img">
        <div class="blog__data">
            <div class="blog__meta">
                <span class="blog__date">${blogFormatDate(a.date)}</span>
                <span class="blog__dot">&middot;</span>
                <span class="blog__read">${a.readTime}</span>
            </div>
            <h3 class="blog__title">${a.title}</h3>
            <p class="blog__excerpt">${a.excerpt}</p>
            ${blogTagsHtml(a.tags)}
            <span class="button button--flex button--small button--link blog__open" data-blog-slug="${a.slug}">
                Read article
                <i class="uil uil-arrow-right button__icon"></i>
            </span>
        </div>`;
}

function blogRelatedHtml(current, all) {
    const related = all
        .filter(a => a.slug !== current.slug)
        .sort((x, y) => {
            const shared = a => a.tags.filter(t => current.tags.includes(t)).length;
            return shared(y) - shared(x);
        })
        .slice(0, 3);

    if (!related.length) return "";

    return `
        <div class="blog__related">
            <h5 class="blog__related-heading">More articles</h5>
            <ul class="blog__related-list">
                ${related.map(a => `
                    <li>
                        <span class="blog__related-link" data-blog-slug="${a.slug}" role="button" tabindex="0">
                            ${a.title}
                            <i class="uil uil-arrow-right"></i>
                        </span>
                        <span class="blog__related-meta">${blogFormatDate(a.date)} &middot; ${a.readTime}</span>
                    </li>`).join("")}
            </ul>
        </div>`;
}

function blogFillModal(article, all) {
    const modal = document.getElementById("blog-modal");
    if (!modal || !article) return;

    modal.querySelector(".modal-title").textContent = article.title;
    modal.querySelector(".detail-meta").textContent =
        `${blogFormatDate(article.date)} · ${article.readTime}`;

    modal.querySelector(".blog-article").innerHTML = `
        <figure class="blog__figure">
            <img src="${article.image}" alt="${article.imageAlt}" class="blog__figure-img">
        </figure>
        <p class="blog__lead">${article.excerpt}</p>
        <div class="blog__prose">${article.body}</div>
        <div class="blog__tags">${blogTagsHtml(article.tags)}</div>
        ${blogRelatedHtml(article, all)}`;

    const allLink = modal.querySelector(".blog-modal-all");
    const onArticlesPage = window.location.pathname.split("/").pop() === ARTICLES_PAGE;
    if (onArticlesPage) {
        allLink.setAttribute("href", "#blog-list");
        allLink.querySelector("span").textContent = "Back to all articles";
    } else {
        allLink.setAttribute("href", ARTICLES_PAGE);
        allLink.querySelector("span").textContent = "All articles";
    }

    modal.querySelector(".blog-article").scrollTop = 0;
    modal.classList.add("modal-active");
    document.getElementById("blog-modal-slug").value = article.slug;
}

function blogOpenArticle(slug, all) {
    const article = all.find(a => a.slug === slug);
    if (article) blogFillModal(article, all);
}

function blogCloseArticle() {
    document.getElementById("blog-modal")?.classList.remove("modal-active");
}

async function initBlog(allArticles) {
    const articles = allArticles ?? await loadArticles();

    /* Cards on the home page */
    const homeGrid = document.querySelector("[data-blog-home]");
    if (homeGrid) {
        const featured = articles.slice(0, 3);

        homeGrid.innerHTML = featured.length
            ? featured.map(a => `<div class="blog__content swiper-slide">${blogCardHtml(a)}</div>`).join("")
            : `<div class="blog__content swiper-slide"><p class="blog__empty">New articles are on the way.</p></div>`;

        if (window.Swiper && featured.length) {
            const blogSwiper = new Swiper(".blog__container", {
                cssMode: true,
                grabCursor: true,
                watchOverflow: true,
                navigation: {
                    nextEl: ".blog__container .swiper-button-next",
                    prevEl: ".blog__container .swiper-button-prev",
                },
                pagination: {
                    el: ".blog__container .swiper-pagination",
                    clickable: true,
                },
            });

            /* The slides are injected moments before init, so Swiper's first metric
               pass can measure an empty track and lock the arrows. Re-measure once
               the browser has laid the cards out. */
            requestAnimationFrame(() => blogSwiper.update());
            window.addEventListener('load', () => blogSwiper.update());
        }
    }

    /* Full list plus tag filter on the articles page */
    const list = document.querySelector("[data-blog-list]");
    if (list) {
        const render = tags => {
            const shown = tags
                ? articles.filter(a => a.tags.includes(tags))
                : articles;
            list.innerHTML = shown.map(a =>
                `<article class="blog__card">${blogCardHtml(a)}</article>`).join("") ||
                `<p class="blog__empty">${articles.length ? "No articles with that tag yet." : "New articles are on the way."}</p>`;
            document.querySelector("[data-blog-count]") &&
                (document.querySelector("[data-blog-count]").textContent =
                    `${shown.length} of ${articles.length} articles`);
        };

        render(null);

        const filterBar = document.querySelector("[data-blog-filters]");
        if (filterBar) {
            const tags = [...new Set(articles.flatMap(a => a.tags))].sort();
            filterBar.innerHTML = ["All", ...tags].map((t, i) =>
                `<li><button type="button" class="blog__filter${i === 0 ? " blog__filter-active" : ""}" data-blog-tag="${t === "All" ? "" : t}">${t}</button></li>`).join("");

            filterBar.addEventListener("click", e => {
                const btn = e.target.closest("[data-blog-tag]");
                if (!btn) return;
                filterBar.querySelectorAll(".blog__filter").forEach(b => b.classList.remove("blog__filter-active"));
                btn.classList.add("blog__filter-active");
                render(btn.dataset.blogTag || null);
            });
        }
    }

    /* Modal wiring, delegated so rendered cards and related links both work */
    document.addEventListener("click", e => {
        const open = e.target.closest("[data-blog-slug]");
        if (open) {
            blogOpenArticle(open.dataset.blogSlug, articles);
            return;
        }
        if (e.target.closest(".blog-modal-close")) blogCloseArticle();
        if (e.target.closest(".blog-modal-all")) blogCloseArticle();
        if (e.target.id === "blog-modal") blogCloseArticle();
    });

    document.addEventListener("keydown", e => {
        if (e.key === "Enter" || e.key === " ") {
            const open = e.target.closest?.("[data-blog-slug]");
            if (open) {
                e.preventDefault();
                blogOpenArticle(open.dataset.blogSlug, articles);
            }
        }
        if (e.key === "Escape") blogCloseArticle();
    });

    /* Shared link: articles.html?article=slug opens that article */
    const slug = new URLSearchParams(window.location.search).get("article");
    if (slug) blogOpenArticle(slug, articles);
}

document.addEventListener("DOMContentLoaded", () => initBlog());
