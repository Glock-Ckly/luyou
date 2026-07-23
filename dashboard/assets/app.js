const page = document.body.dataset.page;
const routes = [
  ['overview', 'index.html', '总览'],
  ['routing', 'routing.html', '路由实验室'],
  ['providers', 'providers.html', 'Provider'],
  ['reliability', 'reliability.html', '可靠性'],
  ['architecture', 'architecture.html', '架构规格'],
];

function el(tag, className = '', text = null) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== null) node.textContent = String(text);
  return node;
}

function setText(id, value) {
  const node = document.getElementById(id);
  if (node) node.textContent = value ?? '—';
}

function badge(text, tone = 'green') {
  return el('span', 'badge ' + tone, text);
}

function apiHeaders(extra = {}) {
  const token = localStorage.getItem('model_router_api_token');
  return {...extra, ...(token ? {Authorization: 'Bearer ' + token} : {})};
}

async function api(path, options = {}) {
  const response = await fetch(path, {...options, headers: apiHeaders(options.headers)});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error?.message || data.error || response.statusText);
  return data;
}

function mountChrome() {
  const header = document.querySelector('[data-header]');
  const footer = document.querySelector('[data-footer]');
  if (header) {
    header.className = 'topbar';
    const nav = el('div', 'shell nav');
    const brand = el('a', 'brand');
    brand.href = 'index.html';
    brand.append(el('span', 'brand-mark', 'L'), el('span', '', 'luyou / model router'));
    const links = el('nav', 'nav-links');
    routes.forEach(([id, href, label]) => {
      const link = el('a', id === page ? 'active' : '', label);
      link.href = href;
      links.append(link);
    });
    nav.append(brand, links, el('div', 'nav-state', 'Router online'));
    header.append(nav);
  }
  if (footer) {
    footer.className = 'footer';
    const row = el('div', 'shell footer-row');
    row.append(el('span', '', 'Specification → DDD → Contract → TDD → Implementation'), el('span', '', '本地 Demo · 不展示密钥与完整 Prompt'));
    footer.append(row);
  }
}

function renderTimeline(container, items) {
  container.replaceChildren();
  if (!items?.length) {
    container.append(el('div', 'empty', '尚无执行事件。'));
    return;
  }
  items.forEach((item) => {
    const status = item.status === 'failed' || item.error_type ? 'failed' : item.status === 'running' ? 'running' : 'success';
    const row = el('div', 'timeline-item ' + status);
    row.append(el('span', 'timeline-dot'));
    const content = el('div', 'timeline-content');
    const detail = item.detail || [item.action, item.error_type, item.latency_ms ? item.latency_ms + ' ms' : ''].filter(Boolean).join(' · ');
    content.append(el('strong', '', item.phase || item.model || item.kind || 'event'), el('span', '', detail));
    row.append(content);
    container.append(row);
  });
}

function showToast(message) {
  const toast = document.querySelector('.toast');
  if (!toast) return;
  toast.textContent = message;
  toast.classList.add('show');
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => toast.classList.remove('show'), 2600);
}

async function initOverview() {
  const [meta, catalog, metrics] = await Promise.all([api('/api/meta'), api('/api/catalog'), api('/api/metrics')]);
  setText('metric-providers', meta.stats.providers);
  setText('metric-models', meta.stats.models);
  setText('metric-routes', meta.stats.routes);
  setText('metric-requests', metrics.metrics.requests);
  setText('metric-successes', metrics.metrics.successes);
  setText('metric-fallbacks', metrics.metrics.fallbacks);
  setText('metric-latency', metrics.metrics.provider_latency_ms + ' ms');
  setText('git-state', meta.git.branch + ' · ' + meta.git.commit);
  setText('catalog-summary', catalog.providers.length + ' 个 Provider，' + catalog.models.length + ' 个模型，全部来自运行时代码目录。');
  renderTimeline(document.getElementById('recent-events'), metrics.events.slice(-8).reverse());
}

