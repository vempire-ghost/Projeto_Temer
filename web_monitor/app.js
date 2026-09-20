const state = { app: {}, providers: {}, tests: {}, omr: {}, computer: {} };
const chartStates = new WeakMap();
const HOUR = 60 * 60 * 1000;
const GRAPH_GAP_MS = 30 * 1000;
let ws;
let reconnectTimer;
let stateRevision = 0;
let appStatusAvailable = false;
let pendingPowerCommand = null;
let powerRequestSequence = 0;
let modalReturnFocus = null;
let temperatureModalReturnFocus = null;
let panelConnected = false;

document.querySelectorAll('.tab').forEach(button => button.addEventListener('click', () => {
  document.querySelectorAll('.tab,.panel').forEach(el => el.classList.remove('active'));
  button.classList.add('active');
  document.getElementById(button.dataset.tab).classList.add('active');
}));

function send(message) {
  if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(message));
}

function connect() {
  const wsUrl = new URL('/ws', window.location.href);
  wsUrl.protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  console.info(`[Painel] Conectando ao WebSocket ${wsUrl.href}`);
  setConnection(false, 'Conectando...');
  ws = new WebSocket(wsUrl);
  ws.onopen = () => {
    console.info('[Painel] WebSocket conectado');
    setConnection(true);
  };
  ws.onclose = event => {
    console.warn(`[Painel] WebSocket desconectado (codigo ${event.code}, motivo: ${event.reason || 'nao informado'})`);
    setConnection(false, 'Desconectado; tentando novamente...');
    clearTimeout(reconnectTimer);
    reconnectTimer = setTimeout(connect, 2000);
  };
  ws.onerror = event => {
    console.error('[Painel] Falha na conexao WebSocket. Verifique a rota /ws e a porta 5005.', event);
  };
  ws.onmessage = event => {
    try {
      const message = JSON.parse(event.data);
      if (message.type === 'state') {
        applyState(message.data, message.revision);
      } else if (message.type === 'patch') {
        (message.patches || [message]).forEach(applyPatch);
      } else if (message.type === 'error') {
        console.warn(`[Painel] Backend recusou a mensagem: ${message.message}`);
      } else if (message.type === 'command_result') {
        handleCommandResult(message);
      }
    } catch (error) {
      console.error('[Painel] Mensagem WebSocket invalida recebida', error);
    }
  };
}

function applyState(data, revision) {
  stateRevision = Number(revision) || 0;
  state.app = data.app || {};
  appStatusAvailable = !!state.app.status;
  state.providers = data.providers || {};
  state.tests = data.tests || {};
  state.omr = data.omr || {};
  state.computer = data.computer || {};
  if (state.app.footer_text) document.getElementById('app-credit').textContent = state.app.footer_text;
  render();
}

function applyPatch(patch) {
  const revision = Number(patch.revision);
  if (!Number.isFinite(revision) || revision <= stateRevision) return;
  const {section, key} = patch;
  if (!section || key == null) return;
  if (section === 'app') {
    Object.assign(state.app, patch.changes || {});
    if (Object.prototype.hasOwnProperty.call(patch.changes || {}, 'status')) appStatusAvailable = true;
    stateRevision = revision;
    renderApp();
    return;
  }
  state[section] ||= {};
  const target = state[section][key] ||= {};
  Object.assign(target, patch.changes || {});
  if (Array.isArray(patch.points)) appendUnique(target, 'history', patch.points);
  if (Array.isArray(patch.drops)) appendUnique(target, 'drops', patch.drops);
  stateRevision = revision;
  renderSection(section, key);
}

function appendUnique(target, field, values) {
  const items = target[field] ||= [];
  values.forEach(value => {
    const last = items[items.length - 1];
    if (JSON.stringify(last) !== JSON.stringify(value)) items.push(value);
  });
  if (items.length > 86400) items.splice(0, items.length - 86400);
}

function renderSection(section, key) {
  if (section === 'providers') renderProviders(key);
  else if (section === 'tests') renderTests(key);
  else if (section === 'omr') renderOmr(key);
  else if (section === 'computer') renderComputer();
}

function setConnection(online, offlineText = 'Desconectado') {
  panelConnected = online;
  const el = document.getElementById('connection');
  el.classList.toggle('online', online);
  el.classList.toggle('offline', !online);
  el.querySelector('em').textContent = online ? 'Conectado' : offlineText;
  if (!online) {
    appStatusAvailable = false;
    renderApp();
    renderComputer();
  }
}

function render() { renderApp(); renderProviders(); renderTests(); renderOmr(); renderComputer(); }

