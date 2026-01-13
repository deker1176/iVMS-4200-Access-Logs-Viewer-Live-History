HTML = r"""
<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>Проходы iVMS (live + история)</title>
<style>
body { font-family: Arial, sans-serif; margin:18px; }
h2 { margin: 0 0 10px 0; }
.toolbar { display:flex; flex-wrap:wrap; gap:10px; align-items:flex-end; margin-bottom:12px; }
.toolbar .f { display:flex; flex-direction:column; }
input, select { padding:6px; min-width: 160px; }
button { padding:7px 12px; cursor:pointer; }
.badge { display:inline-block; padding:4px 8px; border:1px solid #ddd; border-radius:999px; background:#fafafa; margin-left:6px; font-size:12px; }
.tabs { display:flex; gap:8px; margin: 10px 0; }
.tab { padding:8px 10px; border:1px solid #ddd; border-radius:8px; cursor:pointer; background:#fff; }
.tab.active { background:#f3f3f3; }
.panel { display:none; }
.panel.active { display:block; }
.log { border:1px solid #ddd; border-radius:10px; overflow:hidden; }
.row { padding:8px 10px; border-bottom:1px solid #eee; }
.row:last-child { border-bottom:none; }
.small { color:#666; font-size:12px; }
.vhod { color:green; font-weight:bold; }
.vihod { color:#b00; font-weight:bold; }
table { border-collapse:collapse; width:100%; }
th, td { border-bottom:1px solid #eee; padding:8px; text-align:left; }
th { background:#fafafa; }
.right { text-align:right; }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace; }
</style>
</head>
<body>

<h2>Проходы (live + история)
  <span class="badge" id="sseStatus">SSE: off</span>
  <span class="badge" id="loadedInfo">Загружено: 0</span>
</h2>

<div class="toolbar">
  <div class="f"><label>Дата с</label><input type="date" id="dateFrom"></div>
  <div class="f"><label>Дата по</label><input type="date" id="dateTo"></div>
  <div class="f"><label>Время с</label><input type="time" id="timeFrom"></div>
  <div class="f"><label>Время по</label><input type="time" id="timeTo"></div>
  <div class="f"><label>Дверь</label><select id="door"><option value="">Все</option></select></div>
  <div class="f"><label>Поиск</label><input type="text" id="search" placeholder="ФИО / карта / ID"></div>

  <div class="f">
    <label>Live</label>
    <button id="liveBtn" onclick="toggleLive()">Включить Live</button>
  </div>

  <div class="f">
    <label>Действия</label>
    <div style="display:flex; gap:8px;">
      <button onclick="applyFilters()">Применить</button>
      <button onclick="resetFilters()">Сброс</button>
    </div>
  </div>
</div>

<div class="tabs">
  <div class="tab active" onclick="showTab('log')">Лог</div>
  <div class="tab" onclick="showTab('summary')">Сводка (кто где)</div>
  <div class="tab" onclick="showTab('worktime')">Отчёт времени</div>
</div>

<div id="tab_log" class="panel active">
  <div class="log" id="log"></div>
</div>

<div id="tab_summary" class="panel">
  <div class="log">
    <table id="summaryTbl">
      <thead><tr>
        <th>Сотрудник</th><th>ID</th><th>Статус</th><th>Последнее событие</th><th>Дверь</th><th>Карта</th>
      </tr></thead>
      <tbody></tbody>
    </table>
  </div>
</div>

<div id="tab_worktime" class="panel">
  <div class="log">
    <table id="workTbl">
      <thead><tr>
        <th>Сотрудник</th><th>ID</th><th>Первый вход</th><th>Последний выход</th><th class="right">Итого внутри</th>
      </tr></thead>
      <tbody></tbody>
    </table>
  </div>
</div>

<script>
let es = null;
let liveOn = false;

function showTab(name){
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  document.querySelectorAll('.panel').forEach(p=>p.classList.remove('active'));
  const idx = {log:0, summary:1, worktime:2}[name];
  document.querySelectorAll('.tab')[idx].classList.add('active');
  document.getElementById('tab_'+name).classList.add('active');
}

function getFilters(){
  const f = {};
  ['dateFrom','dateTo','timeFrom','timeTo','door','search'].forEach(id=>{
    const v = document.getElementById(id).value;
    if(v) f[id]=v;
  });
  return f;
}

function qs(obj){
  const p = new URLSearchParams();
  Object.entries(obj).forEach(([k,v])=>p.append(k,v));
  return p.toString();
}

function dirLabel(d){
  d = (d||'').toLowerCase();
  if(d === 'vhod') return ['Вход','vhod'];
  if(d === 'vihod') return ['Выход','vihod'];
  return [d,''];
}

function renderLog(rows, mode){
  const box = document.getElementById('log');
  if(mode === 'replace') box.innerHTML = '';
  rows.forEach(e=>{
    const [lbl, cls] = dirLabel(e.direction);
    const row = document.createElement('div');
    row.className = 'row';
    row.innerHTML = `
      <div><b class="mono">${e.authDateTime}</b> — <span class="${cls}">${lbl}</span> — ${e.personName} <span class="small">(${e.employeeID||''})</span></div>
      <div class="small">Дверь: <b>${e.deviceName||''}</b> | Карта: ${e.cardNo||''} | serialNo: ${e.serialNo||''}</div>
    `;
    if(mode === 'prepend' && box.firstChild) box.insertBefore(row, box.firstChild);
    else box.appendChild(row);
  });
}

function renderSummary(rows){
  const tb = document.querySelector('#summaryTbl tbody');
  tb.innerHTML = '';
  rows.forEach(r=>{
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${r.personName||''}</td>
      <td class="mono">${r.employeeID||''}</td>
      <td>${r.status||''}</td>
      <td class="mono">${r.lastAuthDateTime||''} (${r.lastDirection||''})</td>
      <td>${r.lastDeviceName||''}</td>
      <td class="mono">${r.cardNo||''}</td>
    `;
    tb.appendChild(tr);
  });
}

function renderWorktime(rows){
  const tb = document.querySelector('#workTbl tbody');
  tb.innerHTML = '';
  rows.forEach(r=>{
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${r.personName||''}</td>
      <td class="mono">${r.employeeID||''}</td>
      <td class="mono">${r.firstIn||''}</td>
      <td class="mono">${r.lastOut||''}</td>
      <td class="mono right">${r.totalInside||'00:00:00'}</td>
    `;
    tb.appendChild(tr);
  });
}

async function loadDoors(){
  const r = await fetch('/api/doors');
  const arr = await r.json();
  const s = document.getElementById('door');
  arr.forEach(name=>{
    const o = document.createElement('option');
    o.value = name;
    o.textContent = name;
    s.appendChild(o);
  });
}

async function loadAll(){
  const f = getFilters();
  const r1 = await fetch('/api/log?'+qs(f));
  const log = await r1.json();
  document.getElementById('loadedInfo').textContent = 'Загружено: ' + log.length;
  renderLog(log, 'replace');

  const r2 = await fetch('/api/summary?'+qs(f));
  renderSummary(await r2.json());

  const r3 = await fetch('/api/worktime?'+qs(f));
  renderWorktime(await r3.json());
}

async function applyFilters(){
  await loadAll();
  if(liveOn) {
    stopLive();
    startLive();
  }
}

async function resetFilters(){
  document.querySelectorAll('input,select').forEach(e=>e.value='');
  await applyFilters();
}

function setSseStatus(txt){
  document.getElementById('sseStatus').textContent = 'SSE: ' + txt;
}

function startLive(){
  const f = getFilters();
  const url = '/sse?' + qs(f);
  es = new EventSource(url);
  setSseStatus('connecting...');
  es.onopen = ()=> setSseStatus('connected');
  es.onerror = ()=> setSseStatus('error');
  es.onmessage = (ev)=>{
    try{
      const msg = JSON.parse(ev.data);
      if(msg.type === 'batch'){
        if(msg.rows && msg.rows.length){
          renderLog(msg.rows.slice().reverse(), 'prepend');
          // quick refresh summary/worktime with same filters (keeps UI accurate)
          loadAll();
        }
      }
    }catch(e){}
  };
  liveOn = true;
  document.getElementById('liveBtn').textContent = 'Выключить Live';
}

function stopLive(){
  if(es){
    es.close();
    es = null;
  }
  liveOn = false;
  document.getElementById('liveBtn').textContent = 'Включить Live';
  setSseStatus('off');
}

function toggleLive(){
  if(liveOn) stopLive();
  else startLive();
}

loadDoors().then(loadAll);
</script>

</body>
</html>
"""
