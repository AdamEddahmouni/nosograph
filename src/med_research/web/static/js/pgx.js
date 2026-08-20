document.getElementById('submit-btn').addEventListener('click', async () => {
  const textarea = document.getElementById('genotype-input');
  const resultEl = document.getElementById('result');
  let payload;
  try {
    payload = JSON.parse(textarea.value);
  } catch (e) {
    resultEl.textContent = 'Invalid JSON: ' + e.message;
    return;
  }
  // Ensure payload is an object mapping gene -> array of alleles
  const body = { genotypes: payload };
  try {
    const resp = await fetch('/pgx/evaluate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!resp.ok) {
      const err = await resp.json();
      resultEl.textContent = 'Error: ' + (err.detail || resp.statusText);
      return;
    }
    const data = await resp.json();
    // Render nicely
    let out = '';
    data.forEach(item => {
      out += `${item.gene}: ${item.phenotype}\nDosing guidance: ${item.dosing_guidance}\n\n`;
    });
    resultEl.textContent = out.trim();
  } catch (e) {
    resultEl.textContent = 'Request failed: ' + e.message;
  }
});
