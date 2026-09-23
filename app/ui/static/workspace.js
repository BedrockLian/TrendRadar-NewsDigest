(() => {
  const dialog = document.getElementById('ask-dialog');
  const form = document.getElementById('ask-form');
  const answers = document.getElementById('answers');
  const storage = {
    get(key) { try { return JSON.parse(sessionStorage.getItem(key)); } catch (_) { return null; } },
    set(key, value) { try { sessionStorage.setItem(key, JSON.stringify(value)); } catch (_) {} },
    remove(key) { try { sessionStorage.removeItem(key); } catch (_) {} }
  };

  const feedFilter = document.getElementById('feed-filter');
  feedFilter?.addEventListener('input', () => {
    const query = feedFilter.value.trim().toLocaleLowerCase();
    const rows = document.querySelectorAll('.settings-sources [data-feed-name]');
    let visible = 0;
    rows.forEach(row => {
      row.hidden = !row.dataset.feedName.toLocaleLowerCase().includes(query);
      if (!row.hidden) visible += 1;
    });
    document.getElementById('feed-visible-count').textContent = query ? `${visible} / ${rows.length} 个来源` : `${rows.length} 个来源`;
    document.getElementById('feed-filter-empty').hidden = visible !== 0;
  });

  document.getElementById('ask-open')?.addEventListener('click', () => {
    dialog.showModal();
    setTimeout(() => document.getElementById('question')?.focus(), 0);
  });
  document.getElementById('ask-close')?.addEventListener('click', () => dialog.close());
  dialog?.addEventListener('click', event => { if (event.target === dialog) dialog.close(); });

  let conversation = storage.get('radar-conversation');
  let activeStream;
  const makeAnswer = () => {
    const node = document.createElement('article');
    node.className = 'answer';
    node.innerHTML = '<p class="answer-status">正在检索新闻库…</p><div class="answer-text"></div><div class="answer-evidence"></div>';
    answers?.append(node);
    return node;
  };
  const renderResult = (box, state) => {
    const status = box.querySelector('.answer-status');
    const text = box.querySelector('.answer-text');
    const citations = box.querySelector('.answer-evidence');
    if (state.status === 'completed') {
      status.textContent = '回答完成';
      text.textContent = state.result?.text || '';
      citations.replaceChildren();
      for (const item of state.result?.evidence || []) {
        const link = document.createElement('a');
        link.href = item.internal_url || item.url || `/news/?q=${encodeURIComponent(item.title.slice(0, 20))}`;
        link.textContent = `[${item.version_id}] ${item.title}`;
        citations.append(link);
      }
      return true;
    }
    if (state.status === 'failed') {
      status.textContent = '本次生成未完成';
      text.textContent = state.error || '任务失败，可重新提问。';
      return true;
    }
    status.textContent = state.status === 'pending' ? '等待 AI 任务…' : '正在检索和核对来源…';
    text.textContent = state.result?.partial || '';
    return false;
  };
  const addRecover = (box, job) => {
    if (box.querySelector('.answer-recover')) return;
    const button = document.createElement('button');
    button.type = 'button'; button.className = 'quiet answer-recover'; button.textContent = '重新连接任务';
    button.addEventListener('click', () => { button.remove(); watchJob(job, box, 0); });
    box.append(button);
  };
  const pollJob = async (job, box) => {
    const response = await fetch(`/api/v1/jobs/${job}/`);
    if (!response.ok) throw new Error('任务状态不可用');
    const state = await response.json();
    if (renderResult(box, state)) { storage.remove('radar-active-job'); form?.querySelector('button').removeAttribute('disabled'); return true; }
    return false;
  };
  const watchJob = (job, box, attempt = 0) => {
    activeStream?.close();
    storage.set('radar-active-job', {job, conversation});
    const stream = new EventSource(`/api/v1/jobs/${job}/stream/`); activeStream = stream;
    stream.addEventListener('state', event => {
      const state = JSON.parse(event.data);
      if (renderResult(box, state)) { stream.close(); storage.remove('radar-active-job'); form?.querySelector('button').removeAttribute('disabled'); }
    });
    stream.onerror = async () => {
      stream.close();
      try { if (await pollJob(job, box)) return; } catch (_) {}
      if (attempt < 3) {
        box.querySelector('.answer-status').textContent = `连接中断，正在重连（${attempt + 1}/3）…`;
        setTimeout(() => watchJob(job, box, attempt + 1), 1000 * 2 ** attempt);
      } else {
        box.querySelector('.answer-status').textContent = '连接暂时中断，任务仍可能在后台继续';
        addRecover(box, job); form?.querySelector('button').removeAttribute('disabled');
      }
    };
  };
  const pending = storage.get('radar-active-job');
  if (pending && form) {
    conversation = pending.conversation; storage.set('radar-conversation', conversation);
    const box = makeAnswer(); form.querySelector('button').disabled = true; watchJob(pending.job, box);
  }
  form?.addEventListener('submit', async event => {
    event.preventDefault();
    const button = form.querySelector('button'); const box = makeAnswer(); button.disabled = true;
    try {
      const response = await fetch('/api/v1/answer/', {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRFToken': form.querySelector('[name=csrfmiddlewaretoken]').value}, body: JSON.stringify({question: form.question.value, conversation})});
      const data = await response.json(); if (!response.ok) throw new Error(data.error || '暂时无法回答');
      conversation = data.conversation; storage.set('radar-conversation', conversation); form.question.value = '';
      watchJob(data.job, box);
    } catch (error) { box.querySelector('.answer-status').textContent = '无法开始任务'; box.querySelector('.answer-text').textContent = error.message; button.disabled = false; }
  });

  const expand = document.getElementById('brief-expand');
  expand?.addEventListener('click', () => {
    const preview = document.getElementById('brief-preview'); const open = preview.classList.toggle('expanded');
    expand.setAttribute('aria-expanded', String(open)); expand.textContent = open ? '收起简报' : `展开全部 ${preview.children.length} 条`;
  });

  const dataNode = document.getElementById('crawl-data');
  if (!dataNode) return;
  const data = JSON.parse(dataNode.textContent).series;
  const charts = [
    {id: 'arrival-chart', keys: [['added', '--blue'], ['updated', '--orange']], line: true},
    {id: 'duplicate-chart', keys: [['duplicate', '--chart-duplicate']], line: false}
  ];
  const draw = chart => {
    const canvas = document.getElementById(chart.id); if (!canvas) return;
    const css = getComputedStyle(document.documentElement); const color = key => css.getPropertyValue(key).trim();
    const width = canvas.clientWidth, height = canvas.clientHeight, ratio = devicePixelRatio || 1;
    canvas.width = width * ratio; canvas.height = height * ratio; const ctx = canvas.getContext('2d'); ctx.scale(ratio, ratio);
    if (!data.length) { document.getElementById('chart-empty').textContent = '这个时段没有采集记录。历史导入单独统计。'; return; }
    const max = Math.max(1, ...data.flatMap(point => chart.keys.map(([key]) => point[key] || 0)));
    const left = 40, top = 12, plotH = height - 42, plotW = width - left - 8; ctx.font = '10px Geist, system-ui';
    for (let n = 0; n <= 4; n++) { const y = top + plotH * n / 4; ctx.strokeStyle = color('--line'); ctx.beginPath(); ctx.moveTo(left, y); ctx.lineTo(width, y); ctx.stroke(); ctx.fillStyle = color('--muted'); ctx.fillText(Math.round(max * (1 - n / 4)), 2, y + 4); }
    chart.keys.forEach(([key, token]) => {
      ctx.strokeStyle = color(token); ctx.fillStyle = color(token); ctx.lineWidth = 2; ctx.beginPath();
      data.forEach((point, index) => { const x = left + (data.length === 1 ? 0 : plotW * index / (data.length - 1)); const y = top + plotH - plotH * (point[key] || 0) / max; if (chart.line) index ? ctx.lineTo(x, y) : ctx.moveTo(x, y); else ctx.fillRect(x, y, Math.max(2, plotW / data.length - 2), top + plotH - y); });
      if (chart.line) ctx.stroke();
    });
    const steps = Math.min(5, data.length); for (let i = 0; i < steps; i++) { const index = Math.round(i * (data.length - 1) / Math.max(1, steps - 1)); const x = left + plotW * index / Math.max(1, data.length - 1); const date = new Date(data[index].time); ctx.fillStyle = color('--muted'); ctx.fillText(date.toLocaleString('zh-CN', {timeZone: 'Asia/Shanghai', month: 'numeric', day: 'numeric', hour: '2-digit'}), Math.min(x, width - 54), height - 7); }
  };
  const redraw = () => charts.forEach(draw); window.addEventListener('themechange', redraw); redraw(); charts.forEach(c => { const el = document.getElementById(c.id); if (el) new ResizeObserver(() => draw(c)).observe(el); });
})();