function renderApp() {
  if (state.app.footer_text) document.getElementById('app-credit').textContent = state.app.footer_text;
  const status = appStatusAvailable ? state.app.status || {} : {};
  const labels = {
    server_status: ['Operacional', 'Indisponível'],
    coopera_online: ['Online', 'Offline'],
    claro_online: ['Online', 'Offline'],
    unifique_online: ['Online', 'Offline'],
    vps_vpn_conectado: ['Conectado', 'Desconectado'],
    vps_jogo_conectado: ['Conectado', 'Desconectado']
  };
  Object.entries(labels).forEach(([key, texts]) => {
    const chip = document.querySelector(`[data-status="${key}"]`);
    const online = status[key] === true;
    chip.classList.toggle('online', online);
    chip.classList.toggle('offline', !online);
    const serverName = key === 'server_status' && online && status.servidor_conectado;
    chip.querySelector('small').textContent = serverName ? `${texts[0]} · ${serverName}` : texts[online ? 0 : 1];
  });
}

const powerModal = document.getElementById('power-modal');
const powerConfirm = document.getElementById('power-confirm');
const powerCancel = document.getElementById('power-cancel');
const temperatureModal = document.getElementById('temperature-modal');
const temperatureModalClose = document.getElementById('temperature-modal-close');
const temperatureTriggers = [
  document.getElementById('temperature-summary-trigger'),
  document.getElementById('temperature-card-trigger')
];

document.querySelectorAll('[data-power-action]').forEach(button => {
  button.addEventListener('click', () => openPowerModal(button.dataset.powerAction, button));
});

function openPowerModal(action, trigger) {
  if (pendingPowerCommand) return;
  const serverAndVps = action === 'poweroff';
  pendingPowerCommand = { action, trigger, sent: false };
  modalReturnFocus = trigger;
  document.getElementById('power-modal-message').textContent = serverAndVps
    ? 'Esta ação desligará o servidor e as VPS. O desligamento não pode ser desfeito.'
    : 'Esta ação desligará apenas o servidor. As VPS permanecerão ligadas e o desligamento não pode ser desfeito.';
  powerModal.hidden = false;
  document.body.classList.add('modal-open');
  powerCancel.focus();
}

function closePowerModal() {
  if (pendingPowerCommand?.sent) return;
  powerModal.hidden = true;
  document.body.classList.remove('modal-open');
  pendingPowerCommand = null;
  modalReturnFocus?.focus();
  modalReturnFocus = null;
}

powerCancel.addEventListener('click', closePowerModal);
powerModal.querySelector('[data-modal-close]').addEventListener('click', closePowerModal);
temperatureTriggers.forEach(trigger => trigger.addEventListener('click', () => openTemperatureModal(trigger)));
temperatureModalClose.addEventListener('click', closeTemperatureModal);
temperatureModal.querySelector('[data-temperature-modal-close]').addEventListener('click', closeTemperatureModal);

function openTemperatureModal(trigger) {
  const data = (state.computer || {}).local || {};
  const sourceAvailable = panelConnected && data.temperature_source_available === true;
  const hasTemperature = sourceAvailable && finiteNumber(data.temperature_c) != null;
  const status = document.getElementById('temperature-modal-status');
  if (hasTemperature) {
    status.textContent = 'O LibreHardwareMonitor está respondendo e fornecendo a temperatura da CPU.';
  } else if (sourceAvailable) {
    status.textContent = data.temperature_error || 'O servidor respondeu, mas não forneceu uma temperatura de CPU válida.';
  } else {
    status.textContent = data.temperature_error || 'O LibreHardwareMonitor não está em execução ou não respondeu.';
  }
  temperatureModalReturnFocus = trigger;
  temperatureModal.hidden = false;
  document.body.classList.add('modal-open');
  temperatureModalClose.focus();
}

function closeTemperatureModal() {
  temperatureModal.hidden = true;
  document.body.classList.remove('modal-open');
  temperatureModalReturnFocus?.focus();
  temperatureModalReturnFocus = null;
}

powerConfirm.addEventListener('click', () => {
  if (!pendingPowerCommand || pendingPowerCommand.sent) return;
  if (!ws || ws.readyState !== WebSocket.OPEN) {
    showCommandFeedback(false, 'Painel desconectado. O comando não foi enviado.');
    closePowerModal();
    return;
  }
  const requestId = `power-${Date.now()}-${++powerRequestSequence}`;
  pendingPowerCommand.sent = true;
  pendingPowerCommand.requestId = requestId;
  pendingPowerCommand.trigger.disabled = true;
  powerConfirm.disabled = true;
  powerConfirm.textContent = 'Executando...';
  send({ action: pendingPowerCommand.action, request_id: requestId });
  pendingPowerCommand.timeout = setTimeout(() => finishPowerCommand(false, 'Sem resposta do backend. Verifique o Gerenciador.'), 30000);
});

