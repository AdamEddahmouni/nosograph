document.addEventListener("DOMContentLoaded", () => {
  const canvas = document.getElementById("spatial-canvas");
  const ctx = canvas.getContext("2d");
  const loadBtn = document.getElementById("load-spatial-btn");
  const radiusSlider = document.getElementById("spatial-radius");
  const radiusVal = document.getElementById("radius-val");
  const spotInfo = document.getElementById("spot-info");
  const moranScore = document.getElementById("moran-score");
  const moranPattern = document.getElementById("moran-pattern");
  const lrScore = document.getElementById("lr-score");
  const lrDensity = document.getElementById("lr-density");

  const apiKey = localStorage.getItem("med_research_api_key") || "";
  function getHeaders() {
    const headers = { "Content-Type": "application/json" };
    if (apiKey) headers["X-API-Key"] = apiKey;
    return headers;
  }

  let currentSpots = [];
  let hoveredSpot = null;

  radiusSlider.addEventListener("input", (e) => {
    radiusVal.textContent = `${e.target.value} μm`;
  });

  function getExpressionColor(val, min = 0, max = 6) {
    const ratio = Math.max(0, Math.min(1, (val - min) / (max - min)));
    if (ratio < 0.5) {
      // Blue to Yellow
      const r = Math.round(ratio * 2 * 234 + (1 - ratio * 2) * 59);
      const g = Math.round(ratio * 2 * 179 + (1 - ratio * 2) * 130);
      const b = Math.round(ratio * 2 * 8 + (1 - ratio * 2) * 246);
      return `rgb(${r}, ${g}, ${b})`;
    } else {
      // Yellow to Red
      const r = Math.round((ratio - 0.5) * 2 * 239 + (1 - (ratio - 0.5) * 2) * 234);
      const g = Math.round((ratio - 0.5) * 2 * 68 + (1 - (ratio - 0.5) * 2) * 179);
      const b = Math.round((ratio - 0.5) * 2 * 68 + (1 - (ratio - 0.5) * 2) * 8);
      return `rgb(${r}, ${g}, ${b})`;
    }
  }

  function renderSpots(activeGene) {
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Draw dark background grid lines
    ctx.strokeStyle = "#1e293b";
    ctx.lineWidth = 1;
    for (let x = 0; x < canvas.width; x += 40) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, canvas.height);
      ctx.stroke();
    }
    for (let y = 0; y < canvas.height; y += 40) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(canvas.width, y);
      ctx.stroke();
    }

    // Draw spots
    currentSpots.forEach(s => {
      const expr = (s.features && s.features[activeGene]) || 0;
      const color = getExpressionColor(expr);
      const isHovered = hoveredSpot && hoveredSpot.barcode === s.barcode;

      ctx.beginPath();
      ctx.arc(s.x, s.y, isHovered ? 11 : 7, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.fill();
      ctx.strokeStyle = isHovered ? "#ffffff" : "#0f172a";
      ctx.lineWidth = isHovered ? 2.5 : 1;
      ctx.stroke();
    });
  }

  canvas.addEventListener("mousemove", (e) => {
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;

    hoveredSpot = currentSpots.find(s => Math.hypot(s.x - mx, s.y - my) <= 9);
    if (hoveredSpot) {
      const g = document.getElementById("primary-gene").value;
      const expr = (hoveredSpot.features && hoveredSpot.features[g]) || 0;
      spotInfo.innerHTML = `<strong>${hoveredSpot.barcode}</strong> (${hoveredSpot.region}) | ${g}: <span style="color:#0284c7;font-weight:700;">${expr}</span> | (x: ${hoveredSpot.x}, y: ${hoveredSpot.y})`;
    } else {
      spotInfo.textContent = "Hover over spots for barcode & coordinates";
    }
    renderSpots(document.getElementById("primary-gene").value);
  });

  loadBtn.addEventListener("click", async () => {
    const disease = document.getElementById("spatial-disease").value;
    const gene = document.getElementById("primary-gene").value;
    const lig = document.getElementById("ligand-gene").value;
    const rec = document.getElementById("receptor-gene").value;
    const radius = parseFloat(document.getElementById("spatial-radius").value);

    try {
      loadBtn.disabled = true;
      loadBtn.textContent = "Loading...";

      // 1. Fetch sample spots
      const res = await fetch(`/api/spatial/sample-data?disease=${disease}&num_spots=160`, {
        headers: getHeaders(),
      });
      const data = await res.json();
      currentSpots = data.spots || [];

      // 2. Run Moran's I & Ligand-Receptor calculation
      const calcRes = await fetch("/api/spatial/analyze", {
        method: "POST",
        headers: getHeaders(),
        body: JSON.stringify({
          spots: currentSpots,
          gene: gene,
          ligand_gene: lig,
          receptor_gene: rec,
          radius: radius,
        }),
      });
      const metrics = await calcRes.json();

      moranScore.textContent = metrics.morans_i_score;
      moranPattern.textContent = metrics.spatial_pattern;
      lrScore.textContent = metrics.ligand_receptor_interaction.colocalization_score;
      lrDensity.textContent = `${metrics.ligand_receptor_interaction.interaction_density} (${lig} ↔ ${rec})`;

      renderSpots(gene);
    } catch (err) {
      console.error("Spatial fetch failed", err);
      alert("Failed to load spatial data: " + err.message);
    } finally {
      loadBtn.disabled = false;
      loadBtn.textContent = "🔬 Load & Compute Spatial Metrics";
    }
  });

  // Trigger initial load
  loadBtn.click();
});
