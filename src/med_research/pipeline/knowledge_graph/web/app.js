/**
 * Lupus Knowledge Graph — Interactive Cytoscape.js Visualization
 *
 * Features:
 *   - Heterogeneous graph with genes, drugs, pathways, and SLE
 *   - Node & edge type filtering
 *   - Search with highlight + pan
 *   - Click-to-inspect detail panel
 *   - Tooltip hover previews
 *   - Animated layout
 */

// ============================================
// Constants
// ============================================

const TYPE_COLORS = {
    gene: '#4ade80',
    drug: '#60a5fa',
    pathway: '#f59e0b',
    disease: '#f43f5e',
};

const TYPE_SHAPES = {
    gene: 'ellipse',
    drug: 'round-rectangle',
    pathway: 'diamond',
    disease: 'star',
};

const EDGE_COLORS = {
    TARGETS: '#60a5fa',
    TREATS: '#4ade80',
    PARTICIPATES_IN: '#a78bfa',
    DRIVES: '#f43f5e',
    MODULATES: '#f59e0b',
    ASSOCIATED_WITH: '#94a3b8',
};

const EDGE_STROKE_STYLES = {
    TARGETS: 'solid',
    TREATS: 'solid',
    PARTICIPATES_IN: 'dashed',
    DRIVES: 'solid',
    MODULATES: 'dotted',
    ASSOCIATED_WITH: 'dashed',
};

// ============================================
// State
// ============================================

let cy = null;
let allElements = [];
let activeFilters = { gene: true, drug: true, pathway: true, disease: true };
let activeEdgeFilters = {
    TARGETS: true,
    TREATS: true,
    PARTICIPATES_IN: true,
    DRIVES: true,
    MODULATES: true,
    ASSOCIATED_WITH: true,
};

// ============================================
// Cytoscape Initialization
// ============================================

async function init() {
    // Show loading
    const container = document.getElementById('cy');
    container.innerHTML = `
        <div class="loading-overlay">
            <div class="loading-spinner"></div>
            <div>Loading Knowledge Graph...</div>
        </div>
    `;

    try {
        const response = await fetch('graph_data.json');
        const graphData = await response.json();
        allElements = graphData.elements;
        renderGraph(allElements);
        updateStats();
        setupEventListeners();
    } catch (err) {
        container.innerHTML = `
            <div class="loading-overlay">
                <p style="color: #f43f5e;">⚠️ Could not load graph data</p>
                <p style="font-size: 0.8rem; margin-top: 8px;">
                    Run <code>python build_graph.py --export</code> first
                </p>
            </div>
        `;
        console.error('Failed to load graph data:', err);
    }
}

// ============================================
// Graph Rendering
// ============================================

function renderGraph(elements) {
    const container = document.getElementById('cy');
    container.innerHTML = '';

    cy = cytoscape({
        container: container,
        elements: elements,
        style: getGraphStyles(),
        layout: {
            name: 'cose',
            animate: true,
            animationDuration: 1500,
            animationEasing: 'ease-in-out-cubic',
            nodeRepulsion: function (node) {
                return node.data('type') === 'disease' ? 60000 : 12000;
            },
            idealEdgeLength: function (edge) {
                return 120;
            },
            nodeOverlap: 24,
            gravity: 4,
            numIter: 2000,
            initialTemp: 200,
            coolingFactor: 0.95,
            minTemp: 1.0,
        },
        wheelSensitivity: 0.3,
        minZoom: 0.15,
        maxZoom: 3.5,
    });

    // Node click → show details
    cy.on('tap', 'node', (evt) => {
        const node = evt.target;
        showNodeDetails(node);
    });

    // Background click → clear selection
    cy.on('tap', (evt) => {
        if (evt.target === cy) {
            clearDetails();
            cy.elements().unselect();
        }
    });

    // Hover tooltip
    cy.on('mouseover', 'node', (evt) => {
        const node = evt.target;
        showTooltip(evt, node);
    });

    cy.on('mouseout', 'node', () => {
        hideTooltip();
    });

    cy.on('mouseover', 'edge', (evt) => {
        const edge = evt.target;
        showEdgeTooltip(evt, edge);
    });

    cy.on('mouseout', 'edge', () => {
        hideTooltip();
    });

    // Animate disease node pulse
    const diseaseNode = cy.$('#Lupus\\ \\(SLE\\)');
    if (diseaseNode.length) {
        diseaseNode.style({
            'border-width': 4,
            'border-color': '#f43f5e',
        });
    }
}

// ============================================
// Cytoscape Styles
// ============================================

