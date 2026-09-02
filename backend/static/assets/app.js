const MAX_VISIBLE_MESSAGES = 100;

function restoredMessages() {
  try {
    const value = JSON.parse(sessionStorage.getItem('estatebot.messages') || '[]');
    return Array.isArray(value) ? value.slice(-MAX_VISIBLE_MESSAGES) : [];
  } catch {
    return [];
  }
}

const state = {
  conversationId: sessionStorage.getItem('estatebot.conversation_id') || null,
  messages: restoredMessages(),
  selectedModel: sessionStorage.getItem('estatebot.model') || '',
  modelLabels: {},
  models: [],
  stats: null,
  busy: false,
  rateTimer: null,
  toastTimer: null,
};

const $ = (id) => document.getElementById(id);
const chatLog = $('chat-log');
const suggestions = $('suggestions');
const workspace = $('workspace');
const composer = $('composer');
const input = $('message');
const send = $('send');
const modelTrigger = $('model-trigger');
const modelMenu = $('model-menu');
const modelOptions = $('model-options');
const aboutDialog = $('about-dialog');

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  })[character]);
}

function inlineMarkdown(value) {
  return value
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code>$1</code>');
}

function markdown(value) {
  const lines = escapeHtml(value).split('\n');
  const output = [];
  let paragraph = [];
  let list = [];

  const flushParagraph = () => {
    if (!paragraph.length) return;
    output.push(`<p>${inlineMarkdown(paragraph.join('<br>'))}</p>`);
    paragraph = [];
  };
  const flushList = () => {
    if (!list.length) return;
    output.push(`<ul>${list.map((item) => `<li>${inlineMarkdown(item)}</li>`).join('')}</ul>`);
    list = [];
  };

  lines.forEach((line) => {
    const item = line.match(/^\s*[-*]\s+(.+)$/);
    if (item) {
      flushParagraph();
      list.push(item[1]);
      return;
    }
    flushList();
    if (!line.trim()) {
      flushParagraph();
      return;
    }
    paragraph.push(line);
  });
  flushList();
  flushParagraph();
  return output.join('') || '<p></p>';
}

function trimMessages() {
  if (state.messages.length > MAX_VISIBLE_MESSAGES) {
    state.messages.splice(0, state.messages.length - MAX_VISIBLE_MESSAGES);
  }
}

function save() {
  try {
    sessionStorage.setItem('estatebot.messages', JSON.stringify(state.messages));
    if (state.conversationId) sessionStorage.setItem('estatebot.conversation_id', state.conversationId);
    else sessionStorage.removeItem('estatebot.conversation_id');
    if (state.selectedModel) sessionStorage.setItem('estatebot.model', state.selectedModel);
    else sessionStorage.removeItem('estatebot.model');
  } catch {
    // Storage can be disabled or full; the active page remains functional.
  }
}

function iconMarkup(name) {
  const icons = {
    copy: '<svg aria-hidden="true" viewBox="0 0 24 24"><rect x="8" y="8" width="11" height="11" rx="2"/><path d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3"/></svg>',
    external: '<svg aria-hidden="true" viewBox="0 0 24 24"><path d="M14 5h5v5M10 14 19 5M19 13v6H5V5h6"/></svg>',
    check: '<svg class="model-check" aria-hidden="true" viewBox="0 0 24 24"><path d="m5 12 4 4L19 6"/></svg>',
  };
  return icons[name] || '';
}

function showToast(text) {
  const toast = $('toast');
  toast.textContent = text;
  toast.hidden = false;
  if (state.toastTimer) clearTimeout(state.toastTimer);
  state.toastTimer = setTimeout(() => { toast.hidden = true; }, 1800);
}

async function copyText(value) {
  try {
    await navigator.clipboard.writeText(value);
    showToast('Answer copied');
  } catch {
    showToast('Copy unavailable');
  }
}

function modelLabel(modelId) {
  return state.modelLabels[modelId] || modelId || '';
}

