 const topicInput = document.getElementById('topic');
  const runBtn = document.getElementById('run-btn');
  const resultArea = document.getElementById('result-area');
  const manifestDate = document.getElementById('manifest-date');

  manifestDate.textContent = new Date().toLocaleDateString('fr-FR', {
    day: 'numeric', month: 'long', year: 'numeric'
  });

  document.querySelectorAll('.preset-chip').forEach(btn => {
    btn.addEventListener('click', () => {
      topicInput.value = btn.dataset.preset;
      topicInput.focus();
    });
  });

  async function checkStatus() {
    const dotMcp = document.getElementById('dot-mcp');
    const labelMcp = document.getElementById('label-mcp');
    const dotLlm = document.getElementById('dot-llm');
    const labelLlm = document.getElementById('label-llm');

    try {
      const res = await fetch('/api/status');
      const data = await res.json();

      dotMcp.className = 'dot ' + (data.mcp_connected ? 'ok' : 'bad');
      labelMcp.textContent = data.mcp_connected
        ? `MCP connecté (${(data.tools || []).length} outils)`
        : 'MCP indisponible';

      dotLlm.className = 'dot ' + (data.llm_connected ? 'ok' : 'bad');
      labelLlm.textContent = data.llm_connected ? 'LLM prêt' : 'LLM indisponible';
    } catch (e) {
      dotMcp.className = 'dot bad';
      labelMcp.textContent = 'Statut injoignable';
      dotLlm.className = 'dot bad';
      labelLlm.textContent = '—';
    }
  }

  function renderLoading() {
    resultArea.innerHTML = `
      <div class="loading-state">
        <span class="spinner"></span>
        <span>L'agent interroge les outils et rédige le rapport…</span>
      </div>`;
  }

  function renderError(message) {
    resultArea.innerHTML = `
      <div class="error-state">
        <h2>L'analyse a échoué</h2>
        <p>${escapeHtml(message)}</p>
      </div>`;
  }

  function renderReport(markdown) {
    const html = marked.parse(markdown || '_Rapport vide._');
    resultArea.innerHTML = `<div class="report">${html}</div>`;
  }

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  async function runAnalysis() {
    const topic = topicInput.value.trim();
    if (!topic) {
      topicInput.focus();
      return;
    }

    runBtn.disabled = true;
    runBtn.textContent = 'Analyse en cours…';
    renderLoading();

    try {
      const res = await fetch('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic })
      });
      const data = await res.json();

      if (!res.ok || data.error) {
        renderError(data.error || `Erreur serveur (${res.status})`);
      } else {
        renderReport(data.report);
      }
    } catch (e) {
      renderError('Connexion au serveur impossible. Vérifiez que l\'application est bien démarrée.');
    } finally {
      runBtn.disabled = false;
      runBtn.textContent = "Lancer l'analyse";
    }
  }

  runBtn.addEventListener('click', runAnalysis);
  topicInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) runAnalysis();
  });

  checkStatus();