'use strict';
const $ = selector => document.querySelector(selector);
const categories = {red:'Red y conectividad',seguridad:'Seguridad',infraestructura:'Infraestructura',cuenta_acceso:'Cuentas y acceso',correo_colaboracion:'Correo y colaboración',impresion:'Impresión',hardware:'Hardware',software:'Software',otros:'Revisión manual'};
const destinations = {nivel_1:'Nivel 1',nivel_2:'Nivel 2',nivel_3:'Nivel 3',seguridad:'Seguridad'};
let records = [], selected = null, filter = 'all', engineOnline = false, created = 0;
const escapeHTML = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const badge = p => `<span class="priority ${escapeHTML(p)}">${escapeHTML(p)}</span>`;

async function request(path, options = {}) {
  const response = await fetch(path, {...options, signal: AbortSignal.timeout(7000)});
  const type = response.headers.get('content-type') || '';
  if (!type.includes('application/json')) throw new Error('El motor local no está disponible. Abrí INICIAR_DEMO.bat para analizar casos nuevos.');
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'No se pudo completar el análisis.');
  return result;
}

function showView(view) {
  $('#queue-view').hidden = view !== 'queue';
  $('#lab-view').hidden = view !== 'lab';
  document.querySelectorAll('[data-view]').forEach(b => {
    b.classList.toggle('active', b.dataset.view === view);
    b.setAttribute('aria-pressed', String(b.dataset.view === view));
  });
  if (view === 'lab') $('#lab-view').scrollIntoView({behavior:'smooth',block:'start'});
}

function renderMetrics() {
  $('#metric-total').textContent = records.length;
  $('#metric-critical').textContent = records.filter(r => r.result.priority === 'P1').length;
  $('#metric-security').textContent = records.filter(r => r.result.escalation_level === 'seguridad').length;
  $('#metric-manual').textContent = records.filter(r => r.result.needs_manual_review).length;
}

function renderQueue() {
  const term = $('#search').value.toLocaleLowerCase('es');
  const visible = records.filter(({ticket:t,result:r}) => (filter === 'all' || r.priority === filter) &&
    `${t.id} ${t.title} ${t.description} ${categories[r.category]}`.toLocaleLowerCase('es').includes(term))
    .sort((a,b) => a.result.priority.localeCompare(b.result.priority) || a.ticket.id.localeCompare(b.ticket.id));
  $('#queue-count').textContent = visible.length;
  $('#ticket-list').innerHTML = visible.length ? visible.map(({ticket:t,result:r}) => `<button class="ticket-row ${selected?.ticket.id === t.id ? 'selected' : ''}" data-id="${escapeHTML(t.id)}" aria-pressed="${selected?.ticket.id === t.id}" aria-label="${escapeHTML(t.id + ': ' + t.title + ', ' + r.priority)}"><span class="ticket-copy"><span class="ticket-meta">${escapeHTML(t.id)} · ${t.id.startsWith('LAB-') ? 'LABORATORIO' : 'CASO SINTÉTICO'}</span><span class="ticket-title">${escapeHTML(t.title)}</span><span class="ticket-category">${escapeHTML(categories[r.category] || r.category)}</span></span><span>${badge(r.priority)}</span><span class="destination">${escapeHTML(destinations[r.escalation_level])} ↗</span></button>`).join('') : '<div class="empty">No hay incidentes con estos filtros.<br>Probá otra prioridad o búsqueda.</div>';
  $('#ticket-list').querySelectorAll('[data-id]').forEach(button => button.addEventListener('click', () => selectTicket(button.dataset.id)));
}

function resultMarkup({ticket:t,result:r}, detail = false) {
  const decisions = `<div class="decision-grid"><div><small>IMPACTO</small><b>${escapeHTML(r.impact)}</b></div><div><small>URGENCIA</small><b>${escapeHTML(r.urgency)}</b></div></div><div class="route-box"><small>CANAL DE ATENCIÓN</small><b>${escapeHTML(r.escalation_team)}</b><p>${r.escalate_immediately ? '↗ Escalación inmediata' : r.escalate ? 'Derivación al equipo especializado' : 'Atención de primer nivel'}</p></div>`;
  const reasons = `<div><h4 class="reasons-title">La lógica detrás<span>${r.reasons.length} señales</span></h4><ol class="reasons">${r.reasons.map(reason => `<li>${escapeHTML(reason)}</li>`).join('')}</ol></div>`;
  const heading = `<div class="detail-top"><span class="detail-id">${escapeHTML(t.id)} / ANÁLISIS</span>${badge(r.priority)}</div><h3>${escapeHTML(t.title)}</h3><p class="detail-description">${escapeHTML(t.description)}</p><span class="category-badge">${escapeHTML(categories[r.category] || r.category)}</span>`;
  if (detail) return heading + decisions + reasons + '<button class="scenario-button" id="try-variation">⌘ ¿Y si cambiamos el escenario?<br><b>Abrir este caso en el laboratorio →</b></button>';
  return `<div>${heading}${decisions}<p class="result-note">Caso ficticio analizado con el motor de Python. El resultado es una demostración de reglas, no una decisión operativa real.</p></div>${reasons}`;
}

function selectTicket(id) {
  selected = records.find(r => r.ticket.id === id);
  if (!selected) return;
  renderQueue();
  $('#detail').innerHTML = resultMarkup(selected, true);
  $('#try-variation').addEventListener('click', () => populateForm(selected.ticket));
}

function populateForm(ticket) {
  const form = $('#case-form');
  form.elements.title.value = ticket.title;
  form.elements.description.value = ticket.description;
  form.elements.affected_users.value = ticket.affected_users;
  form.elements.workaround.value = ticket.workaround_available === true ? 'yes' : ticket.workaround_available === false ? 'no' : 'unknown';
  $('#form-feedback').textContent = '';
  $('#lab-result').hidden = true;
  showView('lab');
  form.elements.title.focus({preventScroll:true});
}

const presets = {
  security:{title:'Ransomware detectado en un equipo',description:'Un archivo sospechoso cifró los documentos. Aislamos el equipo como alternativa temporal. Necesitamos atención urgente.',affected_users:15,workaround_available:true},
  network:{title:'Toda la oficina está sin internet',description:'La red está caída. No podemos trabajar ni acceder al sistema de producción.',affected_users:25,workaround_available:false},
  printer:{title:'Impresora no imprime',description:'Una persona no puede imprimir. Hay otra impresora disponible como alternativa temporal.',affected_users:1,workaround_available:true}
};

$('#case-form').addEventListener('submit', async event => {
  event.preventDefault();
  if (!engineOnline) { $('#form-feedback').textContent = 'Abrí INICIAR_DEMO.bat para conectar el motor local y analizar un caso nuevo.'; return; }
  const form = event.currentTarget;
  if (!form.reportValidity()) return;
  const ticket = {id:`LAB-${String(++created).padStart(4,'0')}`,title:form.elements.title.value.trim(),description:form.elements.description.value.trim(),affected_users:Number(form.elements.affected_users.value),workaround_available:form.elements.workaround.value === 'unknown' ? null : form.elements.workaround.value === 'yes',requester:'usuario-laboratorio'};
  $('#analyze').disabled = true;
  $('#form-feedback').textContent = 'Analizando señales…';
  try {
    const record = await request('/api/triage',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({meta:{synthetic:true},tickets:[ticket]})});
    records.push(record);
    $('#lab-result').innerHTML = resultMarkup(record);
    $('#lab-result').hidden = false;
    $('#form-feedback').textContent = 'Análisis completo. El caso también está disponible en tu bandeja durante esta sesión.';
    renderMetrics();
    selectTicket(record.ticket.id);
    $('#lab-result').scrollIntoView({behavior:'smooth',block:'start'});
  } catch(error) { $('#form-feedback').textContent = error.message; }
  finally { $('#analyze').disabled = false; }
});

document.querySelectorAll('[data-view]').forEach(b => b.addEventListener('click', () => showView(b.dataset.view)));
document.querySelectorAll('[data-preset]').forEach(b => b.addEventListener('click', () => populateForm(presets[b.dataset.preset])));
document.querySelectorAll('[data-filter]').forEach(button => button.addEventListener('click', () => {
  filter = button.dataset.filter;
  document.querySelectorAll('[data-filter]').forEach(b => b.setAttribute('aria-pressed',String(b === button)));
  renderQueue();
}));
$('#search').addEventListener('input', renderQueue);
$('#reset-queue').addEventListener('click', () => {
  filter = 'all'; $('#search').value = '';
  document.querySelectorAll('[data-filter]').forEach(b => b.setAttribute('aria-pressed',String(b.dataset.filter === 'all')));
  renderQueue();
});
[$('#hero-create'),$('#new-case')].forEach(b => b.addEventListener('click', () => populateForm(presets.network)));
$('#about-button').addEventListener('click', () => $('#about-dialog').showModal());
$('.close-dialog').addEventListener('click', () => $('#about-dialog').close());
document.addEventListener('keydown', event => {
  if (event.key === '/' && !['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName) && !$('#about-dialog').open) {
    event.preventDefault(); showView('queue'); $('#search').focus();
  }
});

(async () => {
  let payload;
  try { payload = await request('/api/demo'); engineOnline = true; }
  catch { try { payload = await request('./demo-data.json'); } catch {
    $('#ticket-list').innerHTML = '<p class="empty">No se pudo cargar la muestra. Abrí la demo con INICIAR_DEMO.bat.</p>';
    $('#detail').textContent = 'Sin casos disponibles.'; $('#engine-status').textContent = 'Muestra no disponible'; return;
  }}
  records = payload.records;
  $('#engine-status').textContent = engineOnline ? '● Motor local conectado' : '◌ Modo muestra';
  $('#offline-note').hidden = engineOnline;
  renderMetrics();
  const first = [...records].sort((a,b) => a.result.priority.localeCompare(b.result.priority))[0];
  if (first) selectTicket(first.ticket.id);
})();