function handleCommandResult(message) {
  if (!pendingPowerCommand || message.request_id !== pendingPowerCommand.requestId) return;
  finishPowerCommand(message.success === true, message.message || (message.success ? 'Comando aceito.' : 'Falha ao executar o comando.'));
}

function finishPowerCommand(success, message) {
  if (!pendingPowerCommand) return;
  clearTimeout(pendingPowerCommand.timeout);
  pendingPowerCommand.trigger.disabled = false;
  powerConfirm.disabled = false;
  powerConfirm.textContent = 'Confirmar desligamento';
  powerModal.hidden = true;
  document.body.classList.remove('modal-open');
  pendingPowerCommand = null;
  modalReturnFocus?.focus();
  modalReturnFocus = null;
  showCommandFeedback(success, message);
}

function showCommandFeedback(success, message) {
  const feedback = document.getElementById('command-feedback');
  feedback.textContent = message;
  feedback.classList.toggle('success', success);
  feedback.classList.toggle('error', !success);
  feedback.hidden = false;
  clearTimeout(feedback.hideTimer);
  feedback.hideTimer = setTimeout(() => { feedback.hidden = true; }, 8000);
}

document.addEventListener('keydown', event => {
  if (!temperatureModal.hidden) {
    if (event.key === 'Escape') {
      event.preventDefault();
      closeTemperatureModal();
    } else if (event.key === 'Tab') {
      const focusable = [...temperatureModal.querySelectorAll('a[href],button:not(:disabled)')];
      const first = focusable[0], last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }
    return;
  }
  if (powerModal.hidden) return;
  if (event.key === 'Escape') {
    event.preventDefault();
    closePowerModal();
  } else if (event.key === 'Tab') {
    const focusable = [powerCancel, powerConfirm].filter(button => !button.disabled);
    const first = focusable[0], last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  }
});

function renderProviders(onlyId = null) {
  const grid = document.getElementById('provider-grid');
  Object.entries(state.providers || {}).forEach(([id, data]) => {
    if (onlyId != null && id !== String(onlyId)) return;
    let card = document.getElementById(`provider-${id}`);
    if (!card) {
      card = document.getElementById('provider-template').content.firstElementChild.cloneNode(true);
      card.id = `provider-${id}`;
      card.querySelector('.start').onclick = () => send({action:'provider_start', interface:id});
      card.querySelector('.stop').onclick = () => send({action:'provider_stop', interface:id});
      grid.appendChild(card);
    }
    card.querySelector('.label').textContent = id;
    card.querySelector('h3').textContent = data.name || id;
    setStatus(card, data.running);
    const history = Array.isArray(data.history) ? data.history : [];
    const latestLatency = latestFinite(history, 'latency');
    const latestLoss = latestFinite(history, 'loss');
    card.querySelector('.latency').textContent = latestLatency == null ? '--' : `${formatNumber(latestLatency)} ms`;
    card.querySelector('.loss').textContent = latestLoss == null ? '--' : `${formatNumber(latestLoss)}%`;
    card.querySelector('.drops').textContent = (data.drops || []).length;
    card.querySelector('.output').textContent = data.output || 'Aguardando dados...';
    drawChart(card.querySelector('canvas'), history, data.drops || []);
  });
}

