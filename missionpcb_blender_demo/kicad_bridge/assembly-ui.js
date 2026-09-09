/* The widget controls native Blender. It does not render a second CAD scene. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  let live = null, assembly = null, busy = false, selected = '', filter = 'issues', profile = null;
  let renderedFindings = '', renderedParts = '', lastSession = '', transformObject = '';
  const drafts = new Map();
  const nodes = (selector, root = document) => [...root.querySelectorAll(selector)];
  function el(tag, value = '', cls = '') {
    const node = document.createElement(tag); node.textContent = value;
    if (cls) node.className = cls;
    return node;
  }
  function notice(message, error = false) {
    $('notice').textContent = message || ''; $('notice').classList.toggle('error', error);
  }
  function ready() { return !!(live?.connected && assembly); }
  function controls() {
    nodes('[data-native]').forEach(node => { node.disabled = busy || !ready(); });
    nodes('[data-capability="comments"]').forEach(node => { node.disabled = busy || !ready() || !Array.isArray(assembly.comments); });
    $('moreView').disabled = busy || !ready() || !assembly.presentation;
    $('openBlender').disabled = busy;
    $('openBlender').textContent = ready() ? 'Show Blender' : 'Open Blender';
    const part = assembly?.objects.find(row => row.id === $('object').value);
    $('dimensions').disabled = busy || !ready() || ['electronics', 'component'].includes(part?.role);
    $('selectBody').disabled = busy || !ready() || !$('bodyObject').value;
    $('generateHousing').disabled = busy || !ready() || !profile?.adopted || profile.stale || !!assembly.different_project;
    $('edit').disabled = busy || !ready() || !part;
    $('updatePcb').disabled = busy || !ready() || !!assembly.different_project;
    $('place').disabled = busy || !ready() || !part || !$('region').value;
    nodes('[data-view="chest"]').forEach(node => { node.disabled = busy || !ready() || !assembly.objects.some(row => row.role === 'body'); });
  }
  async function request(url, body, headers = {}) {
    const response = await fetch(url, { method: 'POST', headers: { 'X-Widget-Token': token, ...headers }, body });
    const data = await response.json();
    if (!response.ok) throw Error(data.error || 'The request could not be completed.');
    return data;
  }
  async function action(actionName, payload = {}, message = 'Working in Blender…') {
    if (busy || !ready()) return false;
    busy = true; controls(); notice(message);
    try {
      const result = await request('/assembly/action', JSON.stringify({ action: actionName, expected_session: live.session, ...payload }), { 'Content-Type': 'application/json' });
      if (result.state) accept(result.state);
      notice(result.message);
      await refresh();
      return true;
    } catch (error) { notice(error.message, true); return false; }
    finally { busy = false; controls(); }
  }
  function openSection(name) {
    nodes('[data-section]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.section === name)));
    nodes('.workspace-section').forEach(section => { section.hidden = section.id !== name; });
  }
  function chooseOptions(id, values) {
    const select = $(id), old = select.value;
    const signature = JSON.stringify(values.map(row => [row.id, row.name, row.value]));
    if (select.dataset.signature === signature) return;
    select.dataset.signature = signature; select.replaceChildren();
    for (const row of values) {
      const option = el('option', row.ref ? `${row.ref} · ${row.value || row.name}` : row.name);
      option.value = row.id; select.append(option);
    }
    if (values.some(row => row.id === old)) select.value = old;
  }
  function offline(message) {
    live = null; assembly = null; renderedFindings = ''; renderedParts = '';
    $('status').className = 'connection'; $('status').textContent = 'Disconnected';
    $('stats').replaceChildren(); $('issueCount').textContent = '';
    $('checks').replaceChildren(empty('Blender is disconnected', 'Open Blender to reconnect to the saved assembly. Live results will appear here.'));
    $('partList').replaceChildren(); $('partDetails').replaceChildren(); $('timeline').replaceChildren();
    $('coverage').textContent = ''; chooseOptions('object', []); chooseOptions('region', []);
    if (!busy) notice(message || 'The Blender adapter is offline. Open the saved assembly to reconnect.');
    controls();
  }
  function empty(title, description) {
    const box = el('div', '', 'empty-state'); box.append(el('strong', title), el('div', description)); return box;
  }
  function rows() {
    if (!assembly) return [];
    return [
      ...(assembly.findings || []).map(f => ({ ...f, key: 'fit:' + f.id, category: 'Assembly fit', refs: [] })),
      ...(assembly.native_findings || []).map(f => ({ ...f, key: 'pcb:' + f.id, category: 'Component constraint', refs: f.kicad_refs || [] }))
    ];
  }
  function isReview(row) { return !['FAIL', 'PASS'].includes(row.status); }
  function comments(row) { return (assembly?.comments || []).filter(comment => comment.finding_id === row.id); }
  function refButton(label, object) {
    const button = el('button', label); button.dataset.native = '';
    button.onclick = () => action('assembly_focus', { object }, `Focusing ${label} in Blender…`);
    return button;
  }
  function findingCard(row) {
    const article = el('article', '', 'finding ' + (row.status || 'unknown').toLowerCase());
    const header = el('div', '', 'finding-header');
    header.append(el('span', row.status === 'FAIL' ? 'FLAGGED' : row.status === 'PASS' ? 'PASS' : 'NEEDS REVIEW', 'badge ' + (row.status === 'PASS' ? 'pass' : row.status === 'FAIL' ? '' : 'skip')), el('span', row.category, 'category'));
    const rawTitle = row.title || row.id || 'Finding';
    const title = rawTitle.includes('_') ? (row.subjects?.length > 1 ? row.subjects.join(' / ') + ' separation' : row.message || rawTitle.replaceAll('_', ' ')) : rawTitle;
    article.append(header, el('h3', title));
    const reason = row.reason || row.explanation || row.message;
    if (reason && reason !== row.title && reason !== row.message) article.append(el('p', reason));
    else if (row.title && reason !== row.title) article.append(el('p', reason));
    if (Number.isFinite(row.measured_mm) && Number.isFinite(row.required_mm)) {
      article.append(el('p', `${row.measured_mm.toFixed(2)} mm measured · ${row.required_mm.toFixed(2)} mm required`, 'measurement'));
    }
    if (row.suggestion) article.append(el('p', row.suggestion));
    if (row.method || row.rationale) article.append(el('p', row.method || row.rationale, 'method'));
    const refs = el('div', '', 'refs');
    for (const ref of row.refs) refs.append(refButton(ref + ' ↗', 'part-' + ref));
    if (!row.refs.length && row.object) {
      const object = assembly.objects.find(item => item.id === row.object);
      if (object) refs.append(refButton('Show ' + object.name, row.object));
    }
    article.append(refs);
    const details = el('details'); details.dataset.finding = row.key;
    const saved = comments(row);
    details.append(el('summary', saved.length ? `Review notes · ${saved.length}` : 'Add review note'));
    for (const comment of saved) {
      const note = el('div', '', 'comment');
      if (comment.created) {
        const date = new Date(typeof comment.created === 'number' ? comment.created * 1000 : comment.created);
        if (!Number.isNaN(date.valueOf())) note.append(el('small', date.toLocaleString()));
      }
      note.append(el('span', comment.text)); details.append(note);
    }
    const label = el('label', 'Comment on this finding');
    const field = el('textarea'); field.placeholder = 'Reason, design decision, or follow-up…'; field.maxLength = 2000;
    field.value = drafts.get(row.key) || ''; field.oninput = () => drafts.set(row.key, field.value);
    label.append(field); details.append(label);
    const result = el('span', '', 'comment-state'); result.setAttribute('role', 'status');
    const save = el('button', 'Save note in Blender'); save.dataset.native = '';
    save.dataset.capability = 'comments';
    if (!Array.isArray(assembly.comments)) result.textContent = 'Reconnect the updated Blender adapter to enable native notes.';
    save.onclick = async () => {
      const text = field.value.trim();
      if (!text) { result.textContent = 'Write a note first.'; field.focus(); return; }
      result.textContent = 'Saving note…';
      if (await action('assembly_comment', { finding_id: row.id, text, object: row.object || (row.refs[0] ? 'part-' + row.refs[0] : undefined) })) {
        drafts.delete(row.key); field.value = ''; result.textContent = 'Note saved with the native assembly.';
        renderedFindings = ''; renderFindings();
      } else result.textContent = 'Note was not saved. See the message above.';
    };
    details.append(save, result); article.append(details); return article;
  }
  function renderFindings() {
    if (!assembly) return;
    const all = rows();
    const selectedRows = all.filter(row => filter === 'issues' ? row.status !== 'PASS' : filter === 'review' ? isReview(row) : row.status === filter);
    const signature = JSON.stringify([selectedRows, assembly.comments, assembly.component_check_error, assembly.objects.map(row => [row.id, row.name])]);
    if (signature === renderedFindings) return;
    renderedFindings = signature;
    const opened = new Set(nodes('details[open][data-finding]', $('checks')).map(node => node.dataset.finding));
    $('checks').replaceChildren();
    if (assembly.component_check_error) $('checks').append(empty('Component checks unavailable', assembly.component_check_error));
    for (const row of selectedRows) {
      const card = findingCard(row); const detail = card.querySelector('details'); detail.open = opened.has(row.key);
      $('checks').append(card);
    }
    if (!selectedRows.length && !assembly.component_check_error) $('checks').append(empty(filter === 'PASS' ? 'No completed passes yet' : 'No findings in this filter', filter === 'issues' ? 'Review the Brief section for evidence and requirements that geometry checks cannot resolve.' : 'Choose another filter to inspect the other check results.'));
    controls();
  }
  function renderSummary() {
    const fit = assembly.findings || [], native = assembly.native_findings || [], coverage = assembly.model_coverage || {};
    const models = coverage.modeled_refs || [], missing = coverage.missing_model_refs || [];
    const pending = rows().filter(isReview).length;
    const values = [
      [fit.filter(f => f.status === 'FAIL').length, 'Fit issues', `${fit.filter(f => f.status === 'PASS').length} fit checks passed`],
      [assembly.component_check_error ? '—' : native.filter(f => f.status === 'FAIL').length, 'Component flags', 'Placement constraints'],
      [pending, 'Needs review', 'Evidence or setup missing'],
      [models.length + missing.length ? `${models.length}/${models.length + missing.length}` : '—', '3D models', missing.length ? `${missing.length} package missing` : 'Coverage from KiCad']
    ];
    $('stats').replaceChildren(...values.map(([value, label, subtitle], index) => {
      const cell = el('div', '', 'summary-cell' + (index < 2 && value > 0 ? ' issue' : ''));
      cell.append(el('strong', String(value)), el('span', label), el('small', subtitle)); return cell;
    }));
    $('issueCount').textContent = String(rows().filter(f => f.status !== 'PASS').length || '');
    const approximate = assembly.objects.filter(o => o.approximate).map(o => o.ref);
    $('coverage').textContent = [missing.length ? `Missing package geometry: ${missing.join(', ')}. Those references remain in checks.` : '', approximate.length ? `Approximate package models: ${approximate.join(', ')}.` : '', assembly.stale ? 'The geometry has changed; check results need refreshing.' : ''].filter(Boolean).join(' ');
  }
  function renderParts() {
    const query = $('partSearch').value.trim().toLowerCase();
    const objects = assembly.objects.filter(o => o.role !== 'region');
    if (!objects.some(o => o.id === selected)) selected = objects.find(o => o.ref)?.id || objects[0]?.id || '';
    const visible = objects.filter(o => [o.ref, o.value, o.name, o.role].join(' ').toLowerCase().includes(query));
    const signature = JSON.stringify([visible.map(o => [o.id, o.name, o.value, o.missing_model]), rows(), selected, query]);
    if (renderedParts !== signature) {
      renderedParts = signature; const scroll = $('partList').scrollTop; $('partList').replaceChildren();
      for (const object of visible) {
        const button = el('button', '', 'part' + (object.id === selected ? ' active' : ''));
        button.setAttribute('aria-pressed', String(object.id === selected));
        const name = el('span'); name.append(el('strong', object.ref || object.name), el('small', object.ref ? object.value || (object.missing_model ? 'Package model missing' : object.role) : object.role));
        const count = rows().filter(f => f.status !== 'PASS' && (f.refs.includes(object.ref) || f.object === object.id)).length;
        button.append(name, el('span', String(count), 'count'));
        button.onclick = () => { selected = object.id; $('object').value = selected; renderParts(); controls(); };
        $('partList').append(button);
      }
      if (!visible.length) $('partList').append(el('p', 'No components match this search.', 'help'));
      $('partList').scrollTop = scroll;
    }
    const object = objects.find(o => o.id === selected), box = $('partDetails');
    if (!object) { box.replaceChildren(); return; }
    const signatureDetails = JSON.stringify([object, rows().filter(f => f.refs.includes(object.ref) || f.object === object.id), assembly.comments]);
    if (box.dataset.signature === signatureDetails) return;
    box.dataset.signature = signatureDetails; box.replaceChildren();
    box.append(el('h3', object.ref ? `${object.ref} · ${object.value || object.name}` : object.name));
    const properties = el('dl', '', 'property-grid');
    for (const [label, value] of [['Role', object.role], ['3D geometry', object.missing_model ? 'Missing package model' : object.approximate ? 'Approximate package' : object.dimensions_mm ? 'Mesh available' : 'Assembly reference'], ['Position · mm', vectorText(object.position_mm)], ['Rotation · °', vectorText(object.rotation_deg)], ['Bounds · mm', vectorText(object.dimensions_mm)], ['Mounting area', object.region?.replace('region-', '') || 'Unassigned']]) {
      const cell = el('div'); cell.append(el('dt', label), el('dd', value)); properties.append(cell);
    }
    box.append(properties, refButton('Focus in Blender ↗', object.id));
    const edit = el('button', 'Edit placement'); edit.onclick = () => { $('object').value = object.id; readTransform(); openSection('build'); };
    const buttons = el('div', '', 'button-row'); buttons.append(edit); box.append(buttons);
    const related = rows().filter(f => f.status !== 'PASS' && (f.refs.includes(object.ref) || f.object === object.id));
    for (const row of related) box.append(findingCard(row));
    if (!related.length) box.append(el('p', 'No current geometry or placement flags for this object. Brief evidence may still be incomplete.', 'help'));
    controls();
  }
  function vectorText(value) { return value ? value.map(number => Number(number).toFixed(2)).join(' × ') : 'Not available'; }
  function accept(data) {
    if (!data.connected && !data.assembly) { offline(data.error); return; }
    live = { ...data, connected: true }; assembly = data.assembly;
    if (!assembly) { offline('Blender is connected. Confirm a KiCad board to start the assembly.'); return; }
    if (lastSession && lastSession !== live.session) {
      for (const id of ['position', 'rotation', 'dimensions']) $(id).value = '';
      transformObject = ''; $('transformStatus').textContent = 'The native file or scene changed. Read its transform before editing.';
    }
    lastSession = live.session;
    $('status').className = 'connection online'; $('status').textContent = 'Blender connected';
    $('projectFile').textContent = data.file ? data.file.split('/').slice(-2).join(' / ') : 'Native assembly · not yet saved';
    $('projectFile').title = data.file || '';
    const sourceName = assembly.source_board?.split('/').pop();
    $('pcbSource').textContent = assembly.different_project ? `This model belongs to ${assembly.source_board.split('/').slice(-2,-1)[0]}. KiCad is using ${assembly.active_pcb_file.split('/').slice(-2,-1)[0]}; open the model’s source project to update it.` : assembly.saved_source_changed ? `${sourceName || 'Saved PCB'} changed. Update the assembly to review the latest board.` : assembly.saved_source_unavailable ? 'The source PCB file is unavailable.' : sourceName ? `${sourceName} · imported ${assembly.source_hash?.slice(0, 8) || 'revision'}` : 'Imported native KiCad board · update to synchronize current edits.';
    $('pcbSource').classList.toggle('source-stale', !!(assembly.saved_source_changed || assembly.different_project));
    chooseOptions('object', assembly.objects.filter(o => o.role !== 'region'));
    chooseOptions('region', assembly.objects.filter(o => o.role === 'region'));
    chooseOptions('bodyObject', assembly.objects.filter(o => o.role === 'body'));
    if (assembly.active_body_id) $('bodyObject').value = assembly.active_body_id;
    const body = assembly.objects.find(o => o.id === assembly.active_body_id);
    $('bodySource').textContent = body?.source || (body ? 'Reference anatomy; upload another body model to use it here.' : 'Add a reference body, or import your own CAD with Geometry type set to Body reference.');
    renderSummary(); renderFindings(); renderParts();
    $('timeline').replaceChildren(...(assembly.timeline || []).slice().reverse().map(row => el('li', row.reason)));
    controls();
  }
  async function refresh() {
    const response = await fetch('/assembly/state');
    if (!response.ok) throw Error('Cannot reach the local Blender connection service.');
    accept(await response.json());
  }
  function vector(id, positive = false) {
    const raw = $(id).value.split(',').map(value => value.trim());
    const values = raw.map(Number);
    if (raw.length !== 3 || raw.some(v => !v) || values.some(v => !Number.isFinite(v) || (positive && v <= 0))) throw Error('Enter three ' + (positive ? 'positive ' : '') + 'numbers separated by commas.');
    return values;
  }
  function readTransform() {
    const object = assembly?.objects.find(row => row.id === $('object').value);
    if (!object) return;
    $('position').value = object.position_mm.map(v => v.toFixed(3)).join(', ');
    $('rotation').value = object.rotation_deg.map(v => v.toFixed(3)).join(', ');
    $('dimensions').value = '';
    transformObject = object.id;
    $('transformStatus').textContent = `Loaded ${object.ref || object.name}. Position uses its parent coordinates.`;
    controls();
  }
  nodes('[data-section]').forEach(button => { button.onclick = () => openSection(button.dataset.section); });
  nodes('[data-filter]').forEach(button => { button.onclick = () => { filter = button.dataset.filter; nodes('[data-filter]').forEach(b => b.setAttribute('aria-pressed', String(b === button))); renderedFindings = ''; renderFindings(); }; });
  nodes('[data-view]').forEach(button => { button.onclick = () => assembly?.presentation ? action('assembly_view', { view: button.dataset.view }, 'Changing the native Blender view…') : action('assembly_focus', { object: { board: 'board', assembly: 'device', chest: 'body' }[button.dataset.view] }); });
  $('moreView').onchange = () => { const view = $('moreView').value; if (view) action('assembly_view', { view }); $('moreView').value = ''; };
  $('partSearch').oninput = () => { if (assembly) renderParts(); };
  $('object').onchange = () => {
    for (const id of ['position', 'rotation', 'dimensions']) $(id).value = '';
    transformObject = ''; $('transformStatus').textContent = 'Read this object’s transform before editing.'; controls();
  };
  $('region').onchange = controls;
  $('bodyObject').onchange = controls;
  $('selectBody').onclick = () => action('assembly_select_body', { object: $('bodyObject').value });
  $('generateHousing').onclick = async () => {
    if (busy || !ready() || !profile?.adopted || profile.stale) return;
    busy = true; controls(); notice('Generating editable housing from the reviewed brief profile…');
    try {
      const result = await request('/workflow/generate-housing', JSON.stringify({ profile_revision: profile.revision, expected_session: live.session }), { 'Content-Type': 'application/json' });
      if (result.state) accept(result.state); await refresh(); notice(result.message || 'Housing generated in Blender.');
    } catch (error) { notice(error.message, true); }
    finally { busy = false; controls(); }
  };
  $('openBlender').onclick = async () => {
    if (busy) return; busy = true; controls(); notice('Opening the saved assembly in Blender…');
    try { const result = await request('/assembly/open', '{}', { 'Content-Type': 'application/json' }); accept(result.state); notice(result.message); }
    catch (error) { notice(error.message, true); }
    finally { busy = false; controls(); }
  };
  $('updatePcb').onclick = async () => {
    if (busy || !ready()) return;
    busy = true; controls(); notice('Reading the active KiCad board, saving it, and updating the native assembly…');
    const session = live.session;
    try {
      const response = await fetch('/state'); const board = await response.json();
      if (!response.ok || !board.connected || !board.revision) throw Error(board.error || 'Open the project PCB in KiCad before updating.');
      if (!board.parts?.length) throw Error('The active KiCad board is empty. Open the source PCB or build the new board first.');
      const result = await request('/assembly/confirm', JSON.stringify({ revision: board.revision, expected_session: session }), { 'Content-Type': 'application/json' });
      if (result.state) accept(result.state); await refresh(); notice(result.message + ` Imported ${board.parts.length} component references.`);
    } catch (error) { notice(error.message, true); }
    finally { busy = false; controls(); }
  };
  for (const [id, command] of [['check','assembly_check'],['save','assembly_save'],['body','assembly_body'],['fitChest','assembly_fit_chest'],['sample','assembly_sample']]) $(id).onclick = () => action(command);
  $('focus').onclick = () => action('assembly_focus', { object: $('object').value });
  $('place').onclick = () => action('assembly_place', { object: $('object').value, region: $('region').value });
  $('load').onclick = readTransform;
  $('edit').onclick = () => {
    try {
      if (transformObject && transformObject !== $('object').value) throw Error('Read the current object transform first.');
      const payload = { object: $('object').value };
      for (const key of ['position','rotation','dimensions']) if ($(key).value.trim() && !$(key).disabled) payload[key] = vector(key, key === 'dimensions');
      if (Object.keys(payload).length === 1) throw Error('Enter a position, rotation or product size to apply.');
      action('assembly_edit', payload);
    } catch (error) { notice(error.message, true); }
  };
  $('addRegion').onclick = () => {
    try { action('assembly_region', { name: $('regionName').value.trim(), center: vector('center'), size: vector('size', true), reason: $('reason').value, parent: 'device' }); }
    catch (error) { notice(error.message, true); }
  };
  $('upload').onclick = async () => {
    const file = $('file').files[0]; if (!file) { notice('Choose a CAD file first.', true); return; }
    if (busy || !ready()) return; busy = true; controls(); notice(`Importing ${file.name} into Blender…`);
    try {
      const result = await request('/assembly/upload', file, { 'X-Filename': encodeURIComponent(file.name), 'X-Units': $('units').value, 'X-Role': $('assetRole').value, 'X-Blender-Session': live.session || '' });
      if (result.state) accept(result.state); notice(result.message); await refresh(); $('file').value = '';
    } catch (error) { notice(error.message, true); }
    finally { busy = false; controls(); }
  };
  async function engineering() {
    try {
      const response = await fetch('/workflow/summary');
      if (!response.ok) throw Error('Engineering details are unavailable. Open Engineering review for the current report.');
      const data = await response.json();
      const profileResponse = await fetch('/workflow/profile');
      if (profileResponse.ok) profile = await profileResponse.json();
      $('housingProfile').textContent = profile?.adopted ? (profile.stale ? 'The brief changed. Review the device profile before generating housing.' : `Reviewed profile: ${profile.adopted.device_kind.toUpperCase()} · ${profile.adopted.mount} · ${profile.adopted.attachment}`) : 'No reviewed device profile yet. Open Engineering review to confirm the body location, attachment and enclosure dimensions.';
      controls();
      const briefText = typeof data.brief === 'string' ? data.brief : data.brief?.text || data.project_brief?.text || '';
      $('briefFacts').replaceChildren();
      const facts = briefText.replace(/\s+/g, ' ').match(/[^.!?]+[.!?]+(?:\s|$)|[^.!?]+$/g) || [];
      for (const [index, fact] of facts.entries()) {
        const paragraph = fact.trim();
        const label = /worn|wear.*days|showers/i.test(paragraph) ? 'Wear & environment' : /electrode|biopotential/i.test(paragraph) ? 'Signal & connectivity' : /cradle|recharg|contact window/i.test(paragraph) ? 'Charging' : /enclosure|interior/i.test(paragraph) ? 'Enclosure' : /shirt|thin enough/i.test(paragraph) ? 'Wearability' : /hospital|regulatory/i.test(paragraph) ? 'Pilot & review' : index === 0 ? 'Device' : 'Requirement';
        const card = el('div', '', 'brief-item'); card.append(el('span', label), el('strong', paragraph)); $('briefFacts').append(card);
      }
      $('requirements').replaceChildren();
      const checks = [...(data.wearable_checks || []), ...(data.requirements || [])];
      for (const row of checks) {
        const item = el('article', '', 'requirement');
        item.append(el('span', row.status || 'EVIDENCE NEEDED', 'badge ' + (row.status === 'PASS' ? 'pass' : row.status === 'FAIL' ? '' : 'skip')), el('h3', row.title || row.requirement || row.id), el('p', row.message || row.rule || row.reason || ''));
        $('requirements').append(item);
      }
      $('engineeringStatus').textContent = (data.project_name ? `Engineering brief for ${data.project_name}. ` : '') + (data.brief?.interpretation_status || data.project_brief?.interpretation_status || 'Placement checks and wearable evidence are tracked separately. Open engineering review for measurements and decisions.');
    } catch (error) { $('engineeringStatus').textContent = error.message; }
  }
  document.addEventListener('missionpcb:brief-saved', engineering);
  controls(); refresh().catch(error => offline(error.message)); engineering();
  setInterval(() => { if (!busy) refresh().catch(error => offline(error.message)); }, 2500);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) { refresh().catch(error => offline(error.message)); engineering(); } });
})();
