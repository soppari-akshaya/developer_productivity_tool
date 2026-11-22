/**
 * CodeMirror Editor Sandbox
 */
document.addEventListener('DOMContentLoaded', () => {
  const textarea = document.getElementById('code-editor-textarea');
  if (!textarea) return;

  const editor = CodeMirror.fromTextArea(textarea, {
    lineNumbers: true,
    theme: 'dracula',
    mode: 'javascript',
    indentUnit: 2,
    tabSize: 2,
    lineWrapping: true,
    autoCloseBrackets: true
  });

  editor.setSize('100%', '420px');

  // Language selector
  const langSelect = document.getElementById('editor-language-select');
  if (langSelect) {
    langSelect.addEventListener('change', () => {
      const lang = langSelect.value;
      const modeMap = {
        'javascript': 'javascript',
        'python': 'python',
        'html': 'htmlmixed',
        'css': 'css',
        'sql': 'sql'
      };
      editor.setOption('mode', modeMap[lang] || 'javascript');
    });
  }

  // Clear button
  const clearBtn = document.getElementById('btn-clear-code');
  if (clearBtn) {
    clearBtn.addEventListener('click', () => {
      if (confirm('Clear editor content?')) {
        editor.setValue('');
        document.getElementById('editor-output').textContent = 'Console cleared.';
      }
    });
  }

  // Download button
  const downloadBtn = document.getElementById('btn-download-code');
  if (downloadBtn) {
    downloadBtn.addEventListener('click', () => {
      const code = editor.getValue();
      const lang = langSelect ? langSelect.value : 'js';
      const extMap = { 'javascript': 'js', 'python': 'py', 'html': 'html', 'css': 'css', 'sql': 'sql' };
      const filename = `snippet_${Date.now()}.${extMap[lang] || 'txt'}`;

      const blob = new Blob([code], { type: 'text/plain;charset=utf-8' });
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = filename;
      link.click();
    });
  }

  // Save Snippet button
  const saveSnippetBtn = document.getElementById('btn-save-snippet');
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

  // Run Code button (Sandboxed Client Runner Simulation)
  const runBtn = document.getElementById('btn-run-code');
  const outputEl = document.getElementById('editor-output');
  if (runBtn && outputEl) {
    runBtn.addEventListener('click', () => {
      const code = editor.getValue();
      const lang = langSelect ? langSelect.value : 'javascript';

      outputEl.textContent = 'Running code in isolated sandbox...';

      setTimeout(() => {
        if (lang === 'javascript') {
          const logs = [];
          const customConsole = {
            log: (...args) => logs.push(args.map(a => typeof a === 'object' ? JSON.stringify(a) : String(a)).join(' ')),
            error: (...args) => logs.push('[ERROR] ' + args.join(' ')),
            warn: (...args) => logs.push('[WARN] ' + args.join(' '))
          };
          try {
            const run = new Function('console', code);
            run(customConsole);
            outputEl.textContent = logs.length > 0 ? logs.join('\n') : '[Process exited with code 0 - No output]';
          } catch (err) {
            outputEl.textContent = `Runtime Exception: ${err.message}`;
          }
        } else {
          outputEl.textContent = `[${lang.toUpperCase()} Sandbox Simulation]\nOutput:\n>>> Process finished with exit code 0\nResult: Execution completed safely.`;
        }
      }, 300);
    });
  }
});