function getGraphStyles() {
    const nodeStyles = Object.entries(TYPE_COLORS)
        .map(([type, color]) => ({
            selector: `node[type="${type}"]`,
            style: {
                'background-color': color,
                'shape': TYPE_SHAPES[type] || 'ellipse',
                'width': type === 'disease' ? 55 : type === 'pathway' ? 36 : 28,
                'height': type === 'disease' ? 55 : type === 'pathway' ? 36 : 28,
                'label': 'data(label)',
                'color': '#e0e0e8',
                'font-size': type === 'disease' ? '12px' : '10px',
                'font-weight': type === 'disease' ? 'bold' : 'normal',
                'text-valign': 'bottom',
                'text-halign': 'center',
                'text-margin-y': type === 'disease' ? 10 : 6,
                'text-wrap': 'wrap',
                'text-max-width': '180px',
                'border-width': type === 'disease' ? 3 : 2,
                'border-color': color,
                'border-opacity': 0.6,
                'opacity': 1,
            },
        }));

    const edgeStyles = Object.entries(EDGE_COLORS)
        .map(([type, color]) => ({
            selector: `edge[type="${type}"]`,
            style: {
                'line-color': color,
                'target-arrow-color': color,
                'target-arrow-shape': 'triangle',
                'arrow-scale': 0.7,
                'width': type === 'TREATS' || type === 'DRIVES' ? 2 : 1.2,
                'line-style': EDGE_STROKE_STYLES[type] || 'solid',
                'opacity': 0.5,
                'curve-style': 'bezier',
            },
        }));

    return [
        // Base node
        {
            selector: 'node',
            style: {
                'font-family': 'Inter, system-ui, sans-serif',
                'transition-property': 'opacity, width, height, border-width',
                'transition-duration': '0.2s',
                'transition-timing-function': 'ease',
            },
        },
        // Selected node
        {
            selector: 'node:selected',
            style: {
                'border-width': 5,
                'border-opacity': 1,
                'border-color': '#ffffff',
                'opacity': 1,
            },
        },
        // Highlighted nodes (from search)
        {
            selector: 'node.highlighted',
            style: {
                'border-width': 6,
                'border-color': '#fbbf24',
                'border-opacity': 1,
                'z-index': 9999,
            },
        },
        // Base edge
        {
            selector: 'edge',
            style: {
                'transition-property': 'opacity',
                'transition-duration': '0.2s',
            },
        },
        // Faded (not in filter)
        {
            selector: 'node.filtered-out, edge.filtered-out',
            style: { 'opacity': 0.08 },
        },
        ...nodeStyles,
        ...edgeStyles,
    ];
}

// ============================================
// Filtering
// ============================================

function applyFilters() {
    if (!cy) return;

    cy.nodes().forEach((node) => {
        const nodeType = node.data('type');
        node.removeClass('filtered-out');
        if (!activeFilters[nodeType]) {
            node.addClass('filtered-out');
        }
    });

    cy.edges().forEach((edge) => {
        const edgeType = edge.data('type');
        edge.removeClass('filtered-out');
        if (!activeEdgeFilters[edgeType]) {
            edge.addClass('filtered-out');
        }
    });

    updateStats();
}

// ============================================
// Search
// ============================================

function searchNodes(query) {
    if (!cy || !query.trim()) {
        clearSearch();
        return;
    }

    const q = query.toLowerCase().trim();
    const resultsContainer = document.getElementById('search-results');

    // Find matching nodes
    const matches = cy.nodes().filter((node) => {
        const label = (node.data('label') || '').toLowerCase();
        const id = (node.data('id') || '').toLowerCase();
        const description = (node.data('description') || '').toLowerCase();
        return label.includes(q) || id.includes(q) || description.includes(q);
    });

    // Clear all highlights
    cy.nodes().removeClass('highlighted');

    if (matches.length === 0) {
        resultsContainer.innerHTML =
            '<div class="search-result-item" style="color: var(--text-muted);">No results found</div>';
        return;
    }

    // Show first 8 results
    const displayMatches = matches.slice(0, 8);
    resultsContainer.innerHTML = displayMatches
        .map((node) => {
            const type = node.data('type');
            const color = TYPE_COLORS[type] || '#fff';
            return `
            <div class="search-result-item" data-node-id="${node.data('id')}">
                <span style="color:${color}; margin-right:6px;">●</span>
                <strong>${escapeHtml(node.data('label') || node.data('id'))}</strong>
                <span style="color:var(--text-muted); font-size:0.7rem; margin-left:4px;">${type}</span>
            </div>
          `;
        })
        .join('');

    // Click handler for search results
    resultsContainer.querySelectorAll('.search-result-item').forEach((item) => {
        item.addEventListener('click', () => {
            const nodeId = item.dataset.nodeId;
            const node = cy.getElementById(nodeId);
            if (node.length) {
                // Highlight
                cy.nodes().removeClass('highlighted');
                node.addClass('highlighted');

                // Pan and zoom
                cy.animate({
                    center: { eles: node },
                    zoom: 1.4,
                    duration: 600,
                    easing: 'ease-in-out-cubic',
                });

                // Show details
                showNodeDetails(node);
            }
        });
    });
}