function renderMessage(message) {
  const row = document.createElement('article');
  row.className = `message ${message.role}`;

  const avatar = document.createElement('div');
  avatar.className = 'avatar';
  avatar.textContent = message.role === 'user' ? 'You' : 'EB';
  avatar.setAttribute('aria-hidden', 'true');

  const content = document.createElement('div');
  content.className = 'message-content';

  if (message.role === 'assistant') {
    const head = document.createElement('div');
    head.className = 'message-head';
    const name = document.createElement('strong');
    name.textContent = 'EstateBot';
    head.appendChild(name);

    const meta = document.createElement('span');
    meta.className = 'message-model';
    if (message.typing) {
      meta.textContent = state.selectedModel ? `Thinking with ${modelLabel(state.selectedModel)}…` : 'Checking the source data…';
    } else if (message.model_used) {
      const fallback = message.requested_model && message.requested_model !== message.model_used;
      meta.textContent = `· ${modelLabel(message.model_used)}${fallback ? ' fallback' : ''}`;
    } else if (message.grounded === false && !message.error) {
      meta.textContent = '· No matching source data';
    } else if (message.citations?.length) {
      meta.textContent = '· Source-grounded';
    } else if (message.retrieval_mode === 'structured') {
      meta.textContent = '· Corpus summary';
    }
    if (meta.textContent) head.appendChild(meta);
    content.appendChild(head);
  }

  const bubble = document.createElement('div');
  bubble.className = `bubble ${message.grounded === false ? 'not-found' : ''} ${message.error ? 'error-bubble' : ''} ${message.typing ? 'typing' : ''}`;
  if (message.typing && !message.content) {
    bubble.innerHTML = '<span class="typing-dots" aria-label="EstateBot is thinking"><i></i><i></i><i></i></span>';
  } else {
    bubble.innerHTML = markdown(message.content);
    if (message.typing) {
      const cursor = document.createElement('span');
      cursor.className = 'streaming-cursor';
      cursor.setAttribute('aria-hidden', 'true');
      bubble.appendChild(cursor);
    }
  }

  if (message.retry) {
    const button = document.createElement('button');
    button.className = 'retry-button';
    button.type = 'button';
    button.disabled = state.busy;
    button.textContent = 'Try again';
    button.addEventListener('click', () => {
      if (state.busy) return;
      state.messages = state.messages.filter((item) => item !== message);
      render();
      sendMessage(message.retry);
    });
    bubble.appendChild(button);
  }
  content.appendChild(bubble);

  if (message.citations?.length) {
    const sources = document.createElement('div');
    sources.className = 'sources';
    if (message.citations.some((citation) => citation.record_type)) sources.classList.add('has-property-cards');
    const label = document.createElement('span');
    label.className = 'sources-label';
    label.textContent = `${message.citations.length} source${message.citations.length === 1 ? '' : 's'}`;
    sources.appendChild(label);

    message.citations.forEach((citation) => {
      const link = document.createElement('a');
      link.className = `citation ${citation.record_type ? 'property-card' : ''}`;
      link.href = citation.source_url;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      link.setAttribute('aria-label', `Open source: ${citation.name || citation.source_id}`);

      const sourceName = citation.source_site === 'darglobal' ? 'DarGlobal' : 'Wasalt';
      const site = document.createElement('span');
      site.className = 'citation-site';
      site.textContent = citation.source_site === 'darglobal' ? 'DG' : 'W';

      if (citation.record_type) {
        const media = document.createElement('span');
        media.className = 'property-media';
        if (citation.image_url) {
          const image = document.createElement('img');
          image.src = citation.image_url;
          image.alt = '';
          image.loading = 'lazy';
          image.referrerPolicy = 'no-referrer';
          image.addEventListener('error', () => {
            image.remove();
            media.classList.add('image-unavailable');
          });
          media.appendChild(image);
        } else {
          media.classList.add('image-unavailable');
        }
        const sourceBadge = document.createElement('span');
        sourceBadge.className = 'property-source';
        sourceBadge.textContent = sourceName;
        media.appendChild(sourceBadge);

        const cardBody = document.createElement('span');
        cardBody.className = 'property-card-body';
        const title = document.createElement('strong');
        title.textContent = citation.name || citation.source_id;
        const location = document.createElement('span');
        location.className = 'property-location';
        location.textContent = citation.location || 'Location not published';
        const facts = document.createElement('span');
        facts.className = 'property-facts';
        [citation.property_category?.replaceAll('_', ' '), citation.bedrooms, citation.price]
          .filter(Boolean)
          .forEach((value) => {
            const fact = document.createElement('span');
            fact.textContent = value;
            facts.appendChild(fact);
          });
        const footer = document.createElement('span');
        footer.className = 'property-footer';
        footer.textContent = 'View source';
        footer.insertAdjacentHTML('beforeend', iconMarkup('external'));
        cardBody.append(title, location);
        if (facts.childElementCount) cardBody.appendChild(facts);
        cardBody.appendChild(footer);
        link.append(media, cardBody);
        sources.appendChild(link);
        return;
      }

      const copy = document.createElement('span');
      copy.className = 'citation-copy';
      const title = document.createElement('strong');
      title.textContent = citation.name || citation.source_id;
      const source = document.createElement('small');
      source.textContent = sourceName;
      copy.append(title, source);
      link.append(site, copy);
      link.insertAdjacentHTML('beforeend', iconMarkup('external'));
      sources.appendChild(link);
    });
    content.appendChild(sources);
  }

  if (message.role === 'assistant' && !message.typing && !message.error && (message.model_used || message.citations?.length || message.retrieval_mode === 'structured')) {
    const actions = document.createElement('div');
    actions.className = 'message-actions';
    const copy = document.createElement('button');
    copy.type = 'button';
    copy.className = 'message-action';
    copy.innerHTML = `${iconMarkup('copy')}<span>Copy</span>`;
    copy.addEventListener('click', () => copyText(message.content));
    actions.appendChild(copy);
    content.appendChild(actions);
  }

  row.append(avatar, content);
  chatLog.appendChild(row);
}

