/* Interview study: the Practice and Sources tabs.

   Practice questions come from the server; this file asks for a new set, appends
   the cards, reveals answers, and looks one up. Sources are uploaded with the
   same session and CSRF header as the rest of the app. No frameworks, no build
   step, and every failure is written into a status line instead of a console. */
(function () {
    'use strict';

    const panel = document.getElementById('interview-panel');
    if (!panel) return;

    const csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';
    const practice = panel.querySelector('[data-practice]');
    const resources = panel.querySelector('[data-resources]');
    const jobId = practice?.dataset.job || resources?.dataset.job || '';
    const practiceList = practice?.querySelector('[data-practice-list]');
    const sourceList = resources?.querySelector('[data-source-list]');
    const practiceStatus = practice?.querySelector('[data-practice-status]');
    const resourceStatus = resources?.querySelector('[data-source-status]');

    // -- tab hash: a reload should land back on the same tab ----------------
    const tabs = [...panel.querySelectorAll('[data-tab]')];
    tabs.forEach((tab) => {
        tab.addEventListener('click', () => {
            history.replaceState(null, '', `#${tab.dataset.tab}`);
        });
    });
    const wanted = (window.location.hash || '').replace('#', '');
    if (['practice', 'resources', 'audio', 'script'].includes(wanted)) {
        panel.querySelector(`[data-tab="${wanted}"]`)?.click();
    }

    function status(node, message, tone) {
        if (!node) return;
        node.textContent = message || '';
        node.classList.toggle('is-error', tone === 'error');
        node.classList.toggle('is-busy', tone === 'busy');
    }

    function busy(button, label) {
        const original = button.innerHTML;
        button.disabled = true;
        button.innerHTML = `<i class="uil uil-spinner-alt button__icon button__icon--lead"></i> ${label}`;
        return () => {
            button.disabled = false;
            button.innerHTML = original;
        };
    }

    async function requestJSON(url, { method = 'GET', body = null, json = false } = {}) {
        const headers = { 'X-CSRF-Token': csrf };
        if (json) headers['Content-Type'] = 'application/json';
        const response = await fetch(url, {
            method,
            headers,
            body: json && body ? JSON.stringify(body) : body,
            credentials: 'same-origin',
        });
        let data = null;
        try {
            data = await response.json();
        } catch (error) {
            /* an empty body is fine for DELETE */
        }
        if (!response.ok) {
            const message = data?.error?.message || `The server returned HTTP ${response.status}.`;
            throw new Error(message);
        }
        return data || {};
    }

    function make(tag, className, text) {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (text !== undefined && text !== null) node.textContent = text;
        return node;
    }

    function listOf(items, className) {
        const list = make('ul', className || 'practice-card__list');
        items.forEach((item) => list.append(make('li', null, item)));
        return list;
    }

    function questionCard(question) {
        const card = make('article', 'practice-card');
        card.dataset.questionId = question.id;
        card.dataset.origin = question.origin || 'practice';

        const head = make('header', 'practice-card__head');
        head.append(make('span', 'chip', question.topic || 'General'));
        head.append(make('span', 'pill', question.difficulty || 'core'));
        if (question.source_title) {
            head.append(make('span', 'practice-card__source', question.source_title));
        }
        const remove = make('button', 'practice-card__remove');
        remove.type = 'button';
        remove.title = 'Remove this question';
        remove.dataset.questionDelete = '';
        remove.innerHTML = '<i class="uil uil-times"></i>';
        head.append(remove);
        card.append(head);

        card.append(make('p', 'practice-card__question', question.question));

        const details = make('details', 'practice-card__answer');
        details.append(make('summary', null, 'Show answer'));
        const body = make('div', 'practice-card__body');
        body.append(make('p', null, question.answer));
        if (question.follow_ups?.length) {
            body.append(make('p', 'practice-card__label', 'Follow-ups'));
            body.append(listOf(question.follow_ups));
            body.append(followUpAnswers(question));
        }
        if (question.citations?.length) {
            body.append(make('p', 'practice-card__label', 'Grounded in'));
            body.append(listOf(question.citations, 'practice-card__list practice-card__list--cite'));
        }
        details.append(body);
        card.append(details);
        return card;
    }

    function followUpAnswers(question) {
        const details = make('details', 'followup-answers');
        details.dataset.followupAnswers = '';
        details.append(make('summary', null, 'Suggested answers'));
        const body = make('div', 'followup-answers__body');
        details.append(body);
        renderFollowUps(body, question.follow_up_answers || []);
        if ((question.follow_up_answers || []).length) details.dataset.loaded = 'true';
        else body.append(make('p', 'followup-answers__hint', 'Open to write one answer for each follow-up.'));
        bindFollowUps(details, question.id);
        return details;
    }

    function renderFollowUps(body, answers) {
        body.innerHTML = '';
        answers.forEach((item) => {
            const row = make('div', 'followup-answer');
            row.append(make('p', 'followup-answer__question', item.question || ''));
            row.append(make('p', 'followup-answer__text', item.answer || ''));
            body.append(row);
        });
    }

    function bindFollowUps(details, questionId) {
        details.addEventListener('toggle', async () => {
            if (!details.open || details.dataset.loaded === 'true' || details.dataset.loading === 'true') return;
            details.dataset.loading = 'true';
            const body = details.querySelector('[data-followup-body]') || details.querySelector('.followup-answers__body');
            if (!body) return;
            body.innerHTML = '';
            body.append(make('p', 'followup-answers__hint', 'Writing answers…'));
            try {
                const data = await requestJSON(`/api/interview/questions/${questionId}/follow-up-answers`, {
                    method: 'POST',
                });
                renderFollowUps(body, data.answers || []);
                if (!(data.answers || []).length) {
                    body.append(make('p', 'followup-answers__hint', 'No answers came back. Try again.'));
                } else {
                    details.dataset.loaded = 'true';
                }
            } catch (error) {
                body.innerHTML = '';
                body.append(make('p', 'followup-answers__hint', error.message));
            } finally {
                delete details.dataset.loading;
            }
        });
    }

    function sourceCard(source) {
        const card = make('article', 'source-card');
        card.dataset.sourceId = source.id;

        const head = make('header', 'source-card__head');
        const identity = make('div', 'source-card__id');
        identity.append(make('span', 'pill source-card__kind', source.kind));
        identity.append(make('h3', 'source-card__title', source.title));
        head.append(identity);
        const remove = make('button', 'practice-card__remove');
        remove.type = 'button';
        remove.title = 'Delete this source';
        remove.dataset.sourceDelete = '';
        remove.innerHTML = '<i class="uil uil-trash-alt"></i>';
        head.append(remove);
        card.append(head);

        const meta = `${(source.chars || 0).toLocaleString()} characters · ${source.chunks} chunk${
            source.chunks === 1 ? '' : 's'
        }${source.questions ? ` · ${source.questions} question${source.questions === 1 ? '' : 's'} generated` : ''}${
            source.filename ? ` · ${source.filename}` : ''
        }`;
        card.append(make('p', 'source-card__meta', meta));
        if (source.source_url) {
            const urlLine = make('p', 'source-card__meta');
            const link = make('a', null, source.source_url);
            link.href = source.source_url;
            link.target = '_blank';
            link.rel = 'noopener noreferrer';
            urlLine.append(link);
            card.append(urlLine);
        }

        const preview = make('details', 'source-card__preview');
        preview.append(make('summary', null, 'Preview the extracted text'));
        preview.append(make('p', null, source.excerpt));
        card.append(preview);

        const actions = make('div', 'source-card__actions');
        const generate = make('button', 'button button--small button--ghost');
        generate.type = 'button';
        generate.dataset.sourceQuestions = '';
        generate.innerHTML = '<i class="uil uil-question-circle button__icon button__icon--lead"></i> Generate questions';
        actions.append(generate);
        card.append(actions);
        return card;
    }

    function clearEmpty(container, selector) {
        container?.querySelector(selector)?.remove();
    }

    function prependQuestions(questions) {
        if (!practiceList) return;
        clearEmpty(practiceList, '[data-practice-empty]');
        const fragment = document.createDocumentFragment();
        (questions || []).forEach((question) => fragment.append(questionCard(question)));
        practiceList.prepend(fragment);
    }

    async function refreshSources() {
        if (!sourceList) return;
        const data = await requestJSON('/api/interview/sources');
        sourceList.innerHTML = '';
        if (!data.sources?.length) {
            const empty = make('div', 'empty');
            empty.dataset.sourceEmpty = '';
            empty.innerHTML = '<span class="empty__icon"><i class="uil uil-folder-open"></i></span>'
                + '<h3 class="empty__title">No sources yet</h3>'
                + '<p class="empty__copy">Add a PDF, a DOCX, an article link or pasted text.</p>';
            sourceList.append(empty);
        } else {
            data.sources.forEach((source) => sourceList.append(sourceCard(source)));
        }
        const count = resources.querySelector('[data-source-count]');
        if (count) {
            const n = data.sources?.length || 0;
            count.textContent = `${n} source${n === 1 ? '' : 's'}`;
        }
    }

    // -- practice ----------------------------------------------------------
    practice?.querySelector('[data-practice-generate]')?.addEventListener('click', async (event) => {
        const button = event.currentTarget;
        const count = Number(practice.querySelector('[data-practice-count]')?.value || 8);
        const difficulty = practice.querySelector('[data-practice-difficulty]')?.value || 'mixed';
        const focus = practice.querySelector('[data-practice-focus]')?.value.trim() || '';
        const restore = busy(button, 'Writing…');
        status(practiceStatus, 'Sampling your sources and writing answers…', 'busy');
        try {
            const data = await requestJSON(`/api/jobs/${jobId}/interview/practice`, {
                method: 'POST',
                json: true,
                body: { count, difficulty, focus, seed: Date.now() % 1_000_000 },
            });
            prependQuestions(data.questions);
            status(practiceStatus, `Added ${data.questions.length} questions. Answer them out loud before revealing.`);
        } catch (error) {
            status(practiceStatus, error.message, 'error');
        } finally {
            restore();
        }
    });

    practice?.querySelector('[data-reveal-all]')?.addEventListener('click', () => {
        practiceList?.querySelectorAll('details').forEach((details) => {
            details.open = true;
        });
    });

    practiceList?.querySelectorAll('[data-followup-answers]:not([data-loaded="true"])').forEach((details) => {
        const card = details.closest('[data-question-id]');
        if (card) bindFollowUps(details, card.dataset.questionId);
    });

    practiceList?.addEventListener('click', async (event) => {
        const remove = event.target.closest('[data-question-delete]');
        if (!remove) return;
        const card = remove.closest('[data-question-id]');
        if (!card) return;
        try {
            await requestJSON(`/api/interview/questions/${card.dataset.questionId}`, { method: 'DELETE' });
            card.remove();
        } catch (error) {
            status(practiceStatus, error.message, 'error');
        }
    });

    // -- answer finder -----------------------------------------------------
    const answerForm = practice?.querySelector('[data-answer-form]');
    const answerResult = practice?.querySelector('[data-answer-result]');
    const answerStatus = practice?.querySelector('[data-answer-status]');
    let lastAnswer = '';

    answerForm?.addEventListener('submit', async (event) => {
        event.preventDefault();
        const input = practice.querySelector('[data-answer-question]');
        const question = (input?.value || '').trim();
        if (!question) {
            status(answerStatus, 'Type a question first.', 'error');
            return;
        }
        const button = practice.querySelector('[data-answer-submit]');
        const restore = busy(button, 'Searching…');
        status(answerStatus, 'Matching your sources and writing an answer…', 'busy');
        try {
            const data = await requestJSON(`/api/jobs/${jobId}/interview/answer`, {
                method: 'POST',
                json: true,
                body: { question },
            });
            lastAnswer = data.answer || '';
            practice.querySelector('[data-answer-question-text]').textContent = data.question || question;
            practice.querySelector('[data-answer-body]').textContent = lastAnswer;
            const followups = practice.querySelector('[data-answer-followups]');
            followups.innerHTML = '';
            (data.follow_ups || []).forEach((item) => followups.append(make('li', null, item)));
            practice.querySelector('[data-answer-followups-label]').hidden = !(data.follow_ups || []).length;
            followups.hidden = !(data.follow_ups || []).length;
            const cites = practice.querySelector('[data-answer-cites]');
            cites.innerHTML = '';
            (data.citations || []).forEach((item) => cites.append(make('li', null, item)));
            practice.querySelector('[data-answer-cites-label]').hidden = !(data.citations || []).length;
            cites.hidden = !(data.citations || []).length;
            answerResult.hidden = false;
            status(answerStatus, data.confidence ? `Answer ready (${data.confidence} confidence).` : 'Answer ready.');
        } catch (error) {
            status(answerStatus, error.message, 'error');
        } finally {
            restore();
        }
    });

    practice?.querySelector('[data-answer-copy]')?.addEventListener('click', async () => {
        if (!lastAnswer) return;
        try {
            await navigator.clipboard.writeText(lastAnswer);
            status(answerStatus, 'Answer copied.');
        } catch (error) {
            status(answerStatus, 'Could not copy. Select the answer and copy it manually.', 'error');
        }
    });

    // -- sources -----------------------------------------------------------
    const sourceForm = resources?.querySelector('[data-source-form]');
    const fileInput = resources?.querySelector('[data-source-file]');
    const fileName = resources?.querySelector('[data-source-file-name]');

    fileInput?.addEventListener('change', () => {
        if (fileName) {
            fileName.textContent = fileInput.files?.[0]?.name || 'PDF, DOCX, MD or text';
        }
    });

    sourceForm?.addEventListener('submit', async (event) => {
        event.preventDefault();
        const submit = resources.querySelector('[data-source-submit]');
        const data = new FormData();
        const title = resources.querySelector('[data-source-title]')?.value.trim() || '';
        const text = resources.querySelector('[data-source-text]')?.value.trim() || '';
        const url = resources.querySelector('[data-source-url]')?.value.trim() || '';
        const file = fileInput?.files?.[0];

        if (!file && !text && !url) {
            status(resourceStatus, 'Choose a file, paste text, or give an article link.', 'error');
            return;
        }
        data.append('title', title);
        if (file) data.append('file', file);
        else if (text) data.append('text', text);
        else data.append('url', url);

        const restore = busy(submit, 'Reading…');
        status(resourceStatus, 'Extracting the text and indexing it…', 'busy');
        try {
            const result = await requestJSON('/api/interview/sources', { method: 'POST', body: data });
            sourceForm.reset();
            if (fileName) fileName.textContent = 'PDF, DOCX, MD or text';
            await refreshSources();
            status(resourceStatus, `Added “${result.source.title}” (${result.source.chunks} chunks).`);
        } catch (error) {
            status(resourceStatus, error.message, 'error');
        } finally {
            restore();
        }
    });

    sourceList?.addEventListener('click', async (event) => {
        const card = event.target.closest('[data-source-id]');
        if (!card) return;
        const id = card.dataset.sourceId;

        if (event.target.closest('[data-source-delete]')) {
            if (!window.confirm('Delete this source and its index? Generated questions stay.')) return;
            try {
                await requestJSON(`/api/interview/sources/${id}`, { method: 'DELETE' });
                await refreshSources();
                status(resourceStatus, 'Source deleted.');
            } catch (error) {
                status(resourceStatus, error.message, 'error');
            }
            return;
        }

        const generate = event.target.closest('[data-source-questions]');
        if (!generate) return;
        const restore = busy(generate, 'Writing…');
        status(resourceStatus, 'Writing questions from this source…', 'busy');
        try {
            const data = await requestJSON(`/api/interview/sources/${id}/questions`, {
                method: 'POST',
                json: true,
                body: { job_id: Number(jobId), count: 5, seed: Date.now() % 1_000_000 },
            });
            prependQuestions(data.questions);
            panel.querySelector('[data-tab="practice"]')?.click();
            status(practiceStatus, `Added ${data.questions.length} questions from this source.`);
            status(resourceStatus, '');
        } catch (error) {
            status(resourceStatus, error.message, 'error');
        } finally {
            restore();
        }
    });
})();
