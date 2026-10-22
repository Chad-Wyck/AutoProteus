'use strict';
const $ = id => document.getElementById(id);
const token = document.querySelector('meta[name="app-token"]').content;
const state = { app: null, session: null, id: null, provider: 'ollama', installed: [], feedIds: new Set(), polling: false, file: null, started: 0, setupBusy: false };
Object.assign(state, {query: '', offset: 0, archived: false, attachments: []});

async function api(path, data, binary = false) {
  const response = await fetch(path, { method: data === undefined ? 'GET' : 'POST', headers: { 'X-AutoProteus-Token': token, 'Content-Type': 'application/json' }, body: data === undefined ? undefined : JSON.stringify(data) });
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try { message = (await response.json()).error || message; } catch (_) {}
    throw new Error(message);
  }
  return binary ? response.blob() : response.json();
}
function visible(id, yes) { $(id).classList.toggle('hidden', !yes); }
function text(id, value) { $(id).textContent = value; }
function node(tag, className, content) { const n = document.createElement(tag); if (className) n.className = className; if (content !== undefined) n.textContent = content; return n; }
function toast(message) { text('toast', message); visible('toast', true); clearTimeout(toast.timer); toast.timer = setTimeout(() => visible('toast', false), 6000); }
function error(id, message) { text(id, message); visible(id, !!message); }
function busy() { return !!state.app?.active; }
function stateAddress() { return '/api/state?' + new URLSearchParams({query: state.query, offset: state.offset, archived: state.archived}); }
function saveBlob(blob, name) { const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 5000); }

function renderApp() {
  const app = state.app, config = app.settings;
  text('app-version', 'v' + app.version);
  const active = app.active;
  visible('active-work', !!active);
  if (active) text('active-work-label', `${active.title} · ${active.activity}`);
  const canSteer = active?.id === state.id && active.status !== 'stopping';
  $('send').disabled = state.sending || (!!active && !canSteer);
  $('send').setAttribute('aria-label', canSteer ? 'Send message' : state.id ? 'Send reply' : 'Start task');
  visible('input-mode', !!canSteer);
  $('restart-seed').disabled = !!active || app.evaluation?.status === 'running';
  $('attach-button').disabled = !!active;
  text('composer-note', canSteer ? 'Changes arrive between actions. Running commands finish first.' : active ? 'Open the active task to send a message.' : 'Enter to send · Shift + Enter for a new line');
  const provider = active?.provider || config.provider;
  text('privacy-label', !config.configured && !active ? 'Local workspace' : provider === 'hosted' ? 'Hosted model · task data sent to provider' : provider === 'ollama' ? 'Local model · on your computer' : 'Scripted demo · no model requests');
  const qualified = config.compatibility;
  text('compatibility-note', qualified?.passed ? `Connection checked · ${qualified.protocol}${qualified.rounds ? ` · ${qualified.rounds} rounds` : ''}${qualified.rejected_call_recovery ? ' · error recovery checked' : ''}${qualified.cached ? ' · saved matching check' : ''}${qualified.identity_complete === false ? '. Some model details are unavailable; reconnecting runs a fresh check.' : ''}` : 'The connection and tool replies are checked when you connect or prepare a model.');
  const native = app.execution?.mode === 'native';
  visible('execution-warning', native); text('execution-warning', app.execution?.warning || '');
  text('terminal-help', native ? 'Commands run with this account’s access. Files and networks are restricted only by your surrounding environment.' : 'Let the agent run Linux commands inside its virtual machine. Your host drives and network remain unavailable.');
  text('try-seed', native ? 'Try edited seed without VM protection →' : 'Try edited seed in a new VM →');
  text('key-help', app.platform === 'windows' ? 'Saved keys are encrypted for your Windows account.' : 'Keys stay in memory for this launch. The surrounding environment must protect them.');
  text('seed-help', native ? 'The agent edits a source copy in harness/. Your surrounding environment must protect the starter and controller.' : 'The agent can edit its own source copy in harness/. Your running seed stays recoverable.');
  text('local-setup-help', 'AutoProteus can prepare the engine and model for you. No separate terminal or server setup needed.');
  text('local-download-note', 'First-time setup downloads the engine and model, which can take several minutes and several GB of disk space. Everything stays in this project when using the managed engine.');
  text('session-count', app.session_page.total);
  text('session-page', app.session_page.total ? `${state.offset + 1}–${state.offset + app.sessions.length}` : '0');
  $('sessions-previous').disabled = state.offset === 0;
  $('sessions-next').disabled = state.offset + app.sessions.length >= app.session_page.total;
  const sessions = $('sessions'); sessions.replaceChildren();
  if (!app.sessions.length) sessions.append(node('p', 'sidebar-empty', state.query || state.archived ? 'No matching sessions.' : 'Your work will appear here.\nEvery session is saved.'));
  app.sessions.forEach(session => {
    const button = node('button', 'session-link' + (session.id === state.id ? ' active' : ''));
    button.title = session.title; button.setAttribute('aria-label', session.title);
    button.append(node('span', 'session-bullet ' + session.status), node('span', 'session-text', session.title));
    button.onclick = () => selectSession(session.id); sessions.append(button);
  });
  text('connection-title', config.configured ? (config.provider === 'demo' ? 'Interactive demo' : config.model) : 'Choose a model');
  text('connection-sub', config.configured ? (config.provider === 'ollama' ? 'Local model' : config.provider === 'demo' ? 'Scripted tour · no AI model' : 'Hosted connection') : 'Get ready to start');
  document.querySelector('.connection-dot').classList.toggle('ready', config.configured);
  const current = active || config;
  text('composer-model', config.configured ? (current.provider === 'demo' ? 'Demo · scripted tour' : current.model + (current.provider === 'ollama' ? ' · local' : ' · hosted')) : 'Choose a model to begin');
  renderSetupProgress(app.setup);
  renderIsolation(app.isolation);
  if (app.evaluation?.id && state.checkSession === app.evaluation.session &&
      (app.evaluation.busy || state.checkReport?.id === app.evaluation.id)) renderEvaluation(app.evaluation);
  visible('evaluation-status', !!app.evaluation?.id);
  if (app.evaluation?.id) text('evaluation-status', app.evaluation.busy ? `Checking seed · ${app.evaluation.results.length}/${app.evaluation.total}` : 'Seed check results');
}