function renderEmptyState() {
  const count = state.stats?.listings_total;
  const cityCount = state.stats?.cities_covered?.length;
  const countryCount = state.stats?.countries_covered?.length;
  const coverage = cityCount && countryCount
    ? ` spanning <strong>${cityCount} cities in ${countryCount} countries</strong>`
    : '';
  chatLog.innerHTML = `
    <div class="empty-state">
      <span class="empty-mark" aria-hidden="true"><svg viewBox="0 0 32 32"><path d="M6.5 14.3 16 6l9.5 8.3v10.2a2 2 0 0 1-2 2h-15a2 2 0 0 1-2-2V14.3Z"/><path d="M12.5 26.5v-8h7v8M4 16l12-10.5L28 16"/></svg></span>
      <p class="eyebrow">SOURCE-GROUNDED PROPERTY SEARCH</p>
      <h1>Where would you like to explore?</h1>
      <p>Ask naturally about cities, projects, prices, bedrooms, or comparisons across <strong>${count ? `${count} verified records` : 'DarGlobal and Wasalt'}</strong>${coverage}.</p>
    </div>`;
}

function render() {
  chatLog.replaceChildren();
  const isEmpty = state.messages.length === 0;
  workspace.classList.toggle('is-empty', isEmpty);
  suggestions.hidden = !isEmpty;
  if (isEmpty) renderEmptyState();
  else state.messages.forEach(renderMessage);
  if (isEmpty) {
    workspace.scrollTop = 0;
    return;
  }
  requestAnimationFrame(() => {
    workspace.scrollTop = workspace.scrollHeight;
  });
}

function addMessage(message) {
  state.messages.push(message);
  trimMessages();
  save();
  render();
}

function updateSendState() {
  send.disabled = state.busy || !input.value.trim();
}

