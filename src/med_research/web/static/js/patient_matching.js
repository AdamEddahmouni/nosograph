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
      synthBtn.textContent = "Generate Random Synthetic Patient";
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
      <div class="sat-loading-box">
        <span class="spinner"></span>
        <p>Evaluating inclusion criteria, biomarker signatures, and travel distances…</p>
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
        resultsContainer.innerHTML = `<div class="sat-empty">No matching trials found for this research vector.</div>`;
        return;
      }

      resultsContainer.innerHTML = data.matches.map(m => `
        <div class="match-card">
          <div class="match-head">
            <div>
              <span class="eligible-badge ${m.is_eligible ? 'badge-pass' : 'badge-fail'}">
                ${m.is_eligible ? 'ELIGIBLE' : 'INELIGIBLE'}
              </span>
              <span class="match-id">${m.trial_id} (${m.phase})</span>
              <h4 class="match-title">${m.title}</h4>
            </div>
            <div class="sat-score">
              <div class="score-meter">${Math.round(m.overall_match_score * 100)}%</div>
              <div class="sat-score-lbl">Match Score</div>
            </div>
          </div>

          <div class="match-criteria">
            <div>
              <strong>Inclusion Criteria Met:</strong>
              <ul>
                ${m.inclusion_reasons && m.inclusion_reasons.length > 0 ? m.inclusion_reasons.map(r => `<li>${r}</li>`).join('') : '<li>Baseline criteria satisfied</li>'}
              </ul>
            </div>
            <div>
              <strong>Violations / Prohibitions:</strong>
              <ul class="${m.exclusion_violations && m.exclusion_violations.length > 0 ? 'violations' : 'clean'}">
                ${m.exclusion_violations && m.exclusion_violations.length > 0 ? m.exclusion_violations.map(v => `<li>${v}</li>`).join('') : '<li>None (Passed)</li>'}
              </ul>
            </div>
          </div>

          <div class="match-foot">
            <span>Estimated Site Proximity: <strong>${m.distance_km} km</strong></span>
            <span>Target Indication: <strong>${payload.disease.toUpperCase()}</strong></span>
          </div>
        </div>
      `).join("");
    } catch (err) {
      resultsContainer.innerHTML = `
        <div class="sat-error-box">
          <strong>Error running match:</strong> ${escapeHtml(err.message)}
        </div>
      `;
    }
  });
});
