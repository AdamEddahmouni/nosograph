document.addEventListener("DOMContentLoaded", () => {
  const genBtn = document.getElementById("generate-hyp-btn");
  const sendBtn = document.getElementById("send-chat-btn");
  const chatInput = document.getElementById("user-chat-input");
  const messagesContainer = document.getElementById("chat-messages");

  const apiKey = localStorage.getItem("med_research_api_key") || "";
  function getHeaders() {
    const headers = { "Content-Type": "application/json" };
    if (apiKey) headers["X-API-Key"] = apiKey;
    return headers;
  }

  function escapeHtml(text) {
    return String(text == null ? '' : text)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
  }

  function appendUserMessage(text) {
    const div = document.createElement("div");
    div.className = "chat-bubble chat-user";
    const strong = document.createElement("strong");
    strong.textContent = "You:";
    div.appendChild(strong);
    div.appendChild(document.createTextNode(" " + escapeHtml(text)));
    messagesContainer.appendChild(div);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
  }

  function appendAgentMessage(html) {
    const div = document.createElement("div");
    div.className = "chat-bubble chat-agent";
    const strong = document.createElement("strong");
    strong.textContent = "Translational Research Agent:";
    div.appendChild(strong);
    div.appendChild(document.createElement("br"));
    div.innerHTML += "<br>" + html;
    messagesContainer.appendChild(div);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
  }

  genBtn.addEventListener("click", async () => {
    const disease = document.getElementById("agent-disease").value;
    const gene = document.getElementById("target-gene").value.trim().toUpperCase();
    if (!gene) return;

    appendUserMessage(`Synthesize full target hypothesis dossier for ${gene} in ${disease}.`);

    try {
      const res = await fetch("/api/agent/hypothesis/generate", {
        method: "POST",
        headers: getHeaders(),
        body: JSON.stringify({ disease_id: disease, gene_symbol: gene }),
      });
      const data = await res.json();
      const h = data.hypothesis;

      const html = `
        <div class="agent-hyp">
          <div class="agent-hyp-head">
            <span class="agent-hyp-title">Target Hypothesis: ${h.target_gene} in ${h.disease_name}</span>
            <span class="agent-hyp-confidence">
              ${Math.round(h.overall_confidence * 100)}% Confidence
            </span>
          </div>

          <p class="agent-hyp-moa">
            ${h.mechanism_of_action_hypothesis}
          </p>

          <div style="margin-bottom:0.75rem;">
            <strong>Multi-Omics &amp; Relational Evidence:</strong>
            <ul class="agent-hyp-list">
              ${h.supporting_evidence.map(e => `
                <li>
                  <span class="badge-evidence">${e.source_type}</span>
                  ${e.description} <em>(${Math.round(e.confidence * 100)}% confidence)</em>
                </li>
              `).join('')}
            </ul>
          </div>

          <div class="agent-hyp-grid">
            <div>
              <strong>Druggability Assessment:</strong><br/>
              · Small Molecule: ${h.druggability_assessment.tractability_small_molecule}<br/>
              · Antibody / Biologic: ${h.druggability_assessment.tractability_antibody}
            </div>
            <div>
              <strong>Recommended Assays:</strong><br/>
              ${h.recommended_assays.slice(0, 2).map(a => `· ${a}`).join('<br/>')}
            </div>
          </div>
        </div>
      `;

      appendAgentMessage(html);
    } catch (err) {
      appendAgentMessage(`<span class="agent-error">Error: ${escapeHtml(err.message)}</span>`);
    }
  });

  async function handleSendChat() {
    const text = chatInput.value.trim();
    if (!text) return;
    chatInput.value = "";
    appendUserMessage(text);

    try {
      const res = await fetch("/api/agent/chat", {
        method: "POST",
        headers: getHeaders(),
        body: JSON.stringify({ query: text, disease_id: document.getElementById("agent-disease").value }),
      });
      const data = await res.json();
      appendAgentMessage(escapeHtml(data.answer).replace(/\n/g, "<br>"));
    } catch (err) {
      appendAgentMessage(`<span class="agent-error">Error: ${escapeHtml(err.message)}</span>`);
    }
  }

  sendBtn.addEventListener("click", handleSendChat);
  chatInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") handleSendChat();
  });
});
