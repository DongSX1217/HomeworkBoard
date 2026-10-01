/* 题目解析助手 —— 前端逻辑
 * 1. 图片：点击 / 拖拽 / 粘贴上传，前端压缩后以 multipart 提交
 * 2. 提交后读取后端 SSE 流，实时更新加载遮罩中的步骤状态
 * 3. 结束后渲染结果，并保留第一步 OCR 文本
 */
(function () {
  'use strict';

  /* ---------- DOM ---------- */
  const form        = document.getElementById('form');
  const userText    = document.getElementById('userText');
  const drop        = document.getElementById('drop');
  const imageInput  = document.getElementById('imageInput');
  const dropHint    = document.getElementById('dropHint');
  const preview     = document.getElementById('preview');
  const clearBtn    = document.getElementById('clearBtn');
  const submitBtn   = document.getElementById('submitBtn');
  const overlay     = document.getElementById('overlay');
  const stepText    = document.getElementById('stepText');
  const step1El     = document.getElementById('step1');
  const step2El     = document.getElementById('step2');
  const resultCard  = document.getElementById('result');
  const resultText  = document.getElementById('resultText');
  const ocrBox      = document.getElementById('ocrBox');
  const ocrText     = document.getElementById('ocrText');
  const copyBtn     = document.getElementById('copyBtn');

  /* ---------- 状态 ---------- */
  let imageBlob = null;      // 压缩后的图片 Blob
  let imageName = 'image.jpg';
  let objectUrl = null;      // 预览用的临时 URL
  let running   = false;     // 防止重复提交

  const STEP_LABEL = {
    1: '正在识别图片中的题目…',
    2: '正在思考并生成答案与易错答案…'
  };

  /* =========================================================
   *  图片处理
   * =======================================================*/

  function loadImage(file) {
    return new Promise(function (resolve, reject) {
      const url = URL.createObjectURL(file);
      const img = new Image();
      img.onload = function () {
        URL.revokeObjectURL(url);
        resolve(img);
      };
      img.onerror = function () {
        URL.revokeObjectURL(url);
        reject(new Error('图片读取失败'));
      };
      img.src = url;
    });
  }

  /** 压缩图片，避免请求体过大（长边 <= maxSide） */
  async function compressImage(file, maxSide, quality) {
    maxSide = maxSide || 1600;
    quality = quality || 0.85;
    const img = await loadImage(file);
    let w = img.naturalWidth || img.width;
    let h = img.naturalHeight || img.height;
    const scale = Math.min(1, maxSide / Math.max(w, h));
    w = Math.max(1, Math.round(w * scale));
    h = Math.max(1, Math.round(h * scale));

    const canvas = document.createElement('canvas');
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = '#ffffff';           // 透明 PNG 转 JPEG 时铺白底
    ctx.fillRect(0, 0, w, h);
    ctx.drawImage(img, 0, 0, w, h);

    return new Promise(function (resolve) {
      canvas.toBlob(function (blob) {
        resolve(blob || file);
      }, 'image/jpeg', quality);
    });
  }

  async function setImage(file) {
    if (!file || !file.type || file.type.indexOf('image/') !== 0) {
      toast('请上传图片文件');
      return;
    }
    try {
      const blob = await compressImage(file);
      imageBlob = blob;
      imageName = ((file.name || 'image').replace(/\.[^.]+$/, '') || 'image') + '.jpg';

      if (objectUrl) URL.revokeObjectURL(objectUrl);
      objectUrl = URL.createObjectURL(blob);
      preview.src = objectUrl;
      preview.classList.add('show');
      drop.classList.add('has-image');
      dropHint.textContent = '已选择图片，点击可更换（或直接粘贴新图）';
    } catch (err) {
      toast('图片处理失败：' + (err.message || err));
    }
  }

  function clearImage() {
    imageBlob = null;
    imageInput.value = '';
    if (objectUrl) {
      URL.revokeObjectURL(objectUrl);
      objectUrl = null;
    }
    preview.removeAttribute('src');
    preview.classList.remove('show');
    drop.classList.remove('has-image');
    dropHint.textContent = '点击、拖拽或粘贴图片到此处上传';
  }

  /* 点击 / 键盘 */
  drop.addEventListener('click', function () { imageInput.click(); });
  drop.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      imageInput.click();
    }
  });
  imageInput.addEventListener('change', function () {
    if (imageInput.files && imageInput.files[0]) setImage(imageInput.files[0]);
  });

  /* 拖拽 */
  ['dragenter', 'dragover'].forEach(function (ev) {
    drop.addEventListener(ev, function (e) {
      e.preventDefault();
      e.stopPropagation();
      drop.classList.add('dragover');
    });
  });
  drop.addEventListener('dragleave', function (e) {
    e.preventDefault();
    e.stopPropagation();
    drop.classList.remove('dragover');
  });
  drop.addEventListener('drop', function (e) {
    e.preventDefault();
    e.stopPropagation();
    drop.classList.remove('dragover');
    const dt = e.dataTransfer;
    if (dt && dt.files && dt.files[0]) setImage(dt.files[0]);
  });
  /* 阻止浏览器在页面其它位置打开拖入的图片 */
  ['dragover', 'drop'].forEach(function (ev) {
    window.addEventListener(ev, function (e) { e.preventDefault(); });
  });

  /* 粘贴 */
  document.addEventListener('paste', function (e) {
    const items = e.clipboardData && e.clipboardData.items;
    if (!items) return;
    for (let i = 0; i < items.length; i++) {
      if (items[i].type && items[i].type.indexOf('image/') === 0) {
        const f = items[i].getAsFile();
        if (f) {
          e.preventDefault();
          setImage(f);
          break;
        }
      }
    }
  });

  /* 清空 */
  clearBtn.addEventListener('click', function () {
    if (running) return;
    userText.value = '';
    clearImage();
    resultCard.classList.add('hidden');
    ocrBox.classList.add('hidden');
    ocrText.textContent = '';
    resultText.textContent = '';
  });

  /* =========================================================
   *  加载遮罩 / 步骤状态
   * =======================================================*/

  function setStepState(n, state) {
    const el = n === 1 ? step1El : step2El;
    el.className = state;
  }

  function startLoading(hasImage) {
    running = true;
    submitBtn.disabled = true;
    submitBtn.classList.add('loading');

    setStepState(1, hasImage ? 'pending' : 'skipped');
    setStepState(2, 'pending');
    stepText.textContent = hasImage ? '正在准备识别图片…' : '正在准备生成答案…';

    ocrBox.classList.add('hidden');
    ocrText.textContent = '';
    resultCard.classList.add('hidden');

    overlay.classList.remove('hidden');
    document.body.style.overflow = 'hidden';
  }

  function finishLoading() {
    running = false;
    submitBtn.disabled = false;
    submitBtn.classList.remove('loading');
    overlay.classList.add('hidden');
    document.body.style.overflow = '';
  }

  /* =========================================================
   *  SSE 解析
   * =======================================================*/

  function readSSE(response, onEvent) {
    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    function handleChunk(chunk) {
      let event = 'message';
      let data = '';
      chunk.split('\n').forEach(function (line) {
        line = line.replace(/\r$/, '');
        if (line.indexOf('event:') === 0) {
          event = line.slice(6).trim();
        } else if (line.indexOf('data:') === 0) {
          data += line.slice(5).trim();
        }
      });
      if (!data) return;
      let payload = null;
      try { payload = JSON.parse(data); } catch (e) { return; }
      onEvent(event, payload);
    }

    return (function pump() {
      return reader.read().then(function (res) {
        if (res.done) {
          if (buffer.trim()) handleChunk(buffer.trim());
          return;
        }
        buffer += decoder.decode(res.value, { stream: true });
        let idx;
        while ((idx = buffer.search(/\r?\n\r?\n/)) !== -1) {
          const chunk = buffer.slice(0, idx);
          buffer = buffer.replace(/^\r?\n\r?\n/, '');
          buffer = buffer.slice(idx === -1 ? 0 : 0); // 占位，实际下面重新裁剪
          break;
        }
        /* 上面的写法不够直观，改为标准做法： */
        buffer = decoder.decode(res.value, { stream: true }) === '' ? buffer : buffer;
        return pump();
      });
    })();
  }

  /* 上面 readSSE 的切分写得太绕，这里用干净版本替换 */
  function streamSSE(response, onEvent) {
    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    function drain() {
      let match;
      const re = /\r?\n\r?\n/;
      while ((match = re.exec(buffer)) !== null) {
        const raw = buffer.slice(0, match.index);
        buffer = buffer.slice(match.index + match[0].length);

        let event = 'message';
        let data = '';
        raw.split(/\r?\n/).forEach(function (line) {
          if (line.indexOf('event:') === 0) event = line.slice(6).trim();
          else if (line.indexOf('data:') === 0) data += line.slice(5).trim();
        });
        if (!data) continue;
        try {
          onEvent(event, JSON.parse(data));
        } catch (e) { /* 忽略无法解析的片段 */ }
      }
    }

    return (function pump() {
      return reader.read().then(function (res) {
        if (res.done) {
          buffer += decoder.decode();
          drain();
          return;
        }
        buffer += decoder.decode(res.value, { stream: true });
        drain();
        return pump();
      });
    })();
  }

  /* =========================================================
   *  提交
   * =======================================================*/

  form.addEventListener('submit', async function (e) {
    e.preventDefault();
    if (running) return;

    const text = userText.value.trim();
    if (!text && !imageBlob) {
      toast('请输入文字或上传图片');
      return;
    }

    const hasImage = !!imageBlob;
    startLoading(hasImage);

    const fd = new FormData();
    fd.append('text', text);
    if (imageBlob) fd.append('image', imageBlob, imageName);

    let finished = false;   // 是否已收到 done / error

    try {
      const resp = await fetch('/api/solve', { method: 'POST', body: fd });

      if (!resp.ok || !resp.body) {
        throw new Error('服务器响应异常（HTTP ' + resp.status + '）');
      }

      await streamSSE(resp, function (event, data) {
        if (event === 'step') {
          const n = data.step;
          const st = data.status;
          setStepState(n, st);
          if (st === 'running') {
            stepText.textContent = STEP_LABEL[n] || '处理中…';
          }
        } else if (event === 'ocr') {
          ocrText.textContent = data.text || '';
          ocrBox.classList.toggle('hidden', !data.text);
        } else if (event === 'done') {
          finished = true;
          setStepState(1, hasImage ? 'done' : 'skipped');
          setStepState(2, 'done');
          stepText.textContent = '已完成';
          finishLoading();
          renderResult(data.result, data.ocr);
        } else if (event === 'error') {
          finished = true;
          setStepState(2, 'error');
          finishLoading();
          toast('生成失败：' + (data.message || '未知错误'));
        }
      });

      if (!finished) {
        finishLoading();
        toast('连接意外结束，请重试');
      }
    } catch (err) {
      finishLoading();
      toast('请求失败：' + (err.message || err));
    }
  });

  /* =========================================================
   *  结果渲染
   * =======================================================*/

  function renderResult(result, ocr) {
    resultText.textContent = result || '（后端未返回内容）';

    if (ocr) {
      ocrText.textContent = ocr;
      ocrBox.classList.remove('hidden');
    } else {
      ocrBox.classList.add('hidden');
    }

    resultCard.classList.remove('hidden');
    resultCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  copyBtn.addEventListener('click', async function () {
    const txt = resultText.textContent || '';
    if (!txt) return;
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(txt);
      } else {
        const ta = document.createElement('textarea');
        ta.value = txt;
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        ta.remove();
      }
      copyBtn.textContent = '已复制 ✓';
      setTimeout(function () { copyBtn.textContent = '复制'; }, 1600);
    } catch (e) {
      toast('复制失败，请手动选择文本');
    }
  });

  /* =========================================================
   *  轻量提示
   * =======================================================*/

  function toast(msg) {
    const el = document.createElement('div');
    el.className = 'toast';
    el.textContent = msg;
    document.body.appendChild(el);
    requestAnimationFrame(function () { el.classList.add('show'); });
    setTimeout(function () {
      el.classList.remove('show');
      setTimeout(function () { el.remove(); }, 300);
    }, 4000);
  }

  /* 暴露给调试（可选） */
  window.__solver = { toast: toast };
})();