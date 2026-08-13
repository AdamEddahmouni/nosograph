/**
 * Medical Research Platform — Live Dashboard JavaScript
 * Calls the FastAPI backend to power module cards with live data.
 * Uses WebSocket for real-time job progress streaming.
 */

const API_BASE = '';

function renderCoverageBadge(coverage) {
    const level = coverage?.level || 'unknown';
    const status = coverage?.status || '';
    const label = level === 'full' ? 'Full coverage'
        : level === 'partial' || status === 'limited_coverage' ? 'Limited coverage'
        : level === 'unsupported' ? 'Unsupported for this disease'
        : 'Coverage unknown';
    const cls = level === 'full' ? 'coverage-full'
        : level === 'partial' || status === 'limited_coverage' ? 'coverage-partial' : 'coverage-unsupported';
    const details = [...(coverage?.missing_inputs || []), ...(coverage?.warnings || []), ...(status === 'limited_coverage' ? ['Coverage is limited for this disease.'] : [])];
    return `<span class="coverage-badge ${cls}" title="${escapeHtml(details.join('; '))}">${label}</span>`;
}

function renderCoveragePanel(coverage) {
    if (!coverage) return '';
    const details = [...(coverage.missing_inputs || []), ...(coverage.warnings || []), ...(coverage.limitations || [])];
    if (coverage.status === 'blocked') {
        return `<div class="coverage-panel coverage-blocked">${renderCoverageBadge(coverage)}<strong> Analysis unavailable for this disease.</strong>${details.length ? `<p>${escapeHtml(details.join(' '))}</p>` : ''}</div>`;
    }
    return `<div class="coverage-panel">${renderCoverageBadge(coverage)}${details.length ? `<p>${escapeHtml(details.join(' '))}</p>` : ''}</div>`;
}

// ── State ────────────────────────────────────────────────────────────────

const activeJobs = {};
const activeSockets = {};
let workspaceSubmissionActive = false;
let workspaceReviews = {};

function setWorkspaceSubmissionState(state) {
    const form = document.getElementById('workspace-form');
    const result = document.getElementById('workspace-result');
    const submit = document.getElementById('workspace-submit');
    const status = document.getElementById('workspace-submit-status');
    const active = ['submitting', 'running'].includes(state);
    workspaceSubmissionActive = active;
    if (form) form.setAttribute('aria-busy', String(active));
    if (result && active) result.setAttribute('aria-busy', 'true');
    if (result && !active) result.removeAttribute('aria-busy');
    if (submit) {
        submit.disabled = active;
        submit.setAttribute('aria-busy', String(active));
    }
    if (status) {
        const messages = {
            idle: 'Ready for a new research question.',
            submitting: 'Submitting workspace job…',
            running: 'Workspace job running; duplicate submissions are disabled.',
            success: 'Workspace dossier ready.',
            failure: 'Workspace run failed. Review the error and try again.',
        };
        status.textContent = messages[state] || messages.idle;
        status.dataset.state = state;
    }
}

// Live disease registry (populated on page load; consumed by the cross-disease view)
const diseaseCache = { list: null };
let diseaseSelectControl = null;
let dashboardRefreshing = false;

const DASHBOARD_MODULE_REGISTRY = {
    kg: 'knowledge_graph',
    repurpose: 'drug_repurposing',
    bioinformatics: 'gwas',
    gwas: 'gwas',
    enrichment: 'enrichment',
    ppi: 'ppi',
    monitor: 'evidence_monitor',
    extractor: 'llm_extractor',
    evidence: 'evidence_gather',
    semantic: 'semantic_search',
    literature: 'literature_mining',
    screening: 'virtual_screening',
    ml: 'ml_predictor',
    cart: 'car_t_predictor',
    biomarker: 'biomarker_discovery',
    expression: 'gene_expression',
    network: 'network_pharmacology',
    safety: 'adverse_events',
    synergy: 'drug_synergy',
    'cross-disease': 'cross_disease',
    trials: 'clinical_trials',
};

const MODULES_WITHOUT_STATIC_REPORT = new Set(['monitor', 'extractor', 'evidence']);

// ── API Helpers ──────────────────────────────────────────────────────────

async function loadWorkspaceAuth() {
    const status = document.getElementById('workspace-auth-status');
    if (!status) return;
    try {
        const session = await apiFetch('/api/auth/me');
        status.textContent = session.authenticated
            ? `Signed in as ${session.researcher_id}`
            : 'Not signed in (sign in to save private reviews)';
        status.dataset.authenticated = String(session.authenticated);
    } catch (error) {
        status.textContent = `Authentication unavailable: ${error.message}`;
    }
}

async function loginWorkspaceResearcher() {
    const status = document.getElementById('workspace-auth-status');
    try {
        const response = await apiFetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                username: document.getElementById('workspace-auth-username')?.value.trim() || '',
                password: document.getElementById('workspace-auth-password')?.value || '',
            }),
        });
        if (status) status.textContent = `Signed in as ${response.researcher_id}`;
        const password = document.getElementById('workspace-auth-password');
        if (password) password.value = '';
        await Promise.all([loadWorkspaceHistory(), loadWorkspaceNotificationSettings(), loadWorkspaceAlerts()]);
    } catch (error) {
        if (status) status.textContent = `Sign-in failed: ${error.message}`;
    }
}

async function logoutWorkspaceResearcher() {
    const status = document.getElementById('workspace-auth-status');
    try {
        await apiFetch('/api/auth/logout', { method: 'POST' });
        if (status) status.textContent = 'Signed out';
    } catch (error) {
        if (status) status.textContent = `Sign-out failed: ${error.message}`;
    }
}

async function apiFetch(path, options = {}) {
    try {
        const headers = {
            'Accept': 'application/json',
            ...options.headers,
        };
        const res = await fetch(`${API_BASE}${path}`, {
            ...options,
            credentials: 'same-origin',
            headers,
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: res.statusText }));
            throw new Error(err.detail || `HTTP ${res.status}`);
        }
        return await res.json();
    } catch (e) {
        if (e.name === 'TypeError' && e.message.includes('fetch')) {
            throw new Error('API server is not running. Start with: python -m med_research.cli serve');
        }
        throw e;
    }
}

function formatNumber(n) {
    return n != null ? n.toLocaleString() : '…';
}

