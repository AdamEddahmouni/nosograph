/*
 * NosoGraph — community experience prototype (synthetic, read-only).
 *
 * BOUNDARY CONTRACT
 * -----------------
 * This file renders a fixed, in-memory fixture list. It is deliberately not a
 * feature of the research product:
 *
 *   - No network access of any kind. Nothing is requested and nothing is sent.
 *   - No browser persistence. No storage of any kind, including local or
 *     session storage, cookies, or client databases.
 *   - No accounts, no authentication, no submission path, no moderation
 *     backend, no reporting backend.
 *   - Every post is fabricated for layout testing. `synthetic: true` is part of
 *     the data, rendered as a visible badge, and never inferred at render time.
 *   - Community experience is not scientific evidence. Nothing in this file
 *     may be joined to the claim/evidence model, and no post may be presented
 *     as supporting or contradicting a biomedical association.
 *
 * If this prototype is ever promoted toward a real surface, it needs a threat
 * model, a retention policy, a moderation duty-of-care plan, and independent
 * privacy review first. Those do not exist yet, and this file must not be
 * mistaken for them.
 */

'use strict';

/*
 * Fixture list. Bodies are short, deliberately non-clinical placeholders: no
 * symptoms, severities, drugs, doses, outcomes, dates, or counts are invented,
 * because inventing any of those would be fabricating health data.
 */
const POSTS = [
    {
        id: 'sle-001',
        disease: 'sle',
        synthetic: true,
        content_origin: 'fabricated_placeholder',
        moderation: 'published',
        theme: 'Appointment coordination',
        body:
            'Placeholder narrative about coordinating appointments across more than one ' +
            'clinic. No clinical detail is recorded, and no outcome is described.'
    },
    {
        id: 'sle-002',
        disease: 'sle',
        synthetic: true,
        content_origin: 'fabricated_placeholder',
        moderation: 'pending_review',
        theme: 'Waiting-room experience',
        body:
            'Placeholder narrative about waiting-room comfort and how delays were ' +
            'communicated. Intended to exercise the pending moderation state only.'
    },
    {
        id: 'sle-003',
        disease: 'sle',
        synthetic: true,
        content_origin: 'fabricated_placeholder',
        moderation: 'hidden_insufficient_context',
        theme: 'Care-team continuity',
        body:
            'Withheld in this prototype because the sample post does not record the ' +
            'context a real moderation policy would require before showing it.'
    },
    {
        id: 'ra-001',
        disease: 'ra',
        synthetic: true,
        content_origin: 'fabricated_placeholder',
        moderation: 'published',
        theme: 'Administrative burden',
        body:
            'Placeholder narrative about paperwork and referral handling. Written to ' +
            'show a published card, not to report anyone\'s experience.'
    },
    {
        id: 'ra-002',
        disease: 'ra',
        synthetic: true,
        content_origin: 'fabricated_placeholder',
        moderation: 'pending_review',
        theme: 'Travel to appointments',
        body:
            'Placeholder narrative about travel planning for routine visits. No ' +
            'clinical content, no outcome, no measurement.'
    },
    {
        id: 'ra-003',
        disease: 'ra',
        synthetic: true,
        content_origin: 'fabricated_placeholder',
        moderation: 'published',
        theme: 'Written visit summaries',
        body:
            'Placeholder narrative about receiving written summaries after a visit. ' +
            'Illustrates card layout and the published state.'
    },
    {
        id: 't1d-001',
        disease: 't1d',
        synthetic: true,
        content_origin: 'fabricated_placeholder',
        moderation: 'pending_review',
        theme: 'Routine coordination',
        body:
            'Placeholder narrative about fitting a daily routine around a working day. ' +
            'Contains no clinical detail and no advice.'
    },
    {
        id: 't1d-002',
        disease: 't1d',
        synthetic: true,
        content_origin: 'fabricated_placeholder',
        moderation: 'hidden_insufficient_context',
        theme: 'Peer support',
        body:
            'Withheld in this prototype because no consent scope is recorded for it. A ' +
            'real implementation would need one before display.'
    }
];

/* Display labels for the three fixture slugs. These are abbreviation expansions
 * only; they are not curated registry metadata and must not be read as such. */
const DISEASE_LABELS = {
    sle: 'sle — systemic lupus erythematosus',
    ra: 'ra — rheumatoid arthritis',
    t1d: 't1d — type 1 diabetes'
};

/* Plain-language gloss for each moderation state. The state code is always
 * rendered verbatim next to the gloss so the state is never colour-only. */
const MODERATION_GLOSS = {
    published: 'visible in this prototype',
    pending_review: 'awaiting moderation, not shown to others',
    hidden_insufficient_context: 'withheld: the sample post records too little context'
};

const SYNTHETIC_BADGE_TEXT = 'Synthetic example';

