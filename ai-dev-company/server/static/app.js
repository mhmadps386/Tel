'use strict';
// AI Dev Company control panel. All data is rendered with textContent (never innerHTML).
let csrf = null;
let pollTimer = null;
const draft = { title: '', request: '' };
const root = document.getElementById('root');

function el(tag, attrs = {}, ...children) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === 'class') n.className = v;
    else if (k === 'text') n.textContent = v;
    else if (k.startsWith('on')) n.addEventListener(k.slice(2), v);
    else if (v !== false && v != null) n.setAttribute(k, v === true ? '' : v);
  }
  for (const c of children.flat()) if (c != null) n.append(c instanceof Node ? c : document.createTextNode(String(c)));
  return n;
}

async function api(path, body) {
  const opts = body === undefined ? {} : {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF': csrf || '' }, body: JSON.stringify(body),
  };
  const res = await fetch(path, { credentials: 'same-origin', ...opts });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) { const e = new Error(data.error || res.statusText); e.status = res.status; throw e; }
  return data;
}

function ago(ts) {
  const s = Math.max(0, Math.round(Date.now() / 1000 - new Date(ts).getTime() / 1000));
  return s < 60 ? `${s}s ago` : s < 3600 ? `${Math.round(s / 60)}m ago` : `${Math.round(s / 3600)}h ago`;
}

function statusClass(s) {
  return ({ done: 'ok', completed: 'ok', running: 'warn', in_progress: 'warn', merging: 'warn', approved: 'ok', pass: 'ok',
            failed: 'bad', cancelled: 'muted', rejected: 'bad', needs_owner: 'bad', fail: 'bad',
            awaiting_plan_approval: 'warn', awaiting_merge_approval: 'warn' })[s] || '';
}

function act(fn) {
  return async (ev) => {
    const btn = ev && ev.currentTarget; if (btn) btn.disabled = true;
    try { await fn(); await refresh(); } catch (e) { alert(e.message); } finally { if (btn) btn.disabled = false; }
  };
}

// -- login / password --------------------------------------------------------------
function showLogin(message) {
  clearInterval(pollTimer);
  document.getElementById('logout').hidden = true;
  const err = el('p', { class: 'error', text: message || '' });
  const pw = el('input', { type: 'password', autocomplete: 'current-password', required: true, id: 'pw' });
  const form = el('form', {}, el('label', { for: 'pw', text: 'Owner password' }), pw, el('p'),
    el('button', { class: 'primary', type: 'submit', text: 'Sign in' }), err);
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    try { await api('/api/login', { password: pw.value }); pw.value = ''; start(); }
    catch (x) { err.textContent = x.message; }
  });
  root.className = '';
  root.replaceChildren(el('section', {}, el('h2', { text: 'Private control panel' }),
    el('p', { class: 'muted', text: 'Authorised owner only. Sessions expire after 12 hours.' }), form));
}

function showChangePassword() {
  const cur = el('input', { type: 'password', autocomplete: 'current-password' });
  const nw = el('input', { type: 'password', autocomplete: 'new-password', minlength: 12 });
  const err = el('p', { class: 'error' });
  const form = el('form', {}, el('label', { text: 'Current (initial) password' }), cur,
    el('label', { text: 'New password (12+ characters)' }), nw, el('p'),
    el('button', { class: 'primary', type: 'submit', text: 'Change password' }), err);
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    try { await api('/api/password', { current: cur.value, new: nw.value }); showLogin('Password changed. Sign in again.'); }
    catch (x) { err.textContent = x.message; }
  });
  root.className = '';
  root.replaceChildren(el('section', {}, el('h2', { text: 'Set your own password' }),
    el('p', { class: 'muted', text: 'The initial password must be replaced before the panel can be used.' }), form));
}

// -- main view ---------------------------------------------------------------------
function controls(s) {
  const loop = s.loop, estop = s.estop;
  const state = estop.active ? el('span', { class: 'pill bad', text: 'EMERGENCY STOP' })
    : el('span', { class: `pill ${loop.state === 'running' ? 'ok' : 'warn'}`, text: loop.state.toUpperCase() });
  const auto = el('input', { type: 'checkbox', style: 'width:auto' }); auto.checked = !!loop.auto_continue;
  auto.addEventListener('change', act(() => api('/api/control', { action: 'auto_continue', value: auto.checked })));
  return el('section', { class: 'wide' },
    el('h2', {}, 'AI Manager ', state),
    el('p', { class: 'muted', text: estop.active ? `Reason: ${estop.reason}` : (loop.reason || '') }),
    el('div', { class: 'row' },
      el('button', { class: 'primary', text: 'Start / resume loop', disabled: estop.active,
                     onclick: act(() => api('/api/control', { action: 'start' })) }),
      el('button', { text: 'Pause', onclick: act(() => api('/api/control', { action: 'pause' })) }),
      estop.active
        ? el('button', { text: 'Clear emergency stop', onclick: act(() => api('/api/control', { action: 'clear_estop' })) })
        : el('button', { class: 'danger', text: 'EMERGENCY STOP', onclick: act(async () => {
            if (confirm('Stop all agents immediately?')) await api('/api/control', { action: 'estop' }); }) }),
      el('label', { style: 'display:flex;gap:6px;align-items:center;margin:0' }, auto,
         'Auto-continue to next approved mission (unattended)')));
}

