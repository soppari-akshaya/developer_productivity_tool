/**
 * Live Working Hours Time Tracker Stopwatch
 */
document.addEventListener('DOMContentLoaded', () => {
  const display = document.getElementById('timer-stopwatch-display');
  if (!display) return;

  const startBtn = document.getElementById('timer-start-btn');
  const pauseBtn = document.getElementById('timer-pause-btn');
  const stopBtn = document.getElementById('timer-stop-btn');
  const durationInput = document.getElementById('duration_minutes_input');

  let seconds = 0;
  let interval = null;
  let isRunning = false;

  function updateDisplay() {
    const hrs = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    display.textContent = `${String(hrs).padStart(2, '0')}:${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  }

  if (startBtn) {
    startBtn.addEventListener('click', () => {
      if (!isRunning) {
        isRunning = true;
        interval = setInterval(() => {
          seconds++;
          updateDisplay();
        }, 1000);
        startBtn.disabled = true;
        pauseBtn.disabled = false;
        stopBtn.disabled = false;
      }
    });
  }

  if (pauseBtn) {
    pauseBtn.addEventListener('click', () => {
      if (isRunning) {
        clearInterval(interval);
        isRunning = false;
        startBtn.disabled = false;
        pauseBtn.disabled = true;
      }
    });
  }

  if (stopBtn) {
    stopBtn.addEventListener('click', () => {
      clearInterval(interval);
      isRunning = false;
      const minutesElapsed = Math.max(1, Math.round(seconds / 60));
      if (durationInput) {
        durationInput.value = minutesElapsed;
      }
      // Open save modal if exists
      const modalEl = document.getElementById('saveTimeEntryModal');
      if (modalEl && window.bootstrap) {
        const modal = new bootstrap.Modal(modalEl);
        modal.show();
      }
      startBtn.disabled = false;
      pauseBtn.disabled = true;
      stopBtn.disabled = true;
      seconds = 0;
      updateDisplay();
    });
  }
});

