document.addEventListener("DOMContentLoaded", () => {
  const evalBtn = document.getElementById("eval-lead-btn");
  const batchBtn = document.getElementById("eval-batch-btn");
  const resultsContainer = document.getElementById("lead-results-container");

  const apiKey = localStorage.getItem("med_research_api_key") || "";
  function getHeaders() {
    const headers = { "Content-Type": "application/json" };
    if (apiKey) headers["X-API-Key"] = apiKey;
    return headers;
  }

  // Presets
  document.getElementById("preset-vemurafenib").addEventListener("click", () => {
    document.getElementById("compound-name").value = "Vemurafenib";
    document.getElementById("smiles-input").value = "CCCS(=O)(=O)NC1=C(C(=C(C=C1)F)C(=O)C2=CNC3=NC=C(C=C23)C4=CC=C(C=C4)Cl)F";
  });

  document.getElementById("preset-osimertinib").addEventListener("click", () => {
    document.getElementById("compound-name").value = "Osimertinib";
    document.getElementById("smiles-input").value = "CN1CCN(CC1)C2=CC(=C(C=C2)NC(=O)C=C)NC3=NC=CC(=N3)C4=CN(C5=CC=CC=C54)C";
  });

  document.getElementById("preset-temozolomide").addEventListener("click", () => {
    document.getElementById("compound-name").value = "Temozolomide";
    document.getElementById("smiles-input").value = "CN1C(=O)N2C=NC(=C2N=N1)C(=O)N";
  });

  evalBtn.addEventListener("click", async () => {
    const smiles = document.getElementById("smiles-input").value.trim();
    const name = document.getElementById("compound-name").value.trim();
    if (!smiles) {
      alert("Please enter a SMILES string.");
      return;
    }

    resultsContainer.innerHTML = `
      <div class="sat-loading-box">
        <span class="spinner"></span>
        <p>Computing physicochemical descriptors, CYP liabilities, and ADMET radar…</p>
      </div>
    `;

    try {
      const res = await fetch("/api/lead-opt/analyze", {
        method: "POST",
        headers: getHeaders(),
        body: JSON.stringify({ smiles: smiles, compound_name: name }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Analysis failed");
      }

      const data = await res.json();
      const p = data.properties;

      resultsContainer.innerHTML = `
        <div class="sat-result-card">
          <div class="sat-result-head">
            <div>
              <h3 class="sat-result-name">${data.compound_name}</h3>
              <div class="sat-result-sub">${data.smiles}</div>
            </div>
            <div class="sat-score">
              <div class="sat-score-val ${data.composite_score >= 70 ? 'good' : (data.composite_score >= 50 ? 'mid' : 'bad')}">
                ${data.composite_score}/100
              </div>
              <div class="sat-score-lbl">Drug-Likeness Score</div>
            </div>
          </div>

          <!-- Key Descriptors -->
          <div class="metric-grid">
            <div class="metric-box">
              <div class="val">${p.mw}</div>
              <div class="lbl">Mol Wt (g/mol)</div>
            </div>
            <div class="metric-box">
              <div class="val">${p.logp}</div>
              <div class="lbl">LogP</div>
            </div>
            <div class="metric-box">
              <div class="val">${p.hbd} / ${p.hba}</div>
              <div class="lbl">HBD / HBA</div>
            </div>
            <div class="metric-box">
              <div class="val ${p.lipinski_pass ? 'pass-tag' : 'fail-tag'}">${p.lipinski_pass ? 'PASS' : 'FAIL'}</div>
              <div class="lbl">Lipinski Rule of 5</div>
            </div>
            <div class="metric-box">
              <div class="val ${p.bbb_pass ? 'pass-tag' : 'fail-tag'}">${p.bbb_pass ? 'YES' : 'NO'}</div>
              <div class="lbl">BBB Permeable</div>
            </div>
            <div class="metric-box">
              <div class="val">${p.sa_score ? p.sa_score : 'N/A'}</div>
              <div class="lbl">Synth Access (1-10)</div>
            </div>
          </div>

          <!-- ADMET Radar Bars -->
          <div class="sat-panel">
            <h4>Multi-Objective ADMET Property Profile</h4>
            <div class="sat-panel-grid">
              ${Object.entries(data.admet_radar).map(([k, v]) => `
                <div>
                  <div class="sat-bar-row">
                    <span>${k}</span>
                    <span class="num">${Math.round(v * 100)}%</span>
                  </div>
                  <div class="bar-outer">
                    <div class="bar-inner ${v > 0.5 ? '' : 'risk'}" style="width:${Math.round(v * 100)}%;"></div>
                  </div>
                </div>
              `).join('')}
            </div>
          </div>

          <!-- Toxicity Liabilities -->
          <div class="sat-alert-grid">
            <div class="sat-alert ${p.cyp3a4_inhibit ? 'warn' : 'ok'}">
              <strong>CYP3A4 Inhibition:</strong> ${p.cyp3a4_inhibit ? 'Alert detected' : 'Negative'}
            </div>
            <div class="sat-alert ${p.cyp2d6_inhibit ? 'warn' : 'ok'}">
              <strong>CYP2D6 Inhibition:</strong> ${p.cyp2d6_inhibit ? 'Alert detected' : 'Negative'}
            </div>
            <div class="sat-alert ${p.herg_risk ? 'warn' : 'ok'}">
              <strong>hERG Cardiotox Risk:</strong> ${p.herg_risk ? 'High liability' : 'Low risk'}
            </div>
          </div>
        </div>
      `;
    } catch (err) {
      resultsContainer.innerHTML = `
        <div class="sat-error-box">
          <strong>Error analyzing molecule:</strong> ${escapeHtml(err.message)}
        </div>
      `;
    }
  });

  batchBtn.addEventListener("click", async () => {
    const raw = document.getElementById("batch-smiles-input").value;
    const lines = raw.split("\n").map(s => s.trim()).filter(Boolean);
    if (lines.length === 0) {
      alert("Please paste at least one SMILES string.");
      return;
    }

    resultsContainer.innerHTML = `
      <div class="sat-loading-box">
        <span class="spinner"></span>
        <p>Batch processing ${lines.length} candidate molecules…</p>
      </div>
    `;

    try {
      const res = await fetch("/api/lead-opt/batch-screen", {
        method: "POST",
        headers: getHeaders(),
        body: JSON.stringify({ smiles_list: lines }),
      });
      const data = await res.json();

      resultsContainer.innerHTML = `
        <div class="sat-result-card">
          <h3 class="sat-result-name">Batch Screening Results (${data.passed_count} Passed / ${data.total_screened} Total)</h3>
          <table class="sat-table">
            <thead>
              <tr>
                <th>Rank</th>
                <th>SMILES</th>
                <th>Score</th>
                <th>MW</th>
                <th>LogP</th>
                <th>Lipinski</th>
                <th>BBB</th>
              </tr>
            </thead>
            <tbody>
              ${data.ranked_candidates.map((c, idx) => `
                <tr>
                  <td class="num">#${idx + 1}</td>
                  <td class="mono" title="${c.smiles}">${c.smiles}</td>
                  <td class="num ${c.composite_score >= 70 ? 'good' : 'mid'}">${c.composite_score}</td>
                  <td>${c.mw}</td>
                  <td>${c.logp}</td>
                  <td class="${c.lipinski_pass ? 'pass-tag' : 'fail-tag'}">${c.lipinski_pass ? 'PASS' : 'FAIL'}</td>
                  <td class="${c.bbb_pass ? 'pass-tag' : 'fail-tag'}">${c.bbb_pass ? 'YES' : 'NO'}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      `;
    } catch (err) {
      resultsContainer.innerHTML = `<div class="sat-error-box">${escapeHtml(err.message)}</div>`;
    }
  });
});
