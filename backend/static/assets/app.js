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
  busy: false,
  rateTimer: null,
  selectedModel: sessionStorage.getItem('estatebot.model') || '',
  modelLabels: {},
};

const $ = (id) => document.getElementById(id);
const chatLog = $('chat-log');
const composer = $('composer');
const input = $('message');
const send = $('send');
const modelSelect = $('model-select');

function escapeHtml(value) {
  return value.replace(/[&<>"']/g, (character) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  })[character]);
}

function markdown(value) {
  let text = escapeHtml(value);
  text = text
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\n\n+/g, '</p><p>')
    .replace(/\n[-*] /g, '</p><ul><li>')
    .replace(/\n/g, '<br>')
    .replace(/<\/li><br>/g, '</li>')
    .replace(/(<li>.*?)(?=<br>|$)/g, '$1</li>');
  return `<p>${text}</p>`;
}

function trimMessages() {
  if (state.messages.length > MAX_VISIBLE_MESSAGES) {
    state.messages.splice(0, state.messages.length - MAX_VISIBLE_MESSAGES);
  }
}

function save() {
  try {
    sessionStorage.setItem('estatebot.messages', JSON.stringify(state.messages));
    if (state.conversationId) {
      sessionStorage.setItem('estatebot.conversation_id', state.conversationId);
    }
  } catch {
    // Storage can be disabled or full; chat remains usable for this page view.
  }
}

function renderMessage(message) {
  const row = document.createElement('article');
  row.className = `message ${message.role}`;

  const avatar = document.createElement('div');
  avatar.className = 'avatar';
  avatar.textContent = message.role === 'user' ? 'You' : 'EB';

  const bubble = document.createElement('div');
  bubble.className = `bubble ${message.grounded === false ? 'not-found' : ''} ${message.error ? 'error-bubble' : ''}`;
  bubble.innerHTML = markdown(message.content);

  if (message.retry) {
    const button = document.createElement('button');
    button.className = 'button secondary retry-button';
    button.type = 'button';
    button.disabled = state.busy;
    button.textContent = 'Retry';
    button.addEventListener('click', () => {
      if (state.busy) return;
      state.messages = state.messages.filter((item) => item !== message);
      render();
      sendMessage(message.retry);
    });
    bubble.appendChild(button);
  }

  if (message.citations?.length) {
    const sources = document.createElement('div');
    sources.className = 'sources';
    const label = document.createElement('span');
    label.className = 'sources-label';
    label.textContent = 'Sources';
    sources.appendChild(label);

    message.citations.forEach((citation) => {
      const link = document.createElement('a');
      link.className = 'citation';
      link.href = citation.source_url;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      link.textContent = `${citation.name || citation.source_id} ↗`;
      sources.appendChild(link);
    });
    bubble.appendChild(sources);
  }

  if (message.role === 'assistant' && message.model_used) {
    const model = document.createElement('div');
    model.className = 'model-used';
    model.textContent = `Answered with ${state.modelLabels[message.model_used] || message.model_used}`;
    bubble.appendChild(model);
  }

  row.append(avatar, bubble);
  chatLog.appendChild(row);
}

function render() {
  chatLog.innerHTML = '';
  if (!state.messages.length) {
    chatLog.innerHTML = '<div class="welcome"><strong>What would you like to explore?</strong><br>Ask about properties, projects, locations, prices, or bedrooms from the available DarGlobal and Wasalt data.</div>';
    return;
  }
  state.messages.forEach(renderMessage);
  chatLog.scrollTop = chatLog.scrollHeight;
}

function addMessage(message) {
  state.messages.push(message);
  trimMessages();
  save();
  render();
}

function setBusy(value) {
  state.busy = value;
  input.disabled = value;
  send.disabled = value;
  modelSelect.disabled = value;
  send.textContent = value ? 'Working…' : 'Send';
  document.querySelectorAll('.retry-button').forEach((button) => {
    button.disabled = value;
  });
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
  const wakeTimer = setTimeout(() => {
    banner('Waking up the server… this can take up to about 30 seconds on the free tier.');
  }, 1500);
  const timeout = setTimeout(() => controller.abort(), 30000);

  try {
    const [statsResponse, healthResponse] = await Promise.all([
      fetch('/api/stats', { signal: controller.signal }),
      fetch('/api/health', { signal: controller.signal }),
    ]);
    if (!statsResponse.ok) throw new Error('stats unavailable');

    const stats = await statsResponse.json();
    const health = await healthResponse.json();
    const container = $('stats');
    container.replaceChildren();
    addStat(container, stats.listings_total ?? 0, 'active listings');
    addStat(container, stats.content_documents_total ?? 0, 'content documents');
    addStat(container, (stats.cities_covered || []).length, 'cities covered');
    addStat(container, health.model?.primary || 'data-only', 'configured model');

    const timestamp = document.createElement('p');
    timestamp.textContent = `Last scrape: ${stats.last_scrape_completed_at ? new Date(stats.last_scrape_completed_at).toLocaleString() : 'not recorded yet'}.`;
    container.appendChild(timestamp);
    $('mode-label').textContent = health.retrieval_mode || 'data-only fallback';
    banner('');
    if (!stats.listings_total) {
      banner('The corpus is empty. Run the scraper and ingestion pipeline before asking questions.');
    }
  } catch {
    $('stats').textContent = 'Corpus details are temporarily unavailable.';
    banner('The server is still waking up or temporarily unavailable. Please try again in a moment.', true);
  } finally {
    clearTimeout(wakeTimer);
    clearTimeout(timeout);
  }
}

async function loadModels() {
  try {
    const response = await fetch('/api/models');
    if (!response.ok) throw new Error('models unavailable');
    const payload = await response.json();
    (payload.models || []).forEach((model) => {
      state.modelLabels[model.id] = model.label;
      const option = document.createElement('option');
      option.value = model.id;
      option.textContent = `${model.label} · Free`;
      modelSelect.appendChild(option);
    });
    if ([...modelSelect.options].some((option) => option.value === state.selectedModel)) {
      modelSelect.value = state.selectedModel;
    } else {
      state.selectedModel = '';
      sessionStorage.removeItem('estatebot.model');
    }
    render();
  } catch {
    $('model-help').textContent = 'Automatic free-model fallback is active.';
  }
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
      // An invalid frame cannot be treated as verified output.
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
    banner(`Rate limit reached. You can send another question in ${remaining} second${remaining === 1 ? '' : 's'}.`, true);
    send.textContent = `Wait ${remaining}s`;
  };

  update();
  state.rateTimer = setInterval(update, 250);
}

