/* Study workspace: documents, job-independent question sets and audio.

   The page needs no build step and no framework. Documents and questions both
   come from the same API the job page uses, so a document uploaded here is
   available to a job pack and the other way round. */
(function () {
    'use strict';

    const list = document.querySelector('[data-study-list]');
    if (!list) return;

    const csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';
    const form = document.querySelector('[data-study-form]');
    const upload = document.querySelector('[data-study-upload]');
    const questionCount = document.querySelector('[data-study-question-count]');
    const generateStatus = document.querySelector('[data-study-status]');
    const uploadStatus = document.querySelector('[data-study-upload-status]');
    const audioStatus = document.querySelector('[data-study-audio-status]');
    const sourceList = document.querySelector('[data-study-source-list]');
    const sourcePicks = document.querySelector('[data-study-source-picks]');
    const interviewerSelect = document.querySelector('[data-voice-interviewer]');
    const intervieweeSelect = document.querySelector('[data-voice-interviewee]');
    const player = document.querySelector('[data-study-player]');
    let fallbackPlayer = null;

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

    async function request(url, { method = 'GET', body = null, json = false } = {}) {
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
            /* DELETE and audio may have no JSON body */
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

    // ---------------------------------------------------------------- questions

    function audioButton(text, role, label) {
        const button = make('button', 'button button--small button--ghost');
        button.type = 'button';
        button.dataset.studyAudio = '';
        button.dataset.role = role;
        button.dataset.text = text;
        button.innerHTML = `<i class="uil uil-volume button__icon button__icon--lead"></i> ${label}`;
        return button;
    }

    function questionCard(question) {
        const card = make('article', 'practice-card');
        card.dataset.questionId = question.id;

        const head = make('header', 'practice-card__head');
        head.append(make('span', 'pill', question.difficulty || 'core'));
        if (question.topic) head.append(make('span', 'chip', question.topic));
        if (question.role) head.append(make('span', 'chip', question.role));
        if (question.level) head.append(make('span', 'chip', question.level));
        if (question.source_title) head.append(make('span', 'practice-card__source', question.source_title));
        const remove = make('button', 'practice-card__remove');
        remove.type = 'button';
        remove.title = 'Delete this question';
        remove.dataset.questionDelete = '';
        remove.innerHTML = '<i class="uil uil-times"></i>';
        head.append(remove);
        card.append(head);

        card.append(make('p', 'practice-card__question', question.question));

        const actions = make('div', 'practice-card__audio');
        actions.append(audioButton(question.question, 'question', 'Hear question'));
        actions.append(audioButton(question.answer, 'answer', 'Hear answer'));
        card.append(actions);

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

    function renderQuestions(questions) {
        list.querySelectorAll('.practice-card').forEach((card) => card.remove());
        const empty = list.querySelector('[data-study-empty]');
        if (!questions.length) {
            if (empty) empty.hidden = false;
        } else if (empty) {
            empty.hidden = true;
        }
        questions.forEach((question) => list.append(questionCard(question)));
        if (questionCount) {
            questionCount.textContent = `${questions.length} question${questions.length === 1 ? '' : 's'}`;
        }
    }

    async function loadQuestions() {
        try {
            const data = await request('/api/study/questions');
            renderQuestions(data.questions || []);
        } catch (error) {
            status(generateStatus, error.message, 'error');
        }
    }

    list.addEventListener('click', async (event) => {
        const remove = event.target.closest('[data-question-delete]');
        if (remove) {
            const card = remove.closest('[data-question-id]');
            remove.disabled = true;
            try {
                await request(`/api/interview/questions/${card.dataset.questionId}`, { method: 'DELETE' });
                card.remove();
                const left = list.querySelectorAll('.practice-card').length;
                if (questionCount) {
                    questionCount.textContent = `${left} question${left === 1 ? '' : 's'}`;
                }
                if (!left) {
                    const empty = list.querySelector('[data-study-empty]');
                    if (empty) empty.hidden = false;
                }
            } catch (error) {
                remove.disabled = false;
                status(generateStatus, error.message, 'error');
            }
            return;
        }

        const play = event.target.closest('[data-study-audio]');
        if (play) {
            await speak(play);
        }
    });

    async function speak(button) {
        const restore = busy(button, 'Loading...');
        status(audioStatus, 'Preparing audio...', 'busy');
        const role = button.dataset.role;
        const voice = role === 'answer'
            ? intervieweeSelect?.value || ''
            : interviewerSelect?.value || '';
        try {
            const response = await fetch('/api/study/audio', {
                method: 'POST',
                headers: { 'X-CSRF-Token': csrf, 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: button.dataset.text, role, voice }),
                credentials: 'same-origin',
            });
            if (!response.ok) {
                const data = await response.json().catch(() => ({}));
                throw new Error(data?.error?.message || `Audio failed with HTTP ${response.status}.`);
            }
            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            if (player) {
                player.pause();
                player.src = url;
                player.load();
                try {
                    await player.play();
                    status(audioStatus, '', '');
                } catch (error) {
                    // Some browsers refuse autoplay after an awaited fetch. The
                    // controls are already loaded, so the reader can press play.
                    status(audioStatus, 'Audio is ready — press play in the player.', '');
                    player.focus();
                }
                player.addEventListener('ended', () => URL.revokeObjectURL(url), { once: true });
                return;
            }
            if (fallbackPlayer) fallbackPlayer.pause();
            fallbackPlayer = new Audio(url);
            fallbackPlayer.addEventListener('ended', () => URL.revokeObjectURL(url), { once: true });
            await fallbackPlayer.play();
            status(audioStatus, '', '');
        } catch (error) {
            status(audioStatus, error.message, 'error');
        } finally {
            restore();
        }
    }

    if (form) {
        form.addEventListener('submit', async (event) => {
            event.preventDefault();
            const button = form.querySelector('[data-study-generate-button]');
            const restore = busy(button, 'Writing...');
            status(generateStatus, 'Generating questions and answers...', 'busy');
            const data = new FormData(form);
            const payload = {
                role: data.get('role') || '',
                level: data.get('level') || '',
                count: Number(data.get('count') || 8),
                difficulty: data.get('difficulty') || 'mixed',
                focus: data.get('focus') || '',
                source_ids: [...sourcePicks.querySelectorAll('input[type="checkbox"]:checked')]
                    .map((input) => Number(input.value)),
            };
            try {
                const result = await request('/api/study/questions', {
                    method: 'POST',
                    body: payload,
                    json: true,
                });
                const questions = result.questions || [];
                const existing = [...list.querySelectorAll('.practice-card')]
                    .map((card) => Number(card.dataset.questionId));
                const fresh = questions.filter((question) => !existing.includes(question.id));
                fresh.reverse().forEach((question) => list.prepend(questionCard(question)));
                const total = list.querySelectorAll('.practice-card').length;
                if (questionCount) {
                    questionCount.textContent = `${total} question${total === 1 ? '' : 's'}`;
                }
                list.querySelector('[data-study-empty]')?.setAttribute('hidden', '');
                status(generateStatus, `Added ${fresh.length} question${fresh.length === 1 ? '' : 's'}.`, '');
            } catch (error) {
                status(generateStatus, error.message, 'error');
            } finally {
                restore();
            }
        });
    }

    // ---------------------------------------------------------------- documents

    function sourceCard(source) {
        const card = make('article', 'source-card');
        card.dataset.sourceId = source.id;

        const head = make('header', 'source-card__head');
        const pick = make('label', 'source-card__pick');
        const checkbox = make('input');
        checkbox.type = 'checkbox';
        checkbox.value = source.id;
        checkbox.dataset.studySourcePick = '';
        pick.append(checkbox);
        pick.append(make('span', null, 'Use in the next set'));
        head.append(pick);

        const identity = make('div', 'source-card__id');
        identity.append(make('span', 'pill source-card__kind', source.kind));
        identity.append(make('h3', 'source-card__title', source.title));
        head.append(identity);
        const remove = make('button', 'practice-card__remove');
        remove.type = 'button';
        remove.title = 'Delete this document';
        remove.dataset.sourceDelete = '';
        remove.innerHTML = '<i class="uil uil-trash-alt"></i>';
        head.append(remove);
        card.append(head);

        const meta = make('p', 'source-card__meta');
        const parts = [];
        if (source.chars) parts.push(`${source.chars.toLocaleString()} characters`);
        if (source.questions) parts.push(`${source.questions} questions`);
        if (source.created_at) parts.push(source.created_at.slice(0, 10));
        meta.textContent = parts.join(' · ');
        card.append(meta);
        return card;
    }

    function renderSources(sources) {
        sourceList.querySelectorAll('.source-card').forEach((card) => card.remove());
        const empty = sourceList.querySelector('[data-study-sources-empty]');
        if (empty) empty.hidden = sources.length > 0;
        sources.forEach((source) => sourceList.append(sourceCard(source)));

        const previous = new Map(
            [...sourcePicks.querySelectorAll('input[type="checkbox"]')]
                .map((input) => [input.value, input.checked])
        );
        sourcePicks.replaceChildren();
        if (!sources.length) {
            sourcePicks.append(make('p', 'field__hint', 'No documents yet — upload one to ground the questions.'));
            return;
        }
        sources.forEach((source) => {
            const label = make('label', 'source-pick');
            const checkbox = make('input');
            checkbox.type = 'checkbox';
            checkbox.value = source.id;
            checkbox.dataset.studySourcePick = '';
            checkbox.checked = previous.get(String(source.id)) || false;
            label.append(checkbox);
            label.append(make('span', null, source.title));
            sourcePicks.append(label);
        });
    }

    async function loadSources() {
        try {
            const data = await request('/api/interview/sources');
            renderSources(data.sources || []);
        } catch (error) {
            status(uploadStatus, error.message, 'error');
        }
    }

    sourceList?.addEventListener('click', async (event) => {
        const remove = event.target.closest('[data-source-delete]');
        if (!remove) return;
        const card = remove.closest('[data-source-id]');
        remove.disabled = true;
        try {
            await request(`/api/interview/sources/${card.dataset.sourceId}`, { method: 'DELETE' });
            await loadSources();
        } catch (error) {
            remove.disabled = false;
            status(uploadStatus, error.message, 'error');
        }
    });

    if (upload) {
        upload.addEventListener('submit', async (event) => {
            event.preventDefault();
            const button = upload.querySelector('[data-study-upload-button]');
            const data = new FormData(upload);
            const hasFile = data.get('file') && data.get('file').size;
            if (!hasFile) data.delete('file');
            if (!hasFile && !String(data.get('text') || '').trim() && !String(data.get('url') || '').trim()) {
                status(uploadStatus, 'Add a file, some text or a URL first.', 'error');
                return;
            }
            const restore = busy(button, 'Saving...');
            status(uploadStatus, 'Reading and indexing the document...', 'busy');
            try {
                const response = await fetch('/api/interview/sources', {
                    method: 'POST',
                    headers: { 'X-CSRF-Token': csrf },
                    body: data,
                    credentials: 'same-origin',
                });
                const result = await response.json().catch(() => ({}));
                if (!response.ok) {
                    throw new Error(result?.error?.message || `The upload failed with HTTP ${response.status}.`);
                }
                upload.reset();
                status(uploadStatus, 'Saved.', '');
                await loadSources();
            } catch (error) {
                status(uploadStatus, error.message, 'error');
            } finally {
                restore();
            }
        });
    }

    // ---------------------------------------------------------------- voices

    async function loadVoices() {
        try {
            const data = await request('/api/tts/voices');
            const fill = (select, role) => {
                if (!select) return;
                const current = select.value;
                select.replaceChildren(make('option', null, 'Provider default'));
                select.options[0].value = '';
                (data.voices || []).forEach((voice) => {
                    const option = make('option', null, `${voice.name}${voice.accent ? ` · ${voice.accent}` : ''}`);
                    option.value = voice.id;
                    select.append(option);
                });
                const wanted = current || data.defaults?.[role] || '';
                if (wanted && [...select.options].some((option) => option.value === wanted)) {
                    select.value = wanted;
                }
            };
            fill(interviewerSelect, 'interviewer');
            fill(intervieweeSelect, 'interviewee');
        } catch (error) {
            status(audioStatus, 'Voices could not be loaded; the provider default will be used.', 'error');
        }
    }

    loadSources();
    loadQuestions();
    loadVoices();
})();