function setBusy(value) {
  state.busy = value;
  input.disabled = value;
  modelTrigger.disabled = value;
  $('new-chat').disabled = value;
  document.querySelectorAll('.model-option, .retry-button, .suggestions button').forEach((button) => {
    button.disabled = value;
  });
  updateSendState();
}

function banner(text, error = false) {
  const element = $('status-banner');
  element.hidden = !text;
  element.className = `status-banner ${error ? 'error' : ''}`;
  element.textContent = text || '';
}

function addStat(container, value, label) {
  const card = document.createElement('div');
  card.className = 'stat';
  const strong = document.createElement('strong');
  strong.textContent = String(value);
  const small = document.createElement('small');
  small.textContent = label;
  card.append(strong, small);
  container.appendChild(card);
}

async function loadStats() {
  const controller = new AbortController();
  const wakeTimer = setTimeout(() => banner('EstateBot is waking up. This can take a few moments.'), 1500);
  const timeout = setTimeout(() => controller.abort(), 30000);
  const status = $('corpus-status');

  try {
    const [statsResponse, healthResponse] = await Promise.all([
      fetch('/api/stats', { signal: controller.signal }),
      fetch('/api/health', { signal: controller.signal }),
    ]);
    if (!statsResponse.ok || !healthResponse.ok) throw new Error('service unavailable');

    const stats = await statsResponse.json();
    await healthResponse.json();
    state.stats = stats;

    status.className = 'corpus-status ready';
    status.lastElementChild.textContent = `${stats.listings_total || 0} source records`;

    const container = $('stats');
    container.replaceChildren();
    addStat(container, stats.listings_total ?? 0, 'properties & projects');
    addStat(container, stats.content_documents_total ?? 0, 'supporting documents');
    addStat(container, (stats.cities_covered || []).length, 'cities covered');
    addStat(container, (stats.countries_covered || []).length, 'countries covered');
    addStat(container, 2, 'public sources');
    addStat(container, state.models.length || 6, 'free AI models');

    $('last-scrape').textContent = `Last data capture: ${stats.last_scrape_completed_at ? new Date(stats.last_scrape_completed_at).toLocaleString() : 'not recorded'}.`;
    banner('');
    if (!stats.listings_total) banner('Property data is temporarily unavailable.', true);
    if (!state.messages.length) render();
  } catch {
    status.className = 'corpus-status error';
    status.lastElementChild.textContent = 'Service unavailable';
    $('stats').textContent = 'Corpus details are temporarily unavailable.';
    banner('EstateBot is still starting or temporarily unavailable. Please try again shortly.', true);
  } finally {
    clearTimeout(wakeTimer);
    clearTimeout(timeout);
  }
}

function createModelOption(model) {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'model-option';
  button.setAttribute('role', 'menuitemradio');
  button.dataset.model = model.id;
  button.setAttribute('aria-checked', String(state.selectedModel === model.id));

  const icon = document.createElement('span');
  icon.className = 'model-option-icon';
  icon.textContent = model.id ? model.label.slice(0, 1) : '✦';

  const copy = document.createElement('span');
  copy.className = 'model-option-copy';
  const title = document.createElement('span');
  title.className = 'model-option-title';
  const strong = document.createElement('strong');
  strong.textContent = model.label;
  title.appendChild(strong);
  if (model.free) {
    const badge = document.createElement('span');
    badge.className = 'free-badge';
    badge.textContent = 'Free';
    title.appendChild(badge);
  }
  const detail = document.createElement('small');
  detail.textContent = model.description;
  copy.append(title, detail);

  button.append(icon, copy);
  button.insertAdjacentHTML('beforeend', iconMarkup('check'));
  button.addEventListener('click', () => selectModel(model.id));
  return button;
}

function renderModelOptions() {
  modelOptions.replaceChildren();
  const automatic = {
    id: '',
    label: 'Auto',
    provider: 'EstateBot',
    description: 'Recommended free fallback for the best chance of an answer.',
    free: false,
  };
  [automatic, ...state.models].forEach((model) => modelOptions.appendChild(createModelOption(model)));
}

