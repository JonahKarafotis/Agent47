// The browser displays state; Python owns the conversation and executes tools.
// rendered counts events already shown, so polling does not duplicate messages.
let token = '', rendered = 0, busy = false, initialized = false;
const $ = id => document.getElementById(id);

// All API calls share JSON encoding and the token received during bootstrap.
// Passing a body selects POST; requests without a body use GET.
async function api(path, body) {
  const response = await fetch('/api/' + path, {
    method: body ? 'POST' : 'GET',
    headers: {'Content-Type': 'application/json', 'X-Agent47-Token': token},
    body: body ? JSON.stringify(body) : undefined
  });
  const data = await response.json();
  if (!response.ok) throw Error(data.error);
  return data;
}

function notice(text) {
  $('connection').textContent = text;
}

// Ask Python to query Ollama, then rebuild the model dropdown.
async function models() {
  try {
    const data = await api('models', {});
    $('model').replaceChildren(...data.models.map(name => {
      const item = document.createElement('option');
      item.value = name;
      item.textContent = name;
      return item;
    }));
    notice(data.models.length ? 'Choose a downloaded model.' : 'No local models found. See SETUP.md.');
  } catch (e) {
    notice('Ollama is unavailable. Start Ollama, then refresh. ' + e.message);
  }
}
$('refresh').onclick = models;

// Opening a workspace creates a fresh server session, so clear the old feed too.
$('connect').onclick = async () => {
  try {
    await api('project', {path: $('project').value, model: $('model').value});
    rendered = 0;
    $('feed').replaceChildren();
    notice('Workspace connected.');
    await poll();
  } catch (e) {
    notice(e.message);
  }
};

// Use textContent rather than innerHTML: model/file text must not become executable HTML.
function block(kind, text) {
  const article = document.createElement('article');
  article.className = kind;
  const label = document.createElement('div');
  label.className = 'label';
  label.textContent = kind === 'user' ? 'YOU' : kind === 'assistant' ? 'AGENT47' : kind.toUpperCase();
  const content = document.createElement('pre');
  content.textContent = text;
  article.append(label, content);
  $('feed').append(article);
  return article;
}

// Events become chat messages, expandable tool logs, or one-action approval cards.
function render(event) {
  if ($('welcome')) $('welcome').remove();
  if (event.kind === 'tool') {
    const details = document.createElement('details');
    const summary = document.createElement('summary');
    summary.textContent = event.name;
    const pre = document.createElement('pre');
    pre.textContent = JSON.stringify({arguments: event.arguments, result: event.result}, null, 2);
    details.append(summary, pre);
    $('feed').append(details);
  } else if (event.kind === 'approval') {
    const article = block('approval', 'Approval required\n' + event.request.name + '\n' +
      JSON.stringify(event.request.arguments, null, 2) +
      '\nCommands run with network blocked and project-scoped writes.');
    for (const [label, allow] of [['Approve once', true], ['Deny', false]]) {
      const button = document.createElement('button');
      button.textContent = label;
      button.onclick = async () => {
        try {
          // The server checks that this ID still identifies the pending action.
          await api('approve', {id: event.request.id, allow});
          article.querySelectorAll('button').forEach(b => b.disabled = true);
        } catch (e) {
          notice(e.message);
        }
      };
      article.append(button);
    }
  } else {
    block(event.kind, event.text || '');
  }
  $('feed').scrollTop = $('feed').scrollHeight;
}

// Polling retrieves a snapshot, not a live token stream from the model.
async function poll() {
  try {
    const state = await api('state');
    if (!initialized) {
      if (state.project) $('project').value = state.project;
      initialized = true;
    }
    busy = state.status !== 'idle';
    $('status').textContent = state.status;
    $('workspace').textContent = state.project || 'Choose a project to begin';
    $('send').disabled = busy || !state.project;
    $('connect').disabled = busy;
    state.events.slice(rendered).forEach(render);
    rendered = state.events.length;
  } catch (e) {
    notice(e.message);
  }
}

// Prevent a normal form navigation; submit the task and let polling show progress.
$('chat').onsubmit = async event => {
  event.preventDefault();
  if (busy) return;
  try {
    await api('chat', {message: $('message').value});
    $('message').value = '';
    await poll();
  } catch (e) {
    notice(e.message);
  }
};

// Stop requests are cooperative; an operation already in progress is not interrupted here.
$('stop').onclick = async () => {
  try {
    await api('stop', {});
    notice('Stop requested. An in-flight model call or command must finish before the task stops.');
  } catch (e) {
    notice(e.message);
  }
};

// Suggestions fill the input without sending a task automatically.
document.querySelectorAll('[data-prompt]').forEach(button => button.onclick = () => {
  $('message').value = button.dataset.prompt;
  $('message').focus();
});

// Startup: obtain the local request token, restore visible state, then poll every 1.2 seconds.
(async () => {
  try {
    token = (await (await fetch('/api/bootstrap')).json()).token;
    await poll();
    setInterval(poll, 1200);
    await models();
  } catch (e) {
    notice(e.message);
  }
})();