function escapeHtml(text) {
    return String(text == null ? '' : text)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function workspaceDateLabel(value) {
    const text = String(value || '').trim();
    return text ? text.slice(0, 10) : 'Unknown date';
}

// ── Module Execution ─────────────────────────────────────────────────────

const diseaseQS = () => `disease=${encodeURIComponent(getActiveDisease())}`;
const diseaseIdQS = () => `disease_id=${encodeURIComponent(getActiveDisease())}`;

function workspaceSourceLabel(source) {
    return ({ pubmed: 'PubMed', clinical_trials: 'ClinicalTrials.gov', gwas: 'GWAS Catalog', fda_labels: 'FDA / DailyMed' })[source] || source;
}

async function runModule(module) {
    const resultEl = document.getElementById(`result-${module}`);
    if (!resultEl) return;

    resultEl.className = 'module-result visible loading';
    resultEl.innerHTML = '<span class="spinner"></span> Running analysis…';

    try {
        let data;
        switch (module) {
            case 'kg':
                data = await apiFetch(`/api/kg/stats?${diseaseQS()}`);
                renderKGResult(resultEl, data);
                break;
            case 'expression':
                data = await apiFetch(`/api/expression/correlate?top_n=10&${diseaseIdQS()}`);
                renderExpressionResult(resultEl, data);
                break;
            case 'cart':
                data = await apiFetch(`/api/cart/suitability?top_n=10&${diseaseIdQS()}`);
                renderCartResult(resultEl, data);
                break;
            case 'biomarker':
                data = await apiFetch(`/api/biomarker/discover?top_n=10&${diseaseIdQS()}`);
                renderBiomarkerResult(resultEl, data);
                break;
            case 'semantic': {
                const query = encodeURIComponent(`${activeDiseaseInfo().name} treatment drug repurposing`);
                data = await apiFetch(`/api/semantic/search?q=${query}&top_k=10&${diseaseIdQS()}`);
                renderSemanticResult(resultEl, data);
                break;
            }
            case 'evidence': {
                const query = encodeURIComponent(`${activeDiseaseInfo().name} treatment drug repurposing`);
                data = await apiFetch(`/api/evidence/gather?q=${query}&max_per_source=5&sources=pubmed,preprints,clinical_trials,fda_labels,patents&${diseaseIdQS()}`);
                renderEvidenceResult(resultEl, data);
                break;
            }
            case 'extractor': {
                const query = encodeURIComponent(`${activeDiseaseInfo().name} treatment drug repurposing`);
                data = await apiFetch(`/api/llm/extract?q=${query}&max_articles=10&sources=pubmed,preprints&${diseaseIdQS()}`);
                renderExtractorResult(resultEl, data);
                break;
            }
            case 'monitor':
                data = await apiFetch('/api/monitor/diff');
                renderMonitorResult(resultEl, data);
                break;
            case 'repurpose':
                data = await apiFetch(`/api/repurpose/candidates?top_n=10&${diseaseQS()}`);
                renderRepurposeResult(resultEl, data);
                break;
            case 'bioinformatics':
                data = await apiFetch(`/api/kg/stats?${diseaseQS()}`);
                renderBioResult(resultEl, data);
                break;
            case 'workspace':
                await streamJob(module, resultEl, { disease_id: getActiveDisease() });
                return;
            case 'gwas':
            case 'enrichment':
            case 'ppi':
            case 'literature':
            case 'screening':
            case 'trials':
            case 'ml':
                await streamJob(module, resultEl, { disease_id: getActiveDisease() });
                return;
            case 'synergy':
                await streamJob(module, resultEl, { disease_id: getActiveDisease() });
                return;
            case 'safety':
                await streamJob(module, resultEl, { disease_id: getActiveDisease() });
                return;
            default:
                throw new Error(`Unknown module: ${module}`);
        }
    } catch (e) {
        resultEl.className = 'module-result visible error';
        resultEl.innerHTML = `<strong>Error:</strong> ${e.message}`;
    }
}

// ── Job Submission + WebSocket Streaming ─────────────────────────────────

// Job route aliases used by the dashboard map to registry module_ids server-side.
const JOB_ROUTE_ALIASES = {
    cart: 'car_t_predictor',
    repurpose: 'drug_repurposing',
    biomarker: 'biomarker_discovery',
    expression: 'gene_expression',
    semantic: 'semantic_search',
    evidence: 'evidence_gather',
    extractor: 'llm_extractor',
    monitor: 'evidence_monitor',
};

async function streamJob(module, resultEl, params = {}) {
    const routeId = JOB_ROUTE_ALIASES[module] || module;
    const endpoint = module === 'workspace'
        ? '/api/jobs/workspace'
        : `/api/jobs/${encodeURIComponent(routeId)}`;

    // Submit the job (extra params become query-string arguments)
    const qs = Object.entries(params)
        .filter(([, v]) => v !== undefined && v !== null)
        .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
        .join('&');
    const requestOptions = { method: 'POST' };
    if (module === 'workspace') {
        requestOptions.headers = { 'Content-Type': 'application/json' };
        requestOptions.body = JSON.stringify(params);
    }
    const data = await apiFetch(
        module === 'workspace' ? endpoint : endpoint + (qs ? `?${qs}` : ''),
        requestOptions,
    );
    const jobId = data.job_id;
    const startTime = Date.now();

    let resolveTerminal;
    let rejectTerminal;
    const terminal = new Promise((resolve, reject) => {
        resolveTerminal = resolve;
        rejectTerminal = reject;
    });
    activeJobs[jobId] = {
        module,
        resultEl,
        status: 'PENDING',
        startTime,
        resolveTerminal,
        rejectTerminal,
    };
    if (module === 'workspace') setWorkspaceSubmissionState('running');
    updateJobBadge();
    showJobsSection();
    renderJobQueue();

    // Open WebSocket for real-time progress
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.host}/api/jobs/${jobId}/ws`;
    let ws;
    try {
        ws = new WebSocket(wsUrl);
    } catch (error) {
        settleJob(jobId, false, error.message || 'Could not open the job stream.');
        throw error;
    }

    activeSockets[jobId] = ws;
    resultEl.innerHTML = `<span class="spinner"></span> Job <code>${jobId.slice(0, 8)}&hellip;</code> submitted &mdash; streaming via WebSocket…`;

    ws.onmessage = (event) => {
        let msg;
        try {
            msg = JSON.parse(event.data);
        } catch (error) {
            resultEl.className = 'module-result visible error';
            resultEl.innerHTML = `<strong>Stream error:</strong> ${escapeHtml(error.message)}`;
            settleJob(jobId, false, 'Invalid progress message received.');
            return;
        }
        if (!activeJobs[jobId]) return;
        activeJobs[jobId].status = msg.status;
        renderJobQueue();

        if (msg.status === 'SUCCESS') {
            resultEl.className = 'module-result visible success';
            renderJobResult(module, resultEl, msg.result);
            if (module === 'workspace') loadWorkspaceHistory();
            settleJob(jobId, true);
            return;
        }

        if (msg.status === 'FAILURE') {
            resultEl.className = 'module-result visible error';
            resultEl.innerHTML = `<strong>Job failed:</strong> ${escapeHtml(msg.error || 'Unknown error')}`;
            settleJob(jobId, false, msg.error || 'Unknown job error');
            return;
        }

        if (msg.status === 'TIMEOUT') {
            resultEl.className = 'module-result visible error';
            resultEl.innerHTML = '<strong>Timeout:</strong> Job exceeded 10-minute limit.';
            settleJob(jobId, false, 'Job exceeded the time limit.');
            return;
        }

        if (msg.status === 'ERROR') {
            resultEl.className = 'module-result visible error';
            resultEl.innerHTML = `<strong>Stream error:</strong> ${escapeHtml(msg.error || 'Unknown')}`;
            settleJob(jobId, false, msg.error || 'Unknown stream error');
            return;
        }

        // PENDING, STARTED, PROGRESS — show elapsed time
        const elapsed = updateElapsed(startTime);
        const progress = msg.progress || {};
        const pct = progress.percent != null ? ` (${progress.percent}%)` : '';
        const detail = escapeHtml(progress.message || progress.step || '');
        resultEl.innerHTML = `<span class="spinner"></span> ${escapeHtml(module)} — ${escapeHtml(msg.status)}${pct} (${elapsed})${detail ? `<br><small style=\"color:var(--text-muted);\">${detail}</small>` : ''}`;
    };

    ws.onerror = () => {
        // WebSocket failed. Fall back to HTTP polling once.
        const job = activeJobs[jobId];
        if (!job || job._fallback || job.settled) return;
        job._fallback = true;
        resultEl.innerHTML = `<span class="spinner"></span> WebSocket unavailable — falling back to polling…`;
        cleanupSocket(jobId);
        void pollJobFallback(jobId, module, resultEl);
    };

    ws.onclose = (event) => {
        // If the WebSocket closed without reaching a terminal state, something went wrong.
        // Skip fallback if onerror already started one (prevents duplicate polling loops).
        if (activeJobs[jobId] && !activeJobs[jobId]._fallback) {
            const status = activeJobs[jobId].status;
            if (status !== 'SUCCESS' && status !== 'FAILURE' && status !== 'TIMEOUT') {
                activeJobs[jobId]._fallback = true;
                resultEl.innerHTML = `<span class="spinner"></span> WebSocket closed — falling back to polling…`;
                cleanupSocket(jobId);
                void pollJobFallback(jobId, module, resultEl);
            }
        }
    };

    return terminal;
}

// ── HTTP Polling Fallback ────────────────────────────────────────────────

async function pollJobFallback(jobId, module, resultEl) {
    const maxPolls = 300;
    let polls = 0;
    const startTime = activeJobs[jobId]?.startTime || Date.now();

    while (polls < maxPolls) {
        await new Promise(r => setTimeout(r, 2000));
        polls++;

        try {
            const job = activeJobs[jobId];
            if (!job || job.settled) return;
            const status = await apiFetch(`/api/jobs/${jobId}`);
            if (!activeJobs[jobId] || activeJobs[jobId].settled) return;
            activeJobs[jobId].status = status.status;
            renderJobQueue();

            if (status.status === 'SUCCESS') {
                resultEl.className = 'module-result visible success';
                renderJobResult(module, resultEl, status.result);
                if (module === 'workspace') loadWorkspaceHistory();
                settleJob(jobId, true);
                return;
            }

            if (status.status === 'FAILURE' || status.status === 'TIMEOUT' || status.status === 'ERROR') {
                const message = status.error || (status.status === 'TIMEOUT' ? 'Job exceeded the time limit.' : 'Unknown job error');
                resultEl.className = 'module-result visible error';
                resultEl.innerHTML = `<strong>${escapeHtml(status.status)}:</strong> ${escapeHtml(message)}`;
                settleJob(jobId, false, message);
                return;
            }

            resultEl.innerHTML = `<span class="spinner"></span> ${escapeHtml(module)} — running… (${updateElapsed(startTime)})`;
        } catch (e) {
            resultEl.innerHTML += `<br><small style="color:#f87171;">Poll error: ${escapeHtml(e.message)}</small>`;
        }
    }

    resultEl.className = 'module-result visible error';
    resultEl.innerHTML = '<strong>Timeout:</strong> Job took too long. Check server logs.';
    settleJob(jobId, false, 'Job took too long. Check server logs.');
}

// ── Helpers ──────────────────────────────────────────────────────────────

async function runNetworkAnalysis() {
    const resultEl = document.getElementById('result-network');
    resultEl.className = 'module-result visible loading';
    resultEl.innerHTML = '<span class="spinner"></span> Analyzing network topology...';
    try {
        const [comm, cent] = await Promise.all([
            apiFetch(`/api/kg/communities?${diseaseQS()}`),
            apiFetch(`/api/kg/centrality?metric=betweenness&top_n=10&${diseaseQS()}`),
        ]);
        resultEl.className = 'module-result visible success';
        const topBridge = cent.nodes?.[0];
        resultEl.innerHTML = renderModuleResult([
            ['Communities', comm.n_communities],
            ['Modularity', comm.modularity?.toFixed(3)],
            ['Top Bridge', topBridge ? `${topBridge.label}` : '—'],
            ['Bridge Score', topBridge?.score?.toFixed(4) || '—'],
            ['Algorithm', comm.algorithm],
        ]);
    } catch (e) {
        resultEl.className = 'module-result visible error';
        resultEl.innerHTML = `<strong>Error:</strong> ${e.message}`;
    }
}

function updateElapsed(startTime) {
    const elapsed = Math.round((Date.now() - startTime) / 1000);
    return elapsed < 60 ? `${elapsed}s` : `${Math.round(elapsed / 60)}m ${elapsed % 60}s`;
}

function cleanupSocket(jobId) {
    if (activeSockets[jobId]) {
        activeSockets[jobId].close();
        delete activeSockets[jobId];
    }
}

function cleanupJob(jobId) {
    cleanupSocket(jobId);
    delete activeJobs[jobId];
    updateJobBadge();
    renderJobQueue();
}

function settleJob(jobId, success, errorMessage = '') {
    const job = activeJobs[jobId];
    if (!job || job.settled) return;
    job.settled = true;
    if (success) {
        job.resolveTerminal?.();
    } else {
        job.rejectTerminal?.(new Error(errorMessage || 'Workspace job failed'));
    }
    if (job.module === 'workspace') setWorkspaceSubmissionState(success ? 'success' : 'failure');
    cleanupJob(jobId);
}

function renderJobResult(module, resultEl, result) {
    if (!result) {
        resultEl.innerHTML = '<div class="result-header">✅ Analysis Complete</div>';
        return;
    }

    const coveragePanel = renderCoveragePanel(result.coverage);
    if (result.status === 'blocked' || result.coverage?.status === 'blocked') {
        resultEl.innerHTML = coveragePanel || '<div class="coverage-panel coverage-blocked">Analysis unavailable for this disease.</div>';
        return;
    }
    switch (module) {
        case 'gwas':
            resultEl.innerHTML = coveragePanel + renderModuleResult([
                ['Studies', result.total_studies],
                ['Unique Genes', result.unique_genes],
                ['Validated in KG', result.crossref?.n_validated || 0],
                ['Novel GWAS Genes', result.crossref?.n_novel || 0],
            ]);
            break;
        case 'enrichment':
            const libs = result.libraries || [];
            resultEl.innerHTML = coveragePanel + renderModuleResult([
                ['Genes Analyzed', result.genes_analyzed],
                ['Libraries', libs.length],
                ['Significant Terms', libs.reduce((s, l) => s + l.terms.filter(t => t.adj_p_value < 0.05).length, 0)],
            ]);
            break;
        case 'ppi':
            resultEl.innerHTML = coveragePanel + renderModuleResult([
                ['Network Nodes', result.nodes],
                ['Interactions', result.edges],
                ['Top Hub', result.top_hubs?.[0]?.symbol || '—'],
                ['Untargeted Hubs', result.hub_untargeted?.length || 0],
            ]);
            break;
        case 'literature':
            resultEl.innerHTML = coveragePanel + renderModuleResult([
                ['Articles', result.total_articles],
                ['Queries Run', result.queries_run],
                ['Genes Covered', result.gene_coverage?.length || 0],
            ]);
            break;
        case 'screening':
            resultEl.innerHTML = coveragePanel + renderModuleResult([
                ['Compounds Screened', result.compounds_screened],
                ['Pairings', result.total_pairings],
                ['Tier 1 Hits', result.tier1_count],
                ['Tier 2 Hits', result.tier2_count],
            ]);
            break;
        case 'trials':
            resultEl.innerHTML = coveragePanel + renderModuleResult([
                ['Total Trials', result.total_trials],
                ['Phase 3 Trials', result.phase_distribution?.['Phase 3'] || 0],
                ['MoA Categories', Object.keys(result.moa_distribution || {}).length],
            ]);
            break;
        case 'ml':
            resultEl.innerHTML = renderModuleResult([
                ['Model', result.model_type],
                ['Predictions', result.predictions?.length || 0],
                ['Top Target', result.predictions?.[0]?.gene_name || '—'],
                ['CV AUC', result.cross_val_auc?.toFixed(3) || '—'],
            ]);
            break;
        case 'synergy':
            const topPair = result.pairs?.[0];
            resultEl.innerHTML = renderModuleResult([
                ['Total Pairs Scored', result.total_pairs],
                ['Tier 1 (Strong)', result.tier1_count],
                ['Tier 2 (Promising)', result.tier2_count],
                ['Top Pair', topPair ? `${topPair.drug_a_name?.split('(')[0].trim()} + ${topPair.drug_b_name?.split('(')[0].trim()}` : '—'],
                ['Avg Score', result.avg_score?.toFixed(2)],
            ]);
            break;
        case 'workspace':
            renderWorkspaceResult(resultEl, result);
            break;
        case 'safety':
            resultEl.innerHTML = coveragePanel + renderModuleResult([
                ['Drugs Profiled', result.total_drugs],
                ['Avg Safety Score', result.avg_safety_score?.toFixed(2)],
                ['Safest Drug', result.safest_drug?.split('(')[0].trim() || '—'],
                ['Drugs with BBW', result.drugs_with_bbw],
                ['Disease-Specific Risk Drugs', result.drugs_with_disease_specific_risk ?? result.drugs_with_dil_risk],
            ]);
            break;
    }
}

// ── Result Rendering ─────────────────────────────────────────────────────

function safeCitationUrl(url) {
    try {
        const parsed = new URL(String(url || ''), window.location.origin);
        return ['http:', 'https:'].includes(parsed.protocol) ? parsed.href : '';
    } catch (_) {
        return '';
    }
}

function citationHtml(citation) {
    const label = citation.native_id || citation.doi || citation.source || 'citation';
    const url = safeCitationUrl(citation.url);
    return url
        ? `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(label)}</a>`
        : escapeHtml(label);
}

function claimLookup(claims) {
    return new Map((claims || []).map(claim => [claim.claim_id, claim]));
}

function renderClaimEvidence(claim, label) {
    const citations = (claim.citations || []).map(citationHtml).join(', ') || 'citation unavailable';
    return `<div class="workspace-explanation-claim"><strong>${escapeHtml(label)}</strong> ${escapeHtml(claim.text || '')}<small>${escapeHtml(claim.supporting_snippet || 'No source snippet provided.')} · confidence ${(Number(claim.confidence || 0) * 100).toFixed(0)}% · evidence ${escapeHtml((claim.evidence_ids || []).join(', '))} · ${citations}</small></div>`;
}

function rankingExplanation(item, claimsById, pathsById) {
    const componentRows = Object.entries(item.component_scores || {}).map(([name, value]) => `<span><b>${escapeHtml(name.replaceAll('_', ' '))}</b> ${Number(value || 0).toFixed(1)}</span>`).join('') || '<span>No component details available.</span>';
    const support = (item.supporting_claim_ids || []).map(id => claimsById.get(id) ? renderClaimEvidence(claimsById.get(id), 'supporting evidence:') : `<div class="workspace-explanation-claim"><strong>Supporting evidence:</strong> provenance for ${escapeHtml(id)} is unavailable.</div>`).join('');
    const contradiction = (item.contradicting_claim_ids || []).map(id => claimsById.get(id) ? renderClaimEvidence(claimsById.get(id), 'contradicting evidence:') : `<div class="workspace-explanation-claim"><strong>Contradicting evidence:</strong> provenance for ${escapeHtml(id)} is unavailable.</div>`).join('');
    const graph = (item.graph_explanation_ids || []).map(id => pathsById.get(id)).filter(Boolean).map(path => `<div class="workspace-explanation-claim"><strong>Knowledge graph:</strong> ${path.status === 'found' ? escapeHtml((path.path_labels || []).join(' → ')) : escapeHtml(path.reason || 'No graph path found.')}</div>`).join('');
    return `<details class="workspace-ranking-explanation"><summary>Why this ranked</summary><div class="workspace-component-scores">${componentRows}</div><div class="workspace-explanation-group">${support || '<span class="workspace-muted">No supporting claims.</span>'}${contradiction || '<span class="workspace-muted">No contradicting claims.</span>'}${graph || '<span class="workspace-muted">No graph explanation available.</span>'}</div></details>`;
}

function reviewControls(item, candidateType) {
    const key = `${candidateType}:${item.candidate_id}`;
    const review = workspaceReviews[key] || {};
    const tags = (review.tags || []).join(', ');
    return `<details class="workspace-review-card" data-candidate-id="${escapeHtml(item.candidate_id)}" data-candidate-type="${candidateType}">
        <summary>📝 Researcher review${review.decision && review.decision !== 'unreviewed' ? ` · ${escapeHtml(review.decision)}` : ''}</summary>
        <div class="workspace-review-fields">
            <label>Decision<select data-review-field="decision"><option value="unreviewed" ${review.decision === 'unreviewed' || !review.decision ? 'selected' : ''}>Unreviewed</option><option value="pinned" ${review.decision === 'pinned' ? 'selected' : ''}>📌 Pin candidate</option><option value="rejected" ${review.decision === 'rejected' ? 'selected' : ''}>✕ Reject candidate</option></select></label>
            <label>Tags<input data-review-field="tags" maxlength="500" value="${escapeHtml(tags)}" placeholder="e.g. validate, safety, follow-up"></label>
            <label>Rationale<textarea data-review-field="rationale" maxlength="2000" rows="2" placeholder="Why did you make this decision?">${escapeHtml(review.rationale || '')}</textarea></label>
            <label>Notes<textarea data-review-field="notes" maxlength="5000" rows="2" placeholder="Research notes and next steps">${escapeHtml(review.notes || '')}</textarea></label>
            <label>What changed my mind?<textarea data-review-field="changed_my_mind" maxlength="3000" rows="2" placeholder="Record the evidence that changed your view">${escapeHtml(review.changed_my_mind || '')}</textarea></label>
            <div class="workspace-review-actions"><button class="btn btn-secondary btn-sm" type="button" data-workspace-review-save>Save review</button><button class="btn btn-secondary btn-sm" type="button" data-workspace-review-history>Evidence history</button><span class="workspace-review-status" role="status"></span></div>
            <div class="workspace-review-history" hidden></div>
        </div>
    </details>`;
}

function setupWorkspaceReviewActions() {
    const result = document.getElementById('workspace-result');
    if (!result || result.dataset.reviewActionsBound) return;
    result.dataset.reviewActionsBound = 'true';
    result.addEventListener('click', event => {
        const save = event.target.closest('[data-workspace-review-save]');
        if (save) saveWorkspaceReview(save);
        const history = event.target.closest('[data-workspace-review-history]');
        if (history) loadCandidateHistory(history);
    });
}

function setupWorkspaceResultActions() {
    const result = document.getElementById('workspace-result');
    if (!result || result.dataset.resultActionsBound) return;
    result.dataset.resultActionsBound = 'true';
    result.addEventListener('click', event => {
        const action = event.target.closest('[data-workspace-result-action]')?.dataset.workspaceResultAction;
        if (action === 'download-json') downloadWorkspaceJson();
        if (action === 'open-html') openWorkspaceHtml();
        if (action === 'download-bundle') downloadWorkspaceBundle();
        if (action === 'copy-fingerprint') copyWorkspaceFingerprint();
    });
}

async function loadWorkspaceReviews(runId) {
    if (!runId) return;
    try {
        const data = await apiFetch(`/api/workspace/runs/${encodeURIComponent(runId)}/reviews`);
        workspaceReviews = Object.fromEntries((data.reviews || []).map(review => [`${review.candidate_type}:${review.candidate_id}`, review]));
        document.querySelectorAll('.workspace-review-card').forEach(card => {
            const key = `${card.dataset.candidateType}:${card.dataset.candidateId}`;
            const review = workspaceReviews[key];
            if (!review) return;
            card.querySelector('[data-review-field="decision"]').value = review.decision || 'unreviewed';
            card.querySelector('[data-review-field="tags"]').value = (review.tags || []).join(', ');
            card.querySelector('[data-review-field="rationale"]').value = review.rationale || '';
            card.querySelector('[data-review-field="notes"]').value = review.notes || '';
            card.querySelector('[data-review-field="changed_my_mind"]').value = review.changed_my_mind || '';
        });
    } catch (error) {
        showToast(`Reviews unavailable: ${error.message}`, 'error');
    }
}

async function saveWorkspaceReview(button) {
    const card = button.closest('.workspace-review-card');
    const runId = window.lastWorkspaceDossier?.run_id;
    if (!card || !runId) return;
    const value = field => card.querySelector(`[data-review-field="${field}"]`)?.value || '';
    const payload = {
        candidate_id: card.dataset.candidateId,
        candidate_type: card.dataset.candidateType,
        decision: value('decision'),
        tags: value('tags').split(',').map(tag => tag.trim()).filter(Boolean),
        rationale: value('rationale'),
        notes: value('notes'),
        changed_my_mind: value('changed_my_mind'),
    };
    const status = card.querySelector('.workspace-review-status');
    button.disabled = true;
    try {
        const review = await apiFetch(`/api/workspace/runs/${encodeURIComponent(runId)}/reviews`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        workspaceReviews[`${review.candidate_type}:${review.candidate_id}`] = review;
        if (status) status.textContent = `Saved with fingerprint ${review.provenance_fingerprint || 'n/a'}`;
        showToast('Candidate review saved');
    } catch (error) {
        if (status) status.textContent = `Save failed: ${error.message}`;
        showToast(`Could not save review: ${error.message}`, 'error');
    } finally {
        button.disabled = false;
    }
}

async function loadCandidateHistory(button) {
    const card = button.closest('.workspace-review-card');
    const history = card?.querySelector('.workspace-review-history');
    if (!card || !history) return;
    try {
        const params = new URLSearchParams({ candidate_id: card.dataset.candidateId, candidate_type: card.dataset.candidateType, disease_id: window.lastWorkspaceDossier?.request?.disease_id || '' });
        const data = await apiFetch(`/api/workspace/candidate-history?${params.toString()}`);
        const points = data.points || [];
        history.hidden = false;
        history.innerHTML = points.length ? points.map(point => `<div><strong>${escapeHtml(point.timestamp.slice(0, 10))}</strong> · score ${point.score ?? '—'} · rank ${point.rank ?? '—'} · evidence ${point.evidence_ids.length ? escapeHtml(point.evidence_ids.join(', ')) : 'none'}${point.evidence_added.length ? ` · <span class="delta-up">+${escapeHtml(point.evidence_added.join(', '))}</span>` : ''}${point.evidence_removed.length ? ` · <span class="delta-down">−${escapeHtml(point.evidence_removed.join(', '))}</span>` : ''}</div>`).join('') : '<span class="workspace-muted">No previous runs contain this candidate.</span>';
    } catch (error) {
        history.hidden = false;
        history.innerHTML = `<span class="workspace-muted">History unavailable: ${escapeHtml(error.message)}</span>`;
    }
}

function downloadWorkspaceBundle() {
    const runId = window.lastWorkspaceDossier?.run_id;
    if (!runId) return;        fetch(`${API_BASE}/api/workspace/runs/${encodeURIComponent(runId)}/review-bundle`, { credentials: 'same-origin', headers: { 'Accept': 'application/zip' } })

        .then(async response => { if (!response.ok) throw new Error((await response.json().catch(() => ({}))).detail || `HTTP ${response.status}`); return response.blob(); })
        .then(blob => { const url = URL.createObjectURL(blob); const link = document.createElement('a'); link.href = url; link.download = `workspace-${runId}-review.zip`; link.click(); window.setTimeout(() => URL.revokeObjectURL(url), 1000); })
        .catch(error => showToast(`Could not export review bundle: ${error.message}`, 'error'));
}

const WORKSPACE_GRAPH_COLORS = {
    candidate: '#60a5fa',
    claim: '#c084fc',
    citation: '#22d3ee',
    pathway: '#f59e0b',
    decision: '#4ade80',
    disease: '#f43f5e',
    knowledge_graph: '#94a3b8',
};

let workspaceEvidenceNetwork = null;
let workspaceEvidenceGraph = null;

function workspaceGraphTitle(node) {
    const metadata = node.metadata || {};
    const details = Object.entries(metadata)
        .filter(([, value]) => value !== null && value !== undefined && value !== '' && !Array.isArray(value))
        .slice(0, 5)
        .map(([key, value]) => `${key}: ${value}`)
        .join(' · ');
    return `${node.label}${node.subtitle ? `\n${node.subtitle}` : ''}${details ? `\n${details}` : ''}`;
}

function showWorkspaceGraphDetail(nodeId) {
    const detail = document.getElementById('workspace-graph-detail');
    const node = (workspaceEvidenceGraph?.nodes || []).find(item => item.id === nodeId);
    if (!detail || !node) return;
    const color = WORKSPACE_GRAPH_COLORS[node.type] || '#94a3b8';
    const metadata = Object.entries(node.metadata || {})
        .filter(([, value]) => value !== null && value !== undefined && value !== '' && !Array.isArray(value))
        .slice(0, 12)
        .map(([key, value]) => `<dt>${escapeHtml(key.replaceAll('_', ' '))}</dt><dd>${escapeHtml(String(value))}</dd>`)
        .join('');
    const link = safeCitationUrl(node.url) ? `<p><a href="${escapeHtml(safeCitationUrl(node.url))}" target="_blank" rel="noopener noreferrer">Open source citation ↗</a></p>` : '';
    detail.innerHTML = `<h4>${escapeHtml(node.label)}</h4><span class="graph-type" style="background:${color}">${escapeHtml(node.type.replaceAll('_', ' '))}</span>${node.subtitle ? `<p>${escapeHtml(node.subtitle)}</p>` : ''}${node.description ? `<p>${escapeHtml(node.description)}</p>` : ''}${link}${metadata ? `<dl>${metadata}</dl>` : ''}`;
}

function renderWorkspaceEvidenceGraph(data) {
    const canvas = document.getElementById('workspace-graph-canvas');
    const status = document.getElementById('workspace-graph-status');
    if (!canvas || !status) return;
    workspaceEvidenceGraph = data;
    if (typeof vis === 'undefined') {
        status.textContent = 'Evidence graph unavailable: vis-network library not loaded.';
        canvas.innerHTML = '';
        return;
    }
    const nodes = new vis.DataSet((data.nodes || []).map(node => {
        const color = WORKSPACE_GRAPH_COLORS[node.type] || '#94a3b8';
        return {
            id: node.id,
            label: String(node.label || node.id).slice(0, 46),
            title: workspaceGraphTitle(node),
            shape: node.type === 'candidate' ? 'box' : node.type === 'pathway' ? 'diamond' : node.type === 'decision' ? 'star' : node.type === 'disease' ? 'hexagon' : 'dot',
            size: node.type === 'candidate' ? 24 : node.type === 'decision' ? 21 : 15,
            color: { background: color, border: color, highlight: { background: '#ffffff', border: '#ffffff' } },
            font: { color: '#e0e0e8', size: node.type === 'candidate' ? 13 : 11 },
        };
    }));
    const edges = new vis.DataSet((data.edges || []).map(edge => ({
        id: edge.id,
        from: edge.source,
        to: edge.target,
        label: edge.label || edge.type,
        title: edge.label || edge.type,
        arrows: { to: { enabled: true, scaleFactor: 0.45 } },
        color: { color: edge.type === 'contradicts' ? '#f87171' : edge.type === 'supports' ? '#4ade80' : '#64748b', opacity: 0.65 },
        dashes: ['evidence', 'citation'].includes(edge.type),
        width: edge.type === 'supports' || edge.type === 'contradicts' ? 2 : 1,
        font: { color: '#9ca3af', size: 9, strokeWidth: 0 },
        smooth: { type: 'continuous' },
    })));
    workspaceEvidenceNetwork?.destroy();
    workspaceEvidenceNetwork = new vis.Network(canvas, { nodes, edges }, {
        physics: { enabled: true, solver: 'forceAtlas2Based', forceAtlas2Based: { gravitationalConstant: -55, centralGravity: 0.015, springLength: 145, springConstant: 0.05, damping: 0.55 }, stabilization: { iterations: 220 } },
        interaction: { hover: true, tooltipDelay: 120, navigationButtons: false, keyboard: true },
        nodes: { borderWidth: 1.5, shadow: false },
        edges: { selectionWidth: 2 },
        layout: { improvedLayout: false },
    });
    workspaceEvidenceNetwork.on('click', params => {
        if (params.nodes?.length) showWorkspaceGraphDetail(params.nodes[0]);
    });
    status.textContent = `${data.nodes?.length || 0} nodes · ${data.edges?.length || 0} connections · researcher ${data.researcher_id || 'anonymous'}`;
    const detail = document.getElementById('workspace-graph-detail');
    if (detail) detail.innerHTML = '<span class="workspace-muted">Select a node to inspect its evidence or review metadata.</span>';
}

async function loadWorkspaceEvidenceGraph(runId) {
    const status = document.getElementById('workspace-graph-status');
    if (!status || !runId) return;
    status.textContent = 'Loading evidence graph…';
    try {
        const data = await apiFetch(`/api/workspace/runs/${encodeURIComponent(runId)}/graph`);
        renderWorkspaceEvidenceGraph(data);
    } catch (error) {
        status.textContent = `Evidence graph unavailable: ${error.message}`;
    }
}

function fitWorkspaceEvidenceGraph() {
    workspaceEvidenceNetwork?.fit({ animation: { duration: 500, easingFunction: 'easeInOutQuad' } });
}

function reloadWorkspaceEvidenceGraph() {
    loadWorkspaceEvidenceGraph(window.lastWorkspaceDossier?.run_id);
}

function renderWorkspaceResult(el, payload) {
    const dossier = payload?.dossier || payload || {};
    const drugs = dossier.drug_rankings || [];
    const targets = dossier.target_rankings || [];
    const claims = dossier.claims || [];
    const evidence = dossier.evidence || [];
    const paths = dossier.graph_explanations || [];
    const warningCount = (dossier.warnings || []).length;
    const provenance = dossier.manifest?.provenance || {};
    const claimsById = claimLookup(claims);
    const pathsById = new Map(paths.map(path => [path.explanation_id, path]));
    const sourceStatus = (dossier.source_statuses || []).map(item => `<span class="workspace-source-status ${escapeHtml(item.status)}"><strong>${escapeHtml(workspaceSourceLabel(item.source))}</strong>: ${escapeHtml(item.status)} · ${Number(item.records_found || 0)} records · ${escapeHtml(item.retrieval_mode || 'unknown')}${item.warning ? ` · ${escapeHtml(item.warning)}` : ''}</span>`).join('');
    const qualitySummary = evidence.reduce((summary, item) => { const tier = item.quality_tier || 'tier_3'; summary[tier] = (summary[tier] || 0) + 1; summary.totalScore += Number(item.quality_score || 0); summary.total += 1; return summary; }, { totalScore: 0, total: 0 });
    const qualityAverage = qualitySummary.total ? (qualitySummary.totalScore / qualitySummary.total).toFixed(2) : '—';
    const rankingRows = (items, emptyText, candidateType) => items.length ? items.slice(0, 6).map(item => `
        <div class="workspace-ranking-row">
            <div><strong>${escapeHtml(item.name)}</strong><small>${escapeHtml(item.explanation || '')}</small><small>Support: ${(item.supporting_claim_ids || []).length} · Contradictions: ${(item.contradicting_claim_ids || []).length} · quality ${Number(item.component_scores?.evidence_quality || 0).toFixed(1)} points</small>${rankingExplanation(item, claimsById, pathsById)}${reviewControls(item, candidateType)}</div>
            <span class="workspace-score">${Number(item.score || 0).toFixed(1)}<small>${escapeHtml(item.confidence_band || '')}</small></span>
        </div>`).join('') : `<p class="workspace-muted">${emptyText}</p>`;
    const claimRows = claims.slice(0, 8).map(claim => `
        <div class="workspace-claim"><span class="claim-relation ${escapeHtml(claim.relationship)}">${escapeHtml(claim.relationship)}</span><strong>${escapeHtml(claim.subject_name)}</strong><span>${escapeHtml(claim.text)}</span><small>confidence ${(Number(claim.confidence || 0) * 100).toFixed(0)}% · ${escapeHtml((claim.evidence_ids || []).join(', '))} · ${(claim.citations || []).map(citationHtml).join(', ') || 'citation unavailable'}</small></div>`).join('');
    const pathRows = paths.slice(0, 8).map(path => `<div class="workspace-path"><strong>${escapeHtml(path.candidate_id)}</strong><span>${path.status === 'found' ? escapeHtml((path.path_labels || []).join(' → ')) : escapeHtml(path.reason || 'No graph path found')}</span></div>`).join('');
    const warningRows = (dossier.warnings || []).map(warning => `<li>${escapeHtml(warning)}</li>`).join('');
    const limitationRows = (dossier.limitations || []).map(item => `<li>${escapeHtml(item)}</li>`).join('');
    const request = dossier.request || {};
    const sourceLabels = (request.sources || []).map(workspaceSourceLabel).join(', ') || 'not recorded';
    el.innerHTML = `
        <div class="workspace-result-head"><div><strong>✅ Dossier ready</strong><small>${escapeHtml(dossier.run_id || '')} · ${evidence.length} evidence · ${claims.length} claims</small></div><div class="workspace-export-links"><button class="btn btn-secondary btn-sm" type="button" data-workspace-result-action="download-json">⬇ JSON</button>
