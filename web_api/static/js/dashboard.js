/**
 * Lupus Research Platform — Live Dashboard JavaScript
 * Calls the FastAPI backend to power module cards with live data.
 * Uses WebSocket for real-time job progress streaming.
 */

const API_BASE = '';

// ── State ────────────────────────────────────────────────────────────────

const activeJobs = {};
const activeSockets = {};

// ── API Helpers ──────────────────────────────────────────────────────────

async function apiFetch(path, options = {}) {
    try {
        const res = await fetch(`${API_BASE}${path}`, {
            headers: { 'Accept': 'application/json', ...options.headers },
            ...options,
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: res.statusText }));
            throw new Error(err.detail || `HTTP ${res.status}`);
        }
        return await res.json();
    } catch (e) {
        if (e.name === 'TypeError' && e.message.includes('fetch')) {
            throw new Error('API server is not running. Start with: python web_api/main.py');
        }
        throw e;
    }
}

function formatNumber(n) {
    return n != null ? n.toLocaleString() : '…';
}

// ── Module Execution ─────────────────────────────────────────────────────

async function runModule(module) {
    const resultEl = document.getElementById(`result-${module}`);
    if (!resultEl) return;

    resultEl.className = 'module-result visible loading';
    resultEl.innerHTML = '<span class="spinner"></span> Running analysis…';

    try {
        let data;
        switch (module) {
            case 'kg':
                data = await apiFetch('/api/kg/stats');
                renderKGResult(resultEl, data);
                break;
            case 'expression':
                data = await apiFetch('/api/expression/correlate?top_n=10');
                renderExpressionResult(resultEl, data);
                break;
            case 'cart':
                data = await apiFetch('/api/cart/suitability?top_n=10');
                renderCartResult(resultEl, data);
                break;
            case 'repurpose':
                data = await apiFetch('/api/repurpose/candidates?top_n=10');
                renderRepurposeResult(resultEl, data);
                break;
            case 'bioinformatics':
                data = await apiFetch('/api/kg/stats');
                renderBioResult(resultEl, data);
                break;
            case 'gwas':
            case 'enrichment':
            case 'ppi':
            case 'literature':
            case 'screening':
            case 'trials':
            case 'ml':
            case 'synergy':
            case 'safety':
                await streamJob(module, resultEl);
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

async function streamJob(module, resultEl) {
    const endpoints = {
        gwas: '/api/jobs/gwas',
        enrichment: '/api/jobs/enrichment',
        ppi: '/api/jobs/ppi',
        literature: '/api/jobs/literature',
        screening: '/api/jobs/screening',
        trials: '/api/jobs/trials',
        ml: '/api/jobs/ml',
        synergy: '/api/jobs/synergy',
        safety: '/api/jobs/safety',
    };

    const endpoint = endpoints[module];
    if (!endpoint) throw new Error(`No job endpoint for ${module}`);

    // Submit the job
    const data = await apiFetch(endpoint, { method: 'POST' });
    const jobId = data.job_id;
    const startTime = Date.now();

    activeJobs[jobId] = { module, resultEl, status: 'PENDING', startTime };
    updateJobBadge();
    showJobsSection();
    renderJobQueue();

    // Open WebSocket for real-time progress
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.host}/api/jobs/${jobId}/ws`;
    const ws = new WebSocket(wsUrl);

    activeSockets[jobId] = ws;
    resultEl.innerHTML = `<span class="spinner"></span> Job <code>${jobId.slice(0, 8)}&hellip;</code> submitted &mdash; streaming via WebSocket…`;

    ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        activeJobs[jobId].status = msg.status;
        renderJobQueue();

        if (msg.status === 'SUCCESS') {
            resultEl.className = 'module-result visible success';
            renderJobResult(module, resultEl, msg.result);
            cleanupJob(jobId);
            return;
        }

        if (msg.status === 'FAILURE') {
            resultEl.className = 'module-result visible error';
            resultEl.innerHTML = `<strong>Job failed:</strong> ${msg.error || 'Unknown error'}`;
            cleanupJob(jobId);
            return;
        }

        if (msg.status === 'TIMEOUT') {
            resultEl.className = 'module-result visible error';
            resultEl.innerHTML = '<strong>Timeout:</strong> Job exceeded 10-minute limit.';
            cleanupJob(jobId);
            return;
        }

        if (msg.status === 'ERROR') {
            resultEl.className = 'module-result visible error';
            resultEl.innerHTML = `<strong>Stream error:</strong> ${msg.error || 'Unknown'}`;
            cleanupJob(jobId);
            return;
        }

        // PENDING, STARTED, PROGRESS — show elapsed time
        const elapsed = updateElapsed(startTime);
        const progress = msg.progress || {};
        const pct = progress.percent != null ? ` (${progress.percent}%)` : '';
        const detail = progress.message || progress.step || '';
        resultEl.innerHTML = `<span class="spinner"></span> ${module} — ${msg.status}${pct} (${elapsed})${detail ? `<br><small style=\"color:var(--text-muted);\">${detail}</small>` : ''}`;
    };

    ws.onerror = () => {
        // WebSocket failed. Fall back to HTTP polling silently.
        // Set a guard so onclose (which always follows onerror) doesn't duplicate
        if (activeJobs[jobId]) activeJobs[jobId]._fallback = true;
        resultEl.innerHTML = `<span class="spinner"></span> WebSocket unavailable — falling back to polling…`;
        cleanupSocket(jobId);
        pollJobFallback(jobId, module, resultEl);
    };

    ws.onclose = (event) => {
        // If the WebSocket closed without reaching a terminal state, something went wrong.
        // Skip fallback if onerror already started one (prevents duplicate polling loops).
        if (activeJobs[jobId] && !activeJobs[jobId]._fallback) {
            const status = activeJobs[jobId].status;
            if (status !== 'SUCCESS' && status !== 'FAILURE' && status !== 'TIMEOUT') {
                resultEl.innerHTML = `<span class="spinner"></span> WebSocket closed — falling back to polling…`;
                cleanupSocket(jobId);
                pollJobFallback(jobId, module, resultEl);
            }
        }
    };
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
            const status = await apiFetch(`/api/jobs/${jobId}`);
            activeJobs[jobId].status = status.status;
            renderJobQueue();

            if (status.status === 'SUCCESS') {
                resultEl.className = 'module-result visible success';
                renderJobResult(module, resultEl, status.result);
                cleanupJob(jobId);
                return;
            }

            if (status.status === 'FAILURE') {
                resultEl.className = 'module-result visible error';
                resultEl.innerHTML = `<strong>Job failed:</strong> ${status.error || 'Unknown error'}`;
                cleanupJob(jobId);
                return;
            }

            resultEl.innerHTML = `<span class="spinner"></span> ${module} — running… (${updateElapsed(startTime)})`;
        } catch (e) {
            resultEl.innerHTML += `<br><small style="color:#f87171;">Poll error: ${e.message}</small>`;
        }
    }

    resultEl.className = 'module-result visible error';
    resultEl.innerHTML = '<strong>Timeout:</strong> Job took too long. Check server logs.';
    cleanupJob(jobId);
}

// ── Helpers ──────────────────────────────────────────────────────────────

async function runNetworkAnalysis() {
    const resultEl = document.getElementById('result-network');
    resultEl.className = 'module-result visible loading';
    resultEl.innerHTML = '<span class="spinner"></span> Analyzing network topology...';
    try {
        const [comm, cent] = await Promise.all([
            apiFetch('/api/kg/communities'),
            apiFetch('/api/kg/centrality?metric=betweenness&top_n=10'),
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

function renderJobResult(module, resultEl, result) {
    if (!result) {
        resultEl.innerHTML = '<div class="result-header">✅ Analysis Complete</div>';
        return;
    }

    switch (module) {
        case 'gwas':
            resultEl.innerHTML = renderModuleResult([
                ['Studies', result.total_studies],
                ['Unique Genes', result.unique_genes],
                ['Validated in KG', result.crossref?.n_validated || 0],
                ['Novel GWAS Genes', result.crossref?.n_novel || 0],
            ]);
            break;
        case 'enrichment':
            const libs = result.libraries || [];
            resultEl.innerHTML = renderModuleResult([
                ['Genes Analyzed', result.genes_analyzed],
                ['Libraries', libs.length],
                ['Significant Terms', libs.reduce((s, l) => s + l.terms.filter(t => t.adj_p_value < 0.05).length, 0)],
            ]);
            break;
        case 'ppi':
            resultEl.innerHTML = renderModuleResult([
                ['Network Nodes', result.nodes],
                ['Interactions', result.edges],
                ['Top Hub', result.top_hubs?.[0]?.symbol || '—'],
                ['Untargeted Hubs', result.hub_untargeted?.length || 0],
            ]);
            break;
        case 'literature':
            resultEl.innerHTML = renderModuleResult([
                ['Articles', result.total_articles],
                ['Queries Run', result.queries_run],
                ['Genes Covered', result.gene_coverage?.length || 0],
            ]);
            break;
        case 'screening':
            resultEl.innerHTML = renderModuleResult([
                ['Compounds Screened', result.compounds_screened],
                ['Pairings', result.total_pairings],
                ['Tier 1 Hits', result.tier1_count],
                ['Tier 2 Hits', result.tier2_count],
            ]);
            break;
        case 'trials':
            resultEl.innerHTML = renderModuleResult([
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
        case 'safety':
            resultEl.innerHTML = renderModuleResult([
                ['Drugs Profiled', result.total_drugs],
                ['Avg Safety Score', result.avg_safety_score?.toFixed(2)],
                ['Safest Drug', result.safest_drug?.split('(')[0].trim() || '—'],
                ['Drugs with BBW', result.drugs_with_bbw],
                ['DIL Risk Drugs', result.drugs_with_dil_risk],
            ]);
            break;
    }
}

// ── Result Rendering ─────────────────────────────────────────────────────

function renderModuleResult(rows) {
    let html = '<div class="result-header">✅ Analysis Complete</div>';
    for (const [label, value] of rows) {
        html += `<div class="result-row"><span class="result-label">${label}</span><span class="result-value">${formatNumber(value)}</span></div>`;
    }
    return html;
}

function renderKGResult(el, data) {
    el.className = 'module-result visible success';
    el.innerHTML = renderModuleResult([
        ['Total Nodes', data.total_nodes],
        ['Total Edges', data.total_edges],
        ['Untargeted Genes', data.untargeted_genes?.length || 0],
        ['Top Hub', data.top_hub_genes?.[0]?.name || '—'],
    ]);
}

function renderRepurposeResult(el, data) {
    el.className = 'module-result visible success';
    el.innerHTML = renderModuleResult([
        ['Candidates Scored', data.total],
        ['Avg Score', data.avg_score?.toFixed(2)],
        ['Tier 1 (≥8.0)', data.tier1_count],
        ['Top Drug', data.candidates?.[0]?.drug_name || '—'],
    ]);
}

function renderCartResult(el, data) {
    const top = data.genes?.[0];
    el.className = 'module-result visible success';
    el.innerHTML = renderModuleResult([
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
    el.innerHTML = renderModuleResult([
        ['Drugs Correlated', data.total_drugs],
        ['Avg Score', data.avg_score?.toFixed(2)],
        ['Tier 1 (Strong)', data.tier1_count],
        ['Top Drug', top ? top.drug_name?.split('(')[0].trim() : '—'],
        ['Top Score', top?.composite_score?.toFixed(2) || '—'],
    ]);
}

function renderBioResult(el, data) {
    el.className = 'module-result visible success';
    el.innerHTML = renderModuleResult([
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

// ── Init ─────────────────────────────────────────────────────────────────

async function checkAPIStatus() {
    const indicator = document.getElementById('api-status');
    try {
        await apiFetch('/api/health');
        indicator.textContent = '●';
        indicator.className = 'nav-link nav-status online';
        indicator.title = 'API Connected';
    } catch {
        indicator.textContent = '●';
        indicator.className = 'nav-link nav-status offline';
        indicator.title = 'API Disconnected';
    }
}

async function loadPlatformStats() {
    try {
        const stats = await apiFetch('/api/stats');
        document.getElementById('stat-kg-nodes').textContent = stats.kg_nodes;
        document.getElementById('stat-genes').textContent = stats.genes;
        document.getElementById('stat-candidates').textContent = stats.candidates;
        document.getElementById('stat-edges').textContent = stats.kg_edges;
    } catch {
        // Stats will show '…' placeholders
    }
}

// ── Bootstrap ────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    checkAPIStatus();
    loadPlatformStats();

    setInterval(checkAPIStatus, 30000);
    setInterval(loadPlatformStats, 60000);
});
