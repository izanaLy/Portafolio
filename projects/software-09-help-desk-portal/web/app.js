'use strict';
// Todo el texto del servidor se inserta con textContent: nunca se interpreta como HTML.
const $ = (s) => document.querySelector(s);
const el = (tag, props = {}, ...kids) => {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) k === 'class' ? (n.className = v) : n.setAttribute(k, v);
  n.append(...kids);
  return n;
};
const STATUS = { nuevo: 'Nuevo', en_progreso: 'En progreso', resuelto: 'Resuelto', cerrado: 'Cerrado' };
const NEXT = { nuevo: ['en_progreso', 'resuelto'], en_progreso: ['resuelto'], resuelto: ['en_progreso', 'cerrado'], cerrado: [] };
let priority = 'all', selected = null;

async function api(path, body) {
  let res;
  try {
    res = await fetch(path, body === undefined ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  } catch { throw new Error('No se pudo contactar al servidor. Revisá que siga abierto.'); }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || 'Error ' + res.status);
  return data;
}

async function refresh() {
  const qs = priority === 'all' ? '' : '?priority=' + priority;
  const { tickets } = await api('/api/tickets' + qs);
  $('#count').textContent = '(' + tickets.length + ')';
  const list = $('#list');
  list.replaceChildren(...(tickets.length ? tickets.map((t) => {
    const b = el('button', { type: 'button', class: 'ticket', 'aria-current': String(t.id === selected) },
      el('span', { class: 'badge ' + t.triage.priority }, t.triage.priority),
      el('span', {}, t.id + ' · ' + t.title, el('br'), el('small', {}, STATUS[t.status] + ' · ' + t.triage.escalation_team)));
    b.addEventListener('click', () => show(t.id));
    return b;
  }) : [el('p', { class: 'muted' }, 'No hay tickets con este filtro.')]));
}

async function show(id) {
  selected = id;
  const t = await api('/api/tickets/' + id);
  const d = $('#detail'), tr = t.triage;
  const actions = el('div', { class: 'row' }, ...NEXT[t.status].map((s) => {
    const b = el('button', { type: 'button', class: 'ghost' }, 'Pasar a ' + STATUS[s]);
    b.addEventListener('click', () => act(() => api('/api/tickets/' + id + '/status', { status: s, assignee: 'agente-demo' }), id));
    return b;
  }));
  const form = el('form', { novalidate: '' }, el('label', {}, 'Comentario', el('textarea', { name: 'body', rows: '2', maxlength: '1000' })), el('button', { type: 'submit' }, 'Agregar comentario'));
  form.addEventListener('submit', (e) => { e.preventDefault(); act(() => api('/api/tickets/' + id + '/comments', { body: form.body.value }), id); });
  d.replaceChildren(
    el('h2', {}, t.id + ' · ' + t.title),
    el('p', {}, el('span', { class: 'badge ' + tr.priority }, tr.priority), ' ', STATUS[t.status], t.assignee ? ' · ' + t.assignee : ''),
    el('p', {}, t.description),
    el('p', { class: 'muted' }, 'Categoría: ' + tr.category + ' · Impacto: ' + tr.impact + ' · Urgencia: ' + tr.urgency),
    el('p', {}, 'Destino: ' + tr.escalation_team + (tr.escalate_immediately ? ' · escalación inmediata' : '') + (tr.needs_manual_review ? ' · requiere revisión manual' : '')),
    el('h3', {}, 'Por qué esta prioridad'), el('ul', {}, ...tr.reasons.map((r) => el('li', {}, r))),
    el('h3', {}, 'Acciones'), actions,
    el('h3', {}, 'Historial'), ...t.events.map((e) => el('div', { class: 'event' }, el('small', {}, e.at + ' · ' + e.author + ' · ' + e.kind), el('br'), e.body)),
    form, el('p', { id: 'detail-msg', class: 'msg', role: 'status' }));
  refresh();
}

async function act(fn, id) {
  try { await fn(); await show(id); } catch (err) { const m = $('#detail-msg'); m.textContent = err.message; m.className = 'msg err'; }
}

$('#filters').replaceChildren(...['all', 'P1', 'P2', 'P3', 'P4'].map((p) => {
  const b = el('button', { type: 'button', 'aria-pressed': String(p === priority) }, p === 'all' ? 'Todos' : p);
  b.addEventListener('click', () => { priority = p; document.querySelectorAll('#filters button').forEach((x) => x.setAttribute('aria-pressed', String(x === b))); refresh(); });
  return b;
}));

$('#new').addEventListener('submit', async (e) => {
  e.preventDefault();
  const f = e.target, msg = $('#new-msg');
  const w = f.workaround_available.value;
  try {
    const t = await api('/api/tickets', { title: f.title.value, description: f.description.value, affected_users: Number(f.affected_users.value), workaround_available: w === '' ? null : w === 'true' });
    msg.textContent = 'Creado ' + t.id + ' con prioridad ' + t.triage.priority + '.'; msg.className = 'msg';
    f.reset(); await show(t.id);
  } catch (err) { msg.textContent = err.message; msg.className = 'msg err'; }
});

refresh().catch((err) => { $('#list').textContent = err.message; });