function clearSearch() {
    document.getElementById('search-results').innerHTML = '';
    if (cy) cy.nodes().removeClass('highlighted');
}

// ============================================
// Detail Panel
// ============================================

function showNodeDetails(node) {
    const data = node.data();
    const type = data.type;
    const color = TYPE_COLORS[type] || '#fff';
    const panel = document.getElementById('detail-panel');

    let html = `
        <div class="detail-title" style="color:${color}">${escapeHtml(data.label || data.id)}</div>
        <div class="detail-type ${type}">${type}</div>
    `;

    if (data.description) {
        html += `<div class="detail-desc">${escapeHtml(data.description).substring(0, 300)}</div>`;
    }

    html += '<div class="detail-meta">';

    // Type-specific fields
    if (type === 'gene') {
        if (data.chromosome)
            html += `<span><span class="meta-key">Chromosome:</span><span class="meta-val">${escapeHtml(data.chromosome)}</span></span>`;
        if (data.odds_ratio)
            html += `<span><span class="meta-key">Odds Ratio:</span><span class="meta-val">${data.odds_ratio}</span></span>`;
        if (data.category)
            html += `<span><span class="meta-key">Category:</span><span class="meta-val">${escapeHtml(data.category)}</span></span>`;
    } else if (type === 'drug') {
        if (data.drug_type)
            html += `<span><span class="meta-key">Type:</span><span class="meta-val">${escapeHtml(data.drug_type)}</span></span>`;
        if (data.approval)
            html += `<span><span class="meta-key">Approval:</span><span class="meta-val">${escapeHtml(data.approval).substring(0, 80)}</span></span>`;
        if (data.efficacy)
            html += `<span><span class="meta-key">Efficacy:</span><span class="meta-val">${escapeHtml(data.efficacy).substring(0, 80)}</span></span>`;
    } else if (type === 'pathway') {
        if (data.description)
            html += `<span><span class="meta-key">Description:</span><span class="meta-val">${escapeHtml(data.description).substring(0, 200)}</span></span>`;
    } else if (type === 'disease') {
        if (data.prevalence)
            html += `<span><span class="meta-key">Prevalence:</span><span class="meta-val">${escapeHtml(data.prevalence)}</span></span>`;
    }

    html += '</div>';

    // Connected nodes summary
    const neighbors = node.neighborhood().nodes();
    if (neighbors.length > 0) {
        const neighborTypes = {};
        neighbors.forEach((n) => {
            const nt = n.data('type');
            neighborTypes[nt] = (neighborTypes[nt] || 0) + 1;
        });
        html +=
            '<div class="detail-meta" style="margin-top:8px;"><span><span class="meta-key">Connected to:</span></span>';
        Object.entries(neighborTypes).forEach(([nt, count]) => {
            html += `<span style="padding-left:12px; color:${TYPE_COLORS[nt] || '#fff'};">● ${count} ${nt}${count > 1 ? 's' : ''}</span>`;
        });
        html += '</div>';
    }

    panel.innerHTML = html;
}

function clearDetails() {
    document.getElementById('detail-panel').innerHTML =
        '<p class="muted">Click a node to see details</p>';
}

// ============================================
// Tooltips
// ============================================

function showTooltip(evt, node) {
    const data = node.data();
    const type = data.type;
    const position = evt.renderedPosition || evt.position;
    const tooltip = document.getElementById('tooltip');

    const color = TYPE_COLORS[type] || '#fff';

    tooltip.innerHTML = `
        <div class="tt-title" style="color:${color}">${escapeHtml(data.label || data.id)}</div>
        <div class="tt-type">${type}</div>
        <div style="margin-top:4px; font-size:0.78rem; max-width:280px;">${escapeHtml((data.description || '').substring(0, 180))}</div>
    `;

    const tooltipRect = tooltip.getBoundingClientRect();
    const containerRect = document.getElementById('canvas-container').getBoundingClientRect();

    let left = position.x + 20;
    let top = position.y - tooltipRect.height - 10;

    if (left + tooltipRect.width > containerRect.width) {
        left = position.x - tooltipRect.width - 20;
    }
    if (top < 0) {
        top = position.y + 20;
    }

    tooltip.style.left = left + 'px';
    tooltip.style.top = top + 'px';
    tooltip.classList.add('visible');
}