<button class="btn btn-secondary btn-sm" type="button" data-workspace-result-action="open-html">📄 HTML</button><button class="btn btn-secondary btn-sm" type="button" data-workspace-result-action="download-bundle">📦 Review bundle</button></div></div>
        <div class="workspace-summary-grid"><div><b>${drugs.length}</b><span>drug candidates</span></div><div><b>${targets.length}</b><span>target candidates</span></div><div><b>${evidence.length}</b><span>evidence records</span></div><div><b>${warningCount}</b><span>warnings</span></div></div>
        <div class="workspace-provenance"><strong>Reproducibility</strong><span>Fingerprint: <code>${escapeHtml(provenance.fingerprint || 'not available')}</code></span><span>Research question: ${escapeHtml(request.question || 'not recorded')}</span><span>Sources: ${escapeHtml(sourceLabels)}</span><span>Disease: ${escapeHtml(request.disease_id || 'not recorded')}</span><span>Mode: ${escapeHtml(provenance.cache_or_live || dossier.manifest?.cache_or_live || 'unknown')}</span><button class="btn btn-secondary btn-sm" type="button" data-workspace-result-action="copy-fingerprint">Copy fingerprint</button></div>
        <div class="workspace-source-statuses">${sourceStatus || '<span class="workspace-muted">No source status available.</span>'}</div>
        <div class="workspace-quality-summary"><strong>Evidence quality:</strong> ${Object.entries(qualitySummary).filter(([key]) => !['totalScore', 'total'].includes(key)).map(([tier, count]) => `<span>${escapeHtml(tier.replace('_', ' '))}: ${count}</span>`).join('') || '<span>not classified</span>'}<span>average score: ${qualityAverage}</span></div>
        <div class="workspace-result-columns"><section><h4>💊 Prioritized drugs</h4>${rankingRows(drugs, 'No drug ranking available.', 'drug')}</section><section><h4>🧬 Prioritized targets</h4>${rankingRows(targets, 'No target ranking available.', 'target')}</section></div>
        <details><summary>Claims, citations, and confidence (${claims.length})</summary><div class="workspace-claims">${claimRows || '<p class="workspace-muted">No claims extracted.</p>'}</div></details>
        <details><summary>Knowledge-graph explanations (${paths.length})</summary><div class="workspace-claims">${pathRows || '<p class="workspace-muted">No graph explanations available.</p>'}</div></details>
        ${warningRows ? `<details><summary>Warnings (${warningCount})</summary><ul class="workspace-notices">${warningRows}</ul></details>` : ''}
        ${limitationRows ? `<details><summary>Limitations (${dossier.limitations.length})</summary><ul class="workspace-notices">${limitationRows}</ul></details>` : ''}
        <p class="workspace-disclaimer">${escapeHtml(dossier.disclaimer || 'For research purposes only. Not medical advice.')}</p>`;
    el.className = 'workspace-result visible success';
    window.lastWorkspaceDossier = dossier;
    window.lastWorkspaceHtml = payload?.html || '';
    setupWorkspaceReviewActions();
    setupWorkspaceResultActions();
    loadWorkspaceReviews(dossier.run_id);
    loadWorkspaceEvidenceGraph(dossier.run_id);
    loadWorkspaceAlerts();
}

function copyWorkspaceFingerprint() {
    const fingerprint = window.lastWorkspaceDossier?.manifest?.provenance?.fingerprint;
    if (!fingerprint) return;
    if (navigator.clipboard?.writeText) {
        navigator.clipboard.writeText(fingerprint).then(() => showToast('Fingerprint copied')).catch(() => showToast(fingerprint));
    } else {
        showToast(fingerprint);
    }
}

function openWorkspaceHtml() {
    const dossier = window.lastWorkspaceDossier;
    if (!dossier) return;
    const html = window.lastWorkspaceHtml || `<!doctype html><meta charset="utf-8"><title>Evidence Dossier</title><pre style="white-space:pre-wrap;font:14px system-ui">${escapeHtml(JSON.stringify(dossier, null, 2))}</pre>`;
    const blob = new Blob([html], { type: 'text/html;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    window.open(url, '_blank', 'noopener');
    window.setTimeout(() => URL.revokeObjectURL(url), 60000);
}

function downloadWorkspaceJson() {
    const dossier = window.lastWorkspaceDossier;
    if (!dossier) return;
    const blob = new Blob([JSON.stringify(dossier, null, 2)], { type: 'application/json;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'evidence-dossier.json';
    link.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

let workspaceTrendData = { runs: [], drug_series: [], target_series: [] };

function populateWorkspaceTrendCandidates() {
    const kind = document.getElementById('workspace-trend-kind')?.value || 'drug';
    const candidate = document.getElementById('workspace-trend-candidate');
    if (!candidate) return;
    const previous = candidate.value;
    const series = workspaceTrendData[`${kind}_series`] || [];
    candidate.innerHTML = '<option value="">All candidates</option>' + series.map(item => `<option value="${escapeHtml(item.candidate_id)}">${escapeHtml(item.name)}</option>`).join('');
    candidate.value = series.some(item => item.candidate_id === previous) ? previous : '';
}

async function loadWorkspaceTrends() {
    const status = document.getElementById('workspace-trend-status');
    if (!status) return;
    status.textContent = 'Loading trend data…';
    try {
        workspaceTrendData = await apiFetch('/api/workspace/trends?limit=20');
        populateWorkspaceTrendCandidates();
        renderWorkspaceTrends();
    } catch (error) {
        status.textContent = `Trend data unavailable: ${error.message}`;
        const chart = document.getElementById('workspace-trend-chart');
        const table = document.getElementById('workspace-trend-table');
        const metrics = document.getElementById('workspace-trend-metrics');
        if (chart) chart.innerHTML = '';
        if (table) table.innerHTML = '';
        if (metrics) metrics.innerHTML = '';
    }
}

function workspaceTrendPoint(item, runId) {
    return (item.points || []).find(point => point.run_id === runId);
}

function renderWorkspaceTrendTable(kind, runs, series) {
    const container = document.getElementById('workspace-trend-table');
    if (!container) return;
    const exportButton = '<button class="btn btn-secondary btn-sm" type="button" data-action="workspace-trends-export">⬇ Download CSV</button>';
    if (!runs.length || !series.length) {
        container.innerHTML = `<div class="workspace-trend-table-head"><h4>Tabular trend data</h4>${exportButton}</div><p class="workspace-muted">No ${escapeHtml(kind)} trend data is available yet.</p>`;
        return;
    }
    const headers = runs.map(run => `<th scope="col">${escapeHtml(workspaceDateLabel(run.timestamp))}<span class="workspace-sr-only">, run ${escapeHtml(run.run_id)}</span></th>`).join('');
    const rows = series.map(item => {
        const cells = runs.map(run => {
            const point = workspaceTrendPoint(item, run.run_id);
            const present = point?.present && point.score != null && Number.isFinite(Number(point.score));
            const score = present ? Number(point.score).toFixed(1) : '—';
            const details = present ? `rank ${point.rank ?? 'not available'}, confidence ${point.confidence_band || 'unknown'}` : 'candidate not present in this run';
            return `<td>${escapeHtml(score)}<span class="workspace-sr-only">, ${escapeHtml(details)}</span></td>`;
        }).join('');
        return `<tr><th scope="row">${escapeHtml(item.name || item.candidate_id)}<span class="workspace-sr-only"> (${escapeHtml(kind)} ${escapeHtml(item.candidate_id)})</span></th>${cells}</tr>`;
    }).join('');
    container.innerHTML = `<div class="workspace-trend-table-head"><h4 id="workspace-trend-table-title">Tabular trend data</h4>${exportButton}</div><div class="workspace-trend-table-scroll"><table aria-describedby="workspace-trend-table-title"><caption class="workspace-sr-only">${escapeHtml(kind)} candidate scores across successful Workspace runs. Scores include rank and confidence for screen-reader users.</caption><thead><tr><th scope="col">Candidate</th>${headers}</tr></thead><tbody>${rows}</tbody></table></div>`;
}

function csvCell(value) {
    return `"${String(value == null ? '' : value).replace(/"/g, '""')}"`;
}

function downloadWorkspaceTrendCsv() {
    const kind = document.getElementById('workspace-trend-kind')?.value || 'drug';
    const selected = document.getElementById('workspace-trend-candidate')?.value || '';
    const runs = workspaceTrendData.runs || [];
    const series = (workspaceTrendData[`${kind}_series`] || []).filter(item => !selected || item.candidate_id === selected).slice(0, 8);
    if (!runs.length || !series.length) {
        showToast('No trend data is available to export.', 'error');
        return;
    }
    const header = ['candidate_type', 'candidate_id', 'candidate_name', 'run_id', 'timestamp', 'present', 'score', 'rank', 'confidence_band', 'evidence_count', 'claim_count', 'warning_count'];
    const rows = series.flatMap(item => runs.map(run => {
        const point = workspaceTrendPoint(item, run.run_id) || {};
        return [kind, item.candidate_id, item.name, run.run_id, point.timestamp || run.timestamp, point.present === true, point.score ?? '', point.rank ?? '', point.confidence_band || '', run.evidence_count ?? '', run.claim_count ?? '', run.warning_count ?? ''];
    }));
    const csv = [header, ...rows].map(row => row.map(csvCell).join(',')).join('\r\n') + '\r\n';
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `workspace-${kind}-trends.csv`;
    link.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function renderWorkspaceTrends() {
    const status = document.getElementById('workspace-trend-status');
    const chart = document.getElementById('workspace-trend-chart');
    const table = document.getElementById('workspace-trend-table');
    const metrics = document.getElementById('workspace-trend-metrics');
    if (!status || !chart || !table || !metrics) return;
    populateWorkspaceTrendCandidates();
    const kind = document.getElementById('workspace-trend-kind')?.value || 'drug';
    const selected = document.getElementById('workspace-trend-candidate')?.value || '';
    const runs = workspaceTrendData.runs || [];
    const series = (workspaceTrendData[`${kind}_series`] || []).filter(item => !selected || item.candidate_id === selected).slice(0, 8);
    renderWorkspaceTrendTable(kind, runs, series);
    if (runs.length < 2) {
        status.textContent = runs.length ? 'Save at least two successful runs to see trends.' : 'Run a workspace query to start an evidence trend.';
        chart.innerHTML = '';
        metrics.innerHTML = '';
        return;
    }
    status.textContent = `${runs.length} successful runs · ${series.length} ${kind} series`;
    const width = 720;
    const height = 220;
    const pad = { left: 42, right: 16, top: 18, bottom: 34 };
    const x = index => pad.left + (index * (width - pad.left - pad.right)) / Math.max(1, runs.length - 1);
    const y = score => pad.top + ((100 - Number(score)) * (height - pad.top - pad.bottom)) / 100;
    const colors = ['#67e8f9', '#a78bfa', '#4ade80', '#fbbf24', '#f472b6', '#fb7185', '#60a5fa', '#c084fc'];
    const grid = [0, 25, 50, 75, 100].map(value => `<line x1="${pad.left}" x2="${width - pad.right}" y1="${y(value)}" y2="${y(value)}" class="trend-grid"/><text x="${pad.left - 8}" y="${y(value) + 4}" class="trend-axis">${value}</text>`).join('');
    const paths = series.map((item, seriesIndex) => {
        const points = (item.points || []).filter(point => point.present && point.score != null && runs.some(run => run.run_id === point.run_id));
        const line = points.map((point, index) => {
            const runIndex = runs.findIndex(run => run.run_id === point.run_id);
            return `${index ? 'L' : 'M'} ${x(runIndex)} ${y(point.score)}`;
        }).join(' ');
        const dots = points.map(point => {
            const runIndex = runs.findIndex(run => run.run_id === point.run_id);
            return `<circle cx="${x(runIndex)}" cy="${y(point.score)}" r="4" fill="${colors[seriesIndex % colors.length]}"><title>${escapeHtml(item.name)} · ${escapeHtml(point.timestamp || '')} · score ${Number(point.score).toFixed(1)} · rank ${point.rank ?? '—'} · ${escapeHtml(point.confidence_band || 'unknown')}</title></circle>`;
        }).join('');
        return `<path d="${line}" class="trend-line" stroke="${colors[seriesIndex % colors.length]}"/><text x="${pad.left + 8}" y="${pad.top + 15 + seriesIndex * 15}" class="trend-legend" fill="${colors[seriesIndex % colors.length]}">${escapeHtml(item.name)}</text>${dots}`;
    }).join('');
    const labels = runs.map((run, index) => `<text x="${x(index)}" y="${height - 10}" class="trend-axis" text-anchor="middle">${escapeHtml(workspaceDateLabel(run.timestamp))}</text>`).join('');
    chart.innerHTML = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHtml(kind)} score trends"><title>${escapeHtml(kind)} score trends across saved workspace runs</title>${grid}${paths}${labels}</svg>`;
    metrics.innerHTML = runs.map(run => `<span><b>${escapeHtml(run.evidence_count)}</b> evidence · <b>${escapeHtml(run.claim_count)}</b> claims · <b>${escapeHtml(run.warning_count)}</b> warnings · ${escapeHtml(workspaceDateLabel(run.timestamp))}</span>`).join('');
}

function renderWorkspaceDeliveryStatus(delivery, digestDelivery = {}) {
    const render = (status, entries, emptyText) => {
        if (!status) return;
        const values = Object.entries(entries || {});
        if (!values.length) {
            status.textContent = emptyText;
            return;
        }
        status.textContent = values.map(([channel, value]) => {
            const label = value.status === 'delivered' ? 'delivered' : `failed (${value.attempts || 0})`;
            return `${channel}: ${label}`;
        }).join(' · ');
        status.title = values.map(([channel, value]) => `${channel}: ${value.error || value.delivered_at || 'no details'}`).join('\n');
    };
    render(document.getElementById('workspace-alert-delivery-status'), delivery, 'No alert delivery attempts yet.');
    render(document.getElementById('workspace-digest-delivery-status'), digestDelivery, 'No digest delivery attempts yet.');
}

async function loadWorkspaceNotificationSettings() {
    const email = document.getElementById('workspace-alert-email');
    const emailEnabled = document.getElementById('workspace-alert-email-enabled');
    const slackEnabled = document.getElementById('workspace-alert-slack-enabled');
    const scoreThreshold = document.getElementById('workspace-alert-score-threshold');
    const rankThreshold = document.getElementById('workspace-alert-rank-threshold');
    const qualityThreshold = document.getElementById('workspace-alert-quality-threshold');
    const digestEnabled = document.getElementById('workspace-weekly-digest-enabled');
    const digestWeekday = document.getElementById('workspace-digest-weekday');
    const digestTime = document.getElementById('workspace-digest-time');
    const digestTimezone = document.getElementById('workspace-digest-timezone');
    const status = document.getElementById('workspace-alert-settings-status');
    if (!email || !status) return;
    try {
        const settings = await apiFetch('/api/workspace/notifications');
        email.value = settings.email || '';
        if (emailEnabled) emailEnabled.checked = settings.email_enabled !== false;
        if (slackEnabled) slackEnabled.checked = settings.slack_enabled !== false;
        if (scoreThreshold) scoreThreshold.value = settings.score_drop_threshold ?? 0;
        if (rankThreshold) rankThreshold.value = settings.rank_change_threshold ?? 0;
        if (qualityThreshold) qualityThreshold.value = settings.evidence_quality_change_threshold ?? 0;
        if (digestEnabled) digestEnabled.checked = settings.weekly_digest_enabled === true;
        if (digestWeekday) digestWeekday.value = settings.weekly_digest_weekday ?? 0;
        if (digestTime) digestTime.value = `${String(settings.weekly_digest_hour ?? 9).padStart(2, '0')}:${String(settings.weekly_digest_minute ?? 0).padStart(2, '0')}`;
        if (digestTimezone) digestTimezone.value = settings.weekly_digest_timezone || 'UTC';
        status.textContent = settings.slack_configured ? 'Slack webhook configured.' : 'No Slack webhook configured.';
        renderWorkspaceDeliveryStatus(settings.delivery, settings.digest_delivery);
    } catch (error) {
        status.textContent = `Notification settings unavailable: ${error.message}`;
    }
}

