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
      <div style="background:#fff;padding:2rem;text-align:center;border-radius:8px;border:1px solid #e2e8f0;">
        <span class="spinner" style="display:inline-block;width:24px;height:24px;border:3px solid #cbd5e1;border-top-color:#0284c7;border-radius:50%;animation:spin 1s linear infinite;"></span>
        <p style="margin-top:0.75rem;color:#64748b;">Computing physicochemical descriptors, CYP liabilities, and ADMET radar...</p>
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
        <div class="card" style="background:#fff;padding:1.5rem;border-radius:8px;border:1px solid #e2e8f0;">
          <div style="display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #f1f5f9;padding-bottom:1rem;">
            <div>
              <h3 style="margin:0;font-size:1.3rem;color:#0f172a;">${data.compound_name}</h3>
              <div style="font-family:monospace;font-size:0.8rem;color:#64748b;margin-top:0.25rem;word-break:break-all;">${data.smiles}</div>
            </div>
            <div style="text-align:right;">
              <div style="font-size:1.8rem;font-weight:800;color:${data.composite_score >= 70 ? '#16a34a' : (data.composite_score >= 50 ? '#d97706' : '#dc2626')};">
                ${data.composite_score}/100
              </div>
              <div style="font-size:0.75rem;color:#64748b;">Drug-Likeness Score</div>
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
          <div style="margin-top:1.5rem;background:#f8fafc;padding:1.25rem;border-radius:6px;">
            <h4 style="margin:0 0 1rem;font-size:0.95rem;color:#334155;">Multi-Objective ADMET Property Profile</h4>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;">
              ${Object.entries(data.admet_radar).map(([k, v]) => `
                <div>
                  <div style="display:flex;justify-content:space-between;font-size:0.8rem;">
                    <span>${k}</span>
                    <span style="font-weight:600;">${Math.round(v * 100)}%</span>
                  </div>
                  <div class="bar-outer">
                    <div class="bar-inner" style="width:${Math.round(v * 100)}%;background:${v > 0.5 ? '#0284c7' : '#e11d48'};"></div>
                  </div>
                </div>
              `).join('')}
            </div>
          </div>

          <!-- Toxicity Liabilities -->
          <div style="margin-top:1rem;display:grid;grid-template-columns:1fr 1fr 1fr;gap:0.75rem;font-size:0.85rem;">
            <div style="padding:0.75rem;border-radius:6px;background:${p.cyp3a4_inhibit ? '#fee2e2' : '#f0fdf4'};color:${p.cyp3a4_inhibit ? '#991b1b' : '#166534'};">
              <strong>CYP3A4 Inhibition:</strong> ${p.cyp3a4_inhibit ? '⚠️ Alert Detected' : '✓ Negative'}
            </div>
            <div style="padding:0.75rem;border-radius:6px;background:${p.cyp2d6_inhibit ? '#fee2e2' : '#f0fdf4'};color:${p.cyp2d6_inhibit ? '#991b1b' : '#166534'};">
              <strong>CYP2D6 Inhibition:</strong> ${p.cyp2d6_inhibit ? '⚠️ Alert Detected' : '✓ Negative'}
            </div>
            <div style="padding:0.75rem;border-radius:6px;background:${p.herg_risk ? '#fee2e2' : '#f0fdf4'};color:${p.herg_risk ? '#991b1b' : '#166534'};">
              <strong>hERG Cardiotox Risk:</strong> ${p.herg_risk ? '⚠️ High Liability' : '✓ Low Risk'}
            </div>
          </div>
        </div>
      `;
    } catch (err) {
      resultsContainer.innerHTML = `
        <div style="background:#fee2e2;color:#991b1b;padding:1rem;border-radius:8px;">
          <strong>Error analyzing molecule:</strong> ${err.message}
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
      <div style="background:#fff;padding:2rem;text-align:center;border-radius:8px;border:1px solid #e2e8f0;">
        <span class="spinner" style="display:inline-block;width:24px;height:24px;border:3px solid #cbd5e1;border-top-color:#0284c7;border-radius:50%;animation:spin 1s linear infinite;"></span>
        <p style="margin-top:0.75rem;color:#64748b;">Batch processing ${lines.length} candidate molecules...</p>
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
        <div class="card" style="background:#fff;padding:1.5rem;border-radius:8px;border:1px solid #e2e8f0;">
          <h3 style="margin-top:0;font-size:1.15rem;">Batch Screening Results (${data.passed_count} Passed / ${data.total_screened} Total)</h3>
          <table style="width:100%;border-collapse:collapse;margin-top:1rem;font-size:0.85rem;">
            <thead>
              <tr style="background:#f1f5f9;text-align:left;">
                <th style="padding:0.5rem;">Rank</th>
                <th style="padding:0.5rem;">SMILES</th>
                <th style="padding:0.5rem;">Score</th>
                <th style="padding:0.5rem;">MW</th>
                <th style="padding:0.5rem;">LogP</th>
                <th style="padding:0.5rem;">Lipinski</th>
                <th style="padding:0.5rem;">BBB</th>
              </tr>
            </thead>
            <tbody>
              ${data.ranked_candidates.map((c, idx) => `
                <tr style="border-bottom:1px solid #e2e8f0;">
                  <td style="padding:0.5rem;font-weight:700;">#${idx + 1}</td>
                  <td style="padding:0.5rem;font-family:monospace;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${c.smiles}</td>
                  <td style="padding:0.5rem;font-weight:700;color:${c.composite_score >= 70 ? '#16a34a' : '#d97706'};">${c.composite_score}</td>
                  <td style="padding:0.5rem;">${c.mw}</td>
                  <td style="padding:0.5rem;">${c.logp}</td>
                  <td style="padding:0.5rem;">${c.lipinski_pass ? '✓' : '✗'}</td>
                  <td style="padding:0.5rem;">${c.bbb_pass ? '✓' : '✗'}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      `;
    } catch (err) {
      resultsContainer.innerHTML = `<div style="background:#fee2e2;color:#991b1b;padding:1rem;border-radius:8px;">${err.message}</div>`;
    }
  });
});