function renderTests(onlyId = null) {
  const grid = document.getElementById('test-grid');
  for (let i=0; i<3; i++) {
    if (onlyId != null && String(i) !== String(onlyId)) continue;
    const data = (state.tests || {})[String(i)] || {};
    let card = document.getElementById(`test-${i}`);
    if (!card) {
      card = document.createElement('article'); card.className='card'; card.id=`test-${i}`;
      card.innerHTML = `<div class="card-head"><div><p class="label">TESTE ${i+1}</p><h3>Destino</h3></div><span class="status">Parado</span></div>
        <div class="test-form"><select class="method" aria-label="Método"><option value="mtr">MTR</option><option value="ping">Ping</option><option value="nmap">Nmap</option></select><div class="host-combobox"><input class="host" placeholder="Host ou IP" aria-label="Host ou IP" role="combobox" aria-autocomplete="none" aria-expanded="false" aria-controls="test-host-options-${i}" required><button class="host-toggle" type="button" aria-label="Abrir destinos salvos" aria-controls="test-host-options-${i}" aria-expanded="false">&#9662;</button><div class="host-options" id="test-host-options-${i}" role="listbox" hidden></div></div><input class="port" type="text" inputmode="numeric" pattern="[0-9]*" maxlength="5" placeholder="Porta" aria-label="Porta"><div class="test-actions"><button class="run">Iniciar</button><button class="halt secondary">Parar</button></div></div>
        <div class="chart-panel"><div class="chart-head"><div class="chart-legend"><span class="latency-key">Latência</span><span class="drop-key">Quedas</span></div><button class="chart-live" type="button">Tempo real</button></div><canvas height="230" aria-label="Histórico do teste"></canvas><p class="chart-help">Arraste para histórico · Roda para zoom</p></div>
        <div class="output-panel"><div class="output-head"><span>Saída do teste</span><span class="output-status">Aguardando</span></div><pre>Aguardando dados...</pre></div>`;
      card.querySelector('.method').onchange = e => {
        card.formDirty = true;
        card.querySelector('.port').setCustomValidity('');
        card.querySelector('.port').classList.toggle('hidden', e.target.value !== 'nmap');
        syncSelectedHostPort(card);
      };
      card.querySelector('.host').oninput = () => { card.formDirty = true; };
      card.querySelector('.host').onchange = () => syncSelectedHostPort(card);
      card.querySelector('.host').onkeydown = event => {
        if (event.key === 'Escape') closeHostCombobox(card);
        if (event.altKey && event.key === 'ArrowDown') {
          event.preventDefault();
          openHostCombobox(card);
        }
      };
      card.querySelector('.host-toggle').onclick = () => {
        if (card.querySelector('.host-options').hidden) openHostCombobox(card);
        else closeHostCombobox(card);
      };
      card.querySelector('.host-options').onkeydown = event => {
        if (event.key !== 'Escape') return;
        event.preventDefault();
        closeHostCombobox(card);
        card.querySelector('.host').focus();
      };
      card.querySelector('.port').oninput = () => {
        card.formDirty = true;
        card.querySelector('.port').setCustomValidity('');
      };
      card.querySelector('.run').onclick = () => startTest(card, i);
      card.querySelector('.halt').onclick = () => send({action:'test_stop', index:i});
      grid.appendChild(card);
    }
    if (Array.isArray(data.hosts)) renderHostOptions(card, data.hosts);
    const serverForm = {
      method: data.method || 'mtr',
      host: data.host || '',
      port: data.port || ''
    };
    if (card.pendingForm && Object.keys(serverForm).every(key => serverForm[key] === card.pendingForm[key])) {
      card.formDirty = false;
      card.pendingForm = null;
    }
    setStatus(card, data.running);
    if (!card.formDirty) {
      setUnlessFocused(card.querySelector('.method'), serverForm.method);
      setUnlessFocused(card.querySelector('.host'), serverForm.host);
      setUnlessFocused(card.querySelector('.port'), serverForm.port);
    }
    const effectiveMethod = card.formDirty ? card.querySelector('.method').value : serverForm.method;
    card.querySelector('.port').classList.toggle('hidden', effectiveMethod !== 'nmap');
    card.querySelector('pre').textContent = data.output || 'Aguardando dados...';
    drawChart(card.querySelector('canvas'), data.history || [], data.drops || []);
  }
}

function renderHostOptions(card, hosts) {
  const normalized = (Array.isArray(hosts) ? hosts : [])
    .filter(item => item && typeof item.host === 'string')
    .map(item => ({host: item.host, port: item.port == null ? '' : String(item.port)}));
  const fingerprint = JSON.stringify(normalized);
  if (card.dataset.hostOptions === fingerprint) return;
  card.dataset.hostOptions = fingerprint;
  card.hostOptions = normalized;
  const list = card.querySelector('.host-options');
  const options = normalized.map(item => {
    const option = document.createElement('button');
    option.type = 'button';
    option.className = 'host-option';
    option.setAttribute('role', 'option');
    option.textContent = item.port ? `${item.host}:${item.port}` : item.host;
    option.onclick = () => selectHostOption(card, item);
    return option;
  });
  if (!options.length) {
    const empty = document.createElement('span');
    empty.className = 'host-options-empty';
    empty.textContent = 'Nenhum destino salvo';
    list.replaceChildren(empty);
  } else {
    list.replaceChildren(...options);
  }
  if (!list.hidden) positionHostOptions(card);
}

function openHostCombobox(card) {
  document.querySelectorAll('.host-combobox.open').forEach(combobox => {
    if (!card.contains(combobox)) closeHostCombobox(combobox.closest('.card'));
  });
  const combobox = card.querySelector('.host-combobox');
  const list = card.querySelector('.host-options');
  combobox.classList.add('open');
  list.hidden = false;
  positionHostOptions(card);
  card.querySelector('.host').setAttribute('aria-expanded', 'true');
  card.querySelector('.host-toggle').setAttribute('aria-expanded', 'true');
}

function positionHostOptions(card) {
  const combobox = card.querySelector('.host-combobox');
  const list = card.querySelector('.host-options');
  const rect = combobox.getBoundingClientRect();
  const spaceBelow = window.innerHeight - rect.bottom - 8;
  const spaceAbove = rect.top - 8;
  const desiredHeight = Math.min(220, list.scrollHeight);
  const openAbove = spaceBelow < desiredHeight && spaceAbove > spaceBelow;
  const availableHeight = Math.max(80, Math.min(220, openAbove ? spaceAbove - 4 : spaceBelow));
  list.style.left = `${rect.left}px`;
  list.style.width = `${rect.width}px`;
  list.style.maxHeight = `${availableHeight}px`;
  list.style.top = openAbove
    ? `${Math.max(8, rect.top - Math.min(desiredHeight, availableHeight) - 4)}px`
    : `${rect.bottom + 4}px`;
}

function closeHostCombobox(card) {
  if (!card) return;
  card.querySelector('.host-combobox')?.classList.remove('open');
  const list = card.querySelector('.host-options');
  if (list) list.hidden = true;
  card.querySelector('.host')?.setAttribute('aria-expanded', 'false');
  card.querySelector('.host-toggle')?.setAttribute('aria-expanded', 'false');
}

function selectHostOption(card, selected) {
  card.formDirty = true;
  card.querySelector('.host').value = selected.host;
  if (card.querySelector('.method').value === 'nmap' && selected.port) {
    card.querySelector('.port').value = selected.port;
    card.querySelector('.port').setCustomValidity('');
  }
  closeHostCombobox(card);
  card.querySelector('.host').focus();
}

function syncSelectedHostPort(card) {
  if (card.querySelector('.method').value !== 'nmap') return;
  const selected = (card.hostOptions || []).find(item => item.host === card.querySelector('.host').value.trim());
  if (selected?.port) card.querySelector('.port').value = selected.port;
}

function startTest(card, index) {
  const method = card.querySelector('.method').value;
  const hostInput = card.querySelector('.host');
  const portInput = card.querySelector('.port');
  portInput.setCustomValidity('');
  if (!hostInput.reportValidity()) return;
  if (method === 'nmap') {
    const port = portInput.value.trim();
    if (!/^\d{1,5}$/.test(port) || Number(port) < 1 || Number(port) > 65535) {
      portInput.setCustomValidity('Informe uma porta entre 1 e 65535.');
      portInput.reportValidity();
      return;
    }
  }
  card.pendingForm = {method, host:hostInput.value.trim(), port:method === 'nmap' ? portInput.value.trim() : ''};
  send({action:'test_start', index, ...card.pendingForm});
}

function renderOmr(onlyId = null) {
  const grid = document.getElementById('omr-grid');
  [['vpn','OMR VPN'],['jogo','OMR JOGO']].forEach(([id,name]) => {
    if (onlyId != null && id !== String(onlyId)) return;
    const data = (state.omr || {})[id] || {};
    let card = document.getElementById(`omr-${id}`);
    if (!card) {
      card=document.createElement('article'); card.className='card'; card.id=`omr-${id}`;
      card.innerHTML=`<div class="card-head"><div><p class="label">INTERFACES</p><h3>${name}</h3></div><span class="status">Parado</span></div><div class="actions"><button class="start">Iniciar</button><button class="stop secondary">Parar</button></div><div class="output-panel"><div class="output-head"><span>Leitura da interface</span><span class="output-status">Aguardando</span></div><pre class="output">Aguardando dados...</pre></div><p class="average-title">Velocidades médias</p><div class="output-panel"><div class="output-head"><span>Médias acumuladas</span></div><pre class="averages">Aguardando dados...</pre></div>`;
      card.querySelector('.start').onclick=()=>send({action:'omr_start', target:id});
      card.querySelector('.stop').onclick=()=>send({action:'omr_stop', target:id});
      grid.appendChild(card);
    }
    setStatus(card,data.running); card.querySelector('.output').textContent=data.output||'Aguardando dados...'; card.querySelector('.averages').textContent=data.averages||'Aguardando dados...';
  });
}

