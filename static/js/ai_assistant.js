/**
 * Developer Productivity Tool Assistant Controller
 * Vanilla JavaScript interface for all 11 AI capabilities.
 * Never displays internal provider names to the user.
 */
document.addEventListener('DOMContentLoaded', () => {
  const launcherBtn = document.getElementById('grok-launcher-btn');
  const chatPanel = document.getElementById('grok-chat-panel');
  const closeBtn = document.getElementById('grok-close-btn');
  const clearBtn = document.getElementById('grok-clear-btn');
  const hubBtn = document.getElementById('grok-hub-btn');
  const footerHubLink = document.getElementById('grok-footer-hub-link');
  const confirmClearBtn = document.getElementById('grok-confirm-clear-btn');

  const welcomeView = document.getElementById('grok-welcome-view');
  const chatView = document.getElementById('grok-chat-view');

  const messagesContainer = document.getElementById('grok-messages-container');
  const typingIndicator = document.getElementById('grok-typing-indicator');
  const chatForm = document.getElementById('grok-chat-form');
  const inputTextarea = document.getElementById('grok-input-textarea');
  const sendBtn = document.getElementById('grok-send-btn');

  const actionCard = document.getElementById('grok-action-card');
  const actionTitle = document.getElementById('grok-action-title');
  const actionBody = document.getElementById('grok-action-body');
  const actionCancel = document.getElementById('grok-action-cancel');

  if (!launcherBtn || !chatPanel) return;

  let historyLoaded = false;
  let authorizedProjects = [];
  let userHasMessages = false;

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

  // Switch between Feature Cards Hub and Chat View
  function showWelcomeView() {
    welcomeView.style.display = 'flex';
    chatView.style.display = 'none';
    hubBtn.classList.add('active');
  }

  function showChatView() {
    welcomeView.style.display = 'none';
    chatView.style.display = 'flex';
    hubBtn.classList.remove('active');
    setTimeout(() => {
      inputTextarea?.focus();
      scrollToBottom();
    }, 50);
  }

  hubBtn?.addEventListener('click', () => {
    if (welcomeView.style.display === 'none') {
      showWelcomeView();
    } else {
      showChatView();
    }
  });

  footerHubLink?.addEventListener('click', (e) => {
    e.preventDefault();
    showWelcomeView();
  });

  // Toggle Panel
  function openPanel() {
    chatPanel.style.display = 'flex';
    launcherBtn.classList.add('active');
    if (!historyLoaded) {
      loadHistory();
      loadProjects();
    } else {
      if (!userHasMessages) {
        showWelcomeView();
      } else {
        showChatView();
      }
    }
  }

  function closePanel() {
    chatPanel.style.display = 'none';
    launcherBtn.classList.remove('active');
    hideActionCard();
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
    userHasMessages = true;
    showChatView();
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
    userHasMessages = true;
    showChatView();
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
    showChatView();
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
        userHasMessages = true;
        showChatView();
      } else {
        userHasMessages = false;
        showWelcomeView();
      }
      historyLoaded = true;
    } catch (e) {
      console.warn('Could not load chat history:', e);
      showWelcomeView();
    }
  }

  // Load Authorized Projects
  async function loadProjects() {
    try {
      const res = await fetch('/ai/projects');
      const data = await res.json();
      if (data.success && data.projects) {
        authorizedProjects = data.projects;
      }
    } catch (e) {
      console.warn('Could not load authorized projects:', e);
    }
  }

  // General chat submit
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
        userHasMessages = false;
        messagesContainer.innerHTML = `
          <div class="grok-message-row grok-msg-assistant">
            <div class="grok-msg-avatar"><i class="fa-solid fa-wand-magic-sparkles"></i></div>
            <div class="grok-msg-bubble">
              <div class="grok-msg-text">
                <strong>Welcome to Developer Productivity Tool Assistant!</strong>
                <p class="mb-0 mt-1">How can I help you today? I can help you manage projects, create tasks, generate reports, track bugs, and improve your productivity.</p>
              </div>
              <span class="grok-msg-time">Just now</span>
            </div>
          </div>
        `;
        showWelcomeView();
      }
    } catch (e) {
      alert('Failed to clear conversation history.');
    }
  });

  // Action Form Popover Logic
  function hideActionCard() {
    if (actionCard) {
      actionCard.style.display = 'none';
      actionBody.innerHTML = '';
    }
  }

  actionCancel?.addEventListener('click', hideActionCard);

  // Bind clicks for Feature Cards & Quick Action Chips
  document.querySelectorAll('.grok-feature-card, .grok-chip').forEach(el => {
    el.addEventListener('click', () => {
      const action = el.getAttribute('data-action');
      openActionFlow(action);
    });
  });

  function getProjectOptionsHtml() {
    return authorizedProjects.length > 0
      ? authorizedProjects.map(p => `<option value="${p.id}">${escapeHtml(p.name)} (${p.status}, ${p.progress}%)</option>`).join('')
      : '<option value="">No projects found</option>';
  }

  function openActionFlow(action) {
    showChatView();
    if (!actionCard) return;
    actionCard.style.display = 'block';

    const projectOptions = getProjectOptionsHtml();

    // 1. Create a Project Guidance
    if (action === 'create-project') {
      appendUserMessage("How do I create a project in the platform?");
      setLoading(true);

      fetch('/ai/create-project', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
        body: JSON.stringify({ details: '' })
      })
      .then(res => res.json())
      .then(data => {
        setLoading(false);
        if (data.success) {
          appendAssistantMessage(data.reply);
        } else {
          appendErrorMessage(data.error || 'Failed to load project guidance.');
        }
      })
      .catch(e => {
        setLoading(false);
        appendErrorMessage('Error loading project creation guidance.');
      });

      actionTitle.innerText = 'Create Project - Guidance & Review';
      actionBody.innerHTML = `
        <div class="alert alert-info py-2 px-3 mb-2" style="font-size: 0.75rem; border-radius: 6px;">
          <i class="fa-solid fa-circle-info me-1"></i> The AI Assistant does not insert or save projects to the database. Use the guidance provided in chat, then create your project in the Project Management module.
        </div>
        <a href="/projects/create" class="btn btn-sm btn-primary w-100 mb-2">
          <i class="fa-solid fa-arrow-up-right-from-square me-1"></i> Go to Project Management (/projects/create)
        </a>
        <div class="border-top pt-2 mt-2">
          <label class="form-label text-muted mb-1" style="font-size: 0.72rem;">
            <i class="fa-solid fa-lightbulb text-warning me-1"></i>Have a draft project idea? Get AI feedback & review:
          </label>
          <textarea id="grok-p-draft" class="form-control form-control-sm mb-2" rows="2" placeholder="Enter your draft project details here to check for missing information..."></textarea>
          <button type="button" id="grok-btn-review-p" class="btn btn-sm btn-outline-primary w-100">
            <i class="fa-solid fa-wand-magic-sparkles me-1"></i> Review Draft with AI
          </button>
        </div>
      `;

      document.getElementById('grok-btn-review-p')?.addEventListener('click', async () => {
        const draft = document.getElementById('grok-p-draft')?.value?.trim();
        if (!draft) {
          alert('Please enter your draft project details.');
          return;
        }
        hideActionCard();
        appendUserMessage(`Review Project Draft: ${draft}`);
        setLoading(true);

        try {
          const res = await fetch('/ai/create-project', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
            body: JSON.stringify({ details: draft })
          });
          const data = await res.json();
          setLoading(false);
          if (data.success) {
            appendAssistantMessage(data.reply);
          } else {
            appendErrorMessage(data.error);
          }
        } catch (e) {
          setLoading(false);
          appendErrorMessage('Error reviewing project draft.');
        }
      });

    // 2. Generate Project Report
    } else if (action === 'project-report') {
      appendAssistantMessage("Which project would you like me to generate a report for?", false);
      actionTitle.innerText = 'Generate Project Progress Report';
      actionBody.innerHTML = `
        <div class="mb-2">
          <label class="form-label text-muted" style="font-size: 0.75rem;">Select Authorized Project:</label>
          <select id="grok-report-pid" class="form-select form-select-sm">
            ${projectOptions}
          </select>
        </div>
        <button type="button" id="grok-btn-proj-report" class="btn btn-sm btn-info text-white w-100">
          <i class="fa-solid fa-chart-pie me-1"></i> Generate Progress Report
        </button>
      `;

      document.getElementById('grok-btn-proj-report')?.addEventListener('click', async () => {
        const pid = document.getElementById('grok-report-pid')?.value;
        if (!pid) {
          alert('Please select a project.');
          return;
        }
        const selName = document.getElementById('grok-report-pid')?.selectedOptions[0]?.text || '';
        hideActionCard();
        appendUserMessage(`Generate Project Report: ${selName}`);
        setLoading(true);

        try {
          const res = await fetch('/ai/summarize-project', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
            body: JSON.stringify({ project_id: parseInt(pid, 10) })
          });
          const data = await res.json();
          setLoading(false);
          if (data.success) {
            appendAssistantMessage(data.reply);
          } else {
            appendErrorMessage(data.error);
          }
        } catch (e) {
          setLoading(false);
          appendErrorMessage('Error generating project progress report.');
        }
      });

    // 3. Create a Task Guidance
    } else if (action === 'create-task') {
      appendUserMessage("How do I create a task in the platform?");
      setLoading(true);

      fetch('/ai/generate-task', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
        body: JSON.stringify({ requirement: '' })
      })
      .then(res => res.json())
      .then(data => {
        setLoading(false);
        if (data.success) {
          appendAssistantMessage(data.reply);
        } else {
          appendErrorMessage(data.error || 'Failed to load task guidance.');
        }
      })
      .catch(e => {
        setLoading(false);
        appendErrorMessage('Error loading task creation guidance.');
      });

      actionTitle.innerText = 'Create Task - Guidance & Review';
      actionBody.innerHTML = `
        <div class="alert alert-success py-2 px-3 mb-2" style="font-size: 0.75rem; border-radius: 6px;">
          <i class="fa-solid fa-circle-info me-1"></i> The AI Assistant does not insert or save tasks to the database. Use the guidance provided in chat, then create your task in the Task Management module.
        </div>
        <a href="/tasks/create" class="btn btn-sm btn-success w-100 mb-2">
          <i class="fa-solid fa-arrow-up-right-from-square me-1"></i> Go to Task Management (/tasks/create)
        </a>
        <div class="border-top pt-2 mt-2">
          <label class="form-label text-muted mb-1" style="font-size: 0.72rem;">
            <i class="fa-solid fa-lightbulb text-warning me-1"></i>Have a draft requirement? Get AI feedback & criteria:
          </label>
          <textarea id="grok-t-draft" class="form-control form-control-sm mb-2" rows="2" placeholder="Enter your task requirement or feature description to structure acceptance criteria..."></textarea>
          <div class="mb-2">
            <select id="grok-t-draft-pid" class="form-select form-select-sm">
              <option value="">-- General / No Project --</option>
              ${projectOptions}
            </select>
          </div>
          <button type="button" id="grok-btn-review-t" class="btn btn-sm btn-outline-success w-100">
            <i class="fa-solid fa-wand-magic-sparkles me-1"></i> Review Requirement with AI
          </button>
        </div>
      `;

      document.getElementById('grok-btn-review-t')?.addEventListener('click', async () => {
        const req = document.getElementById('grok-t-draft')?.value?.trim();
        const pid = document.getElementById('grok-t-draft-pid')?.value;
        if (!req) {
          alert('Please enter your task requirement.');
          return;
        }
        hideActionCard();
        appendUserMessage(`Review Task Requirement: ${req}`);
        setLoading(true);

        try {
          const res = await fetch('/ai/generate-task', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
            body: JSON.stringify({ requirement: req, project_id: pid ? parseInt(pid, 10) : null })
          });
          const data = await res.json();
          setLoading(false);
          if (data.success) {
            appendAssistantMessage(data.reply);
          } else {
            appendErrorMessage(data.error);
          }
        } catch (e) {
          setLoading(false);
          appendErrorMessage('Error reviewing task requirement.');
        }
      });

    // 4. Generate Task Report
    } else if (action === 'task-report') {
      appendAssistantMessage("I'll prepare a comprehensive task report based on your authorized sprint data. Which project would you like to report on, or should I summarize all your assigned tasks?", false);
      actionTitle.innerText = 'Generate Task Report';
      actionBody.innerHTML = `
        <div class="mb-2">
          <label class="form-label text-muted" style="font-size: 0.75rem;">Report Scope:</label>
          <select id="grok-task-report-pid" class="form-select form-select-sm">
            <option value="">-- All My Authorized Tasks --</option>
            ${projectOptions}
          </select>
        </div>
        <button type="button" id="grok-btn-task-report" class="btn btn-sm btn-primary w-100">
          <i class="fa-solid fa-table-list me-1"></i> Generate Task Summary Report
        </button>
      `;

      document.getElementById('grok-btn-task-report')?.addEventListener('click', async () => {
        const pid = document.getElementById('grok-task-report-pid')?.value;
        const selText = document.getElementById('grok-task-report-pid')?.selectedOptions[0]?.text || '';
        hideActionCard();
        appendUserMessage(`Generate Task Report: ${selText}`);
        setLoading(true);

        try {
          const res = await fetch('/ai/task-report', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
            body: JSON.stringify({ project_id: pid ? parseInt(pid, 10) : null })
          });
          const data = await res.json();
          setLoading(false);
          if (data.success) {
            appendAssistantMessage(data.reply);
          } else {
            appendErrorMessage(data.error);
          }
        } catch (e) {
          setLoading(false);
          appendErrorMessage('Error generating task report.');
        }
      });

    // 5. Break Project into Tasks
    } else if (action === 'break-project') {
      appendAssistantMessage("Please describe the project or feature you want to build, and I'll break it down into structured tasks and implementation subtasks.", false);
      actionTitle.innerText = 'Break Project into Tasks';
      actionBody.innerHTML = `
        <div class="mb-2">
          <label class="form-label text-muted" style="font-size: 0.75rem;">Project or Feature Description:</label>
          <textarea id="grok-break-desc" class="form-control form-control-sm" rows="3" placeholder="e.g. Build an automated billing and subscription module with Stripe integration, recurring invoices, and PDF downloads..."></textarea>
        </div>
        <button type="button" id="grok-btn-break" class="btn btn-sm btn-warning w-100">
          <i class="fa-solid fa-sitemap me-1"></i> Break Down Project into Work Tasks
        </button>
      `;

      document.getElementById('grok-btn-break')?.addEventListener('click', async () => {
        const desc = document.getElementById('grok-break-desc')?.value?.trim();
        if (!desc) return;
        hideActionCard();
        appendUserMessage(`Break Project into Tasks: ${desc.substring(0, 100)}...`);
        setLoading(true);

        try {
          const res = await fetch('/ai/break-project', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
            body: JSON.stringify({ description: desc })
          });
          const data = await res.json();
          setLoading(false);
          if (data.success) {
            appendAssistantMessage(data.reply);
          } else {
            appendErrorMessage(data.error);
          }
        } catch (e) {
          setLoading(false);
          appendErrorMessage('Error breaking project into tasks.');
        }
      });

    // 6. Create Bug Report
    } else if (action === 'create-bug') {
      appendAssistantMessage("Describe the bug you encountered, and I'll help you prepare a structured bug report.", false);
      actionTitle.innerText = 'Create a Bug Report';
      actionBody.innerHTML = `
        <div class="mb-2">
          <label class="form-label text-muted" style="font-size: 0.75rem;">Describe the Bug / Problem:</label>
          <textarea id="grok-bug-desc" class="form-control form-control-sm" rows="2" placeholder="e.g. When editing a task in dark mode, the status badge text turns invisible"></textarea>
        </div>
        <div class="mb-2">
          <label class="form-label text-muted" style="font-size: 0.75rem;">Related Project (Optional):</label>
          <select id="grok-bug-pid" class="form-select form-select-sm">
            <option value="">-- General / System-wide --</option>
            ${projectOptions}
          </select>
        </div>
        <button type="button" id="grok-submit-bug" class="btn btn-sm btn-danger w-100">
          <i class="fa-solid fa-bug me-1"></i> Generate Structured Bug Report
        </button>
      `;

      document.getElementById('grok-submit-bug')?.addEventListener('click', async () => {
        const desc = document.getElementById('grok-bug-desc')?.value?.trim();
        const pid = document.getElementById('grok-bug-pid')?.value;
        if (!desc) return;
        hideActionCard();
        appendUserMessage(`Create Bug Report: ${desc}`);
        setLoading(true);

        try {
          const res = await fetch('/ai/generate-bug', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
            body: JSON.stringify({ description: desc, project_id: pid ? parseInt(pid, 10) : null })
          });
          const data = await res.json();
          setLoading(false);
          if (data.success) {
            appendAssistantMessage(data.reply);
          } else {
            appendErrorMessage(data.error);
          }
        } catch (e) {
          setLoading(false);
          appendErrorMessage('Error generating bug report.');
        }
      });

    // 7. Analyze a Bug
    } else if (action === 'analyze-bug') {
      appendAssistantMessage("Describe the bug symptoms, error message, or stack trace you're facing, and I'll analyze possible causes and debugging steps.", false);
      actionTitle.innerText = 'Analyze Bug & Diagnostics';
      actionBody.innerHTML = `
        <div class="mb-2">
          <label class="form-label text-muted" style="font-size: 0.75rem;">Bug Symptoms or Error Log:</label>
          <textarea id="grok-analyze-details" class="form-control form-control-sm font-monospace" rows="3" placeholder="Paste traceback, SQL error, or describe intermittent failure..."></textarea>
        </div>
        <button type="button" id="grok-btn-analyze-bug" class="btn btn-sm btn-secondary w-100">
          <i class="fa-solid fa-microscope me-1"></i> Diagnose & Suggest Fix Strategies
        </button>
      `;

      document.getElementById('grok-btn-analyze-bug')?.addEventListener('click', async () => {
        const details = document.getElementById('grok-analyze-details')?.value?.trim();
        if (!details) return;
        hideActionCard();
        appendUserMessage(`Analyze Bug: ${details.substring(0, 100)}...`);
        setLoading(true);

        try {
          const res = await fetch('/ai/analyze-bug', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
            body: JSON.stringify({ details: details })
          });
          const data = await res.json();
          setLoading(false);
          if (data.success) {
            appendAssistantMessage(data.reply);
          } else {
            appendErrorMessage(data.error);
          }
        } catch (e) {
          setLoading(false);
          appendErrorMessage('Error analyzing bug.');
        }
      });

    // 8. Explain Code
    } else if (action === 'explain-code') {
      appendAssistantMessage("Please paste your code snippet here, and I'll explain its purpose, logic, potential bugs, and optimizations.", false);
      actionTitle.innerText = 'Explain Code';
      actionBody.innerHTML = `
        <div class="mb-2">
          <label class="form-label text-muted" style="font-size: 0.75rem;">Programming Language:</label>
          <select id="grok-code-lang" class="form-select form-select-sm">
            <option value="python">Python</option>
            <option value="javascript">JavaScript</option>
            <option value="java">Java</option>
            <option value="sql">SQL</option>
            <option value="html">HTML</option>
            <option value="css">CSS</option>
            <option value="other">Other</option>
          </select>
        </div>
        <div class="mb-2">
          <label class="form-label text-muted" style="font-size: 0.75rem;">Paste Code Snippet:</label>
          <textarea id="grok-code-snippet" class="form-control form-control-sm font-monospace" rows="3" placeholder="Paste code here..."></textarea>
        </div>
        <div class="mb-2">
          <label class="form-label text-muted" style="font-size: 0.75rem;">Specific Focus (Optional):</label>
          <input type="text" id="grok-code-q" class="form-control form-control-sm" placeholder="e.g. Find any performance bottlenecks or security gaps">
        </div>
        <button type="button" id="grok-submit-code" class="btn btn-sm btn-info text-white w-100">
          <i class="fa-solid fa-file-code me-1"></i> Explain Code
        </button>
      `;

      document.getElementById('grok-submit-code')?.addEventListener('click', async () => {
        const code = document.getElementById('grok-code-snippet')?.value?.trim();
        const lang = document.getElementById('grok-code-lang')?.value;
        const q = document.getElementById('grok-code-q')?.value?.trim();
        if (!code) return;
        hideActionCard();
        appendUserMessage(`Explain ${lang} code:\n\`\`\`${lang}\n${code.substring(0, 100)}...\n\`\`\``);
        setLoading(true);

        try {
          const res = await fetch('/ai/explain-code', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
            body: JSON.stringify({ code: code, language: lang, question: q })
          });
          const data = await res.json();
          setLoading(false);
          if (data.success) {
            appendAssistantMessage(data.reply);
          } else {
            appendErrorMessage(data.error);
          }
        } catch (e) {
          setLoading(false);
          appendErrorMessage('Error analyzing code.');
        }
      });

    // 9. Generate Code
    } else if (action === 'generate-code') {
      appendAssistantMessage("What code would you like me to generate? Please specify your requirements and preferred programming language (Python, Java, JavaScript, HTML, CSS, SQL).", false);
      actionTitle.innerText = 'Generate Code';
      actionBody.innerHTML = `
        <div class="mb-2">
          <label class="form-label text-muted" style="font-size: 0.75rem;">Target Language:</label>
          <select id="grok-gen-lang" class="form-select form-select-sm">
            <option value="python">Python</option>
            <option value="java">Java</option>
            <option value="javascript">JavaScript</option>
            <option value="sql">SQL</option>
            <option value="html">HTML</option>
            <option value="css">CSS</option>
          </select>
        </div>
        <div class="mb-2">
          <label class="form-label text-muted" style="font-size: 0.75rem;">Requirements & Specifications:</label>
          <textarea id="grok-gen-reqs" class="form-control form-control-sm" rows="3" placeholder="e.g. Write a Python function that parses CSV files with error handling and deduplication"></textarea>
        </div>
        <button type="button" id="grok-btn-gen-code" class="btn btn-sm btn-success w-100">
          <i class="fa-solid fa-laptop-code me-1"></i> Generate Code
        </button>
      `;

      document.getElementById('grok-btn-gen-code')?.addEventListener('click', async () => {
        const lang = document.getElementById('grok-gen-lang')?.value;
        const reqs = document.getElementById('grok-gen-reqs')?.value?.trim();
        if (!reqs) return;
        hideActionCard();
        appendUserMessage(`Generate ${lang.toUpperCase()} code for: ${reqs.substring(0, 100)}...`);
        setLoading(true);

        try {
          const res = await fetch('/ai/generate-code', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
            body: JSON.stringify({ requirements: reqs, language: lang })
          });
          const data = await res.json();
          setLoading(false);
          if (data.success) {
            appendAssistantMessage(data.reply);
          } else {
            appendErrorMessage(data.error);
          }
        } catch (e) {
          setLoading(false);
          appendErrorMessage('Error generating code.');
        }
      });

    // 10. Generate Daily Work Report
    } else if (action === 'daily-report') {
      appendAssistantMessage("I'll generate your daily work report using your recorded time and work logs. Please mention any specific achievements or challenges you'd like included.", false);
      actionTitle.innerText = 'Generate Daily Work Report';
      actionBody.innerHTML = `
        <div class="mb-2">
          <label class="form-label text-muted" style="font-size: 0.75rem;">Completed Activities Today:</label>
          <textarea id="grok-daily-work" class="form-control form-control-sm" rows="2" placeholder="e.g. Completed unit tests for password toggle and integrated AI Assistant"></textarea>
        </div>
        <div class="mb-2">
          <label class="form-label text-muted" style="font-size: 0.75rem;">Challenges / Blockers Encountered:</label>
          <input type="text" id="grok-daily-challenges" class="form-control form-control-sm" placeholder="e.g. Sandbox network isolation required local testing">
        </div>
        <div class="mb-2">
          <label class="form-label text-muted" style="font-size: 0.75rem;">Tomorrow's Next Steps:</label>
          <input type="text" id="grok-daily-next" class="form-control form-control-sm" placeholder="e.g. Implement code export feature and review PRs">
        </div>
        <button type="button" id="grok-submit-daily" class="btn btn-sm btn-warning w-100">
          <i class="fa-solid fa-calendar-day me-1"></i> Generate Daily Work Report
        </button>
      `;

      document.getElementById('grok-submit-daily')?.addEventListener('click', async () => {
        const work = document.getElementById('grok-daily-work')?.value?.trim();
        const chal = document.getElementById('grok-daily-challenges')?.value?.trim();
        const nxt = document.getElementById('grok-daily-next')?.value?.trim();
        if (!work) return;
        hideActionCard();
        appendUserMessage(`Generate Daily Work Report: ${work.substring(0, 100)}...`);
        setLoading(true);

        try {
          const res = await fetch('/ai/daily-summary', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
            body: JSON.stringify({ work_done: work, challenges: chal, next_steps: nxt })
          });
          const data = await res.json();
          setLoading(false);
          if (data.success) {
            appendAssistantMessage(data.reply);
          } else {
            appendErrorMessage(data.error);
          }
        } catch (e) {
          setLoading(false);
          appendErrorMessage('Error generating daily work report.');
        }
      });

    // 11. Productivity Summary
    } else if (action === 'productivity-summary') {
      appendAssistantMessage("I'll summarize your productivity metrics and task completion rates from today's tracked hours. Let's analyze your progress!", false);
      hideActionCard();
      appendUserMessage("Productivity Summary");
      setLoading(true);

      fetch('/ai/productivity-summary', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() }
      })
      .then(r => r.json())
      .then(data => {
        setLoading(false);
        if (data.success) {
          appendAssistantMessage(data.reply);
        } else {
          appendErrorMessage(data.error);
        }
      })
      .catch(() => {
        setLoading(false);
        appendErrorMessage('Error generating productivity summary.');
      });
    }
  }
});
