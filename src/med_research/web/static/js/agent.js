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

  function appendUserMessage(text) {
    const div = document.createElement("div");
    div.className = "chat-bubble chat-user";
    div.innerHTML = `<strong>You:</strong> ${text}`;
    messagesContainer.appendChild(div);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
  }

  function appendAgentMessage(html) {
    const div = document.createElement("div");
    div.className = "chat-bubble chat-agent";
    div.innerHTML = `<strong>Translational Research Agent:</strong><br/>${html}`;
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
        <div style="margin-top:0.5rem;">
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <span style="font-size:1.1rem;font-weight:700;color:#0284c7;">Target Hypothesis: ${h.target_gene} in ${h.disease_name}</span>
            <span style="background:#e0f2fe;color:#0369a1;padding:0.2rem 0.6rem;border-radius:9999px;font-weight:700;font-size:0.75rem;">
              ${Math.round(h.overall_confidence * 100)}% Confidence
            </span>
          </div>

          <p style="margin:0.5rem 0 0.75rem;color:#334155;background:#f8fafc;padding:0.75rem;border-radius:6px;border-left:3px solid #0284c7;">
            ${h.mechanism_of_action_hypothesis}
          </p>

          <div style="margin-bottom:0.75rem;">
            <strong>Multi-Omics & Relational Evidence:</strong>
            <ul style="margin:0.25rem 0;padding-left:1.2rem;">
              ${h.supporting_evidence.map(e => `
                <li>
                  <span class="badge-evidence">${e.source_type}</span>
                  ${e.description} <em>(${Math.round(e.confidence * 100)}% confidence)</em>
                </li>
              `).join('')}
            </ul>
          </div>

          <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.75rem;font-size:0.8rem;background:#f1f5f9;padding:0.75rem;border-radius:6px;margin-bottom:0.75rem;">
            <div>
              <strong>Druggability Assessment:</strong><br/>
              • Small Molecule: ${h.druggability_assessment.tractability_small_molecule}<br/>
              • Antibody / Biologic: ${h.druggability_assessment.tractability_antibody}
            </div>
            <div>
              <strong>Recommended Assays:</strong><br/>
              ${h.recommended_assays.slice(0, 2).map(a => `• ${a}`).join('<br/>')}
            </div>
          </div>
        </div>
      `;

      appendAgentMessage(html);
    } catch (err) {
      appendAgentMessage(`<span style="color:#dc2626;">Error: ${err.message}</span>`);
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
      appendAgentMessage(data.answer.replace(/\n/g, "<br/>"));
    } catch (err) {
      appendAgentMessage(`<span style="color:#dc2626;">Error: ${err.message}</span>`);
    }
  }

  sendBtn.addEventListener("click", handleSendChat);
  chatInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") handleSendChat();
  });
});