async function saveWorkspaceNotificationSettings() {
    const status = document.getElementById('workspace-alert-settings-status');
    try {
        const payload = {
            email: document.getElementById('workspace-alert-email')?.value.trim() || '',
            email_enabled: document.getElementById('workspace-alert-email-enabled')?.checked !== false,
            slack_webhook_url: document.getElementById('workspace-alert-slack')?.value.trim() || '',
            slack_enabled: document.getElementById('workspace-alert-slack-enabled')?.checked !== false,
            score_drop_threshold: Number(document.getElementById('workspace-alert-score-threshold')?.value || 0),
            rank_change_threshold: Number(document.getElementById('workspace-alert-rank-threshold')?.value || 0),
            evidence_quality_change_threshold: Number(document.getElementById('workspace-alert-quality-threshold')?.value || 0),
            weekly_digest_enabled: document.getElementById('workspace-weekly-digest-enabled')?.checked === true,
            weekly_digest_weekday: Number(document.getElementById('workspace-digest-weekday')?.value || 0),
            weekly_digest_hour: Number((document.getElementById('workspace-digest-time')?.value || '09:00').split(':')[0]),
            weekly_digest_minute: Number((document.getElementById('workspace-digest-time')?.value || '09:00').split(':')[1]),
            weekly_digest_timezone: document.getElementById('workspace-digest-timezone')?.value.trim() || 'UTC',
        };
        const settings = await apiFetch('/api/workspace/notifications', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        if (status) status.textContent = settings.slack_configured ? 'Notification settings saved; Slack configured.' : 'Notification settings saved.';
        renderWorkspaceDeliveryStatus(settings.delivery, settings.digest_delivery);
        const thresholdSummary = `Thresholds: score drop ${settings.score_drop_threshold ?? 0}, rank movement ${settings.rank_change_threshold ?? 0}, quality change ${settings.evidence_quality_change_threshold ?? 0}`;
        if (status) status.textContent += ` ${thresholdSummary}.`;
        const slack = document.getElementById('workspace-alert-slack');
        if (slack) slack.value = '';
        await loadWorkspaceAlerts();
    } catch (error) {
        if (status) status.textContent = `Could not save notification settings: ${error.message}`;
    }
}

function renderWorkspaceDigest(digest) {
    const preview = document.getElementById('workspace-digest-preview');
    if (!preview) return;
    preview.hidden = false;
    preview.textContent = digest.markdown || 'No digest content available.';
}

async function previewWorkspaceDigest() {
    const status = document.getElementById('workspace-alert-settings-status');
    try {
        const digest = await apiFetch('/api/workspace/digest');
        renderWorkspaceDigest(digest);
        if (status) status.textContent = `Digest preview: ${digest.new_evidence_count} new evidence, ${digest.unresolved_reminder_count} unresolved reminders, ${digest.changed_decision_count} changed decisions.`;
    } catch (error) {
        if (status) status.textContent = `Digest preview unavailable: ${error.message}`;
    }
}

async function sendWorkspaceDigest() {
    const status = document.getElementById('workspace-alert-settings-status');
    try {
        const digest = await apiFetch('/api/workspace/digest/send?force=true', { method: 'POST' });
        renderWorkspaceDigest(digest);
        if (status) status.textContent = `Digest sent: ${digest.email_delivered || 0} email, ${digest.slack_delivered || 0} Slack.`;
        await loadWorkspaceNotificationSettings();
    } catch (error) {
        if (status) status.textContent = `Could not send digest: ${error.message}`;
    }
}

function setupWorkspaceAlertActions() {
    const list = document.getElementById('workspace-alert-list');
    if (!list || list.dataset.actionsBound) return;
    list.dataset.actionsBound = 'true';
    list.addEventListener('click', event => {
        const button = event.target.closest('[data-workspace-alert-action]');
        if (!button) return;
        const action = button.dataset.workspaceAlertAction;
        const alertId = button.dataset.alertId;
        if (action === 'review') openWorkspaceAlert(alertId, button.dataset.runId);
        if (action === 'dismiss') markWorkspaceAlertRead(alertId);
    });
}

async function loadWorkspaceAlerts() {
    const list = document.getElementById('workspace-alert-list');
    const count = document.getElementById('workspace-alert-count');
    if (!list) return;
    setupWorkspaceAlertActions();
    try {
        const data = await apiFetch('/api/workspace/alerts?limit=20');
        if (count) count.textContent = data.unread_count ? String(data.unread_count) : '';
        const alerts = data.alerts || [];
        list.innerHTML = alerts.length ? alerts.map(alert => {
            const added = (alert.evidence_added || []).join(', ') || 'new evidence';
            const metricParts = [];
            if (alert.previous_score != null && alert.current_score != null) metricParts.push(`score ${Number(alert.previous_score).toFixed(1)} → ${Number(alert.current_score).toFixed(1)}`);
            if (alert.rank_change) metricParts.push(`rank moved ${alert.rank_change}`);
            if (alert.quality_change != null) metricParts.push(`quality ${Number(alert.quality_change).toFixed(2)}`);
            const delta = metricParts.length ? ` · ${metricParts.join(' · ')}` : '';
            return `<div class="workspace-alert-row ${alert.read_at ? '' : 'unread'}"><div><strong>${escapeHtml(alert.title)}</strong><small>${escapeHtml(alert.message)} · added: ${escapeHtml(added)}${delta}</small><small>${escapeHtml(alert.created_at || '')} · trigger run ${escapeHtml(alert.trigger_run_id)}</small></div><div><button class="btn btn-secondary btn-sm" type="button" data-workspace-alert-action="review" data-alert-id="${escapeHtml(alert.alert_id)}" data-run-id="${escapeHtml(alert.trigger_run_id)}">Review</button>${alert.read_at ? '' : `<button class="btn btn-secondary btn-sm" type="button" data-workspace-alert-action="dismiss" data-alert-id="${escapeHtml(alert.alert_id)}">Dismiss</button>`}</div></div>`;
        }).join('') : '<span class="workspace-muted">No new evidence requires review.</span>';
    } catch (error) {
        list.innerHTML = `<span class="workspace-muted">Alerts unavailable: ${escapeHtml(error.message)}</span>`;
    }
}

async function markWorkspaceAlertRead(alertId) {
    try {
        await apiFetch(`/api/workspace/alerts/${encodeURIComponent(alertId)}/read`, { method: 'POST' });
        await loadWorkspaceAlerts();
    } catch (error) {
        showToast(`Could not dismiss alert: ${error.message}`, 'error');
    }
}

async function openWorkspaceAlert(alertId, runId) {
    await markWorkspaceAlertRead(alertId);
    await openWorkspaceRun(runId);
}

async function loadWorkspaceHistory() {
    const list = document.getElementById('workspace-history-list');
    if (!list) return;
    setupWorkspaceHistoryActions();
    try {
        const data = await apiFetch('/api/workspace/runs?limit=20');
        const runs = data.runs || [];
        list.innerHTML = runs.length ? runs.map(run => `
            <div class="workspace-history-row">
                <label><input type="checkbox" class="workspace-compare-check" value="${escapeHtml(run.run_id)}" aria-label="Compare saved run: ${escapeHtml(run.question)}"> <strong>${escapeHtml(run.question)}</strong></label>
                <span>${escapeHtml(run.status)} · ${escapeHtml(run.evidence_count)} evidence · ${escapeHtml(run.updated_at || '')}</span>
                <div><button class="btn btn-secondary btn-sm" type="button" data-workspace-action="open" data-run-id="${escapeHtml(run.run_id)}" aria-label="Open saved run ${escapeHtml(run.run_id)}">Open</button><button class="btn btn-secondary btn-sm" type="button" data-workspace-action="delete" data-run-id="${escapeHtml(run.run_id)}" aria-label="Delete saved run ${escapeHtml(run.run_id)}">Delete</button></div>
            </div>`).join('') : '<span class="workspace-muted">No saved runs yet. Run a workspace query to create one.</span>';
        if (runs.length > 1) list.innerHTML += '<button class="btn btn-primary btn-sm" type="button" data-workspace-action="compare" aria-describedby="workspace-compare">Compare selected runs</button>';
    } catch (error) {
        list.innerHTML = `<span class="workspace-muted">History unavailable: ${escapeHtml(error.message)}</span>`;
    }
}

function setupWorkspaceHistoryActions() {
    const list = document.getElementById('workspace-history-list');
    if (!list || list.dataset.actionsBound) return;
    list.dataset.actionsBound = 'true';
    list.addEventListener('click', event => {
        const button = event.target.closest('[data-workspace-action]');
        if (!button) return;
        const runId = button.dataset.runId;
        if (button.dataset.workspaceAction === 'open') openWorkspaceRun(runId);
        if (button.dataset.workspaceAction === 'delete') deleteWorkspaceRun(runId);
        if (button.dataset.workspaceAction === 'compare') compareWorkspaceRuns();
    });
}

async function openWorkspaceRun(runId) {
    try {
        const payload = await apiFetch(`/api/workspace/runs/${encodeURIComponent(runId)}`);
        if (!payload.dossier) throw new Error(payload.error || 'This run has no dossier');
        renderWorkspaceResult(document.getElementById('workspace-result'), { dossier: payload.dossier, html: payload.html || '' });
        document.getElementById('workspace-result').scrollIntoView({ behavior: 'smooth', block: 'center' });
    } catch (error) {
        showToast(`Could not open run: ${error.message}`, 'error');
    }
}

async function deleteWorkspaceRun(runId) {
    if (!window.confirm(`Delete saved run ${runId}?`)) return;
    try {
        await apiFetch(`/api/workspace/runs/${encodeURIComponent(runId)}`, { method: 'DELETE' });
        await loadWorkspaceHistory();
        showToast('Saved run deleted');
    } catch (error) {
        showToast(`Could not delete run: ${error.message}`, 'error');
    }
}

async function compareWorkspaceRuns() {
    const selected = [...document.querySelectorAll('.workspace-compare-check:checked')].map(input => input.value);
    const compare = document.getElementById('workspace-compare');
    if (!compare) return;
    if (selected.length !== 2) {
        compare.removeAttribute('aria-busy');
        compare.innerHTML = '<p class="workspace-muted">Select exactly two runs to compare.</p>';
        return;
    }
    compare.setAttribute('aria-busy', 'true');
    compare.innerHTML = '<p class="workspace-muted">Loading comparison…</p>';
    try {
        const data = await apiFetch(`/api/workspace/compare?left=${encodeURIComponent(selected[0])}&right=${encodeURIComponent(selected[1])}`);
        const rows = [...(data.drug_changes || []).map(item => ({ ...item, type: 'Drug' })), ...(data.target_changes || []).map(item => ({ ...item, type: 'Target' }))];
        const reviewRows = (data.review_changes || []).map(item => `<div class="workspace-compare-row"><span>${escapeHtml(item.candidate_type)} · <strong>${escapeHtml(item.candidate_name || item.candidate_id)}</strong></span><span>${escapeHtml(item.left?.decision || 'unreviewed')} → ${escapeHtml(item.right?.decision || 'unreviewed')}</span></div>`).join('');
        const changeRows = rows.map(item => {
            const delta = Number.isFinite(Number(item.score_delta)) ? Number(item.score_delta) : null;
            const deltaLabel = delta == null ? escapeHtml(item.change || 'unchanged') : `${delta >= 0 ? '+' : ''}${delta.toFixed(1)}`;
            const deltaClass = delta == null || delta >= 0 ? 'delta-up' : 'delta-down';
            return `<div class="workspace-compare-row"><span>${escapeHtml(item.type)} · <strong>${escapeHtml(item.name || item.candidate_id)}</strong></span><span>${escapeHtml(item.left_score ?? '—')} → ${escapeHtml(item.right_score ?? '—')} <b class="${deltaClass}">${deltaLabel}</b></span></div>`;
        }).join('');
        compare.innerHTML = `<h4 id="workspace-compare-title">Run comparison</h4><p class="workspace-muted">${escapeHtml(data.left_run_id)} → ${escapeHtml(data.right_run_id)}</p>${changeRows || '<p class="workspace-muted">No ranking changes between these runs.</p>'}${reviewRows ? `<h5>Researcher review changes</h5>${reviewRows}` : ''}`;
    } catch (error) {
        compare.innerHTML = `<p class="workspace-muted">Comparison unavailable: ${escapeHtml(error.message)}</p>`;
    } finally {
        compare.removeAttribute('aria-busy');
    }
}

function submitWorkspace(event) {
    event.preventDefault();
    if (workspaceSubmissionActive) return;
    const selectedSources = [...document.getElementById('workspace-sources').selectedOptions].map(option => option.value);
    const resultEl = document.getElementById('workspace-result');
    if (!selectedSources.length) {
        setWorkspaceSubmissionState('failure');
        if (resultEl) {
            resultEl.className = 'workspace-result visible error';
            resultEl.innerHTML = '<strong>Select at least one evidence source.</strong>';
        }
        return;
    }
    const info = activeDiseaseInfo();
    const params = {
        question: document.getElementById('workspace-question').value.trim(),
        disease_id: info.id,
        sources: selectedSources,
        candidate_type: document.getElementById('workspace-candidate-type').value,
        max_evidence: Number(document.getElementById('workspace-max-evidence').value || 50),
        enable_llm: document.getElementById('workspace-enable-llm').checked,
    };
    const from = document.getElementById('workspace-date-from').value;
    const to = document.getElementById('workspace-date-to').value;
    if (from) params.date_from = from;
    if (to) params.date_to = to;
    resultEl.className = 'workspace-result visible loading';
    resultEl.innerHTML = '<span class="spinner"></span> Preparing workspace…';
    setWorkspaceSubmissionState('submitting');
    streamJob('workspace', resultEl, params).then(() => {
        setWorkspaceSubmissionState('success');
    }).catch(error => {
        setWorkspaceSubmissionState('failure');
        // Terminal WebSocket/polling handlers already rendered a specific,
        // escaped failure message. Preserve it instead of replacing it with
        // the promise rejection's generic "Error" label.
        if (!resultEl.classList.contains('error')) {
            resultEl.className = 'workspace-result visible error';
            resultEl.innerHTML = `<strong>Error:</strong> ${escapeHtml(error.message)}`;
        }
    });
}

function renderModuleResult(rows) {
    let html = '<div class="result-header">✅ Analysis Complete</div>';
    for (const [label, value] of rows) {
        html += `<div class="result-row"><span class="result-label">${label}</span><span class="result-value">${formatNumber(value)}</span></div>`;
    }
    return html;
}

function renderKGResult(el, data) {
    el.className = 'module-result visible success';
    if (data.status === 'blocked' || data.coverage?.status === 'blocked') {
        el.innerHTML = renderCoveragePanel(data.coverage);
        return;
    }
    el.innerHTML = renderCoveragePanel(data.coverage) + renderModuleResult([
        ['Total Nodes', data.total_nodes],
        ['Total Edges', data.total_edges],
        ['Untargeted Genes', data.untargeted_genes?.length || 0],
        ['Top Hub', data.top_hub_genes?.[0]?.name || '—'],
    ]);
}

function renderRepurposeResult(el, data) {
    el.className = 'module-result visible success';
    if (data.status === 'blocked' || data.coverage?.status === 'blocked') {
        el.innerHTML = renderCoveragePanel(data.coverage);
        return;
    }
    el.innerHTML = renderCoveragePanel(data.coverage) + renderModuleResult([
        ['Candidates Scored', data.total],
        ['Avg Score', data.avg_score?.toFixed(2)],
        ['Tier 1 (≥8.0)', data.tier1_count],
        ['Top Drug', data.candidates?.[0]?.drug_name || '—'],
    ]);
}

function renderBiomarkerResult(el, data) {
    const top = data.biomarkers?.[0];
    el.className = 'module-result visible success';
    if (data.status === 'blocked' || data.coverage?.status === 'blocked') {
        el.innerHTML = renderCoveragePanel(data.coverage);
        return;
    }
    el.innerHTML = renderCoveragePanel(data.coverage) + renderModuleResult([
        ['Genes Analyzed', data.total_genes],
        ['Avg Score', data.avg_score?.toFixed(2)],
        ['Strong Biomarkers', data.tier1_count],
        ['Top Gene', top ? top.gene_name : '—'],
        ['Best Modality', top?.best_modality || '—'],
    ]);
}

function renderCartResult(el, data) {
    const top = data.genes?.[0];
    el.className = 'module-result visible success';
    if (data.status === 'blocked' || data.coverage?.status === 'blocked') {
        el.innerHTML = renderCoveragePanel(data.coverage);
        return;
    }
    el.innerHTML = renderCoveragePanel(data.coverage) + renderModuleResult([
        ['Genes Scored', data.total_genes],
        ['Avg Score', data.avg_score?.toFixed(2)],
        ['Tier 1 (Strong)', data.tier1_count],
        ['Top Gene', top ? top.gene_name : '—'],
        ['Top Score', top?.composite_score?.toFixed(2) || '—'],
    ]);
}

function renderExpressionResult(el, data) {
    const top = data.drugs?.[0];
    el.className = 'module-result visible success';
    if (data.status === 'blocked' || data.coverage?.status === 'blocked') {
        el.innerHTML = renderCoveragePanel(data.coverage);
        return;
    }
    el.innerHTML = renderCoveragePanel(data.coverage) + renderModuleResult([
        ['Drugs Correlated', data.total_drugs],
        ['Avg Score', data.avg_score?.toFixed(2)],
        ['Tier 1 (Strong)', data.tier1_count],
        ['Top Drug', top ? top.drug_name?.split('(')[0].trim() : '—'],
        ['Top Score', top?.composite_score?.toFixed(2) || '—'],
    ]);
}

function renderSemanticResult(el, data) {
    const top = data.results?.[0];
    el.className = 'module-result visible success';
    if (data.status === 'blocked' || data.coverage?.status === 'blocked') {
        el.innerHTML = renderCoveragePanel(data.coverage);
        return;
    }
    el.innerHTML = renderCoveragePanel(data.coverage) + renderModuleResult([
        ['Indexed Articles', data.indexed_articles],
        ['Results Found', data.total_results],
        ['Top Match', top ? top.title?.slice(0, 50) + '...' : '—'],
        ['Similarity', top?.similarity?.toFixed(1) || '—'],
    ]);
}

function renderEvidenceResult(el, data) {
    const top = data.results?.[0];
    el.className = 'module-result visible success';
    if (data.status === 'blocked' || data.coverage?.status === 'blocked') {
        el.innerHTML = renderCoveragePanel(data.coverage);
        return;
    }
    el.innerHTML = renderCoveragePanel(data.coverage) + renderModuleResult([
        ['Total Results', data.total_results],
        ['Sources Searched', data.sources_searched?.length || 0],
        ['Top Source', top ? top.source_type?.replace('_',' ').toUpperCase() : '—'],
        ['Top Match', top ? top.title?.slice(0, 50) + '...' : '—'],
    ]);
}

function renderExtractorResult(el, data) {
    const stats = data.stats || {};
    el.className = 'module-result visible success';
    if (data.status === 'blocked' || data.coverage?.status === 'blocked') {
        el.innerHTML = renderCoveragePanel(data.coverage);
        return;
    }
    el.innerHTML = renderCoveragePanel(data.coverage) + renderModuleResult([
        ['Articles Extracted', data.total_extracted],
        ['Successful', data.successful_extractions],
        ['LLM Model', data.model],
        ['Avg Confidence', (stats.avg_confidence || 0) + '%'],
        ['Drugs Found', stats.n_unique_drugs || 0],
    ]);
}

function renderMonitorResult(el, data) {
    const alerts = data.alerts || [];
    const high = alerts.filter(a => a.severity === 'high').length;
    const med = alerts.filter(a => a.severity === 'medium').length;
    const low = alerts.filter(a => a.severity === 'low').length;
    el.className = 'module-result visible success';
    if (data.status === 'blocked' || data.coverage?.status === 'blocked') {
        el.innerHTML = renderCoveragePanel(data.coverage);
        return;
    }
    el.innerHTML = renderCoveragePanel(data.coverage) + renderModuleResult([
        ['Total Changes', data.total_changes],
        ['🔴 High Alerts', high],
        ['🟡 Medium Alerts', med],
        ['🟢 Low Alerts', low],
        ['Hours Elapsed', (data.hours_elapsed || 0).toFixed(1) + 'h'],
    ]);
}

function renderBioResult(el, data) {
    el.className = 'module-result visible success';
    if (data.status === 'blocked' || data.coverage?.status === 'blocked') {
        el.innerHTML = renderCoveragePanel(data.coverage);
        return;
    }
    el.innerHTML = renderCoveragePanel(data.coverage) + renderModuleResult([
        ['Total Nodes', data.total_nodes],
        ['Untargeted Genes', data.untargeted_genes?.length || 0],
        ['Top Hub Gene', data.top_hub_genes?.[0]?.name || '—'],
    ]);
}

// ── Job Queue UI ─────────────────────────────────────────────────────────

function showJobsSection() {
    document.getElementById('jobs').style.display = 'flex';
    document.getElementById('job-queue').style.display = 'flex';
    document.getElementById('jobs-tab').style.color = '#fbbf24';
}

function updateJobBadge() {
    const count = Object.keys(activeJobs).length;
    const badge = document.getElementById('job-count');
    const headerBadge = document.getElementById('jobs-header-count');
    if (count > 0) {
        badge.textContent = count;
        badge.classList.remove('hidden');
        headerBadge.textContent = count;
        headerBadge.style.display = 'inline-block';
    } else {
        badge.classList.add('hidden');
        headerBadge.style.display = 'none';
        document.getElementById('jobs-tab').style.color = '';
    }
}

function renderJobQueue() {
    const container = document.getElementById('job-queue');
    const jobIds = Object.keys(activeJobs);

    if (jobIds.length === 0) {
        container.innerHTML = '<div style="color:var(--text-muted);font-size:0.82rem;padding:12px;">No active jobs. Run an analysis to get started.</div>';
        return;
    }

    container.innerHTML = jobIds.map(id => {
        const job = activeJobs[id];
        const shortId = id.slice(0, 12) + '…';
        const hasSocket = !!activeSockets[id];
        const streamIcon = hasSocket ? '⚡' : '📡';
        return `
            <div class="job-item">
                <div class="job-info">
                    <span class="job-module" style="background:rgba(129,140,248,0.1);color:#818cf8;">${job.module}</span>
                    <code style="font-size:0.72rem;color:var(--text-muted);">${shortId}</code>
                    <span title="${hasSocket ? 'WebSocket streaming' : 'HTTP polling'}" style="font-size:0.65rem;">${streamIcon}</span>
                </div>
                <div class="job-status ${job.status}">
                    ${job.status === 'STARTED' ? '<span class="spinner" style="margin-right:6px;"></span>' : ''}
                    ${job.status}
                </div>
            </div>
        `;
    }).join('');
}

// ── Cross-Disease Analysis ──────────────────────────────────────────
async function runCrossDisease() {
    const resultEl = document.getElementById('result-cross-disease');
    if (!resultEl) return;

    resultEl.className = 'module-result visible loading';
    resultEl.innerHTML = '<span class="spinner"></span> Running cross-disease analysis...';

    try {
        const data = await apiFetch('/api/cross-disease/overlap');

        const geneCount = data.shared_genes && data.shared_genes.shared_genes
            ? data.shared_genes.shared_genes.length : 0;
        const drugCount = data.shared_drugs && data.shared_drugs.shared_drugs
            ? data.shared_drugs.shared_drugs.length : 0;
        const pathCount = data.shared_pathways && data.shared_pathways.shared_pathways
            ? data.shared_pathways.shared_pathways.length : 0;

        resultEl.className = 'module-result visible success';
        resultEl.innerHTML = renderModuleResult([
            ['Diseases Analyzed', data.disease_count],
            ['Shared Genes', geneCount],
            ['Shared Drugs', drugCount],
            ['Shared Pathways', pathCount],
        ]);

        // Render the full comparison view below the card
        renderCrossDiseaseComparison(data);
    } catch (err) {
        resultEl.className = 'module-result visible error';
        resultEl.innerHTML = `<strong>Error:</strong> ${err.message}`;
    }
}

// ── Cross-Disease Comparison View ───────────────────────────────────────

const CD_KNOWN_LABELS = {
    sle: 'SLE', ra: 'RA', ibd: 'IBD', ms: 'MS', ss: 'SS', ssc: 'SSc', t1d: 'T1D',
};

function cdAcronym(id, name) {
    // Curated acronyms win; otherwise derive one from the name's initials
    // (keeping embedded digits: "Type 1 Diabetes" -> T1D).
    if (CD_KNOWN_LABELS[id]) return CD_KNOWN_LABELS[id];
    const clean = String(name || id).replace(/\(.*?\)/g, '').trim();
    let acr = clean.split(/\s+/).filter(Boolean).map(w => {
        const digit = (w.match(/\d/) || [null])[0];
        return digit || w[0] || '';
    }).join('').toUpperCase();
    if (acr.length === 1) acr = clean.replace(/[^a-zA-Z0-9]/g, '').slice(0, 3).toUpperCase();
    return acr || id.toUpperCase();
}

function cdDiseaseList(summary) {
    // Order by the live registry when available; always include any disease
    // present in the response so new diseases show up regardless.
    const present = Object.keys(summary || {});
    const ordered = [];
    for (const d of (diseaseCache && diseaseCache.list) || []) {
        if (present.includes(d.id)) ordered.push(d.id);
    }
    for (const id of present) {
        if (!ordered.includes(id)) ordered.push(id);
    }
    return ordered.map(id => {
        const entry = summary[id] || {};
        const fullName = entry.name || id;
        return {
            id,
            name: fullName.split('(')[0].trim(),
            label: cdAcronym(id, fullName),
        };
    });
}

function cdColorFor(value, max) {
    // value 0..max -> color scale (green -> blue -> purple)
    if (!value) return 'rgba(255,255,255,0.04)';
    const t = Math.min(1, value / max);
    if (t < 0.34) {
        const r = Math.round(74 + (129 - 74) * (t / 0.34));
        const g = Math.round(222 + (140 - 222) * (t / 0.34));
        const b = Math.round(128 + (248 - 128) * (t / 0.34));
        return `rgb(${r},${g},${b})`;
    }
    if (t < 0.67) {
        const tt = (t - 0.34) / 0.33;
        const r = Math.round(129 + (192 - 129) * tt);
        const g = Math.round(140 + (132 - 140) * tt);
        const b = Math.round(248 + (252 - 248) * tt);
        return `rgb(${r},${g},${b})`;
    }
    const tt = (t - 0.67) / 0.33;
    const r = Math.round(192 + (244 - 192) * tt);
    const g = Math.round(132 + (114 - 132) * tt);
    const b = Math.round(252 + (182 - 252) * tt);
    return `rgb(${r},${g},${b})`;
}

function renderCrossDiseaseComparison(data) {
    let section = document.getElementById('cross-disease-view');
    if (!section) {
        section = document.createElement('div');
        section.id = 'cross-disease-view';
        const container = document.getElementById('modules-grid');
        container.parentElement.insertBefore(section, container.nextSibling);
    }

    const summary = data.disease_summary || {};
    const sharedGenes = (data.shared_genes || {}).matrix || {};
    const sharedDrugs = (data.shared_drugs || {}).matrix || {};
    const similarity = data.disease_similarity || [];
    const multiDrugs = data.multi_disease_drugs || [];

    const diseaseNames = cdDiseaseList(summary);
    const diseaseLabel = {};
    for (const d of diseaseNames) diseaseLabel[d.id] = d.label;

    // ── Gene × Disease heatmap ──────────────────────────────────────
    const geneEntries = Object.entries(sharedGenes)
        .map(([gid, g]) => ({
            gid,
            name: g.name || gid,
            per: g.per_disease || {},
            count: Object.keys(g.per_disease || {}).length,
        }))
        .sort((a, b) => b.count - a.count);

    let maxOr = 0;
    for (const g of geneEntries) {
        for (const d of diseaseNames) {
            const or = g.per[d.id] && g.per[d.id].odds_ratio;
            if (or && or > maxOr) maxOr = or;
        }
    }

    const geneRows = geneEntries.map(g => {
        const cells = diseaseNames.map(d => {
            const pd = g.per[d.id];
            const or = pd && pd.odds_ratio;
            const title = pd ? `${pd.category || ''}${or ? ` · OR ${or}` : ''}` : '';
            const val = or != null ? or.toFixed(1) : '';
            return `<td style="background:${cdColorFor(or || 0, maxOr || 1)};color:${or ? '#0a0a0f' : 'rgba(120,120,144,0.35)'};border-radius:4px;text-align:center;" title="${title}">${val}</td>`;
        }).join('');
        return `<tr>
            <td class="gene-name">${g.gid}</td>
            <td class="gene-count">${g.count}/${diseaseNames.length}</td>
            ${cells}
        </tr>`;
    }).join('');

    // ── Similarity matrix ───────────────────────────────────────────
    const simMap = {};
    for (const s of similarity) {
        simMap[`${s.disease_a}|${s.disease_b}`] = s.similarity;
        simMap[`${s.disease_b}|${s.disease_a}`] = s.similarity;
    }
    const simHeader = diseaseNames.map(d => `<th>${escapeHtml(d.label)}</th>`).join('');
    const simRows = diseaseNames.map(d => {
        const cells = diseaseNames.map(d2 => {
            if (d.id === d2.id) return `<td style="background:rgba(129,140,248,0.15);text-align:center;">—</td>`;
            const v = simMap[`${d.id}|${d2.id}`] || 0;
            return `<td style="background:${cdColorFor(v, 1)};text-align:center;color:#0a0a0f;">${v.toFixed(2)}</td>`;
        }).join('');
        return `<tr><td class="gene-name">${escapeHtml(d.label)}</td>${cells}</tr>`;
    }).join('');

    // ── Multi-disease drugs ─────────────────────────────────────────
    const drugRows = multiDrugs.slice(0, 12).map(drug => {
        const diseases = (drug.diseases || drug.disease_ids || []);
        const tags = diseases.slice(0, 7).map(d =>
            `<span class="cd-disease-tag">${escapeHtml(diseaseLabel[d] || d)}</span>`).join('');
        return `<div class="cd-drug-row">
            <div>
                <span class="cd-drug-name">${drug.drug_name || drug.drug_id || drug.name || ''}</span>
                <div class="cd-drug-diseases">${tags}${diseases.length > 7 ? ` <span class="cd-disease-tag">+${diseases.length - 7}</span>` : ''}</div>
            </div>
            <span class="cd-score-badge">${drug.score != null ? drug.score.toFixed(2) : ''}</span>
        </div>`;
    }).join('');

    section.innerHTML = `
        <h2 class="section-title"><span>🌐</span> Cross-Disease Comparison</h2>

        <div class="cd-card">
            <h3>🧬 Gene × Disease Association Heatmap <span style="font-weight:400;color:var(--text-muted);font-size:0.78rem;">(odds ratio by presence)</span></h3>
            <table class="cd-table">
                <thead><tr>
                    <th>Gene</th><th>Coverage</th>
                    ${diseaseNames.map(d => `<th>${escapeHtml(d.label)}</th>`).join('')}
                </tr></thead>
                <tbody>${geneRows}</tbody>
            </table>
            <div class="cd-legend">
                <span><span class="swatch" style="background:${cdColorFor(1, 3)}"></span> OR 1.0</span>
                <span><span class="swatch" style="background:${cdColorFor(2, 3)}"></span> OR 2.0</span>
                <span><span class="swatch" style="background:${cdColorFor(3, 3)}"></span> OR 3.0+</span>
                <span><span class="swatch" style="background:rgba(255,255,255,0.04);border:1px solid #252535;"></span> Not associated</span>
            </div>
        </div>

        <div class="cd-card">
            <h3>🔗 Disease Similarity Matrix <span style="font-weight:400;color:var(--text-muted);font-size:0.78rem;">(shared-biology Jaccard)</span></h3>
            <table class="cd-table" style="min-width:360px;">
                <thead><tr><th></th>${simHeader}</tr></thead>
                <tbody>${simRows}</tbody>
            </table>
        </div>

        <div class="cd-card">
            <h3>💊 Multi-Disease Repurposing Candidates</h3>
            ${drugRows || '<p style="color:var(--text-muted);font-size:0.8rem;">No multi-disease drug data.</p>'}
        </div>
    `;
    section.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// ── Comparative Module View (biomarker / expression / synergy × 7 diseases) ──

async function runModuleComparison() {
    const resultEl = document.getElementById('result-cross-disease');
    if (!resultEl) return;
    resultEl.className = 'module-result visible loading';
    resultEl.innerHTML = '<span class="spinner"></span> Running biomarker · expression · synergy across all diseases…';

    try {
        const data = await apiFetch('/api/cross-disease/modules');
        resultEl.className = 'module-result visible success';
        const modules = data.modules || {};
        resultEl.innerHTML = renderModuleResult([
            ['Diseases Analyzed', data.diseases?.length || 0],
            ['Biomarker Genes', Object.keys(modules.biomarker?.scores || {}).length],
            ['Drugs Correlated', Object.keys(modules.expression?.scores || {}).length],
            ['Synergy Pairs Top', Object.keys(modules.synergy?.top || {}).length],
        ]);
        renderModuleComparison(data);
    } catch (e) {
        resultEl.className = 'module-result visible error';
        resultEl.innerHTML = `<strong>Error:</strong> ${e.message}`;
    }
}

function cmScoreMatrix(diseaseNames, scores, { maxValue = 10 } = {}) {
    // Rows = union of entities (genes/drugs) across diseases, sorted by
    // disease coverage then max score. Cells = per-disease score.
    const entities = new Set();
    const perDisease = {};
    for (const [entity, byDisease] of Object.entries(scores)) {
        entities.add(entity);
        perDisease[entity] = byDisease;
    }

    const rows = [...entities].map(e => ({
        id: e,
        coverage: Object.keys(perDisease[e] || {}).length,
        max: Math.max(0, ...Object.values(perDisease[e] || {})),
    })).sort((a, b) => b.coverage - a.coverage || b.max - a.max);

    const header = `<th>Entity</th>` + diseaseNames.map(d => `<th>${escapeHtml(d.label)}</th>`).join('');
    const body = rows.map(r => {
        const cells = diseaseNames.map(d => {
            const v = (perDisease[r.id] || {})[d.id];
            if (v == null) {
                return `<td style="background:rgba(255,255,255,0.04);color:rgba(120,120,144,0.35);">—</td>`;
            }
            const bg = cdColorFor(v, maxValue);
            const txt = v >= maxValue * 0.45 ? '#0a0a0f' : '#e0e0e8';
            return `<td style="background:${bg};color:${txt};font-weight:600;" title="${escapeHtml(r.id)} · ${escapeHtml(d.label)}: ${v.toFixed(2)}">${v.toFixed(1)}</td>`;
        }).join('');
        return `<tr><td class="gene-name">${escapeHtml(r.id)}</td>${cells}</tr>`;
    }).join('');
    return { header, body, total: rows.length };
}

function renderModuleComparison(data) {
    let section = document.getElementById('comparative-module-view');
    if (!section) {
        section = document.createElement('div');
        section.id = 'comparative-module-view';
        const container = document.getElementById('modules-grid');
        container.parentElement.insertBefore(section, container.nextSibling);
    }

    const diseaseNames = (data.diseases || []).map(d => ({
        id: d.id,
        label: cdAcronym(d.id, d.name),
    }));
    const modules = data.modules || {};
    const bm = modules.biomarker?.scores || {};
    const ex = modules.expression?.scores || {};
    const sy = modules.synergy?.top || {};

    const bmTable = cmScoreMatrix(diseaseNames, bm);
    const exTable = cmScoreMatrix(diseaseNames, ex);

    // Synergy: per-disease top pairs side by side
    const syHeader = diseaseNames.map(d => `<th>${escapeHtml(d.label)}</th>`).join('');
    const syMax = Math.max(0, ...Object.values(sy).flat().map(p => p?.score || 0));
    const syRows = [0, 1, 2, 3, 4].map(rank => {
        const cells = diseaseNames.map(d => {
            const pair = (sy[d.id] || [])[rank];
            if (!pair) return `<td style="color:rgba(120,120,144,0.35);">—</td>`;
            const bg = cdColorFor(pair.score, Math.max(10, syMax));
            return `<td style="background:${bg};color:${pair.score >= 4.5 ? '#0a0a0f' : '#e0e0e8'};font-weight:600;" title="${escapeHtml(pair.label)} · ${pair.score.toFixed(2)}">${escapeHtml(pair.label)}<br><small style="font-weight:700;">${pair.score.toFixed(2)}</small></td>`;
        }).join('');
        return `<tr><td class="gene-count">#${rank + 1}</td>${cells}</tr>`;
    }).join('');

    section.innerHTML = `
        <h2 class="section-title"><span>⚖️</span> Cross-Disease Module Comparison</h2>
        <p style="color:var(--text-muted);font-size:0.82rem;margin-bottom:14px;">
            Biomarker discovery, gene-expression correlation, and drug synergy scored independently for
            every disease — stacked side by side so cross-disease patterns are visible at a glance.
        </p>

        <div class="cd-card">
            <h3>🧬 Biomarker × Disease <span style="font-weight:400;color:var(--text-muted);font-size:0.78rem;">(composite score, ${bmTable.total} genes)</span></h3>
            <table class="cd-table">
                <thead><tr>${bmTable.header}</tr></thead>
                <tbody>${bmTable.body}</tbody>
            </table>
        </div>

        <div class="cd-card">
            <h3>🧬 Expression Correlation × Disease <span style="font-weight:400;color:var(--text-muted);font-size:0.78rem;">(composite score, ${exTable.total} drugs)</span></h3>
            <table class="cd-table">
                <thead><tr>${exTable.header}</tr></thead>
                <tbody>${exTable.body}</tbody>
            </table>
        </div>

        <div class="cd-card">
            <h3>🔗 Top Synergy Pairs per Disease</h3>
            <table class="cd-table" style="min-width:480px;">
                <thead><tr><th>Rank</th>${syHeader}</tr></thead>
                <tbody>${syRows}</tbody>
            </table>
        </div>
    `;
    section.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// ── Knowledge Graph Explorer ────────────────────────────────────────────

const KG_TYPE_COLORS = {
    gene: '#4ade80',
    drug: '#60a5fa',
    pathway: '#f59e0b',
    disease: '#f43f5e',
    unknown: '#787890',
};
const KG_EDGE_COLORS = {
    TARGETS: '#60a5fa',
    TREATS: '#4ade80',
    PARTICIPATES_IN: '#a78bfa',
    DRIVES: '#f43f5e',
    MODULATES: '#f59e0b',
    ASSOCIATED_WITH: '#94a3b8',
    UNKNOWN: '#3a3a4a',
};

let kgNetwork = null;
let kgNodes = null;
let kgEdges = null;
let kgRawElements = null;

function scrollToExplorer() {
    const el = document.getElementById('kg-explorer');
    if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'start' });
        initKGExplorer();
    }
}