async function initRouting() {
  const meta = await api('/api/meta');
  document.getElementById('route-workdir').value = meta.project_path;
  document.getElementById('route-submit').addEventListener('click', async () => {
    const button = document.getElementById('route-submit');
    const prompt = document.getElementById('route-prompt').value.trim();
    if (!prompt) return showToast('请先输入任务描述');
    button.disabled = true;
    renderTimeline(document.getElementById('route-timeline'), [{phase: 'dispatch', detail: '正在分类、路由并执行', status: 'running'}]);
    try {
      const data = await api('/api/route', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({prompt, workdir: document.getElementById('route-workdir').value}),
      });
      setText('route-trace', data.trace_id);
      setText('route-task', data.task_type);
      setText('route-model', data.selected_model);
      setText('route-executor', data.selected_executor);
      setText('route-result', data.result);
      const attempts = data.subtasks.flatMap((task) => task.attempts || []);
      renderTimeline(document.getElementById('route-timeline'), [...data.timeline, ...attempts]);
      const grid = document.getElementById('route-subtasks');
      grid.replaceChildren();
      data.subtasks.forEach((task) => {
        const card = el('article', 'card');
        card.append(el('p', 'eyebrow', 'Subtask ' + (task.index + 1)), el('h3', '', task.task_type), el('p', 'card-muted', task.prompt), el('p', '', task.model + ' · ' + task.executor), badge(task.success ? 'success' : 'failed', task.success ? 'green' : 'red'));
        grid.append(card);
      });
    } catch (error) {
      renderTimeline(document.getElementById('route-timeline'), [{phase: 'error', detail: error.message, status: 'failed'}]);
    } finally {
      button.disabled = false;
    }
  });
}

async function initProviders() {
  const catalog = await api('/api/catalog');
  const grid = document.getElementById('provider-grid');
  grid.replaceChildren();
  catalog.providers.forEach((provider) => {
    const card = el('article', 'card');
    const head = el('div', 'provider-head');
    head.append(el('div', '', provider.name), badge(provider.status, provider.status === 'available' ? 'green' : 'red'));
    card.append(head, el('p', 'card-muted', provider.health_detail));
    const table = el('table', 'model-table');
    table.innerHTML = '<thead><tr><th>模型</th><th>层级</th><th>成本/Mtok</th><th>路由引用</th></tr></thead>';
    const body = el('tbody');
    provider.models.forEach((model) => {
      const row = el('tr');
      [model.name, model.tier, '$' + model.cost_per_mtok, model.route_usage].forEach((value) => row.append(el('td', '', value)));
      body.append(row);
    });
    table.append(body);
    card.append(table);
    grid.append(card);
  });
}

async function initReliability() {
  document.getElementById('reliability-run').addEventListener('click', async () => {
    const taskType = document.getElementById('failure-task').value;
    const baseline = await api('/api/reliability/simulate', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({task_type: taskType, complexity: 'T2'})});
    const payload = {task_type: taskType, complexity: 'T2', failure_mode: document.getElementById('failure-mode').value, retry_once: true, failed_models: [baseline.candidate_chain[0]]};
    const data = await api('/api/reliability/simulate', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)});
    setText('reliability-trace', data.trace_id);
    setText('reliability-outcome', data.outcome);
    setText('reliability-model', data.selected_model || '无');
    setText('reliability-error', data.final_error_type || '无');
    renderTimeline(document.getElementById('reliability-timeline'), data.attempts);
  });
}

async function initArchitecture() {
  const specs = await api('/api/specs');
  const domains = document.getElementById('domain-grid');
  specs.domains.forEach((domain) => {
    const card = el('article', 'card domain-card');
    card.append(el('div', 'domain-name', domain.name), el('h3', '', '负责'), el('p', 'card-muted', domain.owns), el('h3', '', '不负责'), el('p', 'card-muted', domain.excludes));
    domains.append(card);
  });
  specs.quality_gates.forEach((gate) => document.getElementById('quality-gates').append(el('li', '', gate)));
}

mountChrome();
({overview: initOverview, routing: initRouting, providers: initProviders, reliability: initReliability, architecture: initArchitecture}[page] || (() => {}))().catch((error) => showToast(error.message));
