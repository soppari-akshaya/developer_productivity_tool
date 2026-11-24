/**
 * Main application JavaScript: Theme toggle, tooltips, clipboard helpers,
 * and Global Persistent Time Tracker Client.
 */
document.addEventListener('DOMContentLoaded', () => {
  // Theme switcher
  const themeToggleBtns = document.querySelectorAll('.theme-toggle-btn');
  const savedTheme = localStorage.getItem('dpt_theme');
  const initialTheme = (savedTheme === 'dark' || savedTheme === 'light') 
    ? savedTheme 
    : (document.documentElement.getAttribute('data-theme') || 'light');

  function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    document.documentElement.setAttribute('data-bs-theme', theme);
    try {
      localStorage.setItem('dpt_theme', theme);
    } catch (e) {}

    themeToggleBtns.forEach(btn => {
      btn.innerHTML = theme === 'dark' 
        ? '<i class="fa-solid fa-sun text-warning"></i>' 
        : '<i class="fa-solid fa-moon text-secondary"></i>';
      btn.setAttribute('title', theme === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode');
      btn.setAttribute('aria-label', theme === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode');
    });
  }

  applyTheme(initialTheme);

  themeToggleBtns.forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const current = document.documentElement.getAttribute('data-theme') || 'light';
      const targetTheme = current === 'dark' ? 'light' : 'dark';
      applyTheme(targetTheme);
    });
  });

  // Global snippet copy buttons
  document.querySelectorAll('.copy-snippet-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const targetId = btn.getAttribute('data-target');
      const el = document.getElementById(targetId);
      if (el) {
        navigator.clipboard.writeText(el.innerText || el.textContent);
        const orig = btn.innerHTML;
        btn.innerHTML = '<i class="fa-solid fa-check text-success"></i> Copied';
        setTimeout(() => { btn.innerHTML = orig; }, 2000);
      }
    });
  });

  // Browser back-navigation bfcache cache lockout: reload if page restored from cache
  window.addEventListener('pageshow', (event) => {
    if (event.persisted) {
      window.location.reload();
    }
  });
});
