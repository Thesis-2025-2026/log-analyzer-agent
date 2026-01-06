(() => {
  function safeUrl(url) {
    try {
      const trimmed = String(url || '').trim();
      if (!trimmed) return null;
      const parsed = new URL(trimmed, window.location.origin);
      const protocol = parsed.protocol.toLowerCase();
      if (protocol === 'http:' || protocol === 'https:' || protocol === 'mailto:') return parsed.toString();
      return null;
    } catch {
      return null;
    }
  }

  function appendText(parent, text) {
    if (!text) return;
    parent.appendChild(document.createTextNode(text));
  }

  function appendInline(parent, text) {
    const s = String(text ?? '');
    let i = 0;
    while (i < s.length) {
      const idxCode = s.indexOf('`', i);
      const idxLink = s.indexOf('[', i);
      const idxBold = s.indexOf('**', i);

      let idx = -1;
      let kind = null;
      for (const [candidate, k] of [
        [idxCode, 'code'],
        [idxLink, 'link'],
        [idxBold, 'bold'],
      ]) {
        if (candidate !== -1 && (idx === -1 || candidate < idx)) {
          idx = candidate;
          kind = k;
        }
      }

      if (idx === -1) {
        appendText(parent, s.slice(i));
        return;
      }

      if (idx > i) appendText(parent, s.slice(i, idx));

      if (kind === 'code') {
        const end = s.indexOf('`', idx + 1);
        if (end === -1) {
          appendText(parent, s.slice(idx));
          return;
        }
        const code = document.createElement('code');
        code.textContent = s.slice(idx + 1, end);
        parent.appendChild(code);
        i = end + 1;
        continue;
      }

      if (kind === 'bold') {
        const end = s.indexOf('**', idx + 2);
        if (end === -1) {
          appendText(parent, s.slice(idx));
          return;
        }
        const strong = document.createElement('strong');
        appendInline(strong, s.slice(idx + 2, end));
        parent.appendChild(strong);
        i = end + 2;
        continue;
      }

      if (kind === 'link') {
        const closeBracket = s.indexOf(']', idx + 1);
        if (closeBracket === -1 || s[closeBracket + 1] !== '(') {
          appendText(parent, s[idx]);
          i = idx + 1;
          continue;
        }
        const closeParen = s.indexOf(')', closeBracket + 2);
        if (closeParen === -1) {
          appendText(parent, s.slice(idx));
          return;
        }
        const label = s.slice(idx + 1, closeBracket);
        const urlRaw = s.slice(closeBracket + 2, closeParen);
        const href = safeUrl(urlRaw);
        if (!href) {
          appendText(parent, s.slice(idx, closeParen + 1));
          i = closeParen + 1;
          continue;
        }
        const a = document.createElement('a');
        a.href = href;
        a.rel = 'noreferrer noopener';
        a.target = '_blank';
        appendInline(a, label);
        parent.appendChild(a);
        i = closeParen + 1;
        continue;
      }
    }
  }

  function isFence(line) {
    const m = /^```([a-zA-Z0-9_-]+)?\s*$/.exec(line);
    return m ? { lang: m[1] || null } : null;
  }

  function isHeading(line) {
    const m = /^(#{1,6})\s+(.*)$/.exec(line);
    return m ? { level: m[1].length, text: m[2] } : null;
  }

  function isHr(line) {
    return /^(\*\s*\*\s*\*|-{3,}|_\s*_\s*_)$/.test(line.trim());
  }

  function isUlItem(line) {
    const m = /^(\s*)[-*+]\s+(.*)$/.exec(line);
    return m ? { indent: m[1].length, text: m[2] } : null;
  }

  function isOlItem(line) {
    const m = /^(\s*)\d+\.\s+(.*)$/.exec(line);
    return m ? { indent: m[1].length, text: m[2] } : null;
  }

  function splitTableRow(line) {
    const trimmed = line.trim();
    if (!trimmed.includes('|')) return null;
    const raw = trimmed.startsWith('|') ? trimmed.slice(1) : trimmed;
    const raw2 = raw.endsWith('|') ? raw.slice(0, -1) : raw;
    return raw2.split('|').map(c => c.trim());
  }

  function isTableSep(line) {
    const trimmed = line.trim();
    if (!trimmed.includes('|')) return false;
    const cells = splitTableRow(trimmed);
    if (!cells || !cells.length) return false;
    return cells.every(c => /^:?-{3,}:?$/.test(c));
  }

  function startsBlock(line) {
    if (!line) return false;
    if (isFence(line)) return true;
    if (isHeading(line)) return true;
    if (isHr(line)) return true;
    if (isUlItem(line) || isOlItem(line)) return true;
    return false;
  }

  function parseMarkdownToFragment(markdown) {
    const text = String(markdown ?? '').replace(/\r\n/g, '\n');
    const lines = text.split('\n');
    const frag = document.createDocumentFragment();
    let i = 0;

    while (i < lines.length) {
      const line = lines[i];
      if (!line.trim()) {
        i += 1;
        continue;
      }

      const fence = isFence(line);
      if (fence) {
        const lang = fence.lang;
        i += 1;
        const codeLines = [];
        while (i < lines.length && !isFence(lines[i])) {
          codeLines.push(lines[i]);
          i += 1;
        }
        if (i < lines.length && isFence(lines[i])) i += 1;
        const pre = document.createElement('pre');
        const code = document.createElement('code');
        if (lang) code.className = `language-${lang}`;
        code.textContent = codeLines.join('\n');
        pre.appendChild(code);
        frag.appendChild(pre);
        continue;
      }

      const heading = isHeading(line);
      if (heading) {
        const el = document.createElement(`h${heading.level}`);
        appendInline(el, heading.text);
        frag.appendChild(el);
        i += 1;
        continue;
      }

      if (isHr(line)) {
        frag.appendChild(document.createElement('hr'));
        i += 1;
        continue;
      }

      // Table (GFM-ish)
      const headerCells = splitTableRow(line);
      if (headerCells && i + 1 < lines.length && isTableSep(lines[i + 1])) {
        i += 2; // skip header + sep
        const table = document.createElement('table');
        const thead = document.createElement('thead');
        const trh = document.createElement('tr');
        for (const cell of headerCells) {
          const th = document.createElement('th');
          appendInline(th, cell);
          trh.appendChild(th);
        }
        thead.appendChild(trh);
        table.appendChild(thead);
        const tbody = document.createElement('tbody');
        while (i < lines.length) {
          const rowLine = lines[i];
          if (!rowLine.trim()) break;
          const rowCells = splitTableRow(rowLine);
          if (!rowCells) break;
          const tr = document.createElement('tr');
          for (let c = 0; c < headerCells.length; c++) {
            const td = document.createElement('td');
            appendInline(td, rowCells[c] ?? '');
            tr.appendChild(td);
          }
          tbody.appendChild(tr);
          i += 1;
        }
        table.appendChild(tbody);
        frag.appendChild(table);
        continue;
      }

      const ul = isUlItem(line);
      const ol = isOlItem(line);
      if (ul || ol) {
        const listEl = document.createElement(ul ? 'ul' : 'ol');
        while (i < lines.length) {
          const l = lines[i];
          const item = ul ? isUlItem(l) : isOlItem(l);
          if (!item) break;
          const li = document.createElement('li');
          appendInline(li, item.text);
          listEl.appendChild(li);
          i += 1;
        }
        frag.appendChild(listEl);
        continue;
      }

      // Paragraph (merge consecutive non-block lines)
      const paraLines = [line.trim()];
      i += 1;
      while (i < lines.length && lines[i].trim() && !startsBlock(lines[i])) {
        // keep explicit line breaks as spaces for paragraph flow
        paraLines.push(lines[i].trim());
        i += 1;
      }
      const p = document.createElement('p');
      appendInline(p, paraLines.join(' '));
      frag.appendChild(p);
    }

    return frag;
  }

  function renderPlainInto(el, text) {
    el.innerHTML = '';
    el.classList.remove('md');
    el.classList.add('whitespace-pre-wrap', 'break-words');
    el.textContent = String(text ?? '');
  }

  function renderMarkdownInto(el, markdown) {
    try {
      el.innerHTML = '';
      el.classList.add('md');
      el.classList.remove('whitespace-pre-wrap');
      const frag = parseMarkdownToFragment(markdown);
      el.appendChild(frag);
    } catch (e) {
      renderPlainInto(el, markdown);
    }
  }

  window.Markdown = {
    renderMarkdownInto,
    renderPlainInto,
    parseMarkdownToFragment,
  };
})();

