const page = document.body.dataset.page;
const routes = [
  ['tasks', 'tasks.html', '任务工作台'],
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
  const data = response.status === 204 ? null : await response.json();
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

const taskState = {items: [], selected: null, status: '', taskType: '', search: ''};

const taskLabels = {
  draft: '草稿', ready: '待执行', running: '执行中', validating: '验证中',
  completed: '已完成', failed: '失败', cancelled: '已取消',
  low: '低', medium: '中', high: '高', urgent: '紧急',
};

function splitTaskValues(value, lineMode = false) {
  return value.split(lineMode ? /\r?\n/ : /[,，]/).map((item) => item.trim()).filter(Boolean);
}

function taskPayload() {
  return {
    title: document.getElementById('task-title').value.trim(),
    description: document.getElementById('task-description').value.trim(),
    task_type: document.getElementById('task-type').value,
    status: document.getElementById('task-status').value,
    priority: document.getElementById('task-priority').value,
    technology_stack: splitTaskValues(document.getElementById('task-stack').value),
    scope: document.getElementById('task-scope').value.trim(),
    acceptance_criteria: splitTaskValues(document.getElementById('task-criteria').value, true),
    tags: splitTaskValues(document.getElementById('task-tags').value),
    version: Number(document.getElementById('task-version').value) || undefined,
  };
}

function openTaskDialog(task = null) {
  const dialog = document.getElementById('task-dialog');
  document.getElementById('task-form').reset();
  document.getElementById('task-form-error').textContent = '';
  document.getElementById('task-id').value = task?.task_id || '';
  document.getElementById('task-version').value = task?.version || '';
  document.getElementById('task-title').value = task?.title || '';
  document.getElementById('task-description').value = task?.description || '';
  document.getElementById('task-type').value = task?.task_type || 'implementation';
  document.getElementById('task-status').value = task?.status || 'draft';
  document.getElementById('task-priority').value = task?.priority || 'medium';
  document.getElementById('task-stack').value = (task?.technology_stack || []).join(', ');
  document.getElementById('task-scope').value = task?.scope || '';
  document.getElementById('task-criteria').value = (task?.acceptance_criteria || []).join('\n');
  document.getElementById('task-tags').value = (task?.tags || []).join(', ');
  document.getElementById('task-form-kicker').textContent = task ? 'Edit Task' : 'Create Task';
  document.getElementById('task-form-title').textContent = task ? '编辑执行任务' : '新建执行任务';
  dialog.showModal();
}

function taskBadge(value, kind) {
  return el('span', 'task-chip ' + kind + '-' + value, taskLabels[value] || value);
}

function renderTaskDetail() {
  const detail = document.getElementById('task-detail');
  const edit = document.getElementById('task-edit');
  const remove = document.getElementById('task-delete');
  if (!taskState.selected) {
    detail.className = 'task-detail-empty';
    detail.textContent = '从中间列表选择任务查看完整上下文。';
    setText('task-detail-version', '未选择');
    edit.disabled = true;
    remove.disabled = true;
    return;
  }
  const task = taskState.selected;
  detail.className = 'task-detail-content';
  detail.replaceChildren();
  const title = el('h3', '', task.title);
  const badges = el('div', 'task-card-badges');
  badges.append(taskBadge(task.status, 'status'), taskBadge(task.priority, 'priority'));
  const description = el('p', '', task.description);
  const metadata = el('dl', 'task-detail-list');
  const rows = [
    ['类型', task.task_type], ['技术栈', task.technology_stack.join(' · ') || '未设置'],
    ['范围', task.scope || '未设置'], ['验收标准', task.acceptance_criteria.join('；') || '未设置'],
    ['标签', task.tags.join(' · ') || '未设置'], ['更新时间', new Date(task.updated_at).toLocaleString('zh-CN')],
  ];
  rows.forEach(([name, value]) => { metadata.append(el('dt', '', name), el('dd', '', value)); });
  detail.append(title, badges, description, metadata);
  setText('task-detail-version', 'v' + task.version);
  edit.disabled = false;
  remove.disabled = ['running', 'validating'].includes(task.status);
}

function renderTasks() {
  const list = document.getElementById('task-list');
  list.replaceChildren();
  if (!taskState.items.length) {
    const empty = el('div', 'task-list-empty');
    empty.append(el('strong', '', '没有匹配的任务'), el('p', '', '新建一个结构化任务，或调整左侧状态与顶部搜索条件。'));
    list.append(empty);
  }
  taskState.items.forEach((task) => {
    const card = el('article', 'task-item' + (taskState.selected?.task_id === task.task_id ? ' selected' : ''));
    card.dataset.taskId = task.task_id;
    const lead = el('div', 'task-item-lead');
    const badges = el('div', 'task-card-badges');
    badges.append(taskBadge(task.status, 'status'), taskBadge(task.priority, 'priority'), el('span', 'task-chip', task.task_type));
    lead.append(badges, el('h3', '', task.title), el('p', '', task.description));
    const tags = el('div', 'task-card-tags');
    (task.tags.length ? task.tags : ['未标记']).forEach((tag) => tags.append(el('span', '', '#' + tag)));
    lead.append(tags);
    const side = el('div', 'task-item-side');
    side.append(el('small', '', 'v' + task.version), el('time', '', new Date(task.updated_at).toLocaleDateString('zh-CN')));
    const actions = el('div', 'task-inline-actions');
    const view = el('button', '', '查看'); view.type = 'button'; view.dataset.action = 'view';
    const edit = el('button', '', '编辑'); edit.type = 'button'; edit.dataset.action = 'edit';
    const remove = el('button', 'danger', '删除'); remove.type = 'button'; remove.dataset.action = 'delete'; remove.disabled = ['running', 'validating'].includes(task.status);
    actions.append(view, edit, remove); side.append(actions); card.append(lead, side); list.append(card);
  });
  const counts = Object.fromEntries(['draft', 'ready', 'running', 'validating', 'completed', 'failed'].map((status) => [status, taskState.items.filter((task) => task.status === status).length]));
  setText('task-total', taskState.items.length + ' 项'); setText('count-all', taskState.items.length);
  Object.entries(counts).forEach(([status, count]) => setText('count-' + status, count));
  setText('stat-total', taskState.items.length); setText('stat-ready', counts.ready);
  setText('stat-active', counts.running + counts.validating); setText('stat-done', counts.completed);
  renderTaskDetail();
}

async function loadTasks(selectId = null) {
  const query = new URLSearchParams();
  if (taskState.status) query.set('status', taskState.status);
  if (taskState.taskType) query.set('task_type', taskState.taskType);
  if (taskState.search) query.set('search', taskState.search);
  const data = await api('/api/tasks' + (query.size ? '?' + query.toString() : ''));
  taskState.items = data.items;
  if (selectId) taskState.selected = taskState.items.find((task) => task.task_id === selectId) || null;
  else if (taskState.selected) taskState.selected = taskState.items.find((task) => task.task_id === taskState.selected.task_id) || null;
  renderTasks();
}

async function deleteTask(task) {
  if (!task || !confirm('确认删除任务“' + task.title + '”？此操作不可撤销。')) return;
  await api('/api/tasks/' + encodeURIComponent(task.task_id), {method: 'DELETE'});
  if (taskState.selected?.task_id === task.task_id) taskState.selected = null;
  await loadTasks();
  showToast('任务已删除');
}

async function initTasks() {
  document.getElementById('task-create').addEventListener('click', () => openTaskDialog());
  document.getElementById('task-refresh').addEventListener('click', () => loadTasks());
  document.getElementById('task-dialog-close').addEventListener('click', () => document.getElementById('task-dialog').close());
  document.getElementById('task-cancel').addEventListener('click', () => document.getElementById('task-dialog').close());
  document.getElementById('task-search-form').addEventListener('submit', (event) => {
    event.preventDefault(); taskState.search = document.getElementById('task-search').value.trim(); loadTasks();
  });
  document.getElementById('task-type-filter').addEventListener('change', (event) => { taskState.taskType = event.target.value; loadTasks(); });
  document.querySelectorAll('[data-task-status]').forEach((button) => button.addEventListener('click', () => {
    document.querySelectorAll('[data-task-status]').forEach((item) => item.classList.toggle('active', item === button));
    taskState.status = button.dataset.taskStatus; loadTasks();
  }));
  document.getElementById('task-list').addEventListener('click', (event) => {
    const card = event.target.closest('[data-task-id]'); if (!card) return;
    const task = taskState.items.find((item) => item.task_id === card.dataset.taskId); if (!task) return;
    const action = event.target.closest('[data-action]')?.dataset.action || 'view';
    taskState.selected = task;
    if (action === 'edit') openTaskDialog(task); else if (action === 'delete') deleteTask(task); else renderTasks();
  });
  document.getElementById('task-edit').addEventListener('click', () => openTaskDialog(taskState.selected));
  document.getElementById('task-delete').addEventListener('click', () => deleteTask(taskState.selected));
  document.getElementById('task-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    const id = document.getElementById('task-id').value;
    const error = document.getElementById('task-form-error'); error.textContent = '';
    try {
      const saved = await api(id ? '/api/tasks/' + encodeURIComponent(id) : '/api/tasks', {
        method: id ? 'PUT' : 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(taskPayload()),
      });
      document.getElementById('task-dialog').close(); await loadTasks(saved.task_id); showToast(id ? '任务已更新' : '任务已创建');
    } catch (requestError) { error.textContent = requestError.message; }
  });
  await loadTasks();
}

mountChrome();
({tasks: initTasks, overview: initOverview, routing: initRouting, providers: initProviders, reliability: initReliability, architecture: initArchitecture}[page] || (() => {}))().catch((error) => showToast(error.message));
