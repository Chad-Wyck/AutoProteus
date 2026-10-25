'use strict';

// This viewer only requests evidence. Text and tool arguments are never HTML.
function evidenceViewer({api, identifier}) {
  const dialog = document.getElementById('evidence-dialog');
  const list = document.getElementById('evidence-list');
  const more = document.getElementById('evidence-more');
  const status = document.getElementById('evidence-status');
  let offset = 0, loading = false, generation = 0;
  const titles = {
    host_inference_request: 'Model input · saved instructions and tools',
    host_inference_response: 'Model response · reported content',
    host_operation_receipt: 'Operation receipt · saved checkpoint state',
    host_input_delivered: 'Your instruction delivered',
    host_input_queued: 'Your instruction queued',
    action_started: 'Action started', action_result: 'Action result · reported by the agent',
    activation_context_omitted: 'Activation notice omitted from model input',
    host_inference_history_incomplete: 'Evidence recording incomplete'
  };
  const element = (tag, text) => {
    const item = document.createElement(tag); item.textContent = text; return item;
  };
  const showBlob = async (key, target, button) => {
    button.disabled = true;
    try {
      const blob = await api('/api/evidence/blob?' + new URLSearchParams({id: identifier, key}));
      target.textContent = JSON.stringify(blob.value, null, 2);
    } catch (error) { target.textContent = error.message; }
    finally { button.disabled = false; }
  };
  async function load() {
    if (loading) return;
    loading = true; more.disabled = true;
    const current = generation;
    try {
      const page = await api('/api/evidence?' + new URLSearchParams({id: identifier, offset}));
      if (current !== generation) return;
      for (const event of page.events) {
        const row = document.createElement('details');
        row.append(element('summary', `${event.time || ''} · ${titles[event.type] || event.type}`));
        const body = element('pre', JSON.stringify(event.data, null, 2));
        body.style.cssText = 'white-space:pre-wrap;overflow-wrap:anywhere;max-height:40vh;overflow:auto';
        row.append(body);
        const data = event.data || {};
        const references = [];
        if (/^[a-f0-9]{64}$/.test(data.state || '')) references.push(['Instructions, tools and source', data.state]);
        if (/^[a-f0-9]{64}$/.test(data.response || '')) references.push(['Recorded response', data.response]);
        for (const [index, key] of (Array.isArray(data.messages) ? data.messages : []).entries()) {
          if (/^[a-f0-9]{64}$/.test(key)) references.push([`Input message ${index + 1}`, key]);
        }
        for (const [label, key] of references) {
          const detail = document.createElement('details'); detail.append(element('summary', label));
          const output = element('pre', 'Load the original, identity-checked evidence.');
          output.style.cssText = body.style.cssText;
          const button = element('button', 'Load original'); button.className = 'quiet';
          button.onclick = () => showBlob(key, output, button);
          detail.append(button, output); row.append(detail);
        }
        list.append(row);
      }
      offset = page.next_offset;
      document.getElementById('evidence-verification').textContent = JSON.stringify(page.verification, null, 2);
      more.hidden = !page.has_more;
      status.textContent = page.storage_warning?.message || (page.incomplete_tail ?
        'The journal ends with an incomplete record. Original evidence is preserved.' :
        page.has_more ? 'More saved records are available.' : 'Showing the saved records available now.');
    } catch (error) { status.textContent = error.message; }
    finally { loading = false; more.disabled = false; }
  }
  document.getElementById('close-evidence').onclick = () => { generation++; dialog.close(); };
  dialog.oncancel = () => { generation++; };
  more.onclick = load;
  list.replaceChildren(); status.textContent = 'Loading saved evidence…';
  dialog.showModal(); load();
}
