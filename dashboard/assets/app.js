const page = document.body.dataset.page;

const routes = [
  ['overview', 'index.html', '总览'],
  ['routing', 'routing.html', '路由实验室'],
  ['providers', 'providers.html', 'Provider'],
  ['reliability', 'reliability.html', '可靠性'],
  ['architecture', 'architecture.html', '架构规格'],
];

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}

function badge(text, tone = 'green') {
  return el('span', 'badge ' + tone, text);
}

function formatModel(model) {
  return model ? model.replace('/', ' / ') : '—';
}

async function api(path, options) {
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || response.statusText);
  return data;
}

function showToast(message) {
  const toast = document.querySelector('.toast');
  if (!toast) return;
  toast.textContent = message;
  toast.classList.add('show');
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => toast.classList.remove('show'), 2600);
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
      links.appendChild(link);
    });
    nav.append(brand, links, el('div', 'nav-state', 'Router online'));
    header.appendChild(nav);
  }
  if (footer) {
    footer.className = 'footer';
    const row = el('div', 'shell footer-row');
    row.append(el('span', '', 'AI Model Router · Specification → Domain → Test → Implementation'), el('span', '', 'Local demo · no secrets exposed'));
    footer.appendChild(row);
  }
}

function setText(id, value) {
  const node = document.getElementById(id);
  if (node) node.textContent = value ?? '—';
}

function renderTimeline(container, items) {
  container.replaceChildren();
  if (!items || !items.length) {
    container.appendChild(el('div', 'empty', '等待一次真实路由或可靠性演练。'));
    return;
  }
  items.forEach((item) => {
    const status = item.status || (item.error_type ? 'failed' : 'success');
    const row = el('div', 'timeline-item ' + status);
    row.appendChild(el('span', 'timeline-dot'));
    const content = el('div', 'timeline-content');
    const title = item.phase || item.model || 'step';
    content.append(el('strong', '', title), el('span', '', item.detail || [item.error_type, item.action, item.latency_ms ? item.latency_ms + ' ms' : ''].filter(Boolean).join(' · ')));
    row.appendChild(content);
    container.appendChild(row);
  });
}

async function initOverview() {
  const [meta, catalog] = await Promise.all([api('/api/meta'), api('/api/catalog')]);
  setText('metric-providers', meta.stats.providers);
  setText('metric-models', meta.stats.models);
  setText('metric-routes', meta.stats.routes);
  setText('metric-budget', Math.round(meta.budget_ratio * 100) + '%');
  setText('git-state', meta.git.branch + ' · ' + meta.git.commit);
  setText('catalog-summary', catalog.policies.length + ' 类任务策略，' + catalog.providers.length + ' 个 Provider，全部来自运行时代码目录。');
}

async function initRouting() {
  const meta = await api('/api/meta');
  const workdir = document.getElementById('route-workdir');
  workdir.value = meta.project_path;
  setText('route-git', meta.git.branch + ' · ' + meta.git.commit);

  const button = document.getElementById('route-submit');
  button.addEventListener('click', async () => {
    const prompt = document.getElementById('route-prompt').value.trim();
    if (!prompt) return showToast('请先输入任务描述');
    button.disabled = true;
    button.textContent = '正在路由…';
    renderTimeline(document.getElementById('route-timeline'), [{phase: 'dispatch', detail: '分类器与规划器正在处理任务。', status: 'running'}]);
    try {
      const data = await api('/api/route', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({prompt, workdir: workdir.value.trim() || undefined}),
      });
      setText('route-task', data.task_type);
      setText('route-complexity', data.complexity);
      setText('route-model', formatModel(data.selected_model));
      setText('route-executor', data.selected_executor);
      renderTimeline(document.getElementById('route-timeline'), data.timeline || []);
      document.getElementById('route-result').textContent = data.result || '(空结果)';
      const subtasks = document.getElementById('route-subtasks');
      subtasks.replaceChildren();
      (data.subtasks || []).forEach((task) => {
        const card = el('div', 'card');
        const head = el('div', 'provider-head');
        head.append(el('strong', '', task.task_type || 'subtask'), badge(task.status || 'planned', task.status === 'error' ? 'red' : 'blue'));
        card.append(head, el('p', 'card-muted', task.prompt || task.instruction || ''), el('div', 'pill', formatModel(task.model || task.selected_model || task.executor)));
        subtasks.appendChild(card);
      });
      if (!(data.subtasks || []).length) subtasks.appendChild(el('div', 'empty', '本次任务没有拆分子任务。'));
      if (data.selected_executor === 'cursor_queue' || ['code_patch', 'file_edit'].includes(data.task_type)) {
        const queue = await api('/api/cursor/queue');
        setText('queue-count', queue.pending.length);
      } else {
        setText('queue-count', '0');
      }
      showToast('路由完成');
    } catch (error) {
      renderTimeline(document.getElementById('route-timeline'), [{phase: 'error', detail: error.message, status: 'failed'}]);
      document.getElementById('route-result').textContent = '分发失败：' + error.message;
    } finally {
      button.disabled = false;
      button.textContent = '分发任务';
    }
  });
}