function home() {
  state.id = null; state.session = null; state.feedIds.clear(); $('feed').replaceChildren();
  visible('welcome', true); visible('feed', false); visible('activity', false);
  visible('inspector-empty', true); visible('inspector-session', false); visible('trace-button', false);
  visible('session-banner', false); visible('stop', false); visible('send', true);
  visible('input-queue', false);
  text('page-name', 'New task'); $('task').placeholder = 'Describe a task, an idea, or a problem…'; $('task').disabled = false;
  $('task').value = ''; $('send').disabled = false; if (state.app) renderApp(); $('task').focus();
  state.attachments = []; renderAttachments();
}

function resetSessionFilter() {
  state.query = ''; state.offset = 0; state.archived = false;
  $('session-search').value = ''; $('show-archived').checked = false;
}
$('session-search').oninput = () => { state.query = $('session-search').value; state.offset = 0; clearTimeout(state.searchTimer); state.searchTimer = setTimeout(poll, 250); };
$('show-archived').onchange = () => { state.archived = $('show-archived').checked; state.offset = 0; poll(); };
$('sessions-previous').onclick = () => { state.offset = Math.max(0, state.offset - 30); poll(); };
$('sessions-next').onclick = () => { state.offset += 30; poll(); };

function renderAttachments() {
  const area = $('attachments'); area.replaceChildren(); visible('attachments', state.attachments.length > 0);
  state.attachments.forEach((file, index) => {
    const row = node('span', 'attachment', file.path + ' ');
    const remove = node('button', 'quiet', '×'); remove.type = 'button'; remove.setAttribute('aria-label', 'Remove ' + file.path);
    remove.onclick = () => { state.attachments.splice(index, 1); renderAttachments(); };
    row.append(remove); area.append(row);
  });
}
async function encodeFiles(files) {
  if (files.length > 400 || [...files].reduce((n, f) => n + f.size, 0) > 32 * 1024 * 1024) throw new Error('Choose at most 400 files totalling less than 32 MiB.');
  const result = [];
  for (const file of files) {
    if (file.size > 2 * 1024 * 1024) throw new Error('Each imported file must be at most 2 MiB.');
    const bytes = new Uint8Array(await file.arrayBuffer()); let value = '';
    for (let i = 0; i < bytes.length; i += 8192) value += String.fromCharCode(...bytes.subarray(i, i + 8192));
    result.push({path: file.webkitRelativePath || file.name, data: btoa(value), bytes: file.size});
  }
  return result;
}
$('attach-button').onclick = () => $(state.id ? 'import-files' : 'attach-files').click();
$('attach-files').onchange = async () => {
  try {
    const files = await encodeFiles($('attach-files').files);
    if (state.attachments.length + files.length > 400 || [...state.attachments, ...files].reduce((n, f) => n + f.bytes, 0) > 32 * 1024 * 1024) throw new Error('The attachment limit is 400 files and 32 MiB.');
    state.attachments.push(...files); renderAttachments();
  } catch (e) { toast(e.message); } finally { $('attach-files').value = ''; }
};
$('import-session').onclick = () => $('import-files').click();
$('import-files').onchange = async () => {
  try { const files = await encodeFiles($('import-files').files); await api('/api/import', {id: state.id, files: files.map(({path, data}) => ({path, data}))}); toast('Files copied into this task.'); await poll(); }
  catch (e) { toast(e.message); } finally { $('import-files').value = ''; }
};
async function manageSession(action, extra = {}) {
  try {
    await api('/api/session/manage', {id: state.id, action, ...extra});
    state.offset = 0;
    if (action === 'delete') home();
    await poll();
  } catch (e) { toast(e.message); }
}
$('rename-session').onclick = () => { const title = prompt('Rename this session', state.session.title); if (title !== null) manageSession('rename', {title}); };
$('archive-session').onclick = () => manageSession('archive', {archived: !state.session.archived});
$('delete-session').onclick = () => { if (confirm('Move this session to Trash? You can restore it from Saved work & storage.')) manageSession('delete'); };
function byteLabel(bytes) { return bytes < 1048576 ? `${(bytes / 1024).toFixed(1)} KiB` : bytes < 1073741824 ? `${(bytes / 1048576).toFixed(1)} MiB` : `${(bytes / 1073741824).toFixed(1)} GiB`; }
async function refreshStorage() {
  const [usage, trash] = await Promise.all([api('/api/storage'), api('/api/trash')]);
  const area = $('storage-usage'); area.replaceChildren();
  Object.entries(usage).forEach(([name, bytes]) => { const item = node('div', 'storage-item'); item.append(node('span', '', name), node('strong', '', byteLabel(bytes))); area.append(item); });
  const list = $('trash-list'); list.replaceChildren();
  if (!trash.length) list.append(node('p', 'muted', 'Trash is empty.'));
  trash.forEach(session => {
    const row = node('div', 'trash-item'); row.append(node('span', '', session.title));
    const restore = node('button', 'quiet', 'Restore'); restore.onclick = async () => {
      try { await api('/api/session/manage', {id: session.id, action: 'restore'}); await refreshStorage(); await poll(); }
      catch (e) { toast(e.message); }
    }; row.append(restore); list.append(row);
  });
}
$('storage-button').onclick = async () => { try { await refreshStorage(); $('storage-dialog').showModal(); } catch (e) { toast(e.message); } };
$('close-storage').onclick = () => $('storage-dialog').close();