async function initKGExplorer() {
    const canvas = document.getElementById('kg-canvas');
    if (!canvas) return;

    const disease = getActiveDisease();
    const loading = document.querySelector('#kg-canvas .kg-loading');
    if (loading) loading.style.display = 'flex';

    try {
        const data = await apiFetch(`/api/kg/graph?disease=${encodeURIComponent(disease)}`);
        kgRawElements = data.elements || [];
        buildKGNetwork();
        updateKGStats();
        setupKGControls();
    } catch (e) {
        canvas.innerHTML = `<div class="kg-loading"><strong style="color:#f87171;">⚠️ ${e.message}</strong></div>`;
    }
}

function buildKGNetwork() {
    const canvas = document.getElementById('kg-canvas');
    if (!canvas || typeof vis === 'undefined') {
        canvas.innerHTML = `<div class="kg-loading"><strong style="color:#f87171;">⚠️ vis-network library not loaded</strong></div>`;
        return;
    }

    kgNodes = new vis.DataSet();
    kgEdges = new vis.DataSet();

    const nodeMap = {};
    for (const el of kgRawElements) {
        const d = el.data || {};
        const hasSrc = d.from !== undefined || d.source !== undefined;
        const hasDst = d.to !== undefined || d.target !== undefined;
        if (d.id !== undefined && !(hasSrc && hasDst) && !(d.id in nodeMap)) {
            const type = d.type || 'unknown';
            const color = KG_TYPE_COLORS[type] || '#787890';
            nodeMap[d.id] = {
                id: d.id,
                label: d.label || d.id,
                type,
                color: { background: color, border: color, highlight: { background: '#ffffff', border: '#ffffff' } },
                font: { color: '#d0d0dc', size: 13 },
                shape: type === 'drug' ? 'box' : type === 'pathway' ? 'diamond' : type === 'disease' ? 'star' : 'dot',
                title: d.label || d.id,
            };
        }
    }
    for (const el of kgRawElements) {
        const d = el.data || {};
        const from = d.from ?? d.source;
        const to = d.to ?? d.target;
        if (from !== undefined && to !== undefined) {
            const type = d.type || 'UNKNOWN';
            kgEdges.add({
                id: d.id || `${from}--${to}--${type}`,
                from, to,
                type,
                color: { color: KG_EDGE_COLORS[type] || '#3a3a4a', opacity: 0.55 },
                arrows: { to: { enabled: true, scaleFactor: 0.5 } },
                width: 1,
                title: type,
            });
        }
    }

    // Only add nodes that participate in the currently visible filter set
    applyKGNodeFilters();

    const options = {
        nodes: { borderWidth: 1.5, shadow: { enabled: false }, chosen: true },
        edges: { smooth: { type: 'continuous' }, selectionWidth: 1.5 },
        physics: {
            enabled: true,
            solver: 'forceAtlas2Based',
            forceAtlas2Based: { gravitationalConstant: -40, centralGravity: 0.012, springLength: 110, springConstant: 0.06, damping: 0.5 },
            stabilization: { iterations: 180 },
        },
        interaction: { hover: true, tooltipDelay: 120, navigationButtons: false, keyboard: true },
        layout: { improvedLayout: false },
        height: '520px',
    };

    kgNetwork = new vis.Network(canvas, { nodes: kgNodes, edges: kgEdges }, options);

    kgNetwork.on('click', async (params) => {
        if (params.nodes && params.nodes.length > 0) {
            const nodeId = params.nodes[0];
            await showKGNodeDetail(nodeId);
        }
    });
    kgNetwork.on('deselectNode', () => clearKGDetail());
}

function applyKGNodeFilters() {
    if (!kgNodes || !kgRawElements) return;
    const checks = document.querySelectorAll('.kg-filter input[data-type]');
    const visible = {};
    for (const c of checks) visible[c.dataset.type] = c.checked;

    const nodeMap = {};
    for (const el of kgRawElements) {
        const d = el.data || {};
        const hasSrc = d.from !== undefined || d.source !== undefined;
        const hasDst = d.to !== undefined || d.target !== undefined;
        if (d.id !== undefined && !(hasSrc && hasDst) && !(d.id in nodeMap)) {
            const type = d.type || 'unknown';
            nodeMap[d.id] = {
                id: d.id,
                label: d.label || d.id,
                type,
                color: { background: KG_TYPE_COLORS[type] || '#787890', border: KG_TYPE_COLORS[type] || '#787890', highlight: { background: '#ffffff', border: '#ffffff' } },
                font: { color: '#d0d0dc', size: 13 },
                shape: type === 'drug' ? 'box' : type === 'pathway' ? 'diamond' : type === 'disease' ? 'star' : 'dot',
                title: d.label || d.id,
            };
        }
    }

    const visibleIds = new Set(Object.keys(nodeMap).filter(id => visible[nodeMap[id].type] !== false));
    kgNodes.clear();
    kgNodes.add([...visibleIds].map(id => nodeMap[id]));

    // Edges between visible nodes only (filtered by edge types as well)
    const edgeChecks = document.querySelectorAll('.kg-edge-filters input[data-edge-type]');
    const visibleEdges = {};
    for (const ec of edgeChecks) visibleEdges[ec.dataset.edgeType.toLowerCase()] = ec.checked;

    const visEdges = [];
    for (const el of kgRawElements) {
        const d = el.data || {};
        const from = d.from ?? d.source;
        const to = d.to ?? d.target;
        if (from !== undefined && to !== undefined) {
            if (visibleIds.has(from) && visibleIds.has(to)) {
                const type = d.type || 'UNKNOWN';
                const typeLower = type.toLowerCase();
                if (visibleEdges[typeLower] === false) continue;
                visEdges.push({
                    id: d.id || `${from}--${to}--${type}`,
                    from, to, type,
                    color: { color: KG_EDGE_COLORS[type] || '#3a3a4a', opacity: 0.55 },
                    arrows: { to: { enabled: true, scaleFactor: 0.5 } },
                    width: 1,
                    title: type,
                });
            }
        }
    }
    kgEdges.clear();
    kgEdges.add(visEdges);

    if (kgNetwork) kgNetwork.fit({ animation: true });
}

let kgPhysicsEnabled = true;
let kgCentralityActive = false;
let kgCommunityActive = false;

function toggleKGPhysics() {
    if (!kgNetwork) return;
    kgPhysicsEnabled = !kgPhysicsEnabled;
    kgNetwork.setOptions({ physics: { enabled: kgPhysicsEnabled } });
    const btn = document.getElementById('kg-physics-toggle');
    if (btn) {
        btn.textContent = kgPhysicsEnabled ? '⏸ Pause Physics' : '▶ Resume Physics';
        btn.classList.toggle('active-overlay', !kgPhysicsEnabled);
    }
}

async function toggleKGCentrality() {
    if (!kgNetwork || !kgNodes) return;
    kgCentralityActive = !kgCentralityActive;
    const btn = document.getElementById('kg-centrality-toggle');
    if (btn) btn.classList.toggle('active-overlay', kgCentralityActive);

    if (!kgCentralityActive) {
        applyKGNodeFilters();
        return;
    }

    const disease = getActiveDisease();
    try {
        const data = await apiFetch(`/api/kg/centrality?disease=${encodeURIComponent(disease)}&metric=betweenness&top_n=30`);
        const scores = data.scores || {};
        kgNodes.forEach(n => {
            const val = scores[n.id] || scores[n.label] || 0;
            const size = 15 + Math.min(val * 400, 35);
            kgNodes.update({ id: n.id, size, font: { size: val > 0.05 ? 16 : 13 } });
        });
    } catch (e) {
        console.error('Centrality fetch failed:', e);
    }
}

async function toggleKGCommunities() {
    if (!kgNetwork || !kgNodes) return;
    kgCommunityActive = !kgCommunityActive;
    const btn = document.getElementById('kg-community-toggle');
    if (btn) btn.classList.toggle('active-overlay', kgCommunityActive);

    if (!kgCommunityActive) {
        applyKGNodeFilters();
        return;
    }

    const disease = getActiveDisease();
    try {
        const data = await apiFetch(`/api/kg/communities?disease=${encodeURIComponent(disease)}`);
        const communities = data.communities || {};
        const colors = ['#f43f5e', '#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#06b6d4'];
        kgNodes.forEach(n => {
            const commId = communities[n.id] !== undefined ? communities[n.id] : 0;
            const col = colors[commId % colors.length];
            kgNodes.update({
                id: n.id,
                color: { background: col, border: col, highlight: { background: '#ffffff', border: '#ffffff' } }
            });
        });
    } catch (e) {
        console.error('Community fetch failed:', e);
    }
}

function exportKGCanvasImage() {
    const canvas = document.querySelector('#kg-canvas canvas');
    if (!canvas) return;
    const url = canvas.toDataURL('image/png');
    const a = document.createElement('a');
    a.href = url;
    a.download = `knowledge_graph_${getActiveDisease()}.png`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
}

async function expand2HopNeighbors(nodeId) {
    if (!nodeId || !kgNodes || !kgEdges) return;
    const disease = getActiveDisease();
    try {
        const data = await apiFetch(`/api/kg/neighbors/${encodeURIComponent(nodeId)}?hops=2&disease=${encodeURIComponent(disease)}`);
        const neighbors = data.neighbors || [];
        const relationships = data.relationships || [];

        neighbors.forEach(node => {
            if (!kgNodes.get(node.id)) {
                const type = node.type || 'unknown';
                const color = KG_TYPE_COLORS[type] || '#787890';
                kgNodes.add({
                    id: node.id,
                    label: node.label || node.id,
                    type,
                    color: { background: color, border: color, highlight: { background: '#ffffff', border: '#ffffff' } },
                    font: { color: '#d0d0dc', size: 13 },
                    shape: type === 'drug' ? 'box' : type === 'pathway' ? 'diamond' : 'dot',
                    title: node.label || node.id,
                });
            }
        });

        relationships.forEach(rel => {
            const relId = rel.id || `${rel.source}--${rel.target}--${rel.type}`;
            if (!kgEdges.get(relId)) {
                const type = rel.type || 'UNKNOWN';
                kgEdges.add({
                    id: relId,
                    from: rel.source,
                    to: rel.target,
                    type,
                    color: { color: KG_EDGE_COLORS[type] || '#3a3a4a', opacity: 0.7 },
                    arrows: { to: { enabled: true, scaleFactor: 0.5 } },
                    width: 1.5,
                    title: type,
                });
            }
        });

        if (kgNetwork) {
            kgNetwork.selectNodes([nodeId]);
            kgNetwork.fit({ animation: true });
        }
    } catch (e) {
        console.error('Failed to expand neighbors:', e);
    }
}