function showEdgeTooltip(evt, edge) {
    const data = edge.data();
    const tooltip = document.getElementById('tooltip');
    const position = evt.renderedPosition || evt.position;

    tooltip.innerHTML = `
        <div class="tt-type">${data.type}</div>
        <div style="margin-top:4px; font-size:0.78rem; max-width:280px;">${escapeHtml((data.description || '').substring(0, 200))}</div>
    `;

    const tooltipRect = tooltip.getBoundingClientRect();

    tooltip.style.left = position.x + 20 + 'px';
    tooltip.style.top = position.y - tooltipRect.height - 10 + 'px';
    tooltip.classList.add('visible');
}

function hideTooltip() {
    document.getElementById('tooltip').classList.remove('visible');
}

// ============================================
// Stats
// ============================================

function updateStats() {
    if (!cy) return;

    const visibleNodes = cy.nodes().filter((n) => !n.hasClass('filtered-out'));
    const visibleEdges = cy.edges().filter((e) => !e.hasClass('filtered-out'));

    document.getElementById('stat-nodes').textContent = visibleNodes.length;
    document.getElementById('stat-edges').textContent = visibleEdges.length;
    document.getElementById('stat-genes').textContent = visibleNodes.filter(
        (n) => n.data('type') === 'gene'
    ).length;
    document.getElementById('stat-drugs').textContent = visibleNodes.filter(
        (n) => n.data('type') === 'drug'
    ).length;
    document.getElementById('stat-pathways').textContent = visibleNodes.filter(
        (n) => n.data('type') === 'pathway'
    ).length;
}

// ============================================
// Event Listeners
// ============================================

function setupEventListeners() {
    // Search
    const searchInput = document.getElementById('search-input');
    let searchTimeout;
    searchInput.addEventListener('input', () => {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            searchNodes(searchInput.value);
        }, 200);
    });

    // Node type filters
    document.querySelectorAll('.filter-chip[data-filter]').forEach((chip) => {
        chip.addEventListener('click', function () {
            const filterType = this.dataset.filter;
            activeFilters[filterType] = !activeFilters[filterType];
            this.classList.toggle('active', activeFilters[filterType]);
            this.querySelector('input').checked = activeFilters[filterType];
            applyFilters();
        });
    });

    // Edge type filters
    document.querySelectorAll('.filter-chip[data-edge]').forEach((chip) => {
        chip.addEventListener('click', function () {
            const edgeType = this.dataset.edge;
            activeEdgeFilters[edgeType] = !activeEdgeFilters[edgeType];
            this.classList.toggle('active', activeEdgeFilters[edgeType]);
            this.querySelector('input').checked = activeEdgeFilters[edgeType];
            applyFilters();
        });
    });

    // Canvas controls
    document.getElementById('btn-fit').addEventListener('click', () => {
        cy.animate({ fit: { eles: cy.elements(), padding: 40 }, duration: 500 });
    });

    document.getElementById('btn-zoom-in').addEventListener('click', () => {
        cy.animate({ zoom: cy.zoom() * 1.3, duration: 300 });
    });

    document.getElementById('btn-zoom-out').addEventListener('click', () => {
        cy.animate({ zoom: cy.zoom() * 0.7, duration: 300 });
    });

    document.getElementById('btn-reset').addEventListener('click', () => {
        activeFilters = { gene: true, drug: true, pathway: true, disease: true };
        activeEdgeFilters = {
            TARGETS: true,
            TREATS: true,
            PARTICIPATES_IN: true,
            DRIVES: true,
            MODULATES: true,
            ASSOCIATED_WITH: true,
        };
        document.querySelectorAll('.filter-chip').forEach((c) => c.classList.add('active'));
        document.querySelectorAll('.filter-chip input').forEach((c) => (c.checked = true));
        applyFilters();
        clearSearch();
        clearDetails();
        document.getElementById('search-input').value = '';
        cy.animate({ fit: { eles: cy.elements(), padding: 40 }, duration: 500 });
    });

    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            clearSearch();
            clearDetails();
            if (cy) {
                cy.elements().unselect();
                cy.nodes().removeClass('highlighted');
            }
            document.getElementById('search-input').value = '';
        }
        if (e.ctrlKey && e.key === 'f') {
            e.preventDefault();
            document.getElementById('search-input').focus();
        }
    });
}

// ============================================
// Utilities
// ============================================

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ============================================
// Bootstrap
// ============================================

document.addEventListener('DOMContentLoaded', init);