async function selectSession(id) {
  state.id = id; state.session = null; state.feedIds.clear(); $('feed').replaceChildren(); state.started = Date.now();
  visible('welcome', false); visible('feed', true); visible('inspector-empty', false); visible('inspector-session', true); visible('trace-button', true);
  $('task').value = '';
  try {
    const session = await api('/api/session?id=' + id);
    if (state.id !== id) return;
    state.session = session; renderSession(); await refreshFiles(); renderApp();
  } catch (e) { toast(e.message); }
}

const actionLabels = { list_files: 'Looking through files', read_file: 'Reading a file', read_section: 'Reading a section', write_file: 'Writing a file', edit_file: 'Editing a file', update_todo: 'Updating the checklist', run_command: 'Running a command' };
function feedItem(item) {
  const element = node('div', 'feed-item ' + item.kind + (item.kind === 'result' && !item.ok ? ' failed' : ''));
  element.dataset.feedId = item.id;
  if (item.kind === 'action' || item.kind === 'result') {
    const details = node('details');
    const label = item.kind === 'action' ? (actionLabels[item.text] || item.text) + (item.arguments?.path ? ' · ' + item.arguments.path : '') : item.text;
    details.append(node('summary', '', label), node('pre', '', JSON.stringify(item.kind === 'action' ? item.arguments : item.result, null, 2)));
    element.append(details);
  } else element.textContent = item.text;
  return element;
}
function renderSession() {
  const session = state.session;
  text('page-name', session.title);
  const feed = $('feed'), nearBottom = feed.scrollHeight - feed.scrollTop - feed.clientHeight < 130;
  // Keep display memory bounded even when a candidate replaces its whole feed.
  const currentIds = new Set(session.feed.map(item => item.id));
  Array.from(feed.children).forEach(element => { if (!currentIds.has(element.dataset.feedId)) element.remove(); });
  state.feedIds.forEach(id => { if (!currentIds.has(id)) state.feedIds.delete(id); });
  let added = false;
  session.feed.forEach(item => { if (!state.feedIds.has(item.id)) { feed.append(feedItem(item)); state.feedIds.add(item.id); added = true; } });
  if (added && (nearBottom || state.feedIds.size < 5)) feed.scrollTop = feed.scrollHeight;
  const active = state.app?.active?.id === session.id; visible('activity', active); text('activity-label', session.activity);
  text('elapsed', active ? Math.floor((Date.now() - state.started) / 1000) + 's' : '');
  visible('stop', active); visible('send', true); $('stop').disabled = session.status === 'stopping';
  $('task').disabled = session.status === 'stopping'; $('task').placeholder = active ? 'Change direction, or queue something for afterwards…' : 'Add a reply, clarify the task, or request a change…';
  renderInputQueue(session);
  const labels = { running: 'Working', stopping: 'Stopping', completed: session.provider === 'demo' ? 'Demo finished' : 'Agent reported completion', waiting: 'Your input needed', paused: 'Paused', interrupted: 'Interrupted', error: 'Needs attention', ready: 'Ready' };
  text('status-label', labels[session.status] || session.status); $('status-dot').className = 'status-dot ' + session.status;
  renderVerification();
  text('step-count', `${session.steps} step${session.steps === 1 ? '' : 's'} · ${session.provider === 'demo' ? 'Scripted demo' : session.model}`);
  const previouslyNative = session.execution_history?.some(run => run.mode === 'native');
  text('execution-label', session.execution_mode === 'native' ? 'Ran without AutoProteus VM protection' : session.execution_mode === 'vm' ? 'VM execution' + (previouslyNative ? ' · previously ran without VM protection' : '') : 'Execution mode not recorded');
  const todo = $('todo'); todo.replaceChildren();
  if (!session.todo.trim()) todo.append(node('p', 'muted', "The agent hasn't made a checklist yet."));
  session.todo.split('\n').filter(line => line.trim()).forEach(line => {
    const done = /^\s*(?:[-*]\s*)?\[[xX]\]/.test(line);
    const label = line.replace(/^\s*(?:[-*]\s*)?\[[ xX]\]\s*/, '');
    const row = node('div', 'todo-item' + (done ? ' done' : ''));
    row.append(node('span', 'todo-check', done ? '✓' : ''), node('span', '', label)); todo.append(row);
  });
  const resumable = ['paused', 'interrupted', 'error', 'ready'].includes(session.status);
  visible('session-banner', resumable);
  if (resumable) {
    const banner = $('session-banner'); banner.replaceChildren(node('span', '', session.status === 'error' ? 'Your work is saved. Update the connection or try again.' : 'Your session is saved and ready to continue.'));
    const receipt = session.operation_receipts?.at(-1);
    if (receipt && receipt.status !== 'recorded') banner.append(node('span', '', ` Interrupted ${receipt.tool}: ${receipt.status.replaceAll('_', ' ')}. Resume includes a reminder to inspect saved work before retrying.`));
    const button = node('button', '', 'Resume'); button.onclick = () => resume(); banner.append(button);
  }
  if (state.app) renderApp();
  text('archive-session', session.archived ? 'Unarchive' : 'Archive');
  ['rename-session', 'archive-session', 'delete-session', 'import-session'].forEach(id => $(id).disabled = active || !!state.app.evaluation?.busy);
}