async function runMultiDiseaseComparison() {
    const resultDiv = document.getElementById('multi-disease-result');
    if (!resultDiv) return;

    const checkboxes = document.querySelectorAll('#multi-disease-selector input[type="checkbox"]:checked');
    const selectedDiseases = Array.from(checkboxes).map(cb => cb.value);

    if (selectedDiseases.length < 2) {
        resultDiv.innerHTML = `<p class="condition-comparison-placeholder" style="color:#f87171;">Please select at least 2 diseases to compare.</p>`;
        return;
    }

    resultDiv.innerHTML = `<p class="condition-comparison-placeholder"><span class="spinner"></span> Calculating multi-disease pairwise similarity matrix and shared target overlap…</p>`;

    try {
        const [simData, drugsData] = await Promise.all([
            apiFetch('/api/cross-disease/similarity'),
            apiFetch('/api/cross-disease/drugs?top=15')
        ]);

        const allDiseases = simData.diseases || [];
        const rawMatrix = simData.similarity || [];
        const drugs = drugsData.drugs || [];

        const selectedIndices = selectedDiseases.map(id => allDiseases.indexOf(id)).filter(i => i !== -1);
        const labels = selectedIndices.map(i => allDiseases[i].toUpperCase());

        let tableHtml = `<table class="matrix-table"><thead><tr><th>Disease</th>`;
        labels.forEach(l => { tableHtml += `<th>${l}</th>`; });
        tableHtml += `</tr></thead><tbody>`;

        selectedIndices.forEach((rIdx, i) => {
            tableHtml += `<tr><th>${labels[i]}</th>`;
            selectedIndices.forEach((cIdx, j) => {
                const val = (rawMatrix[rIdx] && rawMatrix[rIdx][cIdx] !== undefined) ? rawMatrix[rIdx][cIdx] : (i === j ? 1.0 : 0.0);
                const scoreStr = (val * 100).toFixed(1) + '%';
                const cls = val >= 0.7 ? 'high' : val >= 0.4 ? 'medium' : 'low';
                tableHtml += `<td class="matrix-cell ${cls}">${scoreStr}</td>`;
            });
            tableHtml += `</tr>`;
        });
        tableHtml += `</tbody></table>`;

        let drugsHtml = `<div style="margin-top:20px;"><h4>💊 Top Multi-Disease Drug Candidates</h4><div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:10px;">`;
        drugs.slice(0, 10).forEach(d => {
            drugsHtml += `<div class="kg-rel" style="background:var(--surface);padding:8px 12px;border-radius:8px;border:1px solid var(--border);"><strong>${escapeHtml(d.name || d.id)}</strong> <span class="rel-type" style="margin-left:6px;">${(d.score || d.disease_count || 0)}</span></div>`;
        });
        drugsHtml += `</div></div>`;

        resultDiv.innerHTML = `<div><h3>📊 Pairwise Jaccard Similarity Matrix</h3>${tableHtml}${drugsHtml}</div>`;
    } catch (e) {
        resultDiv.innerHTML = `<p class="condition-comparison-placeholder" style="color:#f87171;">⚠️ ${escapeHtml(e.message)}</p>`;
    }
}

function setupKGControls() {
    const search = document.getElementById('kg-search');
    const checks = document.querySelectorAll('.kg-filter input[data-type]');
    const edgeChecks = document.querySelectorAll('.kg-edge-filters input[data-edge-type]');
    if (search) {
        search.addEventListener('input', () => {
            const q = search.value.trim().toLowerCase();
            if (!kgNetwork || !kgNodes) return;
            if (!q) {
                kgNodes.forEach(n => kgNodes.update({ id: n.id, color: { background: KG_TYPE_COLORS[n.type] || '#787890', border: KG_TYPE_COLORS[n.type] || '#787890', highlight: { background: '#ffffff', border: '#ffffff' } } }));
                kgNetwork.unselectAll();
                return;
            }
            const matches = new Set();
            kgNodes.forEach(n => {
                const hit = (n.label || '').toLowerCase().includes(q) || n.id.toLowerCase().includes(q);
                const color = hit ? { background: '#fbbf24', border: '#fbbf24', highlight: { background: '#ffffff', border: '#ffffff' } } : { background: 'rgba(120,120,144,0.15)', border: 'rgba(120,120,144,0.4)', highlight: { background: '#ffffff', border: '#ffffff' } };
                kgNodes.update({ id: n.id, color });
                if (hit) matches.add(n.id);
            });
            if (matches.size > 0 && kgNetwork) {
                kgNetwork.selectNodes([...matches]);
            }
        });
    }
    for (const c of checks) {
        c.addEventListener('change', applyKGNodeFilters);
    }
    for (const ec of edgeChecks) {
        ec.addEventListener('change', applyKGNodeFilters);
    }
}

function resetKGExplorer() {
    const search = document.getElementById('kg-search');
    if (search) search.value = '';
    if (kgNetwork && kgNodes) {
        kgNodes.forEach(n => {
            kgNodes.update({ id: n.id, color: { background: KG_TYPE_COLORS[n.type] || '#787890', border: KG_TYPE_COLORS[n.type] || '#787890', highlight: { background: '#ffffff', border: '#ffffff' } } });
        });
    }
    if (kgNetwork) kgNetwork.fit({ animation: true });
}

// ── Universal Condition Explorer ─────────────────────────────────────────

let conditionSearchTimer = null;
let activeConditionCurie = null;
let comparisonLeftControl = null;
let comparisonRightControl = null;

function setConditionExplorerBusy(isBusy) {
    const panel = document.getElementById('condition-explorer-panel');
    if (panel) panel.setAttribute('aria-busy', String(isBusy));
}

function renderUniversalClaimEvidence(evidence, directionLabel) {
    const url = evidence.source_url && /^https?:\/\//i.test(evidence.source_url) ? evidence.source_url : '';
    const citation = url
        ? `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(evidence.source_record_id || 'source')}</a>`
        : escapeHtml(evidence.source_record_id || 'source unavailable');
    return `<span class="condition-evidence-chip ${escapeHtml(directionLabel)}">${escapeHtml(directionLabel)}: ${citation}${evidence.evidence_type ? ` · ${escapeHtml(evidence.evidence_type)}` : ''}</span>`;
}

function renderConditionClaimRow(claim) {
    const supporting = (claim.supporting_evidence || []).map(item => renderUniversalClaimEvidence(item, 'supporting')).join('');
    const contradictory = (claim.contradictory_evidence || []).map(item => renderUniversalClaimEvidence(item, 'contradictory')).join('');
    const evidence = supporting || contradictory
        ? `${supporting}${contradictory}`
        : '<span class="condition-empty">No data imported for this section</span>';
    return `<div class="condition-claim">
        <strong>${escapeHtml(claim.predicate)} · ${escapeHtml(claim.object_label || claim.object_curie)}</strong>
        <small>${escapeHtml(claim.subject_curie)} → ${escapeHtml(claim.object_curie)}</small>
        <div>${evidence}</div>
    </div>`;
}

async function searchConditions(query) {
    const results = document.getElementById('condition-search-results');
    if (!results) return;
    const trimmed = (query || '').trim();
    if (!trimmed) {
        results.innerHTML = '<p class="condition-explorer-placeholder">Type to search imported conditions.</p>';
        return;
    }
    setConditionExplorerBusy(true);
    try {
        const data = await apiFetch(`/api/v1/conditions/search?q=${encodeURIComponent(trimmed)}&limit=20`);
        if (!data.items.length) {
            results.innerHTML = '<p class="condition-explorer-placeholder">No imported conditions matched this query.</p>';
            return;
        }
        results.innerHTML = data.items.map(item => `
            <button type="button" class="condition-result-item${item.curie === activeConditionCurie ? ' active' : ''}" data-condition-curie="${escapeHtml(item.curie)}">
                <strong>${escapeHtml(item.label)}</strong>
                <small>${escapeHtml(item.curie)}</small>
            </button>
        `).join('');
        results.querySelectorAll('[data-condition-curie]').forEach(button => {
            button.addEventListener('click', () => {
                void renderConditionExplorer(button.dataset.conditionCurie);
            });
        });
    } catch (error) {
        results.innerHTML = `<p class="condition-explorer-placeholder">Search unavailable: ${escapeHtml(error.message)}</p>`;
    } finally {
        setConditionExplorerBusy(false);
    }
}

async function renderConditionExplorer(curie) {
    const detail = document.getElementById('condition-explorer-detail');
    const depthSelect = document.getElementById('condition-hierarchy-depth');
    if (!detail || !curie) return;
    activeConditionCurie = curie;
    setConditionExplorerBusy(true);
    detail.innerHTML = '<p class="condition-explorer-placeholder"><span class="spinner"></span> Loading condition…</p>';
    const depth = Number(depthSelect?.value || 1);
    try {
        const [summary, hierarchy, claims] = await Promise.all([
            apiFetch(`/api/v1/conditions/${encodeURIComponent(curie)}`),
            apiFetch(`/api/v1/conditions/${encodeURIComponent(curie)}/hierarchy?depth=${depth}`),
            apiFetch(`/api/v1/conditions/${encodeURIComponent(curie)}/claims?limit=100`),
        ]);
        const synonymChips = (summary.synonyms || []).map(item => `<span class="condition-chip">${escapeHtml(item)}</span>`).join('') || '<span class="condition-empty">No data imported for this section</span>';
        const mappingChips = (summary.mappings || []).map(item => `<span class="condition-chip" title="${escapeHtml(item.relation)}">${escapeHtml(item.object_curie)}</span>`).join('') || '<span class="condition-empty">No data imported for this section</span>';
        const hierarchyRows = (hierarchy.nodes || []).filter(node => node.relation !== 'self').map(node => `<div class="condition-chip">${escapeHtml(node.relation)} · ${escapeHtml(node.label)} <small>${escapeHtml(node.curie)}</small></div>`).join('') || '<span class="condition-empty">No data imported for this section</span>';
        const snapshotRows = (summary.snapshots || []).map(item => `<div class="condition-chip">${escapeHtml(item.resource_name)}@${escapeHtml(item.version)}${item.active ? ' · active' : ''}</div>`).join('') || '<span class="condition-empty">No data imported for this section</span>';
        const grouped = {};
        (claims.items || []).forEach(claim => {
            grouped[claim.predicate] = grouped[claim.predicate] || [];
            grouped[claim.predicate].push(claim);
        });
        const claimGroups = Object.keys(grouped).length
            ? Object.entries(grouped).map(([predicate, rows]) => `<div class="condition-claim-group"><h4>${escapeHtml(predicate)}</h4>${rows.map(renderConditionClaimRow).join('')}</div>`).join('')
            : '<span class="condition-empty">No data imported for this section</span>';
        const readiness = summary.readiness || {};
        const readinessClass = readiness.ontology_present ? '' : ' partial';
        detail.innerHTML = `
            <div class="condition-detail-head">
                <h3>${escapeHtml(summary.label)}</h3>
                <p>${escapeHtml(summary.curie)}</p>
                <p>${summary.definition ? escapeHtml(summary.definition) : '<span class="condition-empty">No data imported for this section</span>'}</p>
                <p class="condition-explorer-disclaimer">${escapeHtml(summary.disclaimer?.text || 'For research use only.')}</p>
                <button type="button" class="btn btn-secondary btn-sm" data-action="compare-with-condition" data-condition-curie="${escapeHtml(summary.curie)}">Compare with…</button>
            </div>
            <div class="condition-readiness">
                <span class="${readinessClass}">${readiness.ontology_present ? 'Ontology imported' : 'Ontology missing'}</span>
                <span class="${readiness.legacy_curated ? '' : ' partial'}">${readiness.legacy_curated ? 'Legacy curated projection active' : 'Legacy projection optional'}</span>
                ${readiness.legacy_disease_id ? `<span>Legacy module: ${escapeHtml(readiness.legacy_disease_id)}</span>` : ''}
            </div>
            <div class="condition-section"><h4>Synonyms</h4><div class="condition-chip-list">${synonymChips}</div></div>
            <div class="condition-section"><h4>Mappings</h4><div class="condition-chip-list">${mappingChips}</div></div>
            <div class="condition-section"><h4>Hierarchy</h4>${hierarchyRows}</div>
            <div class="condition-section"><h4>Claims</h4>${claimGroups}</div>
            <div class="condition-section"><h4>Active snapshots</h4>${snapshotRows}</div>`;
        const searchInput = document.getElementById('condition-search-input');
        if (searchInput && searchInput.value.trim()) {
            void searchConditions(searchInput.value);
        }
    } catch (error) {
        detail.innerHTML = `<p class="condition-explorer-placeholder">Could not load condition: ${escapeHtml(error.message)}</p>`;
    } finally {
        setConditionExplorerBusy(false);
    }
}

function initConditionCurieTomSelect(selector) {
    if (typeof TomSelect === 'undefined') return null;
    const element = document.querySelector(selector);
    if (!element) return null;
    return new TomSelect(element, {
        valueField: 'curie',
        labelField: 'label',
        searchField: ['label', 'curie'],
        maxOptions: 20,
        create: false,
        placeholder: 'Search imported conditions…',
        load(query, callback) {
            const trimmed = (query || '').trim();
            if (trimmed.length < 2) return callback();
            apiFetch(`/api/v1/conditions/search?q=${encodeURIComponent(trimmed)}&limit=20`)
                .then(data => callback((data.items || []).map(item => ({
                    curie: item.curie,
                    label: item.label || item.curie,
                }))))
                .catch(() => callback());
        },
        render: {
            option(data, escape) {
                return `<div><strong>${escapeHtml(data.label)}</strong><br><small>${escapeHtml(data.curie)}</small></div>`;
            },
            item(data, escape) {
                return `<div>${escapeHtml(data.label || data.curie)}</div>`;
            },
        },
    });
}

function setComparisonCurie(side, curie, label) {
    const control = side === 'left' ? comparisonLeftControl : comparisonRightControl;
    if (!control || !curie) return;
    if (!control.options[curie]) {
        control.addOption({ curie, label: label || curie });
    }
    control.setValue(curie, true);
}

function openConditionComparison(leftCurie, rightCurie, leftLabel, rightLabel) {
    window.location.hash = 'condition-comparison';
    if (leftCurie) setComparisonCurie('left', leftCurie, leftLabel);
    if (rightCurie) setComparisonCurie('right', rightCurie, rightLabel);
}

async function loadBiomedImportStatus() {
    const panel = document.getElementById('biomed-import-status-panel');
    if (!panel) return;
    try {
        const data = await apiFetch('/api/v1/snapshots?limit=50');
        if (!data.items?.length) {
            panel.innerHTML = '<p class="condition-explorer-placeholder">No imported snapshots found. Run biomed import fixtures or full import.</p>';
            return;
        }
        const rows = data.items.map(item => `
            <tr>
                <td>${escapeHtml(item.resource_name)}</td>
                <td>${escapeHtml(item.version)}</td>
                <td><code>${escapeHtml(item.checksum || '—')}</code></td>
                <td>${item.active ? 'active' : 'inactive'}</td>
            </tr>`).join('');
        panel.innerHTML = `
            <table class="biomed-import-status-table">
                <thead><tr><th>Resource</th><th>Version</th><th>Checksum</th><th>Status</th></tr></thead>
                <tbody>${rows}</tbody>
            </table>`;
    } catch (error) {
        panel.innerHTML = `<p class="condition-explorer-placeholder">Import status unavailable: ${escapeHtml(error.message)}</p>`;
    }
}

function handleUniversalDeepLinks() {
    const params = new URLSearchParams(window.location.search);
    const curie = params.get('curie');
    const left = params.get('left');
    const right = params.get('right');
    if (curie) {
        window.location.hash = 'condition-explorer';
        void renderConditionExplorer(curie);
    }
    if (left || right) {
        openConditionComparison(left || '', right || '');
    }
}

function initConditionExplorer() {
    const searchInput = document.getElementById('condition-search-input');
    const depthSelect = document.getElementById('condition-hierarchy-depth');
    if (!searchInput) return;
    searchInput.addEventListener('input', () => {
        window.clearTimeout(conditionSearchTimer);
        conditionSearchTimer = window.setTimeout(() => {
            void searchConditions(searchInput.value);
        }, 250);
    });
    depthSelect?.addEventListener('change', () => {
        if (activeConditionCurie) void renderConditionExplorer(activeConditionCurie);
    });
}

function setConditionComparisonBusy(isBusy) {
    const panel = document.getElementById('condition-comparison-panel');
    if (panel) panel.setAttribute('aria-busy', String(isBusy));
}

function renderComparisonComponentBars(components, effectiveWeights) {
    const entries = Object.entries(components || {}).filter(([key, value]) => typeof value === 'number' && key !== 'negative_phenotype');
    if (!entries.length) return '<p class="condition-comparison-placeholder">No comparable component scores.</p>';
    return entries.map(([key, value]) => {
        const pct = Math.max(0, Math.min(100, Math.round(value * 100)));
        const weight = effectiveWeights?.[key];
        const weightLabel = typeof weight === 'number' ? ` · weight ${(weight * 100).toFixed(0)}%` : '';
        return `<div class="condition-comparison-bar-row">
            <span>${escapeHtml(key)}${escapeHtml(weightLabel)}</span>
            <div class="condition-comparison-bar"><span style="width:${pct}%"></span></div>
            <span>${pct}%</span>
        </div>`;
    }).join('');
}

function renderComparisonEntityLists(sharedEntities, distinguishingEntities) {
    const shared = Object.entries(sharedEntities || {}).map(([dimension, items]) => {
        if (!items?.length) return '';
        return `<div><strong>Shared ${escapeHtml(dimension)}</strong><div class="condition-chip-list">${items.map(item => `<span class="condition-chip">${escapeHtml(item)}</span>`).join('')}</div></div>`;
    }).join('');
    const distinguishing = Object.entries(distinguishingEntities || {}).map(([dimension, sides]) => {
        const leftOnly = sides?.left_only || [];
        const rightOnly = sides?.right_only || [];
        if (!leftOnly.length && !rightOnly.length) return '';
        return `<div><strong>Distinguishing ${escapeHtml(dimension)}</strong>
            ${leftOnly.length ? `<div>Left only: ${leftOnly.map(item => `<span class="condition-chip">${escapeHtml(item)}</span>`).join('')}</div>` : ''}
            ${rightOnly.length ? `<div>Right only: ${rightOnly.map(item => `<span class="condition-chip">${escapeHtml(item)}</span>`).join('')}</div>` : ''}
        </div>`;
    }).join('');
    if (!shared && !distinguishing) {
        return '<p class="condition-comparison-placeholder">No shared or distinguishing entities reported.</p>';
    }
    return `<div class="condition-comparison-entities">${shared}${distinguishing}</div>`;
}

function renderComparisonResult(result) {
    const container = document.getElementById('condition-comparison-result');
    if (!container || !result) return;
    const disclaimer = escapeHtml(result.disclaimer?.text || 'For research and exploratory analysis only.');
    if (result.status === 'insufficient_data') {
        const missing = (result.coverage?.missing_dimensions || []).join(', ') || 'required dimensions';
        container.innerHTML = `
            <p class="condition-comparison-score">Insufficient comparable data</p>
            <p class="condition-comparison-placeholder">This comparison could not produce a numeric overall score. Missing or non-overlapping dimensions: ${escapeHtml(missing)}.</p>
            <p class="condition-comparison-meta">run_id: ${escapeHtml(result.run_id)}</p>
            <p class="condition-comparison-disclaimer">${disclaimer}</p>`;
        return;
    }
    const overall = typeof result.overall_score === 'number' ? `${Math.round(result.overall_score * 100)}% condition similarity` : 'No overall score';
    const coverage = result.coverage || {};
    const coverageBadges = (coverage.comparable_dimensions || []).map(item => `<span class="condition-chip">${escapeHtml(item)} comparable</span>`).join('');
    container.innerHTML = `
        <p class="condition-comparison-score">${escapeHtml(overall)}</p>
        <p class="condition-comparison-meta">${escapeHtml(result.left_curie)} vs ${escapeHtml(result.right_curie)} · algorithm ${escapeHtml(result.algorithm_id)} v${escapeHtml(result.algorithm_version)}</p>
        <div class="condition-chip-list">${coverageBadges}</div>
        ${renderComparisonComponentBars(result.components, result.effective_weights)}
        ${renderComparisonEntityLists(result.shared_entities, result.distinguishing_entities)}
        <p class="condition-comparison-meta">run_id: <a href="#condition-comparison">${escapeHtml(result.run_id)}</a> · snapshots: ${(result.snapshot_ids || []).map(item => escapeHtml(item)).join(', ') || 'none'}</p>
        <p class="condition-comparison-disclaimer">${disclaimer}</p>`;
}

async function compareConditions() {
    const leftInput = document.getElementById('comparison-left-curie');
    const rightInput = document.getElementById('comparison-right-curie');
    const container = document.getElementById('condition-comparison-result');
    if (!leftInput || !rightInput || !container) return;
    const left = comparisonLeftControl?.getValue() || leftInput.value.trim();
    const right = comparisonRightControl?.getValue() || rightInput.value.trim();
    if (!left || !right) {
        container.innerHTML = '<p class="condition-comparison-placeholder">Enter both condition CURIEs before comparing.</p>';
        return;
    }
    setConditionComparisonBusy(true);
    container.innerHTML = '<p class="condition-comparison-placeholder"><span class="spinner"></span> Running comparison…</p>';
    try {
        const result = await apiFetch('/api/v1/comparisons', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ left_curie: left, right_curie: right }),
        });
        renderComparisonResult(result);
    } catch (error) {
        container.innerHTML = `<p class="condition-comparison-placeholder">Comparison failed: ${escapeHtml(error.message)}</p>`;
    } finally {
        setConditionComparisonBusy(false);
    }
}

function initConditionComparison() {
    const button = document.getElementById('comparison-run-btn');
    const leftInput = document.getElementById('comparison-left-curie');
    const rightInput = document.getElementById('comparison-right-curie');
    if (!button || !leftInput || !rightInput) return;
    comparisonLeftControl = initConditionCurieTomSelect('#comparison-left-curie');
    comparisonRightControl = initConditionCurieTomSelect('#comparison-right-curie');
    button.addEventListener('click', () => { void compareConditions(); });
    [leftInput, rightInput].forEach(input => {
        input.addEventListener('keydown', event => {
            if (event.key === 'Enter') {
                event.preventDefault();
                void compareConditions();
            }
        });
    });
}

