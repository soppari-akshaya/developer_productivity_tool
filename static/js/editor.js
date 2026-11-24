/**
 * CodeMirror Online Code Editor Controller
 * Supports real execution for JavaScript, Python, HTML, CSS, and SQL.
 */
document.addEventListener('DOMContentLoaded', () => {
  const textarea = document.getElementById('code-editor-textarea');
  if (!textarea) return;

  function getCsrfToken() {
    return document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
  }

  // Initial code snippets per language
  const starterCode = {
    javascript: `console.log("Hello from JavaScript");\nconsole.log(10 + 20);`,
    python: `print("Hello from Python")\nprint(10 + 20)`,
    html: `<h1>Hello World</h1>\n<p>HTML is working successfully.</p>`,
    css: `h1 {\n  color: #2563eb;\n  font-family: system-ui, sans-serif;\n}\n\np {\n  color: #475569;\n  font-size: 16px;\n}\n\n.box {\n  background: #f1f5f9;\n  border: 1px solid #cbd5e1;\n  border-radius: 8px;\n  padding: 15px;\n}`,
    sql: `CREATE TABLE test_users (\n    id INTEGER,\n    name TEXT\n);\n\nINSERT INTO test_users VALUES (1, 'Akshaya');\nINSERT INTO test_users VALUES (2, 'Developer');\n\nSELECT * FROM test_users;`
  };

  const editor = CodeMirror.fromTextArea(textarea, {
    lineNumbers: true,
    theme: 'dracula',
    mode: 'javascript',
    indentUnit: 2,
    tabSize: 2,
    lineWrapping: true,
    autoCloseBrackets: true
  });

  editor.setSize('100%', '380px');
  editor.setValue(starterCode.javascript);

  const langSelect = document.getElementById('editor-language-select');
  const runBtn = document.getElementById('btn-run-code');
  const clearBtn = document.getElementById('btn-clear-code');
  const downloadBtn = document.getElementById('btn-download-code');
  const saveSnippetBtn = document.getElementById('btn-save-snippet');
  const resetSqlBtn = document.getElementById('btn-reset-sql');

  const outputEl = document.getElementById('editor-output');
  const statusBadge = document.getElementById('execution-status-badge');
  const outputTableContainer = document.getElementById('editor-output-table');
  const previewContainer = document.getElementById('editor-preview-container');
  const previewFrame = document.getElementById('editor-preview-frame');

  // Track previous selected language to offer starter code on switch if clean
  let prevLang = 'javascript';

  // Language selector change handler
  if (langSelect) {
    langSelect.addEventListener('change', () => {
      const lang = langSelect.value;
      const modeMap = {
        'javascript': 'javascript',
        'python': 'python',
        'html': 'text/html',
        'css': 'css',
        'sql': 'text/x-sql'
      };
      editor.setOption('mode', modeMap[lang] || 'javascript');

      // Show/hide SQL reset button
      if (resetSqlBtn) {
        if (lang === 'sql') {
          resetSqlBtn.classList.remove('d-none');
        } else {
          resetSqlBtn.classList.add('d-none');
        }
      }

      // If current editor content matches previous language's starter code or is empty, switch to new starter code
      const currentVal = editor.getValue().trim();
      if (!currentVal || currentVal === (starterCode[prevLang] || '').trim()) {
        editor.setValue(starterCode[lang] || '');
      }
      prevLang = lang;

      // Reset output display
      clearOutputs();
      if (outputEl) {
        outputEl.textContent = `Switched to ${lang.toUpperCase()}. Click "Run Code" above to execute.`;
        outputEl.style.color = 'var(--text-primary)';
      }
      if (statusBadge) {
        statusBadge.className = 'badge bg-secondary bg-opacity-20 text-muted';
        statusBadge.textContent = 'Ready';
      }
    });
  }

  function clearOutputs() {
    if (outputTableContainer) {
      outputTableContainer.innerHTML = '';
      outputTableContainer.classList.add('d-none');
    }
    if (previewContainer) {
      previewContainer.classList.add('d-none');
    }
    if (previewFrame) {
      previewFrame.srcdoc = '';
    }
  }

  // Clear button
  if (clearBtn) {
    clearBtn.addEventListener('click', () => {
      if (confirm('Clear editor content?')) {
        editor.setValue('');
        clearOutputs();
        if (outputEl) {
          outputEl.textContent = 'Console and editor cleared.';
          outputEl.style.color = 'var(--text-primary)';
        }
        if (statusBadge) {
          statusBadge.className = 'badge bg-secondary bg-opacity-20 text-muted';
          statusBadge.textContent = 'Idle';
        }
      }
    });
  }

  // Download button
  if (downloadBtn) {
    downloadBtn.addEventListener('click', () => {
      const code = editor.getValue();
      const lang = langSelect ? langSelect.value : 'js';
      const extMap = { 'javascript': 'js', 'python': 'py', 'html': 'html', 'css': 'css', 'sql': 'sql' };
      const filename = `code_${Date.now()}.${extMap[lang] || 'txt'}`;

      const blob = new Blob([code], { type: 'text/plain;charset=utf-8' });
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = filename;
      link.click();
    });
  }

  // Save Snippet button
  if (saveSnippetBtn) {
    saveSnippetBtn.addEventListener('click', () => {
      const code = editor.getValue().trim();
      const lang = langSelect ? langSelect.value : 'javascript';
      if (!code) {
        alert('Please write or paste some code before saving as a snippet.');
        return;
      }
      const targetUrl = `/snippets/create?lang=${encodeURIComponent(lang)}&code=${encodeURIComponent(code)}`;
      window.location.href = targetUrl;
    });
  }

  // Reset SQL Database button
  if (resetSqlBtn) {
    resetSqlBtn.addEventListener('click', async () => {
      if (!confirm('Reset your scratch SQL database? Any previously created tables will be cleared.')) return;
      try {
        const response = await fetch('/api/editor/reset-sql', {
          method: 'POST',
          headers: {
            'Accept': 'application/json',
            'X-CSRFToken': getCsrfToken()
          }
        });
        const data = await response.json();
        alert(data.message || 'Scratch SQL database reset.');
        clearOutputs();
        if (outputEl) outputEl.textContent = 'Scratch SQL database has been reset to empty state.';
      } catch (err) {
        alert('Failed to reset scratch SQL database.');
      }
    });
  }

  // Client-side JavaScript execution fallback (with captured console and errors)
  function runJavaScriptInClient(code) {
    const logs = [];
    const customConsole = {
      log: (...args) => logs.push(args.map(a => typeof a === 'object' ? JSON.stringify(a) : String(a)).join(' ')),
      info: (...args) => logs.push('[INFO] ' + args.map(a => typeof a === 'object' ? JSON.stringify(a) : String(a)).join(' ')),
      warn: (...args) => logs.push('[WARN] ' + args.map(a => typeof a === 'object' ? JSON.stringify(a) : String(a)).join(' ')),
      error: (...args) => logs.push('[ERROR] ' + args.map(a => typeof a === 'object' ? JSON.stringify(a) : String(a)).join(' '))
    };
    try {
      const runner = new Function('console', code);
      runner(customConsole);
      return {
        status: 'success',
        output: logs.length > 0 ? logs.join('\n') : '[Process finished with code 0 - No output]'
      };
    } catch (err) {
      return {
        status: 'error',
        output: `${err.name}: ${err.message}`
      };
    }
  }

  // Build clean HTML table from SQL query results
  function renderSqlTables(tables) {
    if (!outputTableContainer || !tables || tables.length === 0) return;
    outputTableContainer.innerHTML = '';

    tables.forEach((tbl, idx) => {
      const wrapper = document.createElement('div');
      wrapper.className = 'table-responsive mb-2';

      const table = document.createElement('table');
      table.className = 'table table-sm table-bordered table-hover align-middle mb-1';
      table.style.fontSize = '0.82rem';

      // Header
      const thead = document.createElement('thead');
      thead.className = 'table-dark';
      const trHead = document.createElement('tr');
      tbl.columns.forEach(col => {
        const th = document.createElement('th');
        th.textContent = col;
        trHead.appendChild(th);
      });
      thead.appendChild(trHead);
      table.appendChild(thead);

      // Body
      const tbody = document.createElement('tbody');
      if (tbl.rows.length === 0) {
        const trEmpty = document.createElement('tr');
        const tdEmpty = document.createElement('td');
        tdEmpty.colSpan = tbl.columns.length || 1;
        tdEmpty.className = 'text-center text-muted py-2';
        tdEmpty.textContent = 'Empty set (0 rows)';
        trEmpty.appendChild(tdEmpty);
        tbody.appendChild(trEmpty);
      } else {
        tbl.rows.forEach(row => {
          const tr = document.createElement('tr');
          row.forEach(val => {
            const td = document.createElement('td');
            td.textContent = val !== null && val !== undefined ? String(val) : 'NULL';
            if (val === null) td.className = 'text-muted fst-italic';
            tr.appendChild(td);
          });
          tbody.appendChild(tr);
        });
      }
      table.appendChild(tbody);
      wrapper.appendChild(table);
      outputTableContainer.appendChild(wrapper);
    });

    outputTableContainer.classList.remove('d-none');
  }

  // Run Code button execution handler
  if (runBtn) {
    runBtn.addEventListener('click', async () => {
      const lang = langSelect ? langSelect.value : 'javascript';
      const code = editor.getValue();

      if (!code.trim()) {
        clearOutputs();
        if (outputEl) {
          outputEl.textContent = 'Please enter code before clicking Run Code.';
          outputEl.style.color = '#ef4444';
        }
        if (statusBadge) {
          statusBadge.className = 'badge bg-warning bg-opacity-20 text-warning';
          statusBadge.textContent = 'Empty Code';
        }
        return;
      }

      // Show Running state
      runBtn.disabled = true;
      runBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin me-1"></i> Running...';
      clearOutputs();

      if (outputEl) {
        outputEl.textContent = `Executing ${lang.toUpperCase()} code...`;
        outputEl.style.color = 'var(--text-primary)';
      }
      if (statusBadge) {
        statusBadge.className = 'badge bg-warning bg-opacity-20 text-warning';
        statusBadge.textContent = 'Executing...';
      }

      try {
        if (lang === 'html') {
          // Render HTML directly in safe sandboxed preview frame
          if (previewFrame && previewContainer) {
            previewFrame.srcdoc = `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body { font-family: system-ui, -apple-system, sans-serif; padding: 15px; margin: 0; color: #1e293b; background: #ffffff; }
  </style>
</head>
<body>
  ${code}
</body>
</html>`;
            previewContainer.classList.remove('d-none');
          }
          if (outputEl) {
            outputEl.textContent = 'HTML rendered successfully in the preview area below.';
            outputEl.style.color = '#10b981';
          }
          if (statusBadge) {
            statusBadge.className = 'badge bg-success bg-opacity-20 text-success';
            statusBadge.textContent = 'Rendered';
          }
        } else if (lang === 'css') {
          // Apply CSS to a dedicated preview document
          if (previewFrame && previewContainer) {
            previewFrame.srcdoc = `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    ${code}
  </style>
</head>
<body>
  <div class="preview-doc" style="padding: 15px; font-family: system-ui, sans-serif;">
    <h1>Sample Heading (h1)</h1>
    <h2>Subheading (h2)</h2>
    <p>This paragraph demonstrates your custom CSS styles, fonts, margins, line heights, and colors.</p>
    <button class="btn btn-primary" type="button" style="padding: 6px 12px; cursor: pointer;">Sample Button</button>
    <div class="box" style="margin-top: 15px; padding: 15px;">
      <strong>Sample Container (.box)</strong>
      <p style="margin: 5px 0 0 0;">Inspect your borders, padding, shadows, and background colors here.</p>
    </div>
  </div>
</body>
</html>`;
            previewContainer.classList.remove('d-none');
          }
          if (outputEl) {
            outputEl.textContent = 'CSS styles applied to the preview document below.';
            outputEl.style.color = '#10b981';
          }
          if (statusBadge) {
            statusBadge.className = 'badge bg-success bg-opacity-20 text-success';
            statusBadge.textContent = 'Rendered';
          }
        } else {
          // Backend execution for Python, JavaScript, and SQL
          const response = await fetch('/api/editor/execute', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Accept': 'application/json',
              'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify({ language: lang, code: code })
          });

          const data = await response.json();

          // Check if fallback needed for JS (e.g. if Node wasn't installed on server)
          if (lang === 'javascript' && data.fallback_to_client) {
            const clientRes = runJavaScriptInClient(code);
            if (outputEl) {
              outputEl.textContent = clientRes.output;
              outputEl.style.color = clientRes.status === 'success' ? 'var(--text-primary)' : '#ef4444';
            }
            if (statusBadge) {
              statusBadge.className = clientRes.status === 'success'
                ? 'badge bg-success bg-opacity-20 text-success'
                : 'badge bg-danger bg-opacity-20 text-danger';
              statusBadge.textContent = clientRes.status === 'success' ? 'Completed' : 'Error';
            }
          } else {
            // Server execution results
            if (outputEl) {
              outputEl.textContent = data.output || '[Process finished with code 0 - No output]';
              outputEl.style.color = data.status === 'success' ? 'var(--text-primary)' : '#ef4444';
            }

            // If SQL query returned tables, render HTML table
            if (lang === 'sql' && data.tables && data.tables.length > 0) {
              renderSqlTables(data.tables);
            }

            if (statusBadge) {
              if (data.status === 'success') {
                const timeStr = data.execution_time !== undefined ? ` (${data.execution_time}s)` : '';
                statusBadge.className = 'badge bg-success bg-opacity-20 text-success';
                statusBadge.textContent = `Completed${timeStr}`;
              } else {
                statusBadge.className = 'badge bg-danger bg-opacity-20 text-danger';
                statusBadge.textContent = data.timeout ? 'Timeout' : 'Error';
              }
            }
          }
        }
      } catch (err) {
        if (outputEl) {
          outputEl.textContent = `Network / Execution Error: ${err.message}`;
          outputEl.style.color = '#ef4444';
        }
        if (statusBadge) {
          statusBadge.className = 'badge bg-danger bg-opacity-20 text-danger';
          statusBadge.textContent = 'Failed';
        }
      } finally {
        runBtn.disabled = false;
        runBtn.innerHTML = '<i class="fa-solid fa-play me-1"></i> Run Code';
      }
    });
  }
});