function renderInputQueue(session) {
  const box = $('input-queue'); box.replaceChildren();
  const stopped = !!state.app && state.app.active?.id !== session.id;
  const rows = (session.input_queue || []).filter(row => ['pending', 'offered'].includes(row.status));
  const latest = (session.input_queue || []).filter(row => row.status === 'delivered').at(-1);
  if (latest) box.append(node('small', 'muted', 'Latest message delivered to the agent.'));
  rows.forEach(row => {
    const item = node('div', 'queued-input');
    const delivery = row.status === 'offered' ? (stopped ? 'Delivery unconfirmed' : 'Delivery in progress') : 'Pending';
    item.append(node('span', '', `${row.mode === 'steer' ? 'Change direction' : 'Afterwards'} · ${delivery}: ${row.message}`));
    if (row.status === 'pending' || stopped) {
      const cancel = node('button', 'quiet', 'Cancel');
      if (row.status === 'offered') cancel.title = 'Prevent this message being sent again. Earlier work is not undone.';
      cancel.onclick = async () => { try { await api('/api/input/cancel', {id: session.id, request_id: row.id}); await poll(); } catch (error) { toast(error.message); } };
      item.append(cancel);
    }
    box.append(item);
  });
  if (rows.length && state.app?.active?.id !== session.id) {
    const resumeQueued = node('button', 'quiet', 'Continue queued work');
    resumeQueued.onclick = () => resume(); box.append(resumeQueued);
  }
  visible('input-queue', !!rows.length || !!latest);
}

function renderVerification() {
  const evidence = state.session?.verification;
  text('output-verification', evidence?.label || 'Saved outputs have not been independently checked.');
  text('verification-scope', evidence?.scope || 'Review the saved files to check the requested outcome.');
  visible('view-verification', !!evidence?.report_id);
  const progress = evidence?.capabilities;
  text('capability-progress', progress ? `Declared in this draft: ${progress.declared.join(', ') || 'No literal tool list found'}.\nSource checks: ${progress.checked_source.replaceAll('_', ' ')} (listed tasks only).\nThis exact draft is active: ${progress.activated ? 'yes' : 'not observed'}.\nObserved model use with this draft: ${progress.model_used.join(', ') || 'none recorded'}.\nDevelopment invocation: ${progress.development_used.join(', ') || 'none recorded'}.` : 'Capability progress appears after a source checkpoint.');
  text('capability-scope', progress?.scope || 'Declaring, checking, activating and using a tool are separate steps.');
  $('review-submission').disabled = !!state.app?.active || !!state.app?.evaluation?.busy;
}
$('view-verification').onclick = () => openChecks();
function renderSubmission(ticket) {
  const body = $('submission-feedback'); body.replaceChildren();
  const summary = document.createElement('p');
  summary.textContent = ticket.ready_for_independent_checks ? 'Public submission checks found no issue. Independent checks are still required.' :
    !ticket.policy.changed_files.length ? 'There is no edited seed submission to review yet.' : 'Review these issues before independent checks:';
  body.append(summary);
  const list = document.createElement('ul');
  for (const issue of ticket.policy.changed_files.length ? ticket.issues : []) {
    const item = document.createElement('li');
    const observation = document.createElement('p');
    observation.textContent = issue.evidence + (issue.paths.length ? ` Paths: ${issue.paths.join(', ')}` : '');
    const explanation = document.createElement('p'); explanation.className = 'muted';
    explanation.textContent = 'Possible explanation: ' + issue.hypothesis;
    item.append(observation, explanation); list.append(item);
  }
  body.append(list);
  if (ticket.development_failure) {
    const label = document.createElement('p'); label.textContent = 'Recent development check (reported by the guest):';
    const output = document.createElement('pre'); output.style.whiteSpace = 'pre-wrap';
    output.textContent = ticket.development_failure.output;
    const hypothesis = document.createElement('p'); hypothesis.className = 'muted';
    hypothesis.textContent = 'Possible explanation: ' + ticket.development_failure.hypothesis;
    body.append(label, output, hypothesis);
  }
  const scope = document.createElement('p'); scope.className = 'muted'; scope.textContent = ticket.scope; body.append(scope);
  text('submission-technical', JSON.stringify(ticket, null, 2));
  $('send-submission-feedback').disabled = ticket.ready_for_independent_checks || !ticket.policy.changed_files.length;
}
$('review-submission').onclick = async () => {
  try {
    const result = await api('/api/submission-review', {id: state.id});
    renderSubmission(result.ticket);
    $('submission-dialog').showModal();
  } catch (error) { toast(error.message); }
};
$('close-submission').onclick = () => $('submission-dialog').close();
$('send-submission-feedback').onclick = async () => {
  try {
    const result = await api('/api/submission-review', {id: state.id});
    if (result.ticket.ready_for_independent_checks || !result.ticket.policy.changed_files.length) { renderSubmission(result.ticket); return; }
    await api('/api/resume', {id: state.id, message: result.message});
    $('submission-dialog').close(); await poll();
  } catch (error) { toast(error.message); }
};