async function fetchGraphPathways() {
    const startInput = document.getElementById('path-start-curie');
    const targetInput = document.getElementById('path-target-curie');
    const depthSelect = document.getElementById('path-max-depth');
    const container = document.getElementById('pathways-result');
    if (!startInput || !targetInput || !container) return;

    const start = startInput.value.trim();
    const target = targetInput.value.trim();
    const depth = parseInt(depthSelect?.value || '3', 10);

    if (!start || !target) {
        container.innerHTML = '<p class="condition-comparison-placeholder">Please enter both start and target CURIEs.</p>';
        return;
    }

    container.innerHTML = '<p class="condition-comparison-placeholder"><span class="spinner"></span> Finding shortest claim pathways…</p>';
    try {
        const query = new URLSearchParams({ start_curie: start, target_curie: target, max_depth: String(depth), limit: '10' });
        const res = await apiFetch(`/api/v1/biomed/pathways?${query.toString()}`);
        renderGraphPathways(res);
    } catch (err) {
        container.innerHTML = `<p class="condition-comparison-placeholder">Error loading pathways: ${escapeHtml(err.message)}</p>`;
    }
}

function renderGraphPathways(res) {
    const container = document.getElementById('pathways-result');
    if (!container) return;

    if (!res || !res.paths || !res.paths.length) {
        container.innerHTML = `<p class="condition-comparison-placeholder">No claim pathways found between ${escapeHtml(res.start_curie || '')} and ${escapeHtml(res.target_curie || '')} within depth ${res.max_depth || 3}.</p>`;
        return;
    }

    const html = res.paths.map((p, idx) => {
        const nodeChips = (p.nodes || []).map((n, i) => {
            const pred = p.predicates && p.predicates[i] ? `<span class="condition-chip" style="background:rgba(99,102,241,0.15);color:#818cf8;margin:0 4px;">${escapeHtml(p.predicates[i])}</span>` : '';
            return `<span class="condition-chip" style="background:rgba(255,255,255,0.06);color:#fff;">${escapeHtml(n)}</span>${pred}`;
        }).join('');
        return `
            <div style="margin-bottom:12px;padding:12px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:8px;">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                    <span style="font-weight:600;font-size:0.85rem;color:var(--text-muted,#787890);">Path #${idx + 1} (${p.nodes ? p.nodes.length - 1 : 0} hops)</span>
                    <span class="hero-badge research" style="font-size:0.75rem;">Score: ${typeof p.score === 'number' ? p.score.toFixed(2) : '1.0'}</span>
                </div>
                <div style="display:flex;align-items:center;flex-wrap:wrap;gap:4px;">${nodeChips}</div>
            </div>
        `;
    }).join('');

    container.innerHTML = `
        <div style="margin-bottom:8px;font-size:0.85rem;color:var(--text-muted,#787890);">Found ${res.total_paths} canonical path(s) from <strong>${escapeHtml(res.start_curie)}</strong> to <strong>${escapeHtml(res.target_curie)}</strong></div>
        ${html}
    `;
}

async function fetchTargetPrioritization() {
    const diseaseInput = document.getElementById('target-rank-disease');
    const topKSelect = document.getElementById('target-rank-top-k');
    const container = document.getElementById('target-rank-result');
    if (!diseaseInput || !container) return;

    const disease = diseaseInput.value.trim();
    const topK = parseInt(topKSelect?.value || '10', 10);

    if (!disease) {
        container.innerHTML = '<p class="condition-comparison-placeholder">Please enter a disease CURIE.</p>';
        return;
    }

    container.innerHTML = '<p class="condition-comparison-placeholder"><span class="spinner"></span> Ranking disease targets…</p>';
    try {
        const query = new URLSearchParams({ top_k: String(topK) });
        const res = await apiFetch(`/api/v1/biomed/target-prioritization/${encodeURIComponent(disease)}?${query.toString()}`);
        renderTargetPrioritization(res);
    } catch (err) {
        container.innerHTML = `<p class="condition-comparison-placeholder">Error ranking targets: ${escapeHtml(err.message)}</p>`;
    }
}

function renderTargetPrioritization(res) {
    const container = document.getElementById('target-rank-result');
    if (!container) return;

    if (!res || !res.rankings || !res.rankings.length) {
        container.innerHTML = `<p class="condition-comparison-placeholder">No target rankings found for ${escapeHtml(res.disease_curie || '')}. Ensure claims exist in the canonical store.</p>`;
        return;
    }

    const rows = res.rankings.map((r, idx) => {
        const vulnPct = Math.max(0, Math.min(100, Math.round((r.vulnerability_score || 0) * 100)));
        return `
            <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
                <td style="padding:8px 12px;font-weight:600;">#${idx + 1}</td>
                <td style="padding:8px 12px;">
                    <div><strong>${escapeHtml(r.target_label || r.target_curie)}</strong></div>
                    <small style="color:var(--text-muted,#787890);">${escapeHtml(r.target_curie)}</small>
                </td>
                <td style="padding:8px 12px;color:#4ade80;">+${r.supporting_evidence || 0}</td>
                <td style="padding:8px 12px;color:#f87171;">-${r.contradictory_evidence || 0}</td>
                <td style="padding:8px 12px;">${typeof r.centrality_score === 'number' ? r.centrality_score.toFixed(3) : '0.000'}</td>
                <td style="padding:8px 12px;">
                    <div style="display:flex;align-items:center;gap:8px;">
                        <div class="condition-comparison-bar" style="flex:1;max-width:120px;"><span style="width:${vulnPct}%"></span></div>
                        <span style="font-weight:600;font-size:0.85rem;">${vulnPct}%</span>
                    </div>
                </td>
            </tr>
        `;
    }).join('');

    container.innerHTML = `
        <div style="margin-bottom:8px;font-size:0.85rem;color:var(--text-muted,#787890);">Target rankings for <strong>${escapeHtml(res.disease_curie)}</strong> (${res.total_targets} total ranked)</div>
        <div style="overflow-x:auto;">
            <table style="width:100%;border-collapse:collapse;text-align:left;font-size:0.9rem;">
                <thead>
                    <tr style="border-bottom:1px solid rgba(255,255,255,0.1);color:var(--text-muted,#787890);">
                        <th style="padding:8px 12px;">Rank</th>
                        <th style="padding:8px 12px;">Target</th>
                        <th style="padding:8px 12px;">Supp. Evidence</th>
                        <th style="padding:8px 12px;">Contra. Evidence</th>
                        <th style="padding:8px 12px;">Centrality</th>
                        <th style="padding:8px 12px;">Vulnerability Score</th>
                    </tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>
        </div>
    `;
}

function initGraphAnalytics() {
    const pathwaysBtn = document.getElementById('pathways-run-btn');
    const targetRankBtn = document.getElementById('target-rank-run-btn');

    if (pathwaysBtn) {
        pathwaysBtn.addEventListener('click', () => { void fetchGraphPathways(); });
    }
    if (targetRankBtn) {
        targetRankBtn.addEventListener('click', () => { void fetchTargetPrioritization(); });
    }
}

async function showKGNodeDetail(nodeId) {
    const panel = document.getElementById('kg-detail');
    if (!panel) return;
    const disease = getActiveDisease();
    try {
        const d = await apiFetch(`/api/kg/node/${encodeURIComponent(nodeId)}?disease=${encodeURIComponent(disease)}`);
        renderKGDetail(panel, d);
    } catch (e) {
        panel.innerHTML = `<strong style="color:#f87171;font-size:0.8rem;">⚠️ ${e.message}</strong>`;
    }
}

function renderKGDetail(panel, d) {
    const type = d.type || 'unknown';
    const color = KG_TYPE_COLORS[type] || '#787890';
    const typeLabel = type.charAt(0).toUpperCase() + type.slice(1);

    const fields = [];
    for (const key of ['category', 'function', 'description', 'odds_ratio', 'mechanism', 'chromosome', 'prevalence', 'disease_id']) {
        if (d[key] != null && d[key] !== '') {
            fields.push(`<div class="kg-field"><div class="kg-field-label">${key.replace(/_/g, ' ')}</div><div class="kg-field-value">${escapeHtml(d[key])}</div></div>`);
        }
    }

    const incoming = (d.incoming || []).slice(0, 12).map(e =>
        `<div class="kg-rel"><span class="rel-type">${e.type || 'link'}</span> ← <strong>${escapeHtml(e.source)}</strong><div class="rel-desc">${escapeHtml(e.description || '')}</div></div>`).join('');
    const outgoing = (d.outgoing || []).slice(0, 12).map(e =>
        `<div class="kg-rel"><span class="rel-type">${e.type || 'link'}</span> → <strong>${escapeHtml(e.target)}</strong><div class="rel-desc">${escapeHtml(e.description || '')}</div></div>`).join('');

    panel.innerHTML = `
        <h4>${escapeHtml(d.label || d.id)}</h4>
        <span class="kg-node-type" style="background:${color}22;color:${color};">${typeLabel}</span>
        <div class="kg-field"><div class="kg-field-label">Node ID</div><div class="kg-field-value"><code style="font-size:0.72rem;">${escapeHtml(d.id)}</code></div></div>
        ${fields.join('')}
        ${incoming ? `<div class="kg-section"><h5>⬅ Incoming (${d.incoming.length})</h5>${incoming}</div>` : ''}
        ${outgoing ? `<div class="kg-section"><h5>➡ Outgoing (${d.outgoing.length})</h5>${outgoing}</div>` : ''}
        <button type="button" class="btn btn-primary btn-sm" style="margin-top:14px;width:100%;" data-action="kg-expand-neighbors" data-node-id="${escapeHtml(d.id)}">🔍 Expand 2-Hop Subgraph</button>
    `;
}

function clearKGDetail() {
    const panel = document.getElementById('kg-detail');
    if (!panel) return;
    panel.innerHTML = `
        <div class="kg-detail-placeholder">
            <div style="font-size:2rem;margin-bottom:8px;">🕸️</div>
            <p>Select a node to inspect its drugs, pathways, and connections.</p>
        </div>`;
}

function updateKGStats() {
    const bar = document.getElementById('kg-stats-bar');
    if (!bar || !kgRawElements) return;
    const nodes = new Set();
    const edges = [];
    const types = {};
    for (const el of kgRawElements) {
        const d = el.data || {};
        const hasSrc = d.from !== undefined || d.source !== undefined;
        const hasDst = d.to !== undefined || d.target !== undefined;
        if (hasSrc && hasDst) {
            edges.push(d);
        } else if (d.id !== undefined) {
            nodes.add(d.id);
            const t = d.type || 'unknown';
            types[t] = (types[t] || 0) + 1;
        }
    }
    bar.innerHTML = `
        <span><b>${nodes.size}</b> nodes</span>
        <span><b>${edges.length}</b> relationships</span>
        <span><b>${types.gene || 0}</b> genes</span>
        <span><b>${types.drug || 0}</b> drugs</span>
        <span><b>${types.pathway || 0}</b> pathways</span>
        <span style="margin-left:auto;">disease: <b style="text-transform:uppercase;">${escapeHtml(getActiveDisease())}</b></span>
    `;
}

// ── Data Export ───────────────────────────────────────────────────────────

const EXPORT_MODULES = [
    ['repurpose', '💊 Drug Repurposing'],
    ['cart', '🔬 CAR-T Scores'],
    ['biomarker', '🧬 Biomarkers'],
    ['trials', '📋 Clinical Trials'],
    ['cross-disease', '🌐 Cross-Disease'],
    ['synergy', '🔗 Drug Synergy'],
    ['safety', '🛡️ Safety Scores'],
    ['expression', '🧬 Expression'],
    ['ml', '🧠 ML Predictions'],
    ['screening', '🔬 Screening'],
    ['network', '🌐 Network'],
    ['literature', '📚 Literature'],
];

async function loadExportGrid() {
    const grid = document.getElementById('export-grid');
    if (!grid) return;
    let items = EXPORT_MODULES;
    try {
        const info = await apiFetch('/api/export/modules');
        if (info && info.modules) {
            const avail = new Set(info.modules.filter(m => m.available).map(m => m.module));
            items = items.map(([mod, label]) => [mod, label, avail.has(mod)]);
        }
    } catch {
        items = items.map(([mod, label]) => [mod, label, true]);
    }

    grid.innerHTML = items.map(([mod, label, available]) => `
        <div class="export-item ${available ? '' : 'unavailable'}" title="${available ? `Export ${label}` : 'Run this module first to generate results'}">
            <span class="export-label">${label}</span>
            <div class="export-actions">
                <a href="/api/export/json/${mod}" class="btn btn-secondary btn-sm">⬇ JSON</a>
                <a href="/api/export/report/${mod}" class="btn btn-secondary btn-sm" target="_blank">📄 HTML</a>
            </div>
        </div>`).join('');
}

// ── Modal + Toast UI ───────────────────────────────────────────────────

function showToast(message, type = 'success') {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'toast-container';
        document.body.appendChild(container);
    }
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = escapeHtml(message);
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(6px)';
        setTimeout(() => toast.remove(), 250);
    }, 4200);
}

/** Promise-based confirm modal. Resolves `true` on confirm, `false` on cancel/✕/Esc/backdrop. */
function openModal({ title, body, confirmText = 'Confirm', cancelText = 'Cancel', danger = false }) {
    return new Promise(resolve => {
        const previouslyFocused = document.activeElement;
        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay';
        overlay.innerHTML = `
            <div class="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title">
                <div class="modal-header">
                    <span class="modal-title" id="modal-title">${escapeHtml(title)}</span>
                    <button type="button" class="modal-close" aria-label="Close">✕</button>
                </div>
                <div class="modal-body">${body}</div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary modal-cancel">${escapeHtml(cancelText)}</button>
                    <button type="button" class="btn ${danger ? 'btn-danger' : 'btn-primary'} modal-confirm">${escapeHtml(confirmText)}</button>
                </div>
            </div>`;
        document.body.appendChild(overlay);

        const modal = overlay.querySelector('.modal');
        const focusables = () => [...overlay.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])')]
            .filter(el => !el.disabled && el.offsetParent !== null);

        const close = (value) => {
            document.removeEventListener('keydown', onKey);
            overlay.remove();
            if (previouslyFocused && previouslyFocused.focus) previouslyFocused.focus();
            resolve(value);
        };
        const onKey = (e) => {
            if (e.key === 'Escape') { close(false); return; }
            if (e.key === 'Tab') {
                const els = focusables();
                if (!els.length) { e.preventDefault(); return; }
                const first = els[0];
                const last = els[els.length - 1];
                if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
                else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
            }
        };
        overlay.querySelector('.modal-close').addEventListener('click', () => close(false));
        overlay.querySelector('.modal-cancel').addEventListener('click', () => close(false));
        overlay.querySelector('.modal-confirm').addEventListener('click', () => close(true));
        overlay.addEventListener('mousedown', (e) => { if (e.target === overlay) close(false); });
        document.addEventListener('keydown', onKey);
        (overlay.querySelector('.modal-confirm') || modal).focus();
    });
}

function formatBytes(bytes) {
    if (bytes == null) return '—';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} kB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// ── Disease Module Manager ─────────────────────────────────────────────

// Filenames of the currently rendered backups (restore buttons reference by index)
let manageBackupNames = [];
// In-flight guard so double-clicking Restore can't stack preview modals
let manageBusy = false;

function manageSection() {
    let section = document.getElementById('disease-manager');
    if (!section) {
        section = document.createElement('div');
        section.id = 'disease-manager';
        section.className = 'cd-card manage-panel';
        const grid = document.getElementById('modules-grid');
        grid.parentElement.insertBefore(section, grid.nextSibling);
    }
    return section;
}

async function openDiseaseManager() {
    const section = manageSection();
    const info = activeDiseaseInfo();
    section.innerHTML = `
        <div class="manage-header">
            <h3>🛠️ Manage Disease Module — <span id="manage-disease-name">${escapeHtml(info.name)}</span></h3>
            <button type="button" class="btn btn-secondary btn-sm" data-action="disease-manager-close">✕ Close</button>
        </div>
        <div class="manage-summary" id="manage-summary"><span class="spinner"></span> Loading module…</div>
        <div class="manage-body">
            <div class="manage-block">
                <h4>🔄 Refresh &amp; Prune</h4>
                <p class="manage-hint">
                    Re-pull genes/drugs/pathways from GWAS Catalog, Open Targets, and Reactome, then drop
                    entities no source reported. A preview is always shown first — nothing is written until
                    you confirm, and every removed entity is backed up for restore.
                </p>
                <div class="manage-options">
                    <label class="manage-opt"><input type="checkbox" id="mng-skip-gwas"> Skip GWAS</label>
                    <label class="manage-opt"><input type="checkbox" id="mng-skip-ot"> Skip Open Targets</label>
                    <label class="manage-opt"><input type="checkbox" id="mng-skip-reactome"> Skip Reactome</label>
                    <label class="manage-opt"><input type="checkbox" id="mng-no-cache"> Bypass cache</label>
                </div>
                <div class="manage-actions">
                    <button type="button" class="btn btn-primary" id="mng-prune-btn" data-action="disease-manager-prune">▶ Run Refresh &amp; Prune Preview</button>
                </div>
                <div class="manage-result" id="mng-prune-result"></div>
            </div>
            <div class="manage-block">
                <h4>🗂️ Backup History</h4>
                <p class="manage-hint">Prunes are snapshotted to <code>data/backups/</code>. Restore re-merges a backup verbatim — curated fields intact.</p>
                <div id="mng-backups"><span class="spinner"></span> Loading backups…</div>
            </div>
            <div class="manage-block manage-block-full">
                <h4>📜 Activity Log</h4>
                <p class="manage-hint">Every prune and restore is recorded server-side to <code>data/audit_log.jsonl</code> — timestamp, entities removed/restored, and the backup involved — so module changes are fully traceable.</p>
                <div class="audit-list" id="mng-audit"><span class="spinner"></span> Loading activity…</div>
            </div>
        </div>`;
    section.scrollIntoView({ behavior: 'smooth', block: 'start' });
    loadManageSummary();
    loadManageBackups();
    loadManageAudit();
}

function closeDiseaseManager() {
    const section = document.getElementById('disease-manager');
    if (section) section.remove();
}

async function loadManageSummary() {
    const el = document.getElementById('manage-summary');
    if (!el) return;
    const id = getActiveDisease();
    try {
        const [backups, registry] = await Promise.all([
            apiFetch(`/api/admin/diseases/${encodeURIComponent(id)}/backups`),
            apiFetch('/api/system/diseases'),
        ]);
        const entry = (registry.diseases || []).find(d => d.id === id) || {};
        el.innerHTML = `
            <div class="manage-chip">🧬 <b>${entry.genes ?? '…'}</b> genes</div>
            <div class="manage-chip">💊 <b>${entry.drugs ?? '…'}</b> drugs</div>
            <div class="manage-chip">🗺️ <b>${entry.pathways ?? '…'}</b> pathways</div>
            <div class="manage-chip">🗂️ <b>${backups.count ?? 0}</b> backup${backups.count === 1 ? '' : 's'}</div>`;
    } catch (e) {
        el.innerHTML = `<span class="manage-err">⚠️ ${escapeHtml(e.message)}</span>`;
    }
}

async function loadManageBackups() {
    const el = document.getElementById('mng-backups');
    if (!el) return;
    const id = getActiveDisease();
    manageBackupNames = [];
    try {
        const data = await apiFetch(`/api/admin/diseases/${encodeURIComponent(id)}/backups`);
        if (!data.backups || data.backups.length === 0) {
            el.innerHTML = '<div class="manage-empty">No backups yet — running a prune writes the first one here.</div>';
            return;
        }
        el.innerHTML = data.backups.map((b, i) => {
            const filename = b.path.split(/[\\/]/).pop();
            manageBackupNames.push(filename);
            return `
            <div class="backup-row">
                <div class="backup-info">
                    <div class="backup-name">${escapeHtml(filename)}</div>
                    <div class="backup-meta">${formatBytes(b.size_bytes)} · ${escapeHtml(b.modified || '')}</div>
                    <div class="backup-contents">
                        ${(b.genes || []).length ? `<span class="tag blue">${b.genes.length} gene${b.genes.length === 1 ? '' : 's'}</span>` : ''}
                        ${(b.drugs || []).length ? `<span class="tag pink">${b.drugs.length} drug${b.drugs.length === 1 ? '' : 's'}</span>` : ''}
                        ${b.readable === false ? '<span class="tag yellow">unreadable</span>' : ''}
                    </div>
                </div>
                <button type="button" class="btn btn-secondary btn-sm" data-action="disease-manager-restore" data-backup-index="${i}" ${b.readable === false ? 'disabled' : ''}>↩ Restore</button>
            </div>`;
        }).join('');
    } catch (e) {
        el.innerHTML = `<span class="manage-err">⚠️ ${escapeHtml(e.message)}</span>`;
    }
}

async function loadManageAudit() {
    const el = document.getElementById('mng-audit');
    if (!el) return;
    const id = getActiveDisease();
    try {
        const data = await apiFetch(`/api/admin/diseases/${encodeURIComponent(id)}/audit?limit=20`);
        const entries = data.entries || [];
        if (entries.length === 0) {
            el.innerHTML = '<div class="manage-empty">No activity yet — prune and restore actions are recorded here.</div>';
            return;
        }
        el.innerHTML = entries.map(a => {
            const isPrune = a.action === 'prune';
            const removed = a.removed || {};
            const restored = a.restored || {};
            const genes = isPrune ? (removed.genes || []) : (restored.genes || []);
            const drugs = isPrune ? (removed.drugs || []) : (restored.drugs || []);
            const skipped = a.skipped || {};
            const nSkipped = (skipped.genes || []).length + (skipped.drugs || []).length;
            const backupFile = (a.backup || '').split(/[\\/]/).pop();
            const verb = isPrune ? 'Removed' : 'Restored';
            const summary = `${verb} ${genes.length} gene${genes.length === 1 ? '' : 's'}, ${drugs.length} drug${drugs.length === 1 ? '' : 's'}`;
            return `
            <div class="audit-row">
                <span class="audit-badge ${isPrune ? 'prune' : 'restore'}">${isPrune ? 'PRUNE' : 'RESTORE'}</span>
                <div class="audit-info">
                    <div class="audit-line">${escapeHtml(summary)}${nSkipped ? ` <span class="manage-sub">· ${nSkipped} skipped</span>` : ''}</div>
                    ${backupFile ? `<div class="audit-meta" title="${escapeHtml(a.backup)}">${escapeHtml(backupFile)}</div>` : ''}
                </div>
                <span class="audit-ts">${escapeHtml(formatAuditTime(a.ts))}</span>
            </div>`;
        }).join('') +
        (data.count > entries.length ? `<div class="manage-sub">Showing the last ${entries.length} of ${data.count} recorded actions.</div>` : '');
    } catch (e) {
        el.innerHTML = `<span class="manage-err">⚠️ ${escapeHtml(e.message)}</span>`;
    }
}