function updateModelTrigger() {
  $('model-current').textContent = state.selectedModel ? modelLabel(state.selectedModel) : 'Auto';
  document.querySelectorAll('.model-option').forEach((button) => {
    button.setAttribute('aria-checked', String(button.dataset.model === state.selectedModel));
  });
}

function selectModel(modelId) {
  state.selectedModel = modelId;
  updateModelTrigger();
  save();
  closeModelMenu(true);
}

async function loadModels() {
  try {
    const response = await fetch('/api/models');
    if (!response.ok) throw new Error('models unavailable');
    const payload = await response.json();
    state.models = payload.models || [];
    state.models.forEach((model) => { state.modelLabels[model.id] = model.label; });
    if (state.selectedModel && !state.models.some((model) => model.id === state.selectedModel)) state.selectedModel = '';
  } catch {
    state.models = [];
    state.selectedModel = '';
  }
  renderModelOptions();
  updateModelTrigger();
  save();
  // Refresh restored message attribution after provider IDs gain friendly labels.
  render();
}

function openModelMenu() {
  if (state.busy) return;
  modelMenu.hidden = false;
  modelTrigger.setAttribute('aria-expanded', 'true');
  const selected = modelOptions.querySelector('[aria-checked="true"]') || modelOptions.querySelector('button');
  selected?.focus();
}

function closeModelMenu(returnFocus = false) {
  modelMenu.hidden = true;
  modelTrigger.setAttribute('aria-expanded', 'false');
  if (returnFocus) modelTrigger.focus();
}

function parseSseChunk(buffer, onEvent) {
  const events = buffer.split('\n\n');
  const tail = events.pop();
  events.forEach((raw) => {
    const event = (raw.match(/^event: (.*)$/m) || [])[1];
    const data = (raw.match(/^data: (.*)$/m) || [])[1];
    if (!event || !data) return;
    try {
      onEvent(event, JSON.parse(data));
    } catch {
      // Invalid frames cannot be treated as verified output.
    }
  });
  return tail;
}

function startRateLimitCountdown(seconds) {
  const deadline = Date.now() + Math.max(1, Math.ceil(seconds)) * 1000;
  if (state.rateTimer) clearInterval(state.rateTimer);
  setBusy(true);

  const update = () => {
    const remaining = Math.max(0, Math.ceil((deadline - Date.now()) / 1000));
    if (!remaining) {
      clearInterval(state.rateTimer);
      state.rateTimer = null;
      banner('');
      setBusy(false);
      return;
    }
    banner(`Free-model limit reached. Try again in ${remaining} second${remaining === 1 ? '' : 's'}.`, true);
  };
  update();
  state.rateTimer = setInterval(update, 250);
}