async function refreshFiles() {
  const id = state.id; if (!id) return;
  const files = await api('/api/files?id=' + id); if (id !== state.id) return;
  const main = $('files'), source = $('source-files'); main.replaceChildren(); source.replaceChildren();
  const artifacts = files.filter(file => !file.path.startsWith('harness/'));
  text('file-count', artifacts.length);
  if (!artifacts.length) main.append(node('p', 'muted', 'No files yet.'));
  files.forEach(file => {
    const button = node('button', 'file-item'); button.title = file.path;
    button.append(node('span', '', '▧'), node('strong', '', file.path.replace(/^harness\//, '')));
    button.onclick = () => openFile(file.path);
    (file.path.startsWith('harness/') ? source : main).append(button);
  });
}

async function startTask(task) {
  if (busy()) { toast('Stop the active task before starting another.'); return; }
  if (!state.app.settings.configured) { openSetup(); return; }
  if (!state.app.isolation?.ready) { state.pendingTask = task; $('isolation-dialog').showModal(); return; }
  const response = await api('/api/start', { task, files: state.attachments.map(({path, data}) => ({path, data})) });
  state.attachments = []; renderAttachments();
  resetSessionFilter();
  $('task').value = ''; state.app = await api(stateAddress()); await selectSession(response.id);
}
async function resume(message = '') {
  try { await api('/api/resume', { id: state.id, message }); state.started = Date.now(); await poll(); return true; }
  catch (e) { toast(e.message); return false; }
}
$('task-form').onsubmit = async event => {
  event.preventDefault(); const task = $('task').value.trim(); if (!task || state.sending) return;
  if (busy() && state.app.active.id !== state.id) { toast('Open the active task to send your message.'); return; }
  state.sending = true; $('send').disabled = true;
  try {
    if (busy()) {
      const input = {id: state.id, message: task, mode: $('input-mode').value};
      if (!state.pendingInput || JSON.stringify(state.pendingInput.input) !== JSON.stringify(input)) state.pendingInput = {input, request_id: crypto.randomUUID()};
      await api('/api/input', {...input, request_id: state.pendingInput.request_id});
      state.pendingInput = null; $('task').value = ''; await poll();
    } else if (state.id) { if (await resume(task)) $('task').value = ''; } else await startTask(task);
  }
  catch (e) { toast(e.message); } finally { state.sending = false; if (state.app) renderApp(); }
};
$('task').onkeydown = event => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); $('task-form').requestSubmit(); } };
$('stop').onclick = async () => { try { await api('/api/stop', { id: state.id }); await poll(); } catch (e) { toast(e.message); } };
$('stop-active').onclick = async () => { try { const id = state.app?.active?.id; if (id) await api('/api/stop', {id}); await poll(); } catch (e) { toast(e.message); } };
$('view-active').onclick = () => { if (state.app.active) selectSession(state.app.active.id); };
$('new-task').onclick = home;
$('details-toggle').onclick = () => { const inspector = document.querySelector('.inspector'); inspector.classList.toggle('open'); $('details-toggle').setAttribute('aria-expanded', inspector.classList.contains('open')); };
document.addEventListener('keydown', event => { if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'n') { event.preventDefault(); home(); } });
document.querySelectorAll('[data-prompt]').forEach(button => { button.onclick = () => { $('task').value = button.dataset.prompt; $('task').focus(); }; });

async function openFile(path) {
  try {
    const file = await api('/api/file?id=' + state.id + '&path=' + encodeURIComponent(path));
    state.file = { id: state.id, path }; text('file-title', path); text('file-content', file.content + (file.truncated ? '\n\n[Preview shortened]' : ''));
    $('file-dialog').showModal();
  } catch (e) { toast(e.message); }
}
$('close-file').onclick = () => $('file-dialog').close();
$('download-file').onclick = async () => { try { const file = state.file; saveBlob(await api('/api/download?id=' + file.id + '&path=' + encodeURIComponent(file.path), undefined, true), file.path.split('/').pop()); } catch (e) { toast(e.message); } };
$('trace-button').onclick = async () => { try { saveBlob(await api('/api/export?id=' + state.id, undefined, true), 'autoproteus-session-' + state.id.slice(0, 8) + '.zip'); } catch (e) { toast(e.message); } };
$('workspace-button').onclick = async () => { try { saveBlob(await api('/api/open-workspace', { id: state.id }, true), 'autoproteus-files-' + state.id.slice(0, 8) + '.zip'); } catch (e) { toast(e.message); } };