function renderComputer() {
  const data = (state.computer || {}).local || {};
  const available = panelConnected && data.available === true;
  const cpu = available ? finiteNumber(data.cpu_percent) : null;
  const temperature = available ? finiteNumber(data.temperature_c) : null;
  const temperatureSourceAvailable = panelConnected && data.temperature_source_available === true;
  const summary = document.getElementById('computer-summary');
  summary.querySelectorAll('b')[0].textContent = cpu == null ? 'CPU indisponível' : `CPU ${formatNumber(cpu)}%`;
  summary.querySelectorAll('b')[1].textContent = temperature == null ? 'Temperatura indisponível' : `${formatNumber(temperature)} °C`;
  summary.classList.toggle('unavailable', !available);
  temperatureTriggers.forEach(trigger => {
    trigger.classList.toggle('unavailable', temperature == null);
    trigger.title = temperatureSourceAvailable
      ? 'Informações da leitura pelo LibreHardwareMonitor'
      : 'Como ativar a leitura pelo LibreHardwareMonitor';
  });

  document.getElementById('computer-cpu').textContent = cpu == null ? 'Indisponível' : `${formatNumber(cpu)}%`;
  document.getElementById('computer-temperature').textContent = temperature == null ? 'Indisponível' : `${formatNumber(temperature)} °C`;
  document.getElementById('computer-temperature-help').textContent = temperature == null
    ? (data.temperature_error || 'LibreHardwareMonitor não respondeu.')
    : 'Leitura fornecida pelo LibreHardwareMonitor.';

  const body = document.getElementById('computer-processes');
  const processes = available && Array.isArray(data.processes) ? data.processes.slice(0, 5) : [];
  if (!processes.length) {
    const row = document.createElement('tr');
    const cell = document.createElement('td');
    cell.colSpan = 2;
    cell.className = 'empty';
    cell.textContent = available ? 'Nenhum processo disponível nesta amostra.' : 'Monitoramento indisponível.';
    row.appendChild(cell);
    body.replaceChildren(row);
  } else {
    body.replaceChildren(...processes.map(process => {
      const row = document.createElement('tr');
      const name = document.createElement('td');
      const usage = document.createElement('td');
      name.textContent = process.name || 'Nome indisponível';
      const value = finiteNumber(process.cpu_percent);
      usage.textContent = value == null ? '--' : `${formatNumber(value)}%`;
      row.append(name, usage);
      return row;
    }));
  }

  const error = document.getElementById('computer-error');
  const message = !panelConnected ? 'Painel desconectado do Gerenciador.' : data.error;
  error.textContent = message || '';
  error.hidden = !message;
}

function setStatus(card, running) {
  const el = card.querySelector('.status');
  el.textContent = running ? 'Executando' : 'Parado';
  el.classList.toggle('running', !!running);
  const outputStatus = card.querySelector('.output-status');
  if (outputStatus) {
    outputStatus.textContent = running ? 'Ao vivo' : 'Aguardando';
    outputStatus.classList.toggle('running', !!running);
  }
}
function setUnlessFocused(input,value) { if(document.activeElement!==input) input.value=value; }