async function sendMessage(text) {
  if (state.busy) return;
  const requestedModel = state.selectedModel;
  closeModelMenu();
  setBusy(true);
  banner('');
  addMessage({ role: 'user', content: text });
  const typing = { role: 'assistant', content: '', typing: true, requested_model: requestedModel };
  state.messages.push(typing);
  trimMessages();
  render();

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 50000);
  let retryAfter = 0;

  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify({ message: text, conversation_id: state.conversationId, model: requestedModel || null }),
      signal: controller.signal,
    });

    if (response.status === 429) {
      const error = await response.json();
      retryAfter = Math.max(1, Number(error.retry_after_seconds || response.headers.get('Retry-After')) || 60);
      throw new Error(`The free-model request limit has been reached.`);
    }
    if (!response.ok) throw new Error('EstateBot could not complete that request.');

    const contentType = response.headers.get('content-type') || '';
    let final = null;

    if (contentType.includes('text/event-stream')) {
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let answer = '';
      let paintPending = false;

      const paint = () => {
        typing.content = answer;
        if (paintPending) return;
        paintPending = true;
        requestAnimationFrame(() => {
          paintPending = false;
          if (state.messages.includes(typing)) render();
        });
      };
      const handleEvent = (event, data) => {
        if (event === 'token') {
          answer += data.text || '';
          paint();
        }
        if (event === 'done') final = data;
      };

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        buffer = parseSseChunk(buffer, handleEvent);
      }
      buffer += decoder.decode();
      if (buffer.trim()) parseSseChunk(`${buffer}\n\n`, handleEvent);
      if (!final) throw new Error('The response was interrupted before verification finished. Please try again.');
      final.answer = answer || final.answer;
    } else {
      final = await response.json();
    }

    state.messages = state.messages.filter((message) => !message.typing);
    state.conversationId = final.conversation_id;
    addMessage({
      role: 'assistant',
      content: final.answer,
      citations: final.citations || [],
      grounded: final.grounded,
      model_used: final.model_used,
      requested_model: requestedModel,
      retrieval_mode: final.retrieval_mode,
      degraded: final.degraded,
    });
  } catch (error) {
    state.messages = state.messages.filter((message) => !message.typing);
    addMessage({
      role: 'assistant',
      content: error.name === 'AbortError' ? 'The request took too long. Please try again.' : error.message || 'Something went wrong. Please try again.',
      retry: text,
      error: true,
      grounded: false,
    });
  } finally {
    clearTimeout(timer);
    if (retryAfter) startRateLimitCountdown(retryAfter);
    else setBusy(false);
    save();
    input.focus();
  }
}

function resizeInput() {
  input.style.height = 'auto';
  input.style.height = `${Math.min(160, Math.max(48, input.scrollHeight))}px`;
  const count = input.value.length;
  $('char-count').textContent = `${count} / 2000`;
  $('char-count').classList.toggle('visible', count >= 1600);
  updateSendState();
}

composer.addEventListener('submit', (event) => {
  event.preventDefault();
  const text = input.value.trim();
  if (!text || state.busy) return;
  input.value = '';
  resizeInput();
  sendMessage(text);
});

input.addEventListener('input', resizeInput);
input.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    composer.requestSubmit();
  }
});

suggestions.querySelectorAll('button').forEach((button) => {
  button.addEventListener('click', () => {
    input.value = button.dataset.prompt;
    resizeInput();
    composer.requestSubmit();
  });
});

modelTrigger.addEventListener('click', () => {
  if (modelMenu.hidden) openModelMenu();
  else closeModelMenu(true);
});
$('model-menu-close').addEventListener('click', () => closeModelMenu(true));
modelOptions.addEventListener('keydown', (event) => {
  if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) return;
  event.preventDefault();
  const options = [...modelOptions.querySelectorAll('.model-option:not(:disabled)')];
  const current = options.indexOf(document.activeElement);
  let next = current;
  if (event.key === 'ArrowDown') next = (current + 1) % options.length;
  if (event.key === 'ArrowUp') next = (current - 1 + options.length) % options.length;
  if (event.key === 'Home') next = 0;
  if (event.key === 'End') next = options.length - 1;
  options[next]?.focus();
});
document.addEventListener('click', (event) => {
  if (!modelMenu.hidden && !modelMenu.contains(event.target) && !modelTrigger.contains(event.target)) closeModelMenu();
});
document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape' && !modelMenu.hidden) {
    event.preventDefault();
    closeModelMenu(true);
  }
});

$('new-chat').addEventListener('click', () => {
  if (state.busy) return;
  state.messages = [];
  state.conversationId = null;
  input.value = '';
  banner('');
  closeModelMenu();
  save();
  render();
  resizeInput();
  input.focus();
  showToast('New chat started');
});

$('about-button').addEventListener('click', () => aboutDialog.showModal());
$('about-close').addEventListener('click', () => aboutDialog.close());
aboutDialog.addEventListener('click', (event) => {
  if (event.target === aboutDialog) aboutDialog.close();
});

render();
renderModelOptions();
updateModelTrigger();
resizeInput();
Promise.allSettled([loadModels(), loadStats()]);