function workersView(s) {
  const items = s.workers.map((w) => {
    const i = w.info || {};
    return el('li', {},
      el('div', { class: 'row' }, el('strong', { text: w.id }),
        el('span', { class: `pill ${w.online ? 'ok' : 'bad'}`, text: w.online ? 'online' : `offline (${Math.round(w.age_s)}s)` })),
      el('div', { class: 'kv' },
        'Sandbox', el('span', { class: i.sandbox_ok ? 'ok' : 'bad', text: i.sandbox_ok ? 'OS sandbox OK' : `unavailable: ${i.sandbox_detail || ''}` }),
        'Codex auth', el('span', { class: i.auth_mode === 'chatgpt' ? 'ok' : 'bad', text: i.auth_mode || 'unknown' }),
        'Login lock', el('span', { text: i.forced_login_method || '—' }),
        'Codex', el('span', { text: i.codex_version || '—' }),
        'Current job', el('span', { text: i.current_job || 'idle' }),
        'Host', el('span', { text: i.host || '—' })));
  });
  const login = s.login || {};
  const loginBox = login.pending && login.user_code
    ? el('div', {}, el('p', { text: 'Finish Codex sign-in on the official OpenAI page:' }),
        el('p', {}, el('a', { href: login.verification_url, target: '_blank', rel: 'noopener noreferrer', text: login.verification_url })),
        el('p', {}, 'Code: ', el('span', { class: 'code', text: login.user_code })),
        el('p', { class: 'muted', text: `Status: ${login.status || 'waiting'} · never share this code` }))
    : el('p', { class: 'muted', text: login.status ? `Last sign-in: ${login.status}` : '' });
  const tokenOut = el('pre', { hidden: true });
  return el('section', {}, el('h2', { text: 'Execution workers' }),
    items.length ? el('ul', { class: 'list' }, items) : el('p', { class: 'muted', text: 'No worker connected yet.' }),
    el('div', { class: 'row' },
      el('button', { text: 'Start Codex sign-in (device code)', onclick: act(() => api('/api/control', { action: 'codex_login' })) }),
      el('button', { class: 'ghost', text: 'Create worker token', onclick: act(async () => {
        const r = await api('/api/worker-tokens', { name: prompt('Worker name', 'owner-worker') || 'worker' });
        tokenOut.hidden = false; tokenOut.textContent = `${r.token}\n\n${r.note}`; }) })),
    loginBox, tokenOut);
}

function submitView(s) {
  const proj = el('select', {}, s.projects.map((p) => el('option', { value: p.id, text: `${p.name}${p.disposable ? ' (disposable)' : ''}` })));
  const title = el('input', { maxlength: 200, placeholder: 'e.g. Add due dates to tasks' });
  const req = el('textarea', { maxlength: 8000, placeholder: 'Describe what you want built and how you will judge it.' });
  // Keep drafts across the 5 s refresh.
  title.value = draft.title; req.value = draft.request;
  title.addEventListener('input', () => { draft.title = title.value; });
  req.addEventListener('input', () => { draft.request = req.value; });
  const form = el('form', {}, el('label', { text: 'Project' }), proj, el('label', { text: 'Title' }), title,
    el('label', { text: 'Request' }), req, el('p'), el('button', { class: 'primary', type: 'submit', text: 'Submit to AI Manager' }));
  form.addEventListener('submit', (e) => { e.preventDefault(); act(async () => {
    await api('/api/missions', { project_id: Number(proj.value), title: title.value, request: req.value });
    draft.title = ''; draft.request = ''; })(); });
  return el('section', {}, el('h2', { text: 'New development task' }),
    el('p', { class: 'muted', text: 'The manager plans it; nothing runs until you approve the plan.' }), form);
}

function approvalsView(s) {
  const items = s.approvals.map((a) => {
    const p = a.payload || {};
    const detail = a.kind === 'plan' ? JSON.stringify(p.plan, null, 2)
      : `Branch: ${p.branch}\nRound: ${p.round}\nChecks: ${JSON.stringify(p.checks, null, 1)}\nTests: ${JSON.stringify(p.tests || {}, null, 1)}\nDiff: ${p.diffstat || ''}\n\n${p.rationale || ''}`;
    return el('li', {}, el('div', { class: 'row' }, el('strong', { text: `#${a.mission_id} ${a.title}` }),
        el('span', { class: 'pill warn', text: a.kind === 'plan' ? 'approve plan' : 'approve merge (disposable repo)' })),
      el('pre', { text: detail }),
      el('div', { class: 'row' },
        el('button', { class: 'primary', text: 'Approve', onclick: act(() => api(`/api/approvals/${a.id}`, { decision: 'approve' })) }),
        el('button', { text: 'Reject', onclick: act(() => api(`/api/approvals/${a.id}`, { decision: 'reject', note: prompt('Reason?') || '' })) })));
  });
  return el('section', {}, el('h2', { text: `Pending approvals (${items.length})` }),
    items.length ? el('ul', { class: 'list' }, items) : el('p', { class: 'muted', text: 'Nothing waiting for you.' }));
}