function drawChart(canvas, history, drops) {
  const points = normalizeHistory(history);
  const dropTimes = (Array.isArray(drops) ? drops : []).map(toTimestamp).filter(Number.isFinite).sort((a, b) => a - b);
  const chart = getChartState(canvas);
  chart.points = points;
  chart.drops = dropTimes;

  const ratio = window.devicePixelRatio || 1;
  const width = canvas.clientWidth || 400;
  const height = canvas.clientHeight || 230;
  const pixelWidth = Math.round(width * ratio);
  const pixelHeight = Math.round(height * ratio);
  if (canvas.width !== pixelWidth || canvas.height !== pixelHeight) {
    canvas.width = pixelWidth;
    canvas.height = pixelHeight;
  }

  const ctx = canvas.getContext('2d');
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  ctx.clearRect(0, 0, width, height);

  const plot = { left: 52, right: width - 14, top: 14, bottom: height - 35 };
  const plotWidth = Math.max(1, plot.right - plot.left);
  const plotHeight = Math.max(1, plot.bottom - plot.top);
  chart.plotWidth = plotWidth;
  const latestDataTime = Math.max(points.length ? points[points.length - 1].time : 0, dropTimes.length ? dropTimes[dropTimes.length - 1] : 0);
  const liveEnd = latestDataTime && Date.now() - latestDataTime > HOUR ? latestDataTime : Date.now();
  chart.liveEnd = liveEnd;
  const earliest = Math.min(points.length ? points[0].time : liveEnd, dropTimes.length ? dropTimes[0] : liveEnd);
  chart.earliest = earliest;
  chart.maxDuration = Math.max(HOUR, liveEnd - earliest + 60000);
  chart.duration = Math.min(chart.duration, chart.maxDuration);
  const end = chart.viewEnd == null ? liveEnd : clampViewEnd(chart.viewEnd, chart);
  if (chart.viewEnd != null) chart.viewEnd = end;
  const start = end - chart.duration;
  const visible = points.filter(point => point.time >= start && point.time <= end);
  const largestValue = visible.reduce((maximum, point) => Math.max(
    maximum,
    Number.isFinite(point.latency) ? point.latency : 0,
    Number.isFinite(point.loss) ? point.loss : 0
  ), 0);
  const yMax = Math.max(120, Math.ceil(largestValue * 1.15 / 10) * 10);
  const xFor = timestamp => plot.left + (timestamp - start) / chart.duration * plotWidth;
  const yFor = value => plot.bottom - Math.max(0, Math.min(value, yMax)) / yMax * plotHeight;

  ctx.font = '10px "Segoe UI", sans-serif';
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {
    const y = plot.top + plotHeight * i / 4;
    const value = Math.round(yMax * (1 - i / 4));
    ctx.strokeStyle = '#deddd5';
    ctx.beginPath(); ctx.moveTo(plot.left, y); ctx.lineTo(plot.right, y); ctx.stroke();
    ctx.fillStyle = '#6b7770'; ctx.textAlign = 'right'; ctx.textBaseline = 'middle'; ctx.fillText(String(value), plot.left - 7, y);
  }
  for (let i = 0; i <= 4; i++) {
    const x = plot.left + plotWidth * i / 4;
    const timestamp = start + chart.duration * i / 4;
    ctx.strokeStyle = '#ebe9e0';
    ctx.beginPath(); ctx.moveTo(x, plot.top); ctx.lineTo(x, plot.bottom); ctx.stroke();
    ctx.fillStyle = '#6b7770'; ctx.textAlign = i === 0 ? 'left' : i === 4 ? 'right' : 'center'; ctx.textBaseline = 'top';
    ctx.fillText(formatTime(timestamp, chart.duration), x, plot.bottom + 7);
  }
  ctx.save();
  ctx.translate(12, plot.top + plotHeight / 2); ctx.rotate(-Math.PI / 2);
  ctx.fillStyle = '#536159'; ctx.textAlign = 'center'; ctx.textBaseline = 'top'; ctx.fillText('Latência (ms) / perda (%)', 0, 0);
  ctx.restore();
  ctx.fillStyle = '#536159'; ctx.textAlign = 'center'; ctx.textBaseline = 'bottom'; ctx.fillText('Horário', plot.left + plotWidth / 2, height - 1);

  ctx.save();
  ctx.beginPath(); ctx.rect(plot.left, plot.top, plotWidth, plotHeight); ctx.clip();
  drawSeries(ctx, visible, 'latency', '#087f5b', xFor, yFor);
  ctx.setLineDash([5, 4]);
  drawSeries(ctx, visible, 'loss', '#d97706', xFor, yFor);
  ctx.setLineDash([]);
  ctx.fillStyle = '#c13d32';
  dropTimes.filter(time => time >= start && time <= end).forEach(time => {
    const x = xFor(time);
    ctx.beginPath(); ctx.moveTo(x, plot.bottom - 11); ctx.lineTo(x - 5, plot.bottom - 2); ctx.lineTo(x + 5, plot.bottom - 2); ctx.closePath(); ctx.fill();
  });
  ctx.restore();

  if (!visible.length) {
    ctx.fillStyle = '#7a857f'; ctx.font = '12px "Segoe UI", sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillText(points.length ? 'Sem amostras nesta janela' : 'Aguardando amostras de latência', plot.left + plotWidth / 2, plot.top + plotHeight / 2);
  }
  const liveButton = canvas.closest('.chart-panel')?.querySelector('.chart-live');
  if (liveButton) liveButton.classList.toggle('following', chart.viewEnd == null);
}

