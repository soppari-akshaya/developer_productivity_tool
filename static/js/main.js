/**
 * Main application JavaScript: Theme toggle, tooltips, clipboard helpers.
 */
document.addEventListener('DOMContentLoaded', () => {
  // Theme switcher
  const themeToggleBtns = document.querySelectorAll('.theme-toggle-btn');
  const currentTheme = localStorage.getItem('dpt_theme') || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');

  function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('dpt_theme', theme);
    themeToggleBtns.forEach(btn => {
      btn.innerHTML = theme === 'dark' 
        ? '<i class="fa-solid fa-sun text-warning"></i>' 
        : '<i class="fa-solid fa-moon text-secondary"></i>';
    });
  }

  applyTheme(currentTheme);

  themeToggleBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const active = document.documentElement.getAttribute('data-theme') || 'light';
      applyTheme(active === 'dark' ? 'light' : 'dark');
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