function missionsView(s) {
  const items = s.missions.map((m) => {
    const jobs = s.jobs.filter((j) => j.mission_id === m.id).sort((a, b) => a.id - b.id);
    const open = !['completed', 'cancelled', 'rejected', 'failed'].includes(m.status);
    return el('li', {},
      el('div', { class: 'row' }, el('strong', { text: `#${m.id} ${m.title}` }),
        el('span', { class: `pill ${statusClass(m.status)}`, text: m.status }),
        el('span', { class: 'muted', text: `round ${m.round}/${m.max_rounds}` }),
        open ? el('button', { class: 'ghost', text: 'Cancel', onclick: act(async () => {
          if (confirm('Cancel this mission and stop its agents?')) await api(`/api/missions/${m.id}/cancel`, {}); }) }) : null),
      el('div', { class: 'log' }, jobs.map((j) => el('div', {},
        el('span', { class: statusClass(j.status), text: `${j.kind}#${j.id} r${j.round} ${j.status}` }),
        ` · ${j.attempts}/${j.max_attempts} · ${Math.round(j.seconds)}s`,
        j.verdict ? el('span', { class: statusClass(j.verdict), text: ` · ${j.verdict}` }) : null,
        j.summary ? ` · ${j.summary}` : '',
        j.tests ? ` · tests: ${j.tests.summary || ('exit ' + j.tests.exit_code)}` : ''))));
  });
  return el('section', { class: 'wide' }, el('h2', { text: 'Missions' }),
    items.length ? el('ul', { class: 'list' }, items) : el('p', { class: 'muted', text: 'No missions yet.' }));
}

function testsView(s) {
  const reviews = s.jobs.filter((j) => j.kind === 'review' && j.tests);
  return el('section', {}, el('h2', { text: 'Test results (manager re-run in sandbox)' }),
    reviews.length ? el('ul', { class: 'list' }, reviews.map((j) => el('li', {},
      el('span', { class: j.tests.exit_code === 0 ? 'ok' : 'bad', text: j.tests.exit_code === 0 ? 'PASS' : 'FAIL' }),
      ` mission #${j.mission_id} round ${j.round}: ${j.tests.summary || ''}`)))
      : el('p', { class: 'muted', text: 'No test runs yet.' }));
}

function usageView(s) {
  const u = s.usage;
  return el('section', {}, el('h2', { text: 'Usage & cost' }),
    el('div', { class: 'kv' },
      'Agent jobs', String(u.agent_jobs), 'Attempts', String(u.attempts), 'Failed jobs', String(u.failed_jobs),
      'Agent time (all)', `${Math.round(u.agent_seconds / 60)} min`, 'Agent time (24h)', `${Math.round(u.agent_seconds_24h / 60)} min`,
      'Paid API calls', String(u.paid_api_calls), 'Billing mode', 'ChatGPT subscription only',
      'Infrastructure', u.infrastructure.railway_services.join(', ')),
    el('p', { class: 'muted', text: u.infrastructure.note }));
}

function activityView(s) {
  return el('section', { class: 'wide' }, el('h2', { text: 'Activity log' }),
    el('div', { class: 'log' }, s.events.map((e) => el('div', {},
      el('span', { class: 'muted', text: `${new Date(e.at).toLocaleTimeString()} ` }),
      el('strong', { text: e.kind }), ` · ${e.actor}`,
      e.mission_id ? ` · mission #${e.mission_id}` : '', e.job_id ? ` · job #${e.job_id}` : '',
      Object.keys(e.data || {}).length ? ` · ${JSON.stringify(e.data).slice(0, 400)}` : ''))));
}

function render(s) {
  csrf = s.csrf;
  document.getElementById('logout').hidden = false;
  if (s.must_change_password) { clearInterval(pollTimer); return showChangePassword(); }
  root.className = 'app';
  root.replaceChildren(controls(s), workersView(s), approvalsView(s), submitView(s), testsView(s),
    missionsView(s), usageView(s), activityView(s),
    el('p', { class: 'muted wide', text: `Updated ${new Date().toLocaleTimeString()} · refreshes every 5 s` }));
}

async function refresh() {
  const focused = document.activeElement;
  const typing = focused && root.contains(focused) && ['INPUT', 'TEXTAREA', 'SELECT'].includes(focused.tagName);
  try {
    const s = await api('/api/state');
    csrf = s.csrf;
    if (!typing) render(s);
  }
  catch (e) { if (e.status === 401) showLogin(); }
}

function start() { refresh(); clearInterval(pollTimer); pollTimer = setInterval(refresh, 5000); }

document.getElementById('logout').addEventListener('click', act(async () => { await api('/api/logout', {}); showLogin('Signed out.'); }));
start();
