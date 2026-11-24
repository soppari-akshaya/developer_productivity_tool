/**
 * Developer Productivity Tool Assistant Controller
 * Clean, professional chatbot UI controller.
 * Never displays internal provider names to the user.
 */
document.addEventListener('DOMContentLoaded', () => {
  const launcherBtn = document.getElementById('grok-launcher-btn');
  const chatPanel = document.getElementById('grok-chat-panel');
  const closeBtn = document.getElementById('grok-close-btn');
  const clearBtn = document.getElementById('grok-clear-btn');
  const confirmClearBtn = document.getElementById('grok-confirm-clear-btn');

  const messagesContainer = document.getElementById('grok-messages-container');
  const typingIndicator = document.getElementById('grok-typing-indicator');
  const inputTextarea = document.getElementById('grok-input-textarea');
  const sendBtn = document.getElementById('grok-send-btn');

  if (!launcherBtn || !chatPanel) return;

  let historyLoaded = false;

  const DEFAULT_WELCOME_HTML = `
    <div class="grok-message-row grok-msg-assistant">
      <div class="grok-msg-avatar">
        <i class="fa-solid fa-wand-magic-sparkles"></i>
      </div>
      <div class="grok-msg-bubble">
        <div class="grok-msg-text">
          <p class="fw-bold mb-2" style="font-size: 0.90rem;">Hello! Welcome to Developer Productivity Tool Assistant.</p>
          <p class="mb-2">I'm here to help you understand the application, learn how to manage projects and tasks, understand bugs, and improve your productivity.</p>
          <p class="mb-0">Ask me anything, and I'll provide explanations, examples, and step-by-step guidance.</p>
        </div>
        <span class="grok-msg-time">Just now</span>
      </div>
    </div>
  `;

  function getCsrfToken() {
    return document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
  }

  // Escape HTML to prevent injection
  function escapeHtml(str) {
    if (!str) return '';
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // Robust Markdown parser for Assistant responses
  function formatMarkdown(text) {
    if (!text) return '';

    const codeBlocks = [];
    let processed = text.replace(/```([a-zA-Z0-9_\-\.]*)\n?([\s\S]*?)```/g, (match, lang, code) => {
      const idx = codeBlocks.length;
      codeBlocks.push({ lang: lang || 'code', code: code.trim() });
      return `%%%AI_CODE_BLOCK_${idx}%%%`;
    });

    processed = escapeHtml(processed);

    // Headers
    processed = processed.replace(/^#### (.*$)/gim, '<h6 class="fw-bold mt-2 mb-1" style="font-size: 0.86rem;">$1</h6>');
    processed = processed.replace(/^### (.*$)/gim, '<h6 class="fw-bold mt-2.5 mb-1" style="font-size: 0.92rem;">$1</h6>');
    processed = processed.replace(/^## (.*$)/gim, '<h5 class="fw-bold mt-2.5 mb-1" style="font-size: 0.98rem;">$1</h5>');

    // Bold & Italic
    processed = processed.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    processed = processed.replace(/\*(.*?)\*/g, '<em>$1</em>');

    // Inline code
    processed = processed.replace(/`([^`]+)`/g, '<code>$1</code>');

    // Checklists & Bullet lists
    processed = processed.replace(/^\s*[\-\*]\s+\[ \]\s+(.*$)/gim, '<li class="list-unstyled"><i class="fa-regular fa-square me-1 text-muted"></i> $1</li>');
    processed = processed.replace(/^\s*[\-\*]\s+\[x\]\s+(.*$)/gim, '<li class="list-unstyled"><i class="fa-solid fa-square-check me-1 text-success"></i> $1</li>');
    processed = processed.replace(/^\s*[\-\*]\s+(.*$)/gim, '<li>$1</li>');
    processed = processed.replace(/(<li>.*<\/li>)/gims, '<ul class="mb-2 ps-3">$1</ul>');

    // Numbered lists
    processed = processed.replace(/^\s*(\d+)\.\s+(.*$)/gim, '<li>$2</li>');

    // Line breaks
    processed = processed.replace(/\n\n+/g, '<p class="mb-2"></p>');
    processed = processed.replace(/\n/g, '<br>');

    // Restore Code Blocks with copy buttons
    processed = processed.replace(/%%%AI_CODE_BLOCK_(\d+)%%%/g, (match, idx) => {
      const block = codeBlocks[parseInt(idx, 10)];
      if (!block) return '';
      const safeCode = escapeHtml(block.code);
      return `<div class="position-relative my-2">
        <button class="grok-copy-block-btn" type="button" onclick="navigator.clipboard.writeText(this.nextElementSibling.innerText); this.innerText='Copied!'; setTimeout(() => this.innerText='Copy', 2000);">Copy</button>
        <pre><code class="language-${escapeHtml(block.lang)}">${safeCode}</code></pre>
      </div>`;
    });

    return processed;
  }

  function scrollToBottom() {
    setTimeout(() => {
      if (messagesContainer) {
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
      }
    }, 50);
  }

  // Toggle Panel
  function openPanel() {
    chatPanel.style.display = 'flex';
    launcherBtn.classList.add('active');
    if (!historyLoaded) {
      loadHistory();
    } else {
      setTimeout(() => {
        inputTextarea?.focus();
        scrollToBottom();
      }, 50);
    }
  }

  function closePanel() {
    chatPanel.style.display = 'none';
    launcherBtn.classList.remove('active');
  }

  launcherBtn.addEventListener('click', () => {
    if (chatPanel.style.display === 'none' || !chatPanel.style.display) {
      openPanel();
    } else {
      closePanel();
    }
  });

  closeBtn?.addEventListener('click', closePanel);

  // Auto-resize textarea
  inputTextarea?.addEventListener('input', () => {
    inputTextarea.style.height = 'auto';
    inputTextarea.style.height = Math.min(inputTextarea.scrollHeight, 110) + 'px';
  });

  // Enter to send, Shift+Enter for newline
  inputTextarea?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  });

  sendBtn?.addEventListener('click', (e) => {
    e.preventDefault();
    handleSend();
  });

  function appendUserMessage(text) {
    const row = document.createElement('div');
    row.className = 'grok-message-row grok-msg-user';
    row.innerHTML = `
      <div class="grok-msg-bubble">
        <div class="grok-msg-text">${escapeHtml(text).replace(/\n/g, '<br>')}</div>
        <span class="grok-msg-time">Just now</span>
      </div>
    `;
    messagesContainer.appendChild(row);
    scrollToBottom();
  }

  function appendAssistantMessage(rawText, addCopyAll = true) {
    const row = document.createElement('div');
    row.className = 'grok-message-row grok-msg-assistant';
    
    let copyBtnHtml = '';
    if (addCopyAll) {
      copyBtnHtml = `<div class="d-flex justify-content-end mt-1">
        <button type="button" class="btn btn-sm btn-link p-0 text-muted" style="font-size: 0.68rem; text-decoration: none;" onclick="navigator.clipboard.writeText(this.closest('.grok-msg-bubble').querySelector('.grok-msg-text').innerText); this.innerHTML='<i class=\\'fa-solid fa-check text-success me-1\\'></i>Copied!'; setTimeout(() => this.innerHTML='<i class=\\'fa-regular fa-copy me-1\\'></i>Copy', 2000);">
          <i class="fa-regular fa-copy me-1"></i>Copy
        </button>
      </div>`;
    }

    row.innerHTML = `
      <div class="grok-msg-avatar">
        <i class="fa-solid fa-wand-magic-sparkles"></i>
      </div>
      <div class="grok-msg-bubble">
        <div class="grok-msg-text">${formatMarkdown(rawText)}</div>
        ${copyBtnHtml}
        <span class="grok-msg-time">Just now</span>
      </div>
    `;
    messagesContainer.appendChild(row);
    scrollToBottom();
  }

  function appendErrorMessage(errText, isConfig = false) {
    const row = document.createElement('div');
    row.className = 'grok-message-row grok-msg-assistant';
    const icon = isConfig ? 'fa-triangle-exclamation' : 'fa-circle-exclamation';
    row.innerHTML = `
      <div class="grok-msg-avatar" style="background: #dc2626;">
        <i class="fa-solid ${icon}"></i>
      </div>
      <div class="grok-msg-bubble">
        <div class="grok-error-banner mb-1">
          <i class="fa-solid ${icon} mt-0.5"></i>
          <div>${escapeHtml(errText)}</div>
        </div>
        <span class="grok-msg-time">Error</span>
      </div>
    `;
    messagesContainer.appendChild(row);
    scrollToBottom();
  }

  function setLoading(loading) {
    if (loading) {
      typingIndicator.style.display = 'block';
      sendBtn.disabled = true;
      scrollToBottom();
    } else {
      typingIndicator.style.display = 'none';
      sendBtn.disabled = false;
    }
  }

  // Load History
  async function loadHistory() {
    try {
      const res = await fetch('/ai/history');
      const data = await res.json();
      if (data.success && data.messages && data.messages.length > 0) {
        messagesContainer.innerHTML = '';
        data.messages.forEach(msg => {
          if (msg.role === 'user') {
            appendUserMessage(msg.content);
          } else {
            appendAssistantMessage(msg.content);
          }
        });
      } else {
        messagesContainer.innerHTML = DEFAULT_WELCOME_HTML;
      }
      historyLoaded = true;
    } catch (e) {
      console.warn('Could not load chat history:', e);
      messagesContainer.innerHTML = DEFAULT_WELCOME_HTML;
      historyLoaded = true;
    }
    setTimeout(() => {
      inputTextarea?.focus();
      scrollToBottom();
    }, 50);
  }

  // Chat submit
  async function handleSend() {
    const text = (inputTextarea.value || '').trim();
    if (!text) return;

    inputTextarea.value = '';
    inputTextarea.style.height = 'auto';

    appendUserMessage(text);
    setLoading(true);

    try {
      const res = await fetch('/ai/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify({ message: text })
      });

      const data = await res.json();
      setLoading(false);

      if (data.success && data.reply) {
        appendAssistantMessage(data.reply);
      } else {
        appendErrorMessage(data.error || 'Failed to receive response from the Assistant.', data.is_config_error);
      }
    } catch (e) {
      setLoading(false);
      appendErrorMessage('Connection error: could not contact server.');
    }
  }

  // Clear conversation history
  clearBtn?.addEventListener('click', () => {
    const modalEl = document.getElementById('grokClearConfirmModal');
    if (modalEl && window.bootstrap) {
      const modal = new bootstrap.Modal(modalEl);
      modal.show();
    }
  });

  confirmClearBtn?.addEventListener('click', async () => {
    try {
      const res = await fetch('/ai/clear-history', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken()
        }
      });
      const data = await res.json();
      const modalEl = document.getElementById('grokClearConfirmModal');
      if (modalEl && window.bootstrap) {
        const modal = bootstrap.Modal.getInstance(modalEl);
        modal?.hide();
      }

      if (data.success) {
        messagesContainer.innerHTML = DEFAULT_WELCOME_HTML;
        scrollToBottom();
      }
    } catch (e) {
      alert('Failed to clear conversation history.');
    }
  });
});
