const state = { providers: {}, tests: {}, omr: {} };
let ws;

document.querySelectorAll('.tab').forEach(button => button.addEventListener('click', () => {
  document.querySelectorAll('.tab,.panel').forEach(el => el.classList.remove('active'));
  button.classList.add('active');
  document.getElementById(button.dataset.tab).classList.add('active');
}));

function send(message) {
  if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(message));
}

function connect() {
  ws = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`);
  ws.onopen = () => setConnection(true);
  ws.onclose = () => { setConnection(false); setTimeout(connect, 2000); };
  ws.onerror = () => ws.close();
  ws.onmessage = event => {
    const message = JSON.parse(event.data);
    if (message.type === 'state') {
      Object.assign(state, message.data);
      render();
    }
  };
}

function setConnection(online) {
  const el = document.getElementById('connection');
  el.classList.toggle('online', online);
  el.classList.toggle('offline', !online);
  el.lastChild.textContent = online ? ' Conectado' : ' Desconectado';
}

function render() { renderProviders(); renderTests(); renderOmr(); }

function renderProviders() {
  const grid = document.getElementById('provider-grid');
  Object.entries(state.providers || {}).forEach(([id, data]) => {
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
    const latest = (data.history || []).at(-1) || {};
    card.querySelector('.latency').textContent = latest.latency == null ? '--' : `${latest.latency} ms`;
    card.querySelector('.loss').textContent = latest.loss == null ? '--' : `${latest.loss}%`;
    card.querySelector('.drops').textContent = (data.drops || []).length;
    card.querySelector('.output').textContent = data.output || 'Aguardando dados...';
    drawChart(card.querySelector('canvas'), data.history || [], data.drops || []);
  });
}

function renderTests() {
  const grid = document.getElementById('test-grid');
  for (let i=0; i<3; i++) {
    const data = (state.tests || {})[String(i)] || {};
    let card = document.getElementById(`test-${i}`);
    if (!card) {
      card = document.createElement('article'); card.className='card'; card.id=`test-${i}`;
      card.innerHTML = `<div class="card-head"><div><p class="label">TESTE ${i+1}</p><h3>Destino</h3></div><span class="status">Parado</span></div>
        <div class="test-form"><select class="method"><option value="mtr">MTR</option><option value="ping">Ping</option><option value="nmap">Nmap</option></select><input class="host" placeholder="Host ou IP"><input class="port" type="number" min="1" max="65535" placeholder="Porta"></div>
        <div class="test-actions"><button class="run">Iniciar</button><button class="halt secondary">Parar</button></div><canvas height="150"></canvas><pre>Aguardando dados...</pre>`;
      card.querySelector('.method').onchange = e => card.querySelector('.port').classList.toggle('hidden', e.target.value !== 'nmap');
      card.querySelector('.run').onclick = () => send({action:'test_start', index:i, method:card.querySelector('.method').value, host:card.querySelector('.host').value, port:card.querySelector('.port').value});
      card.querySelector('.halt').onclick = () => send({action:'test_stop', index:i});
      grid.appendChild(card);
    }
    setStatus(card, data.running);
    setUnlessFocused(card.querySelector('.method'), data.method || 'mtr');
    setUnlessFocused(card.querySelector('.host'), data.host || '');
    setUnlessFocused(card.querySelector('.port'), data.port || '');
    card.querySelector('.port').classList.toggle('hidden', (data.method || card.querySelector('.method').value) !== 'nmap');
    card.querySelector('pre').textContent = data.output || 'Aguardando dados...';
    drawChart(card.querySelector('canvas'), data.history || [], data.drops || []);
  }
}

function renderOmr() {
  const grid = document.getElementById('omr-grid');
  [['vpn','OMR VPN'],['jogo','OMR JOGO']].forEach(([id,name]) => {
    const data = (state.omr || {})[id] || {};
    let card = document.getElementById(`omr-${id}`);
    if (!card) {
      card=document.createElement('article'); card.className='card'; card.id=`omr-${id}`;
      card.innerHTML=`<div class="card-head"><div><p class="label">INTERFACES</p><h3>${name}</h3></div><span class="status">Parado</span></div><div class="actions"><button class="start">Iniciar</button><button class="stop secondary">Parar</button></div><pre class="output">Aguardando dados...</pre><p class="average-title">Velocidades médias</p><pre class="averages">Aguardando dados...</pre>`;
      card.querySelector('.start').onclick=()=>send({action:'omr_start', target:id});
      card.querySelector('.stop').onclick=()=>send({action:'omr_stop', target:id});
      grid.appendChild(card);
    }
    setStatus(card,data.running); card.querySelector('.output').textContent=data.output||'Aguardando dados...'; card.querySelector('.averages').textContent=data.averages||'Aguardando dados...';
  });
}

function setStatus(card, running) { const el=card.querySelector('.status'); el.textContent=running?'Executando':'Parado'; el.classList.toggle('running',!!running); }
function setUnlessFocused(input,value) { if(document.activeElement!==input) input.value=value; }

function drawChart(canvas, history, drops) {
  const ratio=window.devicePixelRatio||1, width=canvas.clientWidth||400, height=150;
  if(canvas.width!==width*ratio){canvas.width=width*ratio;canvas.height=height*ratio;}
  const ctx=canvas.getContext('2d'); ctx.setTransform(ratio,0,0,ratio,0,0); ctx.clearRect(0,0,width,height);
  ctx.strokeStyle='#dddcd2'; ctx.lineWidth=1; [30,75,120].forEach(y=>{ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(width,y);ctx.stroke();});
  const points=history.slice(-180), max=Math.max(120,...points.map(p=>Number(p.latency)||0));
  ctx.strokeStyle='#087f5b';ctx.lineWidth=2;ctx.beginPath();let started=false;
  points.forEach((p,i)=>{if(p.latency==null)return;const x=points.length<2?0:i/(points.length-1)*width,y=height-8-Math.min(Number(p.latency),max)/max*(height-16);started?ctx.lineTo(x,y):ctx.moveTo(x,y);started=true;});ctx.stroke();
  ctx.fillStyle='#c13d32'; (drops||[]).slice(-20).forEach((_,i)=>{const x=width-8-i*7;ctx.beginPath();ctx.moveTo(x,height-3);ctx.lineTo(x-4,height-11);ctx.lineTo(x+4,height-11);ctx.fill();});
}

window.addEventListener('resize', render);
connect();