function renderIsolation(info) {
  if (!info) return;
  const native = state.app.execution?.mode === 'native';
  text('isolation-title', native ? 'Running without VM protection.' : 'A safe place to grow.');
  text('isolation-eyebrow', native ? 'EXTERNAL PROTECTION REQUIRED' : 'PROTECTED ENVIRONMENT');
  text('isolation-description', native ? 'AutoProteus adds no filesystem or network isolation in this mode. The worker has this account’s permissions, including access to the controller. Protection must come from a disposable machine or your externally configured environment.' : 'The agent runs in a fresh Linux virtual machine. Your drives, network, clipboard, and devices stay outside it. Only model requests and bounded saved files pass through the controller.');
  visible('prepare-isolation', !native); visible('isolation-footnote', !native);
  text('isolation-footnote', state.app.platform === 'linux' ? 'One-time guest download: about 70 MB. KVM must be available; the Linux launcher handles dependency and permission setup. Later tasks reuse the downloaded environment.' : 'One-time download: about 290 MB. Windows Hypervisor Platform must be enabled. Subsequent tasks start in a few seconds.');
  text('isolation-message', info.message);
  error('isolation-error', info.error);
  $('prepare-isolation').disabled = info.busy || !info.available;
  text('prepare-isolation', info.busy ? 'Preparing…' : info.ready ? 'Prepare again' : 'Prepare isolated environment');
  text('isolation-status', native ? 'VM protection off' : info.ready ? 'VM isolation ready' : info.busy ? 'Preparing isolation…' : 'Set up isolation');
  if (info.ready && state.pendingTask && $('isolation-dialog').open) {
    const task = state.pendingTask; state.pendingTask = null; $('isolation-dialog').close();
    startTask(task).catch(e => toast(e.message));
  }
}
$('close-isolation').onclick = () => $('isolation-dialog').close();
$('isolation-status').onclick = () => $('isolation-dialog').showModal();
$('try-seed').onclick = async () => {
  try { const result = await api('/api/try-seed', {id: state.id}); resetSessionFilter(); state.app = await api(stateAddress()); await selectSession(result.id); }
  catch (e) { toast(e.message); }
};
$('reset-seed').onclick = async () => {
  try { await api('/api/reset', {id: state.id}); await poll(); }
  catch (e) { toast(e.message); }
};
$('restart-seed').onclick = async () => {
  try { await api('/api/restart-seed', {id: state.id}); await poll(); }
  catch (e) { toast(e.message); }
};
$('prepare-isolation').onclick = async () => {
  try { renderIsolation(await api('/api/isolation/setup', {})); }
  catch (e) { error('isolation-error', e.message); }
};

function renderEvaluation(report) {
  state.checkReport = report;
  const native = (report?.execution_mode || state.app.execution?.mode) === 'native';
  visible('check-execution', native);
  text('check-execution', native ? 'Native functional checks only. The controller, tests and reports are not protected from the code being checked.' : '');
  text('check-description', native ? 'Both versions run the starter tests and the same task suite in fresh Linux processes. Sources and settings are copied for the comparison, but same-account code can alter them. These results do not verify VM isolation.' : 'First, both versions must pass the starter’s unchanged tests. Then they run the same task suite in fresh VMs, with saved files and code behavior checked independently. Your source and model settings are frozen for this comparison.');
  Array.from($('check-repeats').options).forEach(option => { const repeats = Number(option.value); option.textContent = `${repeats} repeat${repeats === 1 ? '' : 's'} · ${(state.app.tasks_count || 16) * repeats * 2} runs`; });
  text('check-message', report?.message || 'Compare this source copy with the starter using the connected model.');
  visible('stop-checks', report?.status === 'running');
  $('run-checks').disabled = report?.status === 'running' || state.app.evaluation?.busy || busy();
  $('check-repeats').disabled = report?.status === 'running';
  const summary = $('check-summary'); summary.replaceChildren();
  for (const version of ['starter', 'edited']) {
    const result = report?.summary?.[version];
    const regression = report?.regressions?.[version];
    if (!result && !regression) continue;
    const card = node('div', 'check-score');
    card.append(node('strong', '', version === 'starter' ? 'Starter seed' : 'Edited seed'),
      node('span', '', result ? `${result.passed}/${result.total} verified tasks` : 'Task comparison not run'));
    if (result) card.append(node('small', '', `${result.seconds}s · ${result.steps} reported steps · ${result.format_repairs} format repairs`));
    if (regression) {
      card.append(node('small', regression.passed ? 'check-pass' : 'check-fail', `${native ? 'Native functional' : 'Seed'} regressions: ${regression.passed ? 'passed' : 'failed'} · ${regression.tests} test${regression.tests === 1 ? '' : 's'}`));
      const details = node('details'); details.append(node('summary', '', 'Guest test output'), node('pre', '', regression.output || ''));
      card.append(details);
    }
    summary.append(card);
  }
  text('check-model', report ? `${report.model} · ${report.results.length}/${report.total} runs · ${report.execution_mode === 'native' ? 'without VM protection' : report.execution_mode === 'vm' ? 'VM execution' : 'execution mode not recorded'}` : 'Uses your connected model.');
  const body = $('check-rows'); body.replaceChildren();
  const rows = new Map();
  for (const result of report?.results || []) {
    const key = result.repeat + '/' + result.task;
    if (!rows.has(key)) rows.set(key, {task:result.task, repeat:result.repeat});
    rows.get(key)[result.version] = result;
  }
  for (const row of rows.values()) {
    const element = node('tr');
    element.append(node('th', '', row.task + ' · ' + row.repeat));
    for (const version of ['starter', 'edited']) {
      const result = row[version], cell = node('td');
      cell.textContent = !result ? 'Pending' : result.passed ? 'Passed' : 'Failed';
      if (result) {
        cell.className = result.passed ? 'check-pass' : 'check-fail';
        cell.title = `${result.seconds}s · ${result.steps} reported steps\n` + (result.detail || result.checks.filter(c => !c.passed).map(c => 'Failed: ' + c.path).join('\n'));
        if (!result.passed) cell.append(node('small', 'check-detail', result.detail || result.checks.filter(c => !c.passed).map(c => 'Missing or incorrect: ' + c.path).join(', ')));
      }
      element.append(cell);
    }
    body.append(element);
  }
  const changes = $('check-changes'); changes.replaceChildren();
  if (report && !report.changes.length) changes.append(node('p', 'muted', 'This source copy matches the starter.'));
  for (const change of report?.changes || []) {
    const details = node('details');
    details.append(node('summary', '', `${change.kind}: ${change.path}`),
      node('pre', '', change.diff || `${change.before_bytes} → ${change.after_bytes} bytes`));
    changes.append(details);
  }
}
async function openChecks() {
  state.checkSession = state.id;
  error('check-error', '');
  let report = state.app.evaluation?.session === state.id ? state.app.evaluation : null;
  if (!report && state.session?.evaluation_check) {
    try { report = await api('/api/seed-check?id=' + encodeURIComponent(state.session.evaluation_check)); }
    catch (e) { error('check-error', e.message); }
  }
  $('check-repeats').value = String(report?.repeats || 2);
  renderEvaluation(report); $('check-dialog').showModal();
}
$('check-seed').onclick = openChecks;
$('evaluation-status').onclick = () => { state.checkSession = state.app.evaluation.session; $('check-repeats').value = String(state.app.evaluation.repeats); renderEvaluation(state.app.evaluation); $('check-dialog').showModal(); };
$('close-checks').onclick = () => $('check-dialog').close();
$('run-checks').onclick = async () => {
  error('check-error', ''); $('run-checks').disabled = true;
  try { renderEvaluation(await api('/api/seed-check', {id:state.checkSession, repeats:Number($('check-repeats').value)})); }
  catch (e) { error('check-error', e.message); $('run-checks').disabled = false; }
};
$('stop-checks').onclick = async () => { try { await api('/api/seed-check/stop', {}); await poll(); } catch (e) { error('check-error', e.message); } };

