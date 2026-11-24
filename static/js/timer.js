/**
 * Dedicated Time Tracker Controller
 * Handles timer controls, strict button visibility per state,
 * local counting, server timestamp synchronization, and persistence.
 */
document.addEventListener('DOMContentLoaded', () => {
  const startBtn = document.getElementById('timer-start-btn');
  const pauseBtn = document.getElementById('timer-pause-btn');
  const resumeBtn = document.getElementById('timer-resume-btn');
  const stopBtn = document.getElementById('timer-stop-btn');

  const displayEl = document.getElementById('timer-stopwatch-display');
  const badgeEl = document.getElementById('timer-active-badge');
  const alertEl = document.getElementById('timer-alert');
  const todayBadge = document.getElementById('timer-today-hours-badge');

  const projSelect = document.getElementById('timer-project-select');
  const taskSelect = document.getElementById('timer-task-select');
  const descInput = document.getElementById('timer-description-input');

  const durationInput = document.getElementById('duration_minutes_input');
  const modalProjSelect = document.getElementById('modal_project_id');
  const modalDescInput = document.getElementById('modal_description');
  const saveModalEl = document.getElementById('saveTimeEntryModal');
  const saveForm = document.getElementById('saveTimeEntryForm');

  let currentStatus = 'idle'; // 'idle', 'running', 'paused'
  let elapsedSeconds = 0;
  let timerInterval = null;
  let lastTick = Date.now();

  function getCsrfToken() {
    return document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
  }

  function formatHMS(totalSecs) {
    const s = Math.max(0, Math.floor(totalSecs || 0));
    const hrs = Math.floor(s / 3600);
    const mins = Math.floor((s % 3600) / 60);
    const secs = s % 60;
    return `${String(hrs).padStart(2, '0')}:${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  }

  function showAlert(message, type = 'danger') {
    if (alertEl) {
      alertEl.className = `alert alert-${type} mb-3 py-2 px-3 text-start`;
      alertEl.textContent = message;
      alertEl.classList.remove('d-none');
    }
  }

  function hideAlert() {
    if (alertEl) {
      alertEl.classList.add('d-none');
      alertEl.textContent = '';
    }
  }

  /**
   * Enforces strict button visibility based on timer state:
   * - idle: Show Start. Hide Pause, Resume, Stop.
   * - running: Show Pause, Stop. Hide Start, Resume.
   * - paused: Show Resume, Stop. Hide Start, Pause.
   */
  function updateControlsUI(status, seconds) {
    currentStatus = status;

    // Update stopwatch display
    if (displayEl) {
      displayEl.textContent = formatHMS(seconds);
    }

    // Update status badge
    if (badgeEl) {
      if (status === 'running') {
        badgeEl.className = 'badge bg-success bg-opacity-20 text-success px-2.5 py-1';
        badgeEl.textContent = 'RUNNING';
      } else if (status === 'paused') {
        badgeEl.className = 'badge bg-warning bg-opacity-20 text-warning px-2.5 py-1';
        badgeEl.textContent = 'PAUSED';
      } else {
        badgeEl.className = 'badge bg-secondary bg-opacity-20 text-secondary px-2.5 py-1';
        badgeEl.textContent = 'IDLE';
      }
    }

    // Strict button visibility
    if (status === 'running') {
      if (startBtn) { startBtn.classList.add('d-none'); startBtn.disabled = true; }
      if (pauseBtn) { pauseBtn.classList.remove('d-none'); pauseBtn.disabled = false; }
      if (resumeBtn) { resumeBtn.classList.add('d-none'); resumeBtn.disabled = true; }
      if (stopBtn) { stopBtn.classList.remove('d-none'); stopBtn.disabled = false; }
    } else if (status === 'paused') {
      if (startBtn) { startBtn.classList.add('d-none'); startBtn.disabled = true; }
      if (pauseBtn) { pauseBtn.classList.add('d-none'); pauseBtn.disabled = true; }
      if (resumeBtn) { resumeBtn.classList.remove('d-none'); resumeBtn.disabled = false; }
      if (stopBtn) { stopBtn.classList.remove('d-none'); stopBtn.disabled = false; }
    } else {
      // idle
      if (startBtn) { startBtn.classList.remove('d-none'); startBtn.disabled = false; }
      if (pauseBtn) { pauseBtn.classList.add('d-none'); pauseBtn.disabled = true; }
      if (resumeBtn) { resumeBtn.classList.add('d-none'); resumeBtn.disabled = true; }
      if (stopBtn) { stopBtn.classList.add('d-none'); stopBtn.disabled = true; }
    }
  }

  function startTicker(initialSeconds) {
    clearInterval(timerInterval);
    elapsedSeconds = initialSeconds;
    lastTick = Date.now();

    timerInterval = setInterval(() => {
      const now = Date.now();
      const delta = Math.floor((now - lastTick) / 1000);
      if (delta >= 1) {
        elapsedSeconds += delta;
        lastTick = now;
        if (displayEl) {
          displayEl.textContent = formatHMS(elapsedSeconds);
        }
      }
    }, 1000);
  }

  function stopTicker() {
    clearInterval(timerInterval);
    timerInterval = null;
  }

  // Filter tasks when project changes
  function updateTaskFilter() {
    if (!projSelect || !taskSelect) return;
    const selectedProj = projSelect.value;
    Array.from(taskSelect.options).forEach(opt => {
      if (!opt.value) return; // Keep "-- Select Task --"
      const optProj = opt.getAttribute('data-project');
      if (!selectedProj || optProj === selectedProj) {
        opt.style.display = '';
      } else {
        opt.style.display = 'none';
        if (taskSelect.value === opt.value) {
          taskSelect.value = '';
        }
      }
    });
  }

  if (projSelect) {
    projSelect.addEventListener('change', updateTaskFilter);
    updateTaskFilter();
  }

  if (taskSelect && projSelect) {
    taskSelect.addEventListener('change', () => {
      const selectedOption = taskSelect.options[taskSelect.selectedIndex];
      const taskProj = selectedOption?.getAttribute('data-project');
      if (taskProj && !projSelect.value) {
        projSelect.value = taskProj;
        updateTaskFilter();
      }
    });
  }

  // Fetch current state from server on page load
  async function fetchCurrentState() {
    try {
      const response = await fetch('/api/timer/current', {
        headers: {
          'Accept': 'application/json',
          'X-CSRFToken': getCsrfToken()
        }
      });
      if (!response.ok) return;

      const data = await response.json();
      if (data.today_total_hours !== undefined && todayBadge) {
        todayBadge.textContent = `${data.today_total_hours} hrs`;
      }

      if (data.active && data.timer) {
        elapsedSeconds = data.timer.elapsed_seconds || 0;

        if (projSelect && data.timer.project_id && !projSelect.value) {
          projSelect.value = data.timer.project_id;
          updateTaskFilter();
        }
        if (taskSelect && data.timer.task_id && !taskSelect.value) {
          taskSelect.value = data.timer.task_id;
        }
        if (descInput && data.timer.description && !descInput.value) {
          descInput.value = data.timer.description;
        }

        if (data.timer.status === 'running') {
          updateControlsUI('running', elapsedSeconds);
          startTicker(elapsedSeconds);
        } else if (data.timer.status === 'paused') {
          stopTicker();
          updateControlsUI('paused', elapsedSeconds);
        } else {
          stopTicker();
          updateControlsUI('idle', 0);
        }
      } else {
        stopTicker();
        updateControlsUI('idle', 0);
      }
    } catch (err) {
      console.warn('Could not fetch active timer state:', err);
    }
  }

  // Start Timer
  if (startBtn) {
    startBtn.addEventListener('click', async (e) => {
      e.preventDefault();
      hideAlert();

      const pVal = projSelect ? projSelect.value : '';
      const tVal = taskSelect ? taskSelect.value : '';
      const projId = pVal ? parseInt(pVal, 10) : null;
      const taskId = tVal ? parseInt(tVal, 10) : null;
      const desc = descInput ? descInput.value.trim() : '';

      startBtn.disabled = true;

      try {
        const response = await fetch('/api/timer/start', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'X-CSRFToken': getCsrfToken()
          },
          body: JSON.stringify({
            project_id: projId,
            task_id: taskId,
            description: desc
          })
        });

        const data = await response.json();

        if (response.ok && data.status === 'success') {
          const initialSecs = Math.max(1, data.timer?.elapsed_seconds || 1);
          updateControlsUI('running', initialSecs);
          startTicker(initialSecs);
        } else {
          startBtn.disabled = false;
          showAlert(data.message || 'Could not start timer. Please try again.');
        }
      } catch (err) {
        startBtn.disabled = false;
        showAlert('Network error while starting timer. Please try again.');
      }
    });
  }

  // Pause Timer
  if (pauseBtn) {
    pauseBtn.addEventListener('click', async (e) => {
      e.preventDefault();
      hideAlert();
      pauseBtn.disabled = true;

      try {
        const response = await fetch('/api/timer/pause', {
          method: 'POST',
          headers: {
            'Accept': 'application/json',
            'X-CSRFToken': getCsrfToken()
          }
        });

        const data = await response.json();
        if (response.ok && data.status === 'success') {
          stopTicker();
          elapsedSeconds = data.timer?.elapsed_seconds || elapsedSeconds;
          updateControlsUI('paused', elapsedSeconds);
        } else {
          pauseBtn.disabled = false;
          showAlert(data.message || 'Could not pause timer.');
        }
      } catch (err) {
        pauseBtn.disabled = false;
        showAlert('Network error pausing timer.');
      }
    });
  }

  // Resume Timer
  if (resumeBtn) {
    resumeBtn.addEventListener('click', async (e) => {
      e.preventDefault();
      hideAlert();
      resumeBtn.disabled = true;

      try {
        const response = await fetch('/api/timer/resume', {
          method: 'POST',
          headers: {
            'Accept': 'application/json',
            'X-CSRFToken': getCsrfToken()
          }
        });

        const data = await response.json();
        if (response.ok && data.status === 'success') {
          elapsedSeconds = data.timer?.elapsed_seconds || elapsedSeconds;
          updateControlsUI('running', elapsedSeconds);
          startTicker(elapsedSeconds);
        } else {
          resumeBtn.disabled = false;
          showAlert(data.message || 'Could not resume timer.');
        }
      } catch (err) {
        resumeBtn.disabled = false;
        showAlert('Network error resuming timer.');
      }
    });
  }

  // Stop & Save Timer Trigger
  if (stopBtn) {
    stopBtn.addEventListener('click', (e) => {
      e.preventDefault();
      hideAlert();

      const elapsedMins = Math.max(1, Math.round(elapsedSeconds / 60));

      // Pre-fill modal
      if (durationInput) durationInput.value = elapsedMins;
      if (modalProjSelect && projSelect) modalProjSelect.value = projSelect.value;
      if (modalDescInput && descInput) modalDescInput.value = descInput.value;

      if (saveModalEl && window.bootstrap) {
        const modal = new bootstrap.Modal(saveModalEl);
        modal.show();
      } else {
        // Direct stop confirmation fallback
        if (confirm('Stop the active timer and save your logged hours?')) {
          const pVal = projSelect ? projSelect.value : '';
          const tVal = taskSelect ? taskSelect.value : '';
          const pId = pVal ? parseInt(pVal, 10) : null;
          const tId = tVal ? parseInt(tVal, 10) : null;
          const desc = descInput ? descInput.value.trim() : '';
          executeStopAndSave(pId, tId, desc);
        }
      }
    });
  }

  // Modal Form Submission to save entry and stop timer
  if (saveForm) {
    saveForm.addEventListener('submit', (e) => {
      e.preventDefault();
      hideAlert();

      const pVal = modalProjSelect ? modalProjSelect.value : '';
      const tVal = taskSelect ? taskSelect.value : '';
      const pId = pVal ? parseInt(pVal, 10) : null;
      const tId = tVal ? parseInt(tVal, 10) : null;
      const desc = modalDescInput ? modalDescInput.value.trim() : '';

      executeStopAndSave(pId, tId, desc);
    });
  }

  async function executeStopAndSave(pId, tId, desc) {
    try {
      const response = await fetch('/api/timer/stop', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
          'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify({
          project_id: pId,
          task_id: tId,
          description: desc
        })
      });

      const data = await response.json();
      if (response.ok && data.status === 'success') {
        stopTicker();
        elapsedSeconds = 0;
        updateControlsUI('idle', 0);

        if (saveModalEl && window.bootstrap) {
          const modalInstance = bootstrap.Modal.getInstance(saveModalEl);
          if (modalInstance) modalInstance.hide();
        }

        // Reload page to refresh history table and today's total
        setTimeout(() => {
          window.location.reload();
        }, 500);
      } else {
        showAlert(data.message || 'Could not save and stop timer.');
      }
    } catch (err) {
      showAlert('Network error saving time record.');
    }
  }

  // Periodic synchronization with server to prevent tab drift
  setInterval(() => {
    if (currentStatus === 'running') {
      fetchCurrentState();
    }
  }, 30000);

  // Initialize
  fetchCurrentState();
});