async function initProviders() {
  const catalog = await api('/api/catalog');
  setText('provider-count', catalog.providers.length);
  setText('model-count', catalog.models.length);
  const root = document.getElementById('provider-grid');
  catalog.providers.forEach((provider) => {
    const card = el('article', 'card');
    const head = el('div', 'provider-head');
    head.append(el('div', '', provider.name), badge(provider.status, 'green'));
    card.appendChild(head);
    const table = el('table', 'model-table');
    const thead = el('thead');
    const hr = el('tr');
    ['Model', 'Tier', '$ / MTok In', '$ / MTok Out', 'Routes'].forEach((label) => hr.appendChild(el('th', '', label)));
    thead.appendChild(hr);
    const tbody = el('tbody');
    provider.models.forEach((model) => {
      const row = el('tr');
      row.append(el('td', '', model.name), el('td', '', model.tier), el('td', 'cost', model.cost_per_mtok.in), el('td', 'cost', model.cost_per_mtok.out), el('td', '', model.route_usage));
      tbody.appendChild(row);
    });
    table.append(thead, tbody);
    card.appendChild(table);
    root.appendChild(card);
  });
  const contract = document.getElementById('provider-contract');
  catalog.provider_contract.forEach((item) => contract.appendChild(el('li', '', item)));
}

async function initReliability() {
  const catalog = await api('/api/catalog');
  const taskSelect = document.getElementById('reliability-task');
  catalog.policies.forEach((policy) => {
    const option = el('option', '', policy.task_type);
    option.value = policy.task_type;
    taskSelect.appendChild(option);
  });
  const models = document.getElementById('failed-models');
  catalog.models.forEach((model, index) => {
    const label = el('label', 'pill');
    label.style.textTransform = 'none';
    label.style.letterSpacing = '0';
    const checkbox = el('input');
    checkbox.type = 'checkbox';
    checkbox.value = model.id;
    checkbox.style.width = 'auto';
    checkbox.style.height = 'auto';
    if (index === 0) checkbox.checked = true;
    label.append(checkbox, document.createTextNode(model.name));
    models.appendChild(label);
  });

  const budget = document.getElementById('reliability-budget');
  const budgetOutput = document.getElementById('budget-output');
  budget.addEventListener('input', () => budgetOutput.textContent = Math.round(Number(budget.value) * 100) + '%');

  document.getElementById('reliability-submit').addEventListener('click', async (event) => {
    const button = event.currentTarget;
    button.disabled = true;
    button.textContent = '演练中…';
    const failed = [...models.querySelectorAll('input:checked')].map((input) => input.value);
    try {
      const data = await api('/api/reliability/simulate', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          task_type: taskSelect.value,
          complexity: document.getElementById('reliability-complexity').value,
          budget_ratio: Number(budget.value),
          failure_mode: document.getElementById('failure-mode').value,
          retry_once: document.getElementById('retry-once').checked,
          failed_models: failed,
        }),
      });
      setText('trace-id', data.trace_id);
      setText('reliability-outcome', data.outcome);
      setText('reliability-selected', formatModel(data.selected_model));
      setText('candidate-chain', data.candidate_chain.map(formatModel).join('  →  '));
      renderTimeline(document.getElementById('reliability-timeline'), data.attempts);
      showToast(data.outcome === 'success' ? 'Fallback 演练成功' : '全部候选均失败');
    } catch (error) {
      showToast(error.message);
    } finally {
      button.disabled = false;
      button.textContent = '运行故障演练';
    }
  });
}

async function initArchitecture() {
  const specs = await api('/api/specs');
  const domains = document.getElementById('domain-grid');
  specs.domains.forEach((domain) => {
    const card = el('article', 'card domain-card');
    card.appendChild(el('div', 'domain-name', domain.name));
    const list = el('dl');
    list.append(el('dt', '', '负责'), el('dd', '', domain.owns), el('dt', '', '不负责'), el('dd', '', domain.excludes));
    card.appendChild(list);
    domains.appendChild(card);
  });
  const adrs = document.getElementById('adr-grid');
  specs.adrs.forEach((adr, index) => {
    const card = el('article', 'card');
    card.append(el('span', 'page-index', 'ADR-00' + (index + 1)), el('h3', '', adr.title), el('p', 'card-muted', adr.decision), el('p', '', adr.consequence));
    adrs.appendChild(card);
  });
  const gates = document.getElementById('quality-gates');
  specs.quality_gates.forEach((gate) => gates.appendChild(el('li', '', gate)));
}

mountChrome();
const initializers = {overview: initOverview, routing: initRouting, providers: initProviders, reliability: initReliability, architecture: initArchitecture};
if (initializers[page]) initializers[page]().catch((error) => showToast('加载失败：' + error.message));
