document.addEventListener("DOMContentLoaded", () => {
  const matchBtn = document.getElementById("run-matching-btn");
  const synthBtn = document.getElementById("synth-cohort-btn");
  const resultsContainer = document.getElementById("results-container");
  const summaryDiv = document.getElementById("matching-summary");

  // Get API key from localStorage or URL if present
  const apiKey = localStorage.getItem("med_research_api_key") || "";

  function getHeaders() {
    const headers = { "Content-Type": "application/json" };
    if (apiKey) headers["X-API-Key"] = apiKey;
    return headers;
  }

  synthBtn.addEventListener("click", async () => {
    const disease = document.getElementById("patient-disease").value;
    try {
      synthBtn.disabled = true;
      synthBtn.textContent = "Generating...";
      const res = await fetch("/api/matching/generate-cohort", {
        method: "POST",
        headers: getHeaders(),
        body: JSON.stringify({ num_patients: 1, disease: disease }),
      });
      const data = await res.json();
      if (data.cohort && data.cohort.length > 0) {
        const pt = data.cohort[0];
        document.getElementById("patient-id").value = pt.patient_id || `PT-${Math.floor(Math.random()*9000+1000)}`;
        document.getElementById("patient-age").value = pt.age || 50;
        document.getElementById("patient-sex").value = pt.sex || "F";
        document.getElementById("patient-ecog").value = pt.ecog_score ?? 1;
        document.getElementById("patient-biomarkers").value = JSON.stringify(pt.biomarkers || {}, null, 2);
        document.getElementById("patient-prior-tx").value = (pt.prior_therapies || []).join(", ");
      }
    } catch (err) {
      console.error("Synthetic generator failed", err);
    } finally {
      synthBtn.disabled = false;
      synthBtn.textContent = "🎲 Generate Random Synthetic Patient";
    }
  });

  matchBtn.addEventListener("click", async () => {
    let biomarkers = {};
    try {
      biomarkers = JSON.parse(document.getElementById("patient-biomarkers").value);
    } catch (e) {
      alert("Invalid JSON in biomarkers field");
      return;
    }

    const priorTx = document.getElementById("patient-prior-tx").value
      .split(",")
      .map(s => s.trim())
      .filter(Boolean);

    const payload = {
      patient_id: document.getElementById("patient-id").value,
      age: parseInt(document.getElementById("patient-age").value, 10),
      sex: document.getElementById("patient-sex").value,
      disease: document.getElementById("patient-disease").value,
      stage: "III",
      biomarkers: biomarkers,
      prior_therapies: priorTx,
      ecog_score: parseInt(document.getElementById("patient-ecog").value, 10),
      location_lat: 37.7749,
      location_lon: -122.4194,
    };

    resultsContainer.innerHTML = `
      <div style="background:#fff;padding:2rem;text-align:center;border-radius:8px;border:1px solid #e2e8f0;">
        <span class="spinner" style="display:inline-block;width:24px;height:24px;border:3px solid #cbd5e1;border-top-color:#0284c7;border-radius:50%;animation:spin 1s linear infinite;"></span>
        <p style="margin-top:0.75rem;color:#64748b;">Evaluating inclusion criteria, biomarker signatures, and travel distances...</p>
      </div>
    `;

    try {
      const res = await fetch("/api/matching/match", {
        method: "POST",
        headers: getHeaders(),
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Matching failed");
      }

      const data = await res.json();
      summaryDiv.textContent = `Found ${data.eligible_trials_count} eligible of ${data.total_trials_evaluated} candidate protocols`;

      if (!data.matches || data.matches.length === 0) {
        resultsContainer.innerHTML = `<div style="background:#fff;padding:1.5rem;border-radius:8px;">No matching trials found.</div>`;
        return;
      }

      resultsContainer.innerHTML = data.matches.map(m => `
        <div class="match-card">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;">
            <div>
              <span class="eligible-badge ${m.is_eligible ? 'badge-pass' : 'badge-fail'}">
                ${m.is_eligible ? '✓ ELIGIBLE' : '✕ INELIGIBLE'}
              </span>
              <span style="margin-left:0.5rem;font-weight:600;color:#64748b;font-size:0.85rem;">${m.trial_id} (${m.phase})</span>
              <h4 style="margin:0.5rem 0 0.25rem;font-size:1.05rem;color:#0f172a;">${m.title}</h4>
            </div>
            <div style="text-align:right;">
              <div class="score-meter">${Math.round(m.overall_match_score * 100)}%</div>
              <div style="font-size:0.75rem;color:#64748b;">Match Score</div>
            </div>
          </div>

          <div style="margin-top:0.75rem;font-size:0.85rem;color:#475569;display:grid;grid-template-columns:1fr 1fr;gap:0.5rem;background:#f8fafc;padding:0.75rem;border-radius:6px;">
            <div>
              <strong>Inclusion Criteria Met:</strong>
              <ul style="margin:0.25rem 0 0;padding-left:1.2rem;">
                ${m.inclusion_reasons && m.inclusion_reasons.length > 0 ? m.inclusion_reasons.map(r => `<li>${r}</li>`).join('') : '<li>Baseline criteria satisfied</li>'}
              </ul>
            </div>
            <div>
              <strong>Violations / Prohibitions:</strong>
              <ul style="margin:0.25rem 0 0;padding-left:1.2rem;color:${m.exclusion_violations && m.exclusion_violations.length > 0 ? '#b91c1c' : '#15803d'};">
                ${m.exclusion_violations && m.exclusion_violations.length > 0 ? m.exclusion_violations.map(v => `<li>${v}</li>`).join('') : '<li>None (Passed)</li>'}
              </ul>
            </div>
          </div>

          <div style="margin-top:0.5rem;font-size:0.8rem;color:#64748b;display:flex;justify-content:space-between;">
            <span>Estimated Site Proximity: <strong>${m.distance_km} km</strong></span>
            <span>Target Indication: <strong>${payload.disease.toUpperCase()}</strong></span>
          </div>
        </div>
      `).join("");
    } catch (err) {
      resultsContainer.innerHTML = `
        <div style="background:#fee2e2;color:#991b1b;padding:1rem;border-radius:8px;">
          <strong>Error running match:</strong> ${err.message}
        </div>
      `;
    }
  });
});
