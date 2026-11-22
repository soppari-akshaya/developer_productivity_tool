/**
 * Pomodoro Deep Work Focus Timer
 */
document.addEventListener('DOMContentLoaded', () => {
  const display = document.getElementById('pomodoro-display');
  if (!display) return;

  const startBtn = document.getElementById('pomo-start-btn');
  const pauseBtn = document.getElementById('pomo-pause-btn');
  const resetBtn = document.getElementById('pomo-reset-btn');
  const modeBadge = document.getElementById('pomo-mode-badge');
  const tabButtons = document.querySelectorAll('.pomo-tab-btn');

  let modeDurations = {
    'focus': 25 * 60,
    'short_break': 5 * 60,
    'long_break': 15 * 60
  };

  let currentMode = 'focus';
  let timeLeft = modeDurations[currentMode];
  let timerInterval = null;
  let isRunning = false;

  function updateDisplay() {
    const mins = Math.floor(timeLeft / 60);
    const secs = timeLeft % 60;
    display.textContent = `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  }

  function setMode(mode) {
    clearInterval(timerInterval);
    isRunning = false;
    currentMode = mode;
    timeLeft = modeDurations[mode];
    updateDisplay();

    if (modeBadge) {
      modeBadge.textContent = mode.replace('_', ' ').toUpperCase();
    }

    tabButtons.forEach(btn => {
      btn.classList.toggle('active', btn.getAttribute('data-mode') === mode);
    });

    startBtn.classList.remove('d-none');
    pauseBtn.classList.add('d-none');
  }

  tabButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      setMode(btn.getAttribute('data-mode'));
    });
  });

  if (startBtn) {
    startBtn.addEventListener('click', () => {
      if (!isRunning) {
        isRunning = true;
        startBtn.classList.add('d-none');
        pauseBtn.classList.remove('d-none');

        timerInterval = setInterval(() => {
          if (timeLeft > 0) {
            timeLeft--;
            updateDisplay();
          } else {
            clearInterval(timerInterval);
            isRunning = false;
            // Record completed session to backend
            fetch('/developer/pomodoro/complete', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                session_type: currentMode,
                duration: Math.round(modeDurations[currentMode] / 60)
              })
            }).catch(console.error);

            alert(`${currentMode === 'focus' ? 'Deep work session completed!' : 'Break time finished!'}`);
            setMode(currentMode === 'focus' ? 'short_break' : 'focus');
          }
        }, 1000);
      }
    });
  }

  if (pauseBtn) {
    pauseBtn.addEventListener('click', () => {
      if (isRunning) {
        clearInterval(timerInterval);
        isRunning = false;
        startBtn.classList.remove('d-none');
        pauseBtn.classList.add('d-none');
      }
    });
  }

  if (resetBtn) {
    resetBtn.addEventListener('click', () => {
      setMode(currentMode);
    });
  }

  updateDisplay();
});

