(() => {
  const media = matchMedia('(min-width: 761px)');
  const pane = document.getElementById('reader-content');
  const archiveKey = 'radar-archive-state';
  const getState = () => { try { return JSON.parse(sessionStorage.getItem(archiveKey)) || {}; } catch (_) { return {}; } };
  const saveState = patch => { try { sessionStorage.setItem(archiveKey, JSON.stringify({...getState(), ...patch})); } catch (_) {} };
  const currentArchive = () => location.pathname + location.search;
  const cleanArchive = () => { const url = new URL(location.href); url.searchParams.delete('article'); return url.pathname + url.search; };
  const back = document.querySelector('.archive-back'); const saved = getState();
  if (back && saved.url && /^\/news\/(?:\?|$)/.test(saved.url)) back.href = saved.url;
  let controller;
  const articlePath = value => /^\/news\/\d+\/(?:\?.*)?$/.test(value || '');
  async function read(path, push = false) {
    if (!pane || !articlePath(path)) return;
    controller?.abort(); controller = new AbortController(); const signal = controller.signal;
    document.getElementById('reader-status').textContent = '正在读取报道'; pane.innerHTML = '<div class="empty">正在读取报道…</div>';
    const pure = path.split('?')[0]; document.querySelectorAll('.archive-list .news-row').forEach(row => { const selected = row.querySelector('h3 a')?.getAttribute('href') === pure; row.classList.toggle('selected', selected); row.querySelector('h3 a')?.toggleAttribute('aria-current', selected); });
    const open = document.getElementById('reader-open'); open.href = path; open.hidden = false;
    if (push) { const url = new URL(location.href); url.searchParams.set('article', path); history.pushState(null, '', url); saveState({url: url.pathname + url.search}); }
    try {
      const target = new URL(path, location.origin); target.searchParams.set('return', currentArchive());
      const response = await fetch(target, {signal}); if (!response.ok) throw new Error();
      const doc = new DOMParser().parseFromString(await response.text(), 'text/html'); const article = doc.querySelector('.article-layout'); if (!article) throw new Error();
      pane.replaceChildren(article); pane.parentElement.scrollTop = 0; document.getElementById('reader-status').textContent = '报道已载入';
    } catch (_) { if (!signal.aborted) pane.innerHTML = '<div class="empty">无法读取报道，请独立打开重试。</div>'; }
  }
  if (pane) {
    const density = localStorage.getItem('radar-density') || 'summary'; document.documentElement.dataset.density = density;
    document.querySelectorAll('[data-density]').forEach(button => { button.classList.toggle('active', button.dataset.density === density); button.addEventListener('click', () => { localStorage.setItem('radar-density', button.dataset.density); document.documentElement.dataset.density = button.dataset.density; document.querySelectorAll('[data-density]').forEach(item => item.classList.toggle('active', item === button)); }); });
    document.querySelector('.archive-list').addEventListener('click', event => {
      const link = event.target.closest('a'); if (!link || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || event.button !== 0 || !articlePath(link.getAttribute('href'))) return;
      saveState({url: currentArchive(), scroll: document.querySelector('.archive-list').scrollTop});
      if (!media.matches) { const target = new URL(link.href); target.searchParams.set('return', currentArchive()); link.href = target; return; }
      event.preventDefault(); read(link.getAttribute('href'), true);
    });
    pane.addEventListener('click', event => { const link = event.target.closest('a'); if (!link || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return; const target = new URL(link.href); if (target.origin === location.origin && articlePath(target.pathname + target.search)) { event.preventDefault(); read(target.pathname + target.search, true); } });
    pane.addEventListener('submit', async event => {
      const action = event.target.closest('[data-reader-action]'); if (!action) return; event.preventDefault(); const status = pane.querySelector('.action-status');
      try { const values = new FormData(action); const body = {}; for (const [key, value] of values) body[key] = key in body ? [].concat(body[key], value) : value; const response = await fetch(action.action, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRFToken': body.csrfmiddlewaretoken}, body: JSON.stringify(body)}); const data = await response.json(); if (!response.ok) throw new Error(data.error); if (body.action === 'favourite') { const label = action.querySelector('[data-favourite-label]'); label.textContent = label.textContent.includes('取消') ? '收藏此版本' : '取消收藏'; } if (status) status.textContent = data.job ? '任务已加入后台队列' : '操作已保存'; } catch (error) { if (status) status.textContent = error.message || '操作失败'; }
    });
    document.getElementById('reader-focus')?.addEventListener('click', event => { const focused = document.querySelector('.archive-layout').classList.toggle('reader-focused'); event.target.textContent = focused ? '返回列表' : '专注阅读'; });
    function restore() { const selected = new URL(location.href).searchParams.get('article'); if (selected) { if (!media.matches) { const target = new URL(selected, location.origin); target.searchParams.set('return', cleanArchive()); location.replace(target); } else read(selected); } else { controller?.abort(); pane.innerHTML = '<div class="empty">选择一篇报道阅读</div>'; document.getElementById('reader-open').hidden = true; } }
    window.addEventListener('popstate', restore); restore(); requestAnimationFrame(() => { const list = document.querySelector('.archive-list'); if (saved.scroll) list.scrollTop = saved.scroll; });
  }
})();