function getChartState(canvas) {
  let chart = chartStates.get(canvas);
  if (chart) return chart;
  chart = { duration: HOUR, viewEnd: null, points: [], drops: [], plotWidth: 1, earliest: Date.now(), liveEnd: Date.now(), maxDuration: HOUR };
  chartStates.set(canvas, chart);
  let dragStart = null;
  canvas.addEventListener('pointerdown', event => {
    dragStart = { x: event.clientX, end: chart.viewEnd == null ? chart.liveEnd : chart.viewEnd };
    canvas.setPointerCapture(event.pointerId); canvas.classList.add('dragging');
  });
  canvas.addEventListener('pointermove', event => {
    if (!dragStart) return;
    chart.viewEnd = clampViewEnd(dragStart.end - (event.clientX - dragStart.x) / chart.plotWidth * chart.duration, chart);
    drawChart(canvas, chart.points, chart.drops);
  });
  const stopDragging = () => { dragStart = null; canvas.classList.remove('dragging'); };
  canvas.addEventListener('pointerup', stopDragging);
  canvas.addEventListener('pointercancel', stopDragging);
  canvas.addEventListener('wheel', event => {
    event.preventDefault();
    const rect = canvas.getBoundingClientRect();
    const ratio = Math.max(0, Math.min(1, (event.clientX - rect.left - 52) / chart.plotWidth));
    const oldDuration = chart.duration;
    const oldEnd = chart.viewEnd == null ? chart.liveEnd : chart.viewEnd;
    const anchor = oldEnd - oldDuration + ratio * oldDuration;
    chart.duration = Math.max(60000, Math.min(chart.maxDuration, oldDuration * Math.exp(event.deltaY * 0.0015)));
    chart.viewEnd = clampViewEnd(anchor + (1 - ratio) * chart.duration, chart);
    drawChart(canvas, chart.points, chart.drops);
  }, { passive: false });
  const reset = () => { chart.duration = HOUR; chart.viewEnd = null; drawChart(canvas, chart.points, chart.drops); };
  canvas.addEventListener('dblclick', reset);
  canvas.closest('.chart-panel')?.querySelector('.chart-live')?.addEventListener('click', reset);
  return chart;
}

function clampViewEnd(end, chart) {
  const minimum = chart.earliest + chart.duration;
  return minimum > chart.liveEnd ? chart.liveEnd : Math.max(minimum, Math.min(chart.liveEnd, end));
}

function normalizeHistory(history) {
  if (!Array.isArray(history)) return [];
  const now = Date.now();
  return history.map((point, index) => {
    const item = point && typeof point === 'object' ? point : { latency: point };
    const parsedTime = toTimestamp(item.time ?? item.timestamp ?? item.date);
    return {
      time: Number.isFinite(parsedTime) ? parsedTime : now - (history.length - 1 - index) * 1000,
      latency: finiteNumber(item.latency ?? item.ping ?? item.value),
      loss: finiteNumber(item.loss ?? item.packet_loss)
    };
  }).filter(point => Number.isFinite(point.time)).sort((a, b) => a.time - b.time);
}

function drawSeries(ctx, points, field, color, xFor, yFor) {
  ctx.strokeStyle = color; ctx.lineWidth = 2; ctx.lineJoin = 'round'; ctx.beginPath();
  let started = false;
  let lastPoint = null;
  let lastTime = null;
  points.forEach(point => {
    const value = point[field];
    if (!Number.isFinite(value)) { started = false; lastTime = null; return; }
    const x = xFor(point.time), y = yFor(value);
    if (started && point.time - lastTime <= GRAPH_GAP_MS) ctx.lineTo(x, y); else ctx.moveTo(x, y);
    lastPoint = { x, y };
    lastTime = point.time;
    started = true;
  });
  ctx.stroke();
  if (lastPoint) {
    ctx.fillStyle = color; ctx.beginPath(); ctx.arc(lastPoint.x, lastPoint.y, 2.5, 0, Math.PI * 2); ctx.fill();
  }
}

function latestFinite(history, field) {
  for (let index = history.length - 1; index >= 0; index--) {
    const value = finiteNumber(history[index]?.[field]);
    if (value != null) return value;
  }
  return null;
}

function finiteNumber(value) {
  if (value === null || value === undefined || value === '') return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function toTimestamp(value) {
  if (typeof value === 'number') return value < 1e12 ? value * 1000 : value;
  if (typeof value !== 'string' || !value.trim()) return NaN;
  const numeric = Number(value);
  if (Number.isFinite(numeric)) return numeric < 1e12 ? numeric * 1000 : numeric;
  return Date.parse(value);
}

function formatNumber(value) { return Number(value).toLocaleString('pt-BR', { maximumFractionDigits: 1 }); }
function formatTime(timestamp, duration) {
  const options = duration > 24 * HOUR ? { day:'2-digit', month:'2-digit', hour:'2-digit', minute:'2-digit' } : { hour:'2-digit', minute:'2-digit' };
  return new Date(timestamp).toLocaleString('pt-BR', options);
}

window.addEventListener('resize', render);
document.addEventListener('pointerdown', event => {
  document.querySelectorAll('.host-combobox.open').forEach(combobox => {
    if (!combobox.contains(event.target)) closeHostCombobox(combobox.closest('.card'));
  });
});
connect();