function formatAuditTime(ts) {
    if (!ts) return '';
    const d = new Date(ts);
    if (isNaN(d.getTime())) return ts;
    return d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function refreshManage() {
    loadManageSummary();
    loadManageBackups();
    loadManageAudit();
    loadPlatformStats();
}

// ── Prune flow (preview → confirm modal → apply) ────────────────────────

async function runPrunePreview() {
    const btn = document.getElementById('mng-prune-btn');
    const resultEl = document.getElementById('mng-prune-result');
    if (!btn || !resultEl) return;

    btn.disabled = true;
    resultEl.className = 'manage-result visible';
    resultEl.innerHTML = '<span class="spinner"></span> Fetching sources (GWAS · Open Targets · Reactome) and computing merge + prune candidates… this can take a minute.';

    const id = getActiveDisease();
    const req = {
        apply: false,
        skip_gwas: document.getElementById('mng-skip-gwas').checked,
        skip_opentargets: document.getElementById('mng-skip-ot').checked,
        skip_reactome: document.getElementById('mng-skip-reactome').checked,
        no_cache: document.getElementById('mng-no-cache').checked,
    };

    let preview;
    try {
        preview = await apiFetch(`/api/admin/diseases/${encodeURIComponent(id)}/prune`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(req),
        });
    } catch (e) {
        resultEl.className = 'manage-result visible error';
        resultEl.innerHTML = `<strong>Preview failed:</strong> ${escapeHtml(e.message)}`;
        btn.disabled = false;
        return;
    }

    const merge = preview.merge || {};
    const prune = preview.prune || {};
    const pruneGenes = prune.genes || [];
    const pruneDrugs = prune.drugs || [];
    const totalPrune = pruneGenes.length + pruneDrugs.length;

    const mergeLines = ['genes', 'drugs', 'pathways'].map(kind => {
        const m = merge[kind] || {};
        return `${kind}: <b>+${(m.added || []).length}</b> added, <b>~${(m.updated || []).length}</b> updated, <b>${(m.kept || []).length}</b> unchanged`;
    }).join('<br>');

    if (totalPrune === 0) {
        resultEl.className = 'manage-result visible success';
        resultEl.innerHTML = `<strong>✅ Nothing to prune.</strong> Every existing entity was re-reported by at least one source.<br><span class="manage-sub">${mergeLines}</span>`;
        return;
    }

    const sourceChips = Object.entries(preview.sources || {})
        .map(([s, ok]) => `${ok ? '✅' : '⚠️'} ${escapeHtml(s)}`).join(' ');
    const pruneChips = [
        ...pruneGenes.map(g => `<span class="candidate-chip gene">${escapeHtml(g)}</span>`),
        ...pruneDrugs.map(d => `<span class="candidate-chip drug">${escapeHtml(d)}</span>`),
    ].join(' ');

    const body = `
        <p class="modal-note"><b>Sources:</b> ${sourceChips || '—'}</p>
        <p class="modal-note"><b>Merge (refresh):</b><br>${mergeLines}</p>
        <p class="modal-note warn">⚠️ <b>${pruneGenes.length} gene${pruneGenes.length === 1 ? '' : 's'} and ${pruneDrugs.length} drug${pruneDrugs.length === 1 ? '' : 's'} would be removed</b> — no source reported them on this run. Every removed entity is backed up to <code>data/backups/</code> and can be restored verbatim later.</p>
        <div class="candidate-list">${pruneChips}</div>`;

    const confirmed = await openModal({
        title: '⚠️ Refresh & Prune Preview',
        body,
        confirmText: `Apply Prune (${totalPrune})`,
        cancelText: 'Cancel',
        danger: true,
    });
    btn.disabled = false;
    if (!confirmed) {
        resultEl.className = 'manage-result visible neutral';
        resultEl.innerHTML = '<span class="manage-sub">Preview complete — nothing was written. Re-run preview to re-evaluate.</span>';
        return;
    }

    resultEl.className = 'manage-result visible';
    resultEl.innerHTML = '<span class="spinner"></span> Applying refresh + prune…';
    try {
        const res = await apiFetch(`/api/admin/diseases/${encodeURIComponent(id)}/prune`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ...req, apply: true }),
        });
        const p = res.prune || {};
        resultEl.className = 'manage-result visible success';
        resultEl.innerHTML = `
            <strong>✅ Prune applied.</strong> Removed ${p.genes?.length || 0} gene(s) and ${p.drugs?.length || 0} drug(s).
            ${p.backup ? `<br><span class="manage-sub">Backup: <code>${escapeHtml(p.backup)}</code></span>` : ''}`;
        showToast(`Prune complete — ${p.genes?.length || 0} gene(s), ${p.drugs?.length || 0} drug(s) removed and backed up.`);
        refreshManage();
    } catch (e) {
        resultEl.className = 'manage-result visible error';
        resultEl.innerHTML = `<strong>Apply failed:</strong> ${escapeHtml(e.message)}`;
        showToast(e.message, 'error');
    }
}

// ── Restore flow (preview → confirm modal → apply) ─────────────────────

async function previewRestore(index) {
    if (manageBusy) return;
    manageBusy = true;
    const restoreBtns = [...document.querySelectorAll('.backup-row .btn')];
    restoreBtns.forEach(b => { b.disabled = true; });
    const filename = manageBackupNames[index];
    const id = getActiveDisease();
    const body = { backup: filename, apply: false };

    let preview;
    try {
        if (!filename) throw new Error('No backup selected');
        preview = await apiFetch(`/api/admin/diseases/${encodeURIComponent(id)}/restore`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
    } catch (e) {
        showToast(e.message, 'error');
        restoreBtns.forEach(b => { b.disabled = false; });
        manageBusy = false;
        return;
    }

    const restored = preview.restored || {};
    const skipped = preview.skipped || {};
    const nGenes = (restored.genes || []).length;
    const nDrugs = (restored.drugs || []).length;
    const nSkipped = (skipped.genes || []).length + (skipped.drugs || []).length;
    const pathways = preview.updated_pathways || [];

    const bodyHtml = `
        <p class="modal-note">Backup: <code>${escapeHtml(filename)}</code></p>
        <p class="modal-note"><b>${nGenes} gene${nGenes === 1 ? '' : 's'}, ${nDrugs} drug${nDrugs === 1 ? '' : 's'}</b> would be restored verbatim (curated fields intact); <b>${nSkipped}</b> already present and skipped.</p>
        ${pathways.length ? `<p class="modal-note">🔗 Re-attached to ${pathways.length} pathway(s): <span class="manage-sub">${pathways.slice(0, 10).map(escapeHtml).join(', ')}</span></p>` : ''}
        ${nGenes ? `<div class="candidate-list">${(restored.genes || []).map(g => `<span class="candidate-chip gene">${escapeHtml(g)}</span>`).join(' ')}</div>` : ''}`;

    const confirmed = await openModal({
        title: '↩ Restore from backup',
        body: bodyHtml,
        confirmText: 'Restore',
        cancelText: 'Cancel',
        danger: true,
    });
    if (!confirmed) return;

    try {
        const res = await apiFetch(`/api/admin/diseases/${encodeURIComponent(id)}/restore`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ backup: filename, apply: true }),
        });
        const r = res.restored || {};
        showToast(`Restored ${(r.genes || []).length} gene(s) and ${(r.drugs || []).length} drug(s) to ${activeDiseaseInfo().label}.`);
        refreshManage();
    } catch (e) {
        showToast(e.message, 'error');
    } finally {
        restoreBtns.forEach(b => { b.disabled = false; });
        manageBusy = false;
    }
}

// ── Init ─────────────────────────────────────────────────────────────────

async function checkAPIStatus() {
    const indicator = document.getElementById('api-status');
    const statApi = document.getElementById('stat-api-status');
    try {
        const health = await apiFetch('/api/health');
        if (indicator) {
            indicator.textContent = '●';
            indicator.className = 'nav-link nav-status online';
            indicator.title = 'API Connected';
        }
        if (statApi) {
            statApi.textContent = 'Online';
            statApi.className = 'stat-value stat-color-green';
        }
        const badge = document.getElementById('api-badge');
        if (badge && health.version) badge.textContent = `⚡ API v${health.version}`;
        return health;
    } catch {
        if (indicator) {
            indicator.textContent = '●';
            indicator.className = 'nav-link nav-status offline';
            indicator.title = 'API Disconnected';
        }
        if (statApi) {
            statApi.textContent = 'Offline';
            statApi.className = 'stat-value';
            statApi.style.color = '#f87171';
        }
        return null;
    }
}

function setStatsLoading(loading) {
    document.querySelectorAll('.stat-card .stat-value').forEach(el => {
        el.closest('.stat-card')?.classList.toggle('is-loading', loading);
    });
}

function animateStatValue(el, value) {
    if (!el) return;
    el.classList.remove('is-loading');
    const text = typeof value === 'number' ? value.toLocaleString() : String(value);
    el.textContent = text;
}

async function loadPlatformStats() {
    setStatsLoading(true);
    try {
        const stats = await apiFetch(`/api/stats?${diseaseQS()}`);
        animateStatValue(document.getElementById('stat-kg-nodes'), stats.kg_nodes);
        animateStatValue(document.getElementById('stat-genes'), stats.genes);
        animateStatValue(document.getElementById('stat-candidates'), stats.candidates);
        animateStatValue(document.getElementById('stat-edges'), stats.kg_edges);
        animateStatValue(document.getElementById('stat-drugs'), stats.drugs);
        animateStatValue(document.getElementById('stat-pathways'), stats.pathways);
        animateStatValue(document.getElementById('stat-modules'), stats.modules);
        animateStatValue(document.getElementById('stat-diseases'), stats.diseases);

        const label = document.getElementById('stat-genes-label');
        if (label) label.textContent = `${stats.disease_name || activeDiseaseInfo().name} Genes`;

        const diseaseTitle = document.getElementById('stats-disease-title');
        if (diseaseTitle) {
            diseaseTitle.textContent = stats.disease_name || activeDiseaseInfo().name;
        }
    } catch {
        setStatsLoading(false);
    }
}

function coverageBadgeForLevel(level, status) {
    const label = level === 'full' ? 'Full'
        : level === 'partial' || status === 'limited_coverage' ? 'Limited'
        : level === 'unsupported' ? 'Unsupported' : 'Unknown';
    const cls = level === 'full' ? 'coverage-full'
        : level === 'partial' || status === 'limited_coverage' ? 'coverage-partial' : 'coverage-unsupported';
    return { label, cls };
}

async function refreshModuleMetadata() {
    const diseaseId = getActiveDisease();
    let modulesData;
    let stats;
    try {
        [modulesData, stats] = await Promise.all([
            apiFetch(`/api/system/modules?disease=${encodeURIComponent(diseaseId)}`),
            apiFetch(`/api/stats?${diseaseQS()}`),
        ]);
    } catch {
        return;
    }

    const byRegistryId = {};
    for (const mod of (modulesData.modules || [])) {
        byRegistryId[mod.module_id] = mod;
    }

    document.querySelectorAll('.module-card[data-module]').forEach(card => {
        const dashId = card.dataset.module;
        const registryId = DASHBOARD_MODULE_REGISTRY[dashId] || dashId;
        const mod = byRegistryId[registryId];
        const badge = card.querySelector('.module-coverage-badge');
        if (badge && mod?.coverage) {
            const { label, cls } = coverageBadgeForLevel(mod.coverage.level, mod.coverage.status);
            badge.textContent = label;
            badge.className = `module-coverage-badge coverage-badge ${cls}`;
            badge.title = [...(mod.coverage.missing_inputs || []), ...(mod.coverage.warnings || [])].join('; ');
        }

        const tagsEl = card.querySelector('[data-dynamic-tags]');
        if (!tagsEl) return;
        const kind = tagsEl.dataset.dynamicTags;
        if (kind === 'kg') {
            tagsEl.innerHTML = `
                <span class="tag green">${stats.genes} genes</span>
                <span class="tag blue">${stats.drugs} drugs</span>
                <span class="tag purple">${stats.pathways} pathways</span>
                <span class="tag yellow">vis-network</span>`;
        } else if (kind === 'repurpose') {
            tagsEl.innerHTML = `
                <span class="tag blue">Scoring Engine</span>
                <span class="tag purple">${stats.candidates} candidates</span>
                <span class="tag green">${stats.genes} genes</span>`;
        }
    });

    document.querySelectorAll('.module-report-link[data-report-module]').forEach(link => {
        const mod = link.dataset.reportModule;
        if (MODULES_WITHOUT_STATIC_REPORT.has(mod)) {
            link.title = 'No static report — use the Evidence Workspace';
        }
    });
}

async function refreshDashboardForDisease(diseaseId) {
    if (dashboardRefreshing) return;
    dashboardRefreshing = true;
    window.localStorage.setItem('active-disease', diseaseId);
    if (diseaseSelectControl && diseaseSelectControl.getValue() !== diseaseId) {
        diseaseSelectControl.setValue(diseaseId, true);
    }
    updateDiseaseDisplay();
    setStatsLoading(true);
    try {
        await Promise.all([
            loadPlatformStats(),
            refreshModuleMetadata(),
            initKGExplorer(),
            loadExportGrid(),
        ]);
    } catch (error) {
        console.error('Soft disease refresh failed; reloading page.', error);
        window.location.reload();
        return;
    } finally {
        dashboardRefreshing = false;
    }
}

function setupNavUi() {
    const toggle = document.getElementById('nav-toggle');
    const menu = document.getElementById('nav-menu');
    if (toggle && menu) {
        toggle.addEventListener('click', () => {
            const open = menu.classList.toggle('is-open');
            toggle.setAttribute('aria-expanded', String(open));
        });
    }

    const updateActiveNav = () => {
        const hash = window.location.hash.replace('#', '') || 'evidence-workspace';
        document.querySelectorAll('.nav-link[data-nav]').forEach(link => {
            link.classList.toggle('active', link.dataset.nav === hash);
        });
    };
    window.addEventListener('hashchange', updateActiveNav);
    updateActiveNav();
}

function initDiseaseTomSelect(selector, diseases, active) {
    if (typeof TomSelect === 'undefined') return null;

    const options = diseases.map(d => ({
        value: d.id,
        text: d.name,
        genes: d.genes,
    }));

    const control = new TomSelect(selector, {
        options,
        items: active ? [active] : [],
        maxOptions: 50,
        searchField: ['text'],
        placeholder: 'Search diseases…',
        allowEmptyOption: false,
        onChange(value) {
            if (!value || value === getActiveDisease()) return;
            void onDiseaseChange(value);
        },
        render: {
            option(data, escape) {
                const genes = data.genes ? ` <small>(${data.genes} genes)</small>` : '';
                return `<div>${escape(data.text)}${genes}</div>`;
            },
            item(data, escape) {
                return `<div>${escape(data.text)}</div>`;
            },
        },
    });
    control.wrapper.classList.add('nav-select-ts');
    return control;
}

function activeDiseaseInfo() {
    const id = getActiveDisease();
    const entry = (diseaseCache.list || []).find(d => d.id === id);
    const name = entry ? entry.name : id;
    return { id, name, label: cdAcronym(id, name) };
}

function updateDiseaseDisplay() {
    const info = activeDiseaseInfo();
    const nameEl = document.getElementById('hero-disease-name');
    if (nameEl) nameEl.textContent = info.name;
    const badgeEl = document.getElementById('hero-disease-badge');
    if (badgeEl) badgeEl.textContent = `🦠 ${info.label}`;
}

// ── Bootstrap ────────────────────────────────────────────────────────────

function onDiseaseChange(diseaseId) {
    void refreshDashboardForDisease(diseaseId);
}

// All dashboard controls use native buttons/forms plus delegated data actions.
// Keeping this binding at document level also covers controls rendered later,
// such as the disease manager and Workspace result/history cards.
function setupDashboardActions() {
    if (document.documentElement.dataset.dashboardActionsBound) return;
    document.documentElement.dataset.dashboardActionsBound = 'true';

    document.addEventListener('click', event => {
        const control = event.target.closest('[data-action]');
        if (!control) return;
        const action = control.dataset.action;
        switch (action) {
            case 'workspace-auth-login': void loginWorkspaceResearcher(); break;
            case 'workspace-auth-logout': void logoutWorkspaceResearcher(); break;
            case 'workspace-history-refresh': void loadWorkspaceHistory(); break;
            case 'workspace-alerts-refresh': void loadWorkspaceAlerts(); break;
            case 'workspace-notifications-save': void saveWorkspaceNotificationSettings(); break;
            case 'workspace-digest-preview': void previewWorkspaceDigest(); break;
            case 'workspace-digest-send': void sendWorkspaceDigest(); break;
            case 'workspace-trends-update': void loadWorkspaceTrends(); break;
            case 'workspace-trends-export': downloadWorkspaceTrendCsv(); break;
            case 'workspace-graph-fit': fitWorkspaceEvidenceGraph(); break;
            case 'workspace-graph-refresh': reloadWorkspaceEvidenceGraph(); break;
            case 'module-run': void runModule(control.dataset.module); break;
            case 'scroll-explorer': scrollToExplorer(); break;
            case 'network-analysis': void runNetworkAnalysis(); break;
            case 'cross-disease': void runCrossDisease(); break;
            case 'module-comparison': void runModuleComparison(); break;
            case 'disease-manager-open': void openDiseaseManager(); break;
            case 'disease-manager-close': closeDiseaseManager(); break;
            case 'disease-manager-prune': void runPrunePreview(); break;
            case 'disease-manager-restore': void previewRestore(Number(control.dataset.backupIndex)); break;
            case 'kg-reset': resetKGExplorer(); break;
            case 'kg-toggle-physics': toggleKGPhysics(); break;
            case 'kg-toggle-centrality': void toggleKGCentrality(); break;
            case 'kg-toggle-communities': void toggleKGCommunities(); break;
            case 'kg-export-png': exportKGCanvasImage(); break;
            case 'kg-expand-neighbors': void expand2HopNeighbors(control.dataset.nodeId); break;
            case 'run-multi-disease-comparison': void runMultiDiseaseComparison(); break;
            case 'compare-with-condition': {
                const curie = control.dataset.conditionCurie;
                if (curie) openConditionComparison(curie, '', control.dataset.conditionLabel || curie, '');
                break;
            }
            default: break;
        }
    });

    document.addEventListener('change', event => {
        const control = event.target.closest('[data-action]');
        if (!control) return;
        if (control.dataset.action === 'disease-change') onDiseaseChange(control.value);
        if (control.dataset.action === 'workspace-trends-render') renderWorkspaceTrends();
    });

    document.addEventListener('submit', event => {
        const form = event.target.closest('[data-action="workspace-submit"]');
        if (!form) return;
        submitWorkspace(event);
    });
}

function getActiveDisease() {
    return window.localStorage.getItem('active-disease') || 'sle';
}

async function loadDiseaseSelector() {
    const selector = document.getElementById('disease-selector');
    if (!selector) return;

    let diseases = null;
    let fetched = false;
    try {
        const data = await apiFetch('/api/system/diseases');
        diseases = (data && data.diseases) || [];
        diseaseCache.list = diseases;
        fetched = true;
    } catch {
        diseases = [{ id: 'sle', name: 'Systemic Lupus Erythematosus', genes: 0 }];
    }

    let active = getActiveDisease();
    if (fetched) {
        const known = diseases.some(d => d.id === active);
        if (!known) {
            active = diseases.some(d => d.id === 'sle') ? 'sle' : (diseases[0] && diseases[0].id) || '';
            window.localStorage.setItem('active-disease', active);
        }
    }

    if (diseaseSelectControl) {
        diseaseSelectControl.destroy();
        diseaseSelectControl = null;
    }

    const options = diseases.map(d =>
        `<option value="${escapeHtml(d.id)}">${escapeHtml(d.name)}${d.genes ? ` (${d.genes} genes)` : ''}</option>`).join('');
    selector.innerHTML = options;
    selector.value = active;

    if (typeof TomSelect !== 'undefined') {
        diseaseSelectControl = initDiseaseTomSelect(selector, diseases, active);
    } else {
        selector.addEventListener('change', () => {
            if (selector.value) onDiseaseChange(selector.value);
        });
    }
}

document.addEventListener('DOMContentLoaded', async () => {
    setupDashboardActions();
    setupNavUi();
    const linkedParams = new URLSearchParams(window.location.search);
    await loadDiseaseSelector();
    updateDiseaseDisplay();
    await checkAPIStatus();
    await loadPlatformStats();
    await refreshModuleMetadata();
    initKGExplorer();
    initConditionExplorer();
    initConditionComparison();
    initGraphAnalytics();
    void loadBiomedImportStatus();
    handleUniversalDeepLinks();
    loadExportGrid();
    loadWorkspaceAuth();
    loadWorkspaceHistory();
    loadWorkspaceTrends();
    loadWorkspaceNotificationSettings();
    loadWorkspaceAlerts();
    if (linkedParams.get('digest_key')) window.setTimeout(previewWorkspaceDigest, 250);

    setInterval(checkAPIStatus, 30000);
    setInterval(loadPlatformStats, 60000);
    setInterval(loadWorkspaceAlerts, 60000);
});