async function sendMessage(text) {
  if (state.busy) return;
  setBusy(true);
  banner('');
  addMessage({ role: 'user', content: text });
  const typing = { role: 'assistant', content: 'Thinking…', typing: true };
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
      body: JSON.stringify({ message: text, conversation_id: state.conversationId, model: state.selectedModel || null }),
      signal: controller.signal,
    });

    if (response.status === 429) {
      const error = await response.json();
      retryAfter = Math.max(1, Number(error.retry_after_seconds || response.headers.get('Retry-After')) || 60);
      throw new Error(`Rate limited. Please wait ${retryAfter} seconds.`);
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
        typing.content = answer || 'Thinking…';
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
      if (!final) {
        throw new Error('The response stream was interrupted before verification completed. Please try again.');
      }
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
    });
  } catch (error) {
    state.messages = state.messages.filter((message) => !message.typing);
    addMessage({
      role: 'assistant',
      content: error.name === 'AbortError' ? 'The request timed out. Please try again.' : error.message || 'Something went wrong. Please try again.',
      retry: text,
      error: true,
      grounded: false,
    });
  } finally {
    clearTimeout(timer);
    if (retryAfter) startRateLimitCountdown(retryAfter);
    else setBusy(false);
    save();
  }
}

composer.addEventListener('submit', (event) => {
  event.preventDefault();
  const text = input.value.trim();
  if (!text || state.busy) return;
  input.value = '';
  $('char-count').textContent = '0 / 2000';
  sendMessage(text);
});

input.addEventListener('input', () => {
  $('char-count').textContent = `${input.value.length} / 2000`;
});

input.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    composer.requestSubmit();
  }
});

modelSelect.addEventListener('change', () => {
  state.selectedModel = modelSelect.value;
  if (state.selectedModel) sessionStorage.setItem('estatebot.model', state.selectedModel);
  else sessionStorage.removeItem('estatebot.model');
});

document.querySelectorAll('.suggestions button').forEach((button) => {
  button.addEventListener('click', () => {
    input.value = button.textContent;
    input.focus();
    composer.requestSubmit();
  });
});

const closeAbout = () => {
  const trigger = $('about-button');
  trigger.focus();
  $('about-panel').hidden = true;
  trigger.setAttribute('aria-expanded', 'false');
};

$('about-button').addEventListener('click', () => {
  if (!$('about-panel').hidden) {
    closeAbout();
    return;
  }
  $('about-panel').hidden = false;
  $('about-button').setAttribute('aria-expanded', 'true');
});
$('about-close').addEventListener('click', closeAbout);
document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape' && !$('about-panel').hidden) closeAbout();
});

render();
Promise.allSettled([loadStats(), loadModels()]);