const REPORT_STATUS_TEXT =
    'Prototype only: the report was recorded in this browser tab\'s memory and ' +
    'nothing was sent anywhere. Reload to clear it.';

/* In-memory only. Never persisted, never transmitted. */
const localReportState = new Set();

const diseaseFilter = document.getElementById('comm-disease-filter');
const stateFilter = document.getElementById('comm-state-filter');
const postsList = document.getElementById('comm-posts');
const resultCount = document.getElementById('comm-result-count');
const reportStatus = document.getElementById('comm-report-status');

function populateDiseaseFilter() {
    const seen = [];
    for (const post of POSTS) {
        if (!seen.includes(post.disease)) {
            seen.push(post.disease);
        }
    }
    for (const slug of seen) {
        const option = document.createElement('option');
        option.value = slug;
        option.textContent = DISEASE_LABELS[slug] || slug;
        diseaseFilter.appendChild(option);
    }
}

function buildStateBadge(state) {
    const badge = document.createElement('span');
    badge.className = 'comm-state comm-state--' + state;
    const gloss = MODERATION_GLOSS[state] || 'unrecognised moderation state';
    badge.textContent = state + ' — ' + gloss;
    return badge;
}

function buildReportButton(post) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'comm-button';
    button.dataset.postId = post.id;
    const pressed = localReportState.has(post.id);
    button.setAttribute('aria-pressed', pressed ? 'true' : 'false');
    button.textContent = 'Report this post (prototype)';

    button.addEventListener('click', function handleReportClick() {
        if (localReportState.has(post.id)) {
            localReportState.delete(post.id);
            button.setAttribute('aria-pressed', 'false');
            reportStatus.textContent =
                'Report withdrawn in this tab only. Nothing was sent anywhere.';
            return;
        }
        localReportState.add(post.id);
        button.setAttribute('aria-pressed', 'true');
        reportStatus.textContent = REPORT_STATUS_TEXT + ' Post id: ' + post.id + '.';
    });

    return button;
}

function buildPost(post) {
    if (post.synthetic !== true) {
        // Fail closed: an unlabelled post must never reach the page.
        return null;
    }

    const item = document.createElement('li');
    item.className = 'comm-post comm-post--' + post.moderation;
    if (post.moderation === 'hidden_insufficient_context') {
        item.classList.add('comm-post--hidden');
    }
    item.dataset.postId = post.id;

    const meta = document.createElement('p');
    meta.className = 'comm-post__meta';

    const disease = document.createElement('span');
    disease.className = 'comm-post__disease';
    disease.textContent = post.disease;
    meta.appendChild(disease);

    const synthetic = document.createElement('span');
    synthetic.className = 'comm-post__synthetic';
    synthetic.textContent = SYNTHETIC_BADGE_TEXT;
    meta.appendChild(synthetic);
    meta.appendChild(buildStateBadge(post.moderation));

    const theme = document.createElement('h3');
    theme.className = 'comm-post__theme';
    theme.textContent = post.theme;

    const body = document.createElement('p');
    body.className = 'comm-post__body';
    body.textContent = post.body;

    const footer = document.createElement('div');
    footer.className = 'comm-post__footer';

    const origin = document.createElement('span');
    origin.className = 'comm-field__hint';
    origin.textContent =
        'Fabricated placeholder (' + post.content_origin + '). Not a real account.';
    footer.appendChild(origin);
    footer.appendChild(buildReportButton(post));

    item.appendChild(meta);
    item.appendChild(theme);
    item.appendChild(body);
    item.appendChild(footer);
    return item;
}

function renderEmptyState() {
    const empty = document.createElement('li');
    empty.className = 'comm-empty';
    empty.textContent =
        'No synthetic posts match this filter. That is a property of this fixed ' +
        'fixture list, not a statement about any real community.';
    return empty;
}

function render() {
    const disease = diseaseFilter.value;
    const moderation = stateFilter.value;

    const visible = POSTS.filter(function matches(post) {
        const diseaseOk = disease === 'all' || post.disease === disease;
        const stateOk = moderation === 'all' || post.moderation === moderation;
        return diseaseOk && stateOk;
    });

    postsList.textContent = '';

    if (visible.length === 0) {
        postsList.appendChild(renderEmptyState());
    } else {
        for (const post of visible) {
            const node = buildPost(post);
            if (node) {
                postsList.appendChild(node);
            }
        }
    }

    resultCount.textContent =
        'Showing ' + visible.length + ' of ' + POSTS.length + ' synthetic posts.';
}

function init() {
    if (!diseaseFilter || !stateFilter || !postsList || !resultCount || !reportStatus) {
        return;
    }
    populateDiseaseFilter();
    diseaseFilter.addEventListener('change', render);
    stateFilter.addEventListener('change', render);
    render();
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}
