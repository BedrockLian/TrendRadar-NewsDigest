(() => {
  const dialog = document.getElementById('ask-dialog');
  document.getElementById('ask-open')?.addEventListener('click', () => dialog.showModal());
  document.getElementById('ask-close')?.addEventListener('click', () => dialog.close());
  let conversation = null;
  document.getElementById('ask-form')?.addEventListener('submit', async event => {
    event.preventDefault();
    const form = event.target, button = form.querySelector('button'), box = document.createElement('div');
    box.className = 'answer'; box.textContent = '正在检索新闻库…';
    document.getElementById('answers').append(box); button.disabled = true;
    try {
      const response = await fetch('/api/v1/answer/', {method:'POST', headers:{'Content-Type':'application/json', 'X-CSRFToken':form.querySelector('[name=csrfmiddlewaretoken]').value}, body:JSON.stringify({question:form.question.value, conversation})});
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || '暂时无法回答');
      conversation = data.conversation;
      const stream = new EventSource(`/api/v1/jobs/${data.job}/stream/`);
      stream.addEventListener('state', e => {
        const state = JSON.parse(e.data);
        box.textContent = state.result.partial || '正在检索和核对来源…';
        if (state.status === 'completed') {
          box.textContent = state.result.text;
          for (const item of state.result.evidence || []) {
            const link = document.createElement('a');
            link.href = `/news/?q=${encodeURIComponent(item.title.slice(0,20))}`;
            link.textContent = `\n[${item.version_id}] ${item.title}`;
            box.append(link);
          }
          stream.close(); button.disabled = false;
        } else if (state.status === 'failed') {
          box.textContent = '本次生成未完成，请稍后重试。'; stream.close(); button.disabled = false;
        }
      });
      stream.onerror = () => {stream.close(); button.disabled = false; box.textContent += '\n连接中断，可在仪表盘查看任务。';};
    } catch(error) {box.textContent = error.message; button.disabled = false;}
  });
  const canvas = document.getElementById('crawl-chart');
  if (!canvas) return;
  const data = JSON.parse(document.getElementById('crawl-data').textContent).series;
  function draw() {
    const width = canvas.clientWidth, height = canvas.clientHeight, ratio = window.devicePixelRatio || 1;
    canvas.width = width * ratio; canvas.height = height * ratio;
    const ctx = canvas.getContext('2d'); ctx.scale(ratio,ratio);
    if (!data.length) {document.getElementById('chart-empty').textContent = '这个时段没有采集记录。历史导入单独统计。'; return;}
    const max = Math.max(1,...data.map(d=>d.added+d.duplicate+d.updated));
    const left=42, top=12, plotH=height-45, plotW=width-left-8;
    ctx.font='10px system-ui'; ctx.fillStyle='#65747e'; ctx.strokeStyle='#e4e9ec';
    for(let n=0;n<=4;n++){const y=top+plotH*n/4;ctx.beginPath();ctx.moveTo(left,y);ctx.lineTo(width,y);ctx.stroke();ctx.fillText(Math.round(max*(1-n/4)),2,y+4);}
    const stride=plotW/data.length;
    data.forEach((d,i)=>{
      let y=top+plotH;
      for(const [key,color] of [['added','#285b80'],['updated','#b77732'],['duplicate','#c9dce9']]){
        const h=plotH*d[key]/max;ctx.fillStyle=color;ctx.fillRect(left+i*stride+2,y-h,Math.max(1,stride-4),h);y-=h;
      }
      if(i%Math.max(1,Math.ceil(data.length/6))===0){ctx.fillStyle='#65747e';const t=new Date(d.time);ctx.fillText(t.toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',month:'numeric',day:'numeric',hour:'2-digit'}),left+i*stride,height-8);}
    });
  }
  draw(); new ResizeObserver(draw).observe(canvas);
})();
