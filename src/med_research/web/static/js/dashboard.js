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

function escapeHtml(text) {
    return String(text == null ? '' : text)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
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
            case 'biomarker':
                data = await apiFetch('/api/biomarker/discover?top_n=10');
                renderBiomarkerResult(resultEl, data);
                break;
            case 'semantic':
                data = await apiFetch('/api/semantic/search?q=lupus+treatment+drug+repurposing&top_k=10');
                renderSemanticResult(resultEl, data);
                break;
            case 'evidence':
                data = await apiFetch('/api/evidence/gather?q=lupus+treatment+drug+repurposing&max_per_source=5&sources=pubmed,preprints,clinical_trials,fda_labels,patents');
                renderEvidenceResult(resultEl, data);
                break;
            case 'extractor':
                data = await apiFetch('/api/llm/extract?q=lupus+treatment+drug+repurposing&max_articles=10&sources=pubmed,preprints');
                renderExtractorResult(resultEl, data);
                break;
            case 'monitor':
                data = await apiFetch('/api/monitor/diff');
                renderMonitorResult(resultEl, data);
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

function renderBiomarkerResult(el, data) {
    const top = data.biomarkers?.[0];
    el.className = 'module-result visible success';
    el.innerHTML = renderModuleResult([
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

function renderSemanticResult(el, data) {
    const top = data.results?.[0];
    el.className = 'module-result visible success';
    el.innerHTML = renderModuleResult([
        ['Indexed Articles', data.indexed_articles],
        ['Results Found', data.total_results],
        ['Top Match', top ? top.title?.slice(0, 50) + '...' : '—'],
        ['Similarity', top?.similarity?.toFixed(1) || '—'],
    ]);
}

function renderEvidenceResult(el, data) {
    const top = data.results?.[0];
    el.className = 'module-result visible success';
    el.innerHTML = renderModuleResult([
        ['Total Results', data.total_results],
        ['Sources Searched', data.sources_searched?.length || 0],
        ['Top Source', top ? top.source_type?.replace('_',' ').toUpperCase() : '—'],
        ['Top Match', top ? top.title?.slice(0, 50) + '...' : '—'],
    ]);
}

function renderExtractorResult(el, data) {
    const stats = data.stats || {};
    el.className = 'module-result visible success';
    el.innerHTML = renderModuleResult([
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
    el.innerHTML = renderModuleResult([
        ['Total Changes', data.total_changes],
        ['🔴 High Alerts', high],
        ['🟡 Medium Alerts', med],
        ['🟢 Low Alerts', low],
        ['Hours Elapsed', (data.hours_elapsed || 0).toFixed(1) + 'h'],
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

const CD_DISEASE_ORDER = ['sle', 'ra', 'ibd', 'ms', 'ss', 'ssc', 't1d'];
const CD_DISEASE_LABELS = {
    sle: 'SLE', ra: 'RA', ibd: 'IBD', ms: 'MS', ss: 'SS', ssc: 'SSc', t1d: 'T1D',
};

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

    const diseaseNames = CD_DISEASE_ORDER
        .filter(d => summary[d])
        .map(d => ({ id: d, name: (summary[d].name || d).split('(')[0].trim() }));

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
    const simHeader = diseaseNames.map(d => `<th>${CD_DISEASE_LABELS[d.id] || d.id}</th>`).join('');
    const simRows = diseaseNames.map(d => {
        const cells = diseaseNames.map(d2 => {
            if (d.id === d2.id) return `<td style="background:rgba(129,140,248,0.15);text-align:center;">—</td>`;
            const v = simMap[`${d.id}|${d2.id}`] || 0;
            return `<td style="background:${cdColorFor(v, 1)};text-align:center;color:#0a0a0f;">${v.toFixed(2)}</td>`;
        }).join('');
        return `<tr><td class="gene-name">${CD_DISEASE_LABELS[d.id] || d.id}</td>${cells}</tr>`;
    }).join('');

    // ── Multi-disease drugs ─────────────────────────────────────────
    const drugRows = multiDrugs.slice(0, 12).map(drug => {
        const diseases = (drug.diseases || drug.disease_ids || []);
        const tags = diseases.slice(0, 7).map(d =>
            `<span class="cd-disease-tag">${CD_DISEASE_LABELS[d] || d}</span>`).join('');
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
                    ${diseaseNames.map(d => `<th>${CD_DISEASE_LABELS[d.id] || d.id}</th>`).join('')}
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

    // Edges between visible nodes only
    const visEdges = [];
    for (const el of kgRawElements) {
        const d = el.data || {};
        const from = d.from ?? d.source;
        const to = d.to ?? d.target;
        if (from !== undefined && to !== undefined) {
            if (visibleIds.has(from) && visibleIds.has(to)) {
                const type = d.type || 'UNKNOWN';
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

function setupKGControls() {
    const search = document.getElementById('kg-search');
    const checks = document.querySelectorAll('.kg-filter input[data-type]');
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
}

function resetKGExplorer() {
    const search = document.getElementById('kg-search');
    if (search) search.value = '';
    // Restore node colors (search dims non-matches) and refit
    if (kgNetwork && kgNodes) {
        kgNodes.forEach(n => {
            kgNodes.update({ id: n.id, color: { background: KG_TYPE_COLORS[n.type] || '#787890', border: KG_TYPE_COLORS[n.type] || '#787890', highlight: { background: '#ffffff', border: '#ffffff' } } });
        });
    }
    if (kgNetwork) kgNetwork.fit({ animation: true });
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

function onDiseaseChange(diseaseId) {
    window.localStorage.setItem('active-disease', diseaseId);
    window.location.reload();
}

function getActiveDisease() {
    return window.localStorage.getItem('active-disease') || 'sle';
}

document.addEventListener('DOMContentLoaded', () => {
    const selector = document.getElementById('disease-selector');
    if (selector) {
        selector.value = getActiveDisease();
    }
    checkAPIStatus();
    loadPlatformStats();
    initKGExplorer();
    loadExportGrid();

    setInterval(checkAPIStatus, 30000);
    setInterval(loadPlatformStats, 60000);
});
