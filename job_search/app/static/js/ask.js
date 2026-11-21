/* Ask workspace: one typed interview question, answered with no job attached.

   The shape of the answer follows the subject (technical, system, low-level,
   coding, behavioural, work history, about yourself). Answers are saved, so the
   cards below the form are the same cards the job page's answer finder shows, and
   every failure is written into a status line instead of the console. */
(function () {
    'use strict';

    const panel = document.querySelector('[data-ask]');
    if (!panel) return;

    const csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';
    const form = panel.querySelector('[data-ask-form]');
    const topicSelect = panel.querySelector('[data-ask-topic]');
    const topicHint = panel.querySelector('[data-ask-topic-hint]');
    const questionInput = panel.querySelector('[data-ask-question]');
    const askStatus = panel.querySelector('[data-ask-status]');

    const result = panel.querySelector('[data-ask-result]');
    const emptyState = panel.querySelector('[data-ask-empty]');
    const answerTopic = panel.querySelector('[data-ask-answer-topic]');

    const list = document.querySelector('[data-ask-list]');
    const count = document.querySelector('[data-ask-count]');

    let lastAnswer = '';

    function status(node, message, tone) {
        if (!node) return;
        node.textContent = message || '';
        node.classList.toggle('is-error', tone === 'error');
        node.classList.toggle('is-busy', tone === 'busy');
    }

    function make(tag, className, text) {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (text !== undefined && text !== null) node.textContent = text;
        return node;
    }

    function listOf(items, className) {
        const node = make('ul', className || 'practice-card__list');
        items.forEach((item) => node.append(make('li', null, item)));
        return node;
    }

    async function request(url, { method = 'GET', body = null } = {}) {
        const headers = { 'X-CSRF-Token': csrf };
        if (body) headers['Content-Type'] = 'application/json';
        const response = await fetch(url, {
            method,
            headers,
            body: body ? JSON.stringify(body) : null,
            credentials: 'same-origin',
        });
        let data = null;
        try {
            data = await response.json();
        } catch (error) {
            /* DELETE has no body */
        }
        if (!response.ok) {
            const message = data?.error?.message || `The server returned HTTP ${response.status}.`;
            throw new Error(message);
        }
        return data || {};
    }

    function busy(button, label) {
        if (!button) return () => {};
        const original = button.innerHTML;
        button.disabled = true;
        button.innerHTML = `<i class="uil uil-spinner-alt button__icon button__icon--lead"></i> ${label}`;
        return () => {
            button.disabled = false;
            button.innerHTML = original;
        };
    }

    // ------------------------------------------------------------- the answer

    function fillList(selector, labelSelector, items) {
        const node = panel.querySelector(selector);
        if (!node) return;
        node.innerHTML = '';
        (items || []).forEach((item) => node.append(make('li', null, item)));
        node.hidden = !(items || []).length;
        const label = panel.querySelector(labelSelector);
        if (label) label.hidden = !(items || []).length;
    }

    function showAnswer(data, asked) {
        lastAnswer = data.answer || '';
        panel.querySelector('[data-ask-question-text]').textContent = data.question || asked;
        panel.querySelector('[data-ask-body]').textContent = lastAnswer;
        fillList('[data-ask-followups]', '[data-ask-followups-label]', data.follow_ups);
        fillList('[data-ask-cites]', '[data-ask-cites-label]', data.citations);
        if (answerTopic) {
            answerTopic.textContent = data.topic || '';
            answerTopic.hidden = !data.topic;
        }
        if (result) result.hidden = false;
        if (emptyState) emptyState.hidden = true;
    }

    // ------------------------------------------------------------- history cards

    function answerCard(question) {
        const card = make('article', 'practice-card');
        card.dataset.questionId = question.id;
        card.dataset.origin = 'answer';

        const head = make('header', 'practice-card__head');
        head.append(make('span', 'chip', question.topic || 'Technical'));
        if (question.role) head.append(make('span', 'pill pill--neutral', question.role));
        if (question.level) head.append(make('span', 'chip', question.level));
        if (question.created_at) {
            head.append(make('span', 'practice-card__source', question.created_at.slice(0, 10)));
        }
        const remove = make('button', 'practice-card__remove');
        remove.type = 'button';
        remove.title = 'Delete this answer';
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
                const data = await request(`/api/interview/questions/${questionId}/follow-up-answers`, {
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

    function updateCount() {
        if (!count || !list) return;
        const total = list.querySelectorAll('.practice-card').length;
        count.textContent = `${total} answered`;
        const empty = list.querySelector('[data-ask-list-empty]');
        if (empty) empty.hidden = total > 0;
    }

    // ------------------------------------------------------------- ask

    function topicOptionLabel() {
        return topicSelect?.selectedOptions?.[0]?.textContent?.trim() || '';
    }

    topicSelect?.addEventListener('change', () => {
        const hint = topicSelect.selectedOptions?.[0]?.dataset?.hint || '';
        if (topicHint) topicHint.textContent = hint;
    });

    form?.addEventListener('submit', async (event) => {
        event.preventDefault();
        const question = (questionInput?.value || '').trim();
        if (question.length < 5) {
            status(askStatus, 'Type a question first.', 'error');
            questionInput?.focus();
            return;
        }
        const restore = busy(panel.querySelector('[data-ask-submit]'), 'Writing…');
        status(askStatus, 'Matching your documents and writing the answer…', 'busy');
        try {
            const data = await request('/api/ask', {
                method: 'POST',
                body: {
                    question,
                    topic: topicSelect?.value || 'technical',
                    role: form.querySelector('[name="role"]')?.value.trim() || '',
                    level: form.querySelector('[name="level"]')?.value || '',
                },
            });
            showAnswer(data, question);
            if (list) {
                list.querySelector('[data-ask-list-empty]')?.remove();
                list.prepend(answerCard(data));
                updateCount();
            }
            if (questionInput) questionInput.value = '';
            const confidence = data.confidence ? ` (${data.confidence} confidence)` : '';
            status(askStatus, `Answered as ${topicOptionLabel() || 'a general'} answer${confidence}.`);
        } catch (error) {
            status(askStatus, error.message, 'error');
        } finally {
            restore();
        }
    });

    panel.querySelector('[data-ask-copy]')?.addEventListener('click', async () => {
        if (!lastAnswer) return;
        try {
            await navigator.clipboard.writeText(lastAnswer);
            status(askStatus, 'Answer copied.');
        } catch (error) {
            status(askStatus, 'Could not copy. Select the answer and copy it manually.', 'error');
        }
    });

    // ------------------------------------------------------------- history

    // Server-rendered cards bind their follow-up sections here; cards added after
    // an ask bind themselves as they are created.
    list?.querySelectorAll('[data-followup-answers]:not([data-loaded="true"])').forEach((details) => {
        const card = details.closest('[data-question-id]');
        if (card) bindFollowUps(details, card.dataset.questionId);
    });

    list?.addEventListener('click', async (event) => {
        const remove = event.target.closest('[data-question-delete]');
        if (!remove) return;
        const card = remove.closest('[data-question-id]');
        if (!card) return;
        remove.disabled = true;
        try {
            await request(`/api/interview/questions/${card.dataset.questionId}`, { method: 'DELETE' });
            card.remove();
            updateCount();
        } catch (error) {
            remove.disabled = false;
            status(askStatus, error.message, 'error');
        }
    });

    updateCount();
})();