function providerTab(provider) {
  state.provider = provider; const local = provider === 'ollama';
  visible('local-panel', local); visible('hosted-panel', !local);
  $('local-tab').classList.toggle('active', local); $('hosted-tab').classList.toggle('active', !local);
  $('local-tab').setAttribute('aria-selected', local); $('hosted-tab').setAttribute('aria-selected', !local);
  error('setup-error', ''); renderConnectButton();
}
function renderConnectButton() {
  const installed = state.installed.some(model => [model.name, model.name.replace(/:latest$/, '')].includes($('local-model').value.trim()));
  $('connect-button').textContent = state.provider === 'hosted' ? 'Test & connect →' : installed ? 'Connect local model →' : 'Prepare local model →';
  $('connect-button').disabled = state.setupBusy;
}
async function detectLocal() {
  try {
    const result = await api('/api/local'); state.installed = result.models;
    $('installed-models').replaceChildren(...result.models.map(model => { const option = node('option'); option.value = model.name; return option; }));
    text('engine-status', result.available ? `Local engine found · ${result.models.length} installed model${result.models.length === 1 ? '' : 's'}` : 'No local engine found. AutoProteus can prepare one for you.');
    $('engine-status').classList.toggle('available', result.available); renderConnectButton();
  } catch (e) { text('engine-status', e.message); }
}
function openSetup() {
  const config = state.app.settings;
  $('local-url').value = config.provider === 'ollama' ? config.base_url : 'http://127.0.0.1:11434';
  if (config.provider === 'ollama') $('local-model').value = config.model;
  if (config.provider === 'hosted') { $('hosted-url').value = config.base_url; $('hosted-model').value = config.model; $('json-mode').checked = config.json_mode; }
  $('hosted-protocol').value = config.protocol;
  $('api-key').value = ''; $('api-key').placeholder = config.has_key ? 'Saved key · leave blank to keep it' : 'Enter a key, if required';
  providerTab(config.provider === 'hosted' ? 'hosted' : 'ollama');
  if (!$('setup-dialog').open) $('setup-dialog').showModal(); detectLocal();
}
$('connection').onclick = openSetup;
$('close-setup').onclick = () => $('setup-dialog').close();
$('local-tab').onclick = () => providerTab('ollama'); $('hosted-tab').onclick = () => providerTab('hosted');
$('local-model').oninput = renderConnectButton;
document.querySelectorAll('[data-model]').forEach(button => { button.onclick = () => { $('local-model').value = button.dataset.model; document.querySelectorAll('[data-model]').forEach(b => b.classList.toggle('selected', b === button)); renderConnectButton(); }; });
$('connection-form').onsubmit = async event => {
  event.preventDefault(); error('setup-error', ''); $('connect-button').disabled = true;
  try {
    if (state.provider === 'hosted') {
      if (!$('hosted-url').value.trim() || !$('hosted-model').value.trim()) throw new Error('Enter a service address and model name.');
      text('connect-button', 'Testing connection…');
      await api('/api/connect', { provider: 'hosted', base_url: $('hosted-url').value.trim(), model: $('hosted-model').value.trim(), api_key: $('api-key').value.trim(), json_mode: $('json-mode').checked, protocol: $('hosted-protocol').value });
      $('api-key').value = ''; $('setup-dialog').close(); toast('Your hosted model is connected.');
    } else {
      const model = $('local-model').value.trim();
      if (!model) throw new Error('Choose a model name.');
      const installed = state.installed.some(item => [item.name, item.name.replace(/:latest$/, '')].includes(model));
      if (installed) { await api('/api/connect', { provider: 'ollama', base_url: $('local-url').value.trim(), model }); $('setup-dialog').close(); toast('Your local model is connected.'); }
      else { await api('/api/settings', { provider: 'ollama', base_url: $('local-url').value.trim(), model, configured: false }); await api('/api/setup', { model }); state.setupBusy = true; }
    }
    await poll();
  } catch (e) { error('setup-error', e.message); }
  finally { renderConnectButton(); }
};
function renderSetupProgress(setup) {
  const wasBusy = state.setupBusy; state.setupBusy = setup.busy;
  visible('setup-progress', setup.busy);
  if (setup.busy) {
    text('setup-message', setup.message); text('setup-percent', setup.progress === null ? '' : setup.progress + '%');
    $('progress-bar').style.width = (setup.progress ?? 0) + '%';
  }
  if (wasBusy && !setup.busy) {
    if (setup.phase === 'ready') { $('setup-dialog').close(); toast(setup.message); detectLocal(); }
    else if (setup.phase === 'error') error('setup-error', setup.message);
  }
  renderConnectButton();
}
async function demo() {
  try {
    await api('/api/connect', { provider: 'demo', model: 'scripted-demo' });
    $('setup-dialog').close(); state.app = await api(stateAddress());
    await startTask('Show me how AutoProteus works: create a welcome note, verify it, and update the checklist.');
  } catch (e) { toast(e.message); }
}
$('demo-home').onclick = demo; $('demo-setup').onclick = demo;

