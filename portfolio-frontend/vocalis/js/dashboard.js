/*=============== DASHBOARD ===============*/
(() => {
  'use strict';

  const { speak, stopSpeech, toast } = window.Vocalis;

  const gallery = document.getElementById('voiceGallery');
  if (!gallery) return;

  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

  /*=============== AUTHORIZED ARRIVAL ===============*/
  const params = new URLSearchParams(window.location.search);
  if (params.get('authorized')) {
    const client = params.get('client') || 'The application';
    window.setTimeout(() => toast(`${client} is connected to your workspace.`), 400);

    params.delete('authorized');
    params.delete('client');
    const query = params.toString();
    try {
      window.history.replaceState({}, '', `${window.location.pathname}${query ? `?${query}` : ''}${window.location.hash}`);
    } catch (error) {
      /* file:// in some browsers refuses history updates */
    }
  }

  /*=============== SMOOTH ANCHORS ===============*/
  $$('a[href^="#"]').forEach((link) => {
    const id = link.getAttribute('href').slice(1);
    if (!id) return;
    const target = document.getElementById(id);
    if (!target) return;

    link.addEventListener('click', (event) => {
      event.preventDefault();
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  });

  /*=============== GALLERY FILTER + SEARCH ===============*/
  const search = document.getElementById('gallerySearch');
  const filters = $$('.filter');
  const voiceItems = $$('.voice-item', gallery);
  const emptyState = document.getElementById('galleryEmpty');
  const invoiceRows = $$('.invoice-table tbody tr');

  let activeFilter = 'all';

  const invoiceEmptyRow = document.createElement('tr');
  invoiceEmptyRow.className = 'invoice-empty';
  invoiceEmptyRow.hidden = true;
  const invoiceEmptyCell = document.createElement('td');
  invoiceEmptyCell.colSpan = 5;
  invoiceEmptyCell.textContent = 'No invoices match that search.';
  invoiceEmptyRow.appendChild(invoiceEmptyCell);
  if (invoiceRows.length) {
    invoiceRows[invoiceRows.length - 1].after(invoiceEmptyRow);
  }

  const matchesQuery = (item, query) => {
    if (!query) return true;
    const tags = item.querySelector('.voice-item__tags');
    const haystack = [
      item.dataset.name,
      item.dataset.lang,
      item.querySelector('p') ? item.querySelector('p').textContent : '',
      tags ? tags.textContent : '',
      item.querySelector('.voice-item__badge') ? item.querySelector('.voice-item__badge').textContent : '',
    ]
      .join(' ')
      .toLowerCase();
    return haystack.includes(query);
  };

  const applyFilters = () => {
    const query = (search ? search.value : '').trim().toLowerCase();
    const counts = { all: 0, designed: 0, cloned: 0 };
    let visible = 0;

    voiceItems.forEach((item) => {
      const queryOk = matchesQuery(item, query);
      if (queryOk) {
        counts.all += 1;
        counts[item.dataset.type] += 1;
      }

      const typeOk = activeFilter === 'all' || item.dataset.type === activeFilter;
      const show = queryOk && typeOk;
      item.hidden = !show;
      if (show) visible += 1;
    });

    filters.forEach((button) => {
      const count = button.querySelector('span');
      if (count) count.textContent = String(counts[button.dataset.filter] || 0);
      const active = button.dataset.filter === activeFilter;
      button.classList.toggle('is-active', active);
      button.setAttribute('aria-pressed', String(active));
    });

    if (emptyState) emptyState.hidden = visible > 0;

    let invoiceVisible = 0;
    invoiceRows.forEach((row) => {
      const show = !query || row.textContent.toLowerCase().includes(query);
      row.hidden = !show;
      if (show) invoiceVisible += 1;
    });
    invoiceEmptyRow.hidden = !query || invoiceVisible > 0;
  };

  filters.forEach((button) => {
    button.addEventListener('click', () => {
      activeFilter = button.dataset.filter;
      applyFilters();
    });
  });

  if (search) {
    search.addEventListener('input', applyFilters);
    search.addEventListener('search', applyFilters);
  }

  applyFilters();

  /*=============== VOICE PREVIEWS ===============*/
  const setTileState = (item, active) => {
    item.classList.toggle('is-playing', active);
    const button = item.querySelector('.voice-item__play');
    if (!button) return;
    button.innerHTML = `<i class="ri-${active ? 'stop' : 'play'}-fill"></i>`;
    button.setAttribute('aria-label', `${active ? 'Stop' : 'Play'} ${item.dataset.name}`);
  };

  voiceItems.forEach((item) => {
    const button = item.querySelector('.voice-item__play');
    if (!button) return;

    button.addEventListener('click', () => {
      if (item.classList.contains('is-playing')) {
        stopSpeech();
        return;
      }

      const started = speak({
        text: item.dataset.line,
        lang: item.dataset.lang,
        pitch: Number(item.dataset.pitch) || 1,
        rate: Number(item.dataset.rate) || 1,
        onStart: () => setTileState(item, true),
        onEnd: () => setTileState(item, false),
      });

      if (!started) {
        toast('This browser can’t preview voices — try Chrome, Edge or Safari.');
      }
    });
  });
})();