function openSettings() {
  const config = state.app.settings;
  text('settings-model', config.configured ? config.model : 'No model connected'); text('settings-provider', config.provider === 'demo' ? 'Interactive demo' : config.provider === 'ollama' ? 'Local model' : 'Hosted connection');
  ['max_steps', 'temperature', 'context_tokens', 'response_tokens', 'request_timeout', 'command_timeout'].forEach(key => $(key.replaceAll('_', '-')).value = config[key]);
  $('protocol').value = config.protocol; $('terminal').checked = config.terminal; $('thinking').value = config.thinking === null ? 'auto' : config.thinking ? 'on' : 'off';
  error('settings-error', ''); $('settings-dialog').showModal();
}
$('settings-button').onclick = openSettings; $('close-settings').onclick = () => $('settings-dialog').close();
$('upgrade-limits').onclick = () => {
  $('max-steps').value = 128; $('response-tokens').value = 8192;
  $('context-tokens').value = Math.max(32768, Number($('context-tokens').value));
  $('request-timeout').value = Math.max(300, Number($('request-timeout').value));
  $('settings-form').querySelector('details').open = true;
  toast('Longer upgrade allowances selected. Save preferences to apply them.');
};
$('change-model').onclick = () => { $('settings-dialog').close(); openSetup(); };
$('settings-form').onsubmit = async event => {
  event.preventDefault(); const data = { protocol: $('protocol').value, terminal: $('terminal').checked, thinking: $('thinking').value === 'auto' ? null : $('thinking').value === 'on' };
  ['max_steps', 'temperature', 'context_tokens', 'response_tokens', 'request_timeout', 'command_timeout'].forEach(key => data[key] = Number($(key.replaceAll('_', '-')).value));
  try { await api('/api/settings', data); $('settings-dialog').close(); toast('Preferences saved. They apply to the next run.'); await poll(); }
  catch (e) { error('settings-error', e.message); }
};
$('quit').onclick = async () => { try { await api('/api/shutdown', {}); $('settings-dialog').close(); toast('AutoProteus is closed. Use the launcher to open it again.'); clearInterval(poll.timer); } catch (e) { toast(e.message); } };

async function poll() {
  if (state.polling) return;
  state.polling = true;
  try {
    const previousWorker = state.app?.active?.id;
    state.app = await api(stateAddress()); renderApp();
    if (state.id) {
      const id = state.id, update = await api('/api/session?' + new URLSearchParams({id, after: state.session?.feed_count || 0, revision: state.session?.revision || -1}));
      if (state.id === id && !update.unchanged) {
        const previous = state.session?.feed || [];
        const feed = update.reset || update.feed_start === 0 ? update.feed : [...previous.slice(0, update.feed_start), ...update.feed];
        state.session = {...update, feed}; renderSession(); await refreshFiles();
      } else if (state.id === id && state.session) {
        // Worker liveness can change after the last saved session revision.
        if (previousWorker !== state.app.active?.id) renderInputQueue(state.session);
        state.session.verification = update.verification; renderVerification();
      }
    }
  } catch (e) { if (!poll.warned) { toast('The app disconnected. Reopen AutoProteus or refresh this page.'); poll.warned = true; } }
  finally { state.polling = false; }
}
async function initialize() {
  try {
    state.app = await api('/api/state'); renderApp();
    const recent = state.app.sessions.find(session => ['running', 'interrupted', 'paused', 'waiting', 'error'].includes(session.status));
    if (recent) await selectSession(recent.id);
    if (!state.app.settings.configured) openSetup();
    poll.timer = setInterval(poll, 1100);
  } catch (e) { toast('AutoProteus could not connect. Refresh the page or use the launcher again.'); }
}
initialize();
