/**
 * Authentication Client Logic
 * Handles Firebase Web SDK Authentication, ID Token verification with Flask,
 * and UI interactions (password visibility toggling, strength meter).
 */
import {
  auth,
  googleProvider,
  githubProvider,
  signInWithPopup,
  signInWithRedirect,
  getRedirectResult,
  createUserWithEmailAndPassword,
  signInWithEmailAndPassword,
  signOut,
  sendPasswordResetEmail,
  updateProfile,
  isConfigured
} from './firebase-config.js';

// Human-friendly Firebase error message mapper
function getFriendlyError(err) {
  const code = err?.code || '';
  switch (code) {
    case 'auth/invalid-email':
      return 'Please enter a valid email address.';
    case 'auth/user-disabled':
      return 'This user account has been disabled by an administrator.';
    case 'auth/user-not-found':
    case 'auth/wrong-password':
    case 'auth/invalid-credential':
      return 'Invalid email or password. Please verify your credentials.';
    case 'auth/email-already-in-use':
      return 'An account with this email already exists. Please sign in instead.';
    case 'auth/weak-password':
      return 'Password should be at least 8 characters long.';
    case 'auth/popup-closed-by-user':
      return 'Sign-in popup was closed before completion. Please try again.';
    case 'auth/popup-blocked':
      return 'Sign-in popup was blocked by your browser. Please allow popups or try again.';
    case 'auth/account-exists-with-different-credential':
      return 'An account already exists with the same email using another provider.';
    case 'auth/unauthorized-domain':
      return 'This domain is not authorized in Firebase Console (Authentication > Settings > Authorized domains).';
    case 'auth/operation-not-allowed':
      return 'This sign-in provider is disabled in Firebase Console. Please enable it under Authentication > Sign-in method.';
    default:
      return err?.message || 'Authentication error. Please check your credentials and network connection.';
  }
}

// Display alert banner in auth form
function showAlert(message, type = 'danger') {
  const container = document.getElementById('auth-alert-container');
  if (!container) return;
  container.innerHTML = `
    <div class="alert alert-${type} alert-dismissible fade show d-flex align-items-center gap-2" role="alert" style="border-radius: 12px; font-size: 0.85rem;">
      <i class="fa-solid fa-${type === 'success' ? 'circle-check' : (type === 'info' ? 'circle-info' : 'circle-exclamation')}"></i>
      <div>${message}</div>
      <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    </div>
  `;
}

// Post ID token to backend verification endpoint
async function sendTokenToBackend(payload) {
  const response = await fetch('/auth/verify-token', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(payload)
  });
  return await response.json();
}

// Check configuration status and alert if missing
function checkFirebaseConfigured() {
  if (!isConfigured || !auth) {
    showAlert('Firebase Authentication is not configured yet. Please configure FIREBASE_API_KEY and other parameters in your .env file.', 'warning');
    return false;
  }
  return true;
}

// Set up UI and authentication handlers
async function initAuth() {
  // ==========================================
  // 1. Password Visibility Toggles (Eye Icon)
  // ==========================================
  function setupPasswordToggle(btnId, inputId) {
    const btn = document.getElementById(btnId);
    const input = document.getElementById(inputId);
    if (btn && input) {
      btn.setAttribute('type', 'button');
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        const isPassword = input.getAttribute('type') === 'password';
        input.setAttribute('type', isPassword ? 'text' : 'password');
        btn.innerHTML = isPassword 
          ? '<i class="fa-solid fa-eye-slash"></i>' 
          : '<i class="fa-solid fa-eye"></i>';
      });
    }
  }

  // Bind password toggle on login and register forms
  setupPasswordToggle('toggle-password-btn', 'password');
  setupPasswordToggle('toggle-confirm-password-btn', 'confirm_password');

  // ==========================================
  // 2. Password Strength Meter on Registration
  // ==========================================
  const passwordInput = document.getElementById('password');
  const strengthContainer = document.querySelector('.strength-bar-container');
  if (passwordInput && strengthContainer) {
    const bars = document.querySelectorAll('.strength-bar');
    const label = document.getElementById('strength-label');

    passwordInput.addEventListener('input', () => {
      const val = passwordInput.value;
      let score = 0;
      if (val.length >= 8) score++;
      if (/[A-Z]/.test(val) && /[a-z]/.test(val)) score++;
      if (/[0-9]/.test(val)) score++;
      if (/[!@#$%^&*(),.?":{}|<>]/.test(val)) score++;

      bars.forEach((b, idx) => {
        b.style.backgroundColor = '#e2e8f0';
        if (val.length > 0 && idx < score) {
          if (score <= 1) b.style.backgroundColor = '#ef4444';
          else if (score === 2) b.style.backgroundColor = '#f59e0b';
          else if (score === 3) b.style.backgroundColor = '#3b82f6';
          else b.style.backgroundColor = '#10b981';
        }
      });

      if (!val) {
        if (label) label.textContent = '';
      } else if (score <= 1) {
        if (label) { label.textContent = 'Weak'; label.style.color = '#ef4444'; }
      } else if (score === 2) {
        if (label) { label.textContent = 'Fair'; label.style.color = '#f59e0b'; }
      } else if (score === 3) {
        if (label) { label.textContent = 'Good'; label.style.color = '#3b82f6'; }
      } else {
        if (label) { label.textContent = 'Strong'; label.style.color = '#10b981'; }
      }
    });
  }

  // ==========================================
  // 3. Handle Firebase Redirect Auth Result
  // ==========================================
  if (isConfigured && auth) {
    try {
      const redirectResult = await getRedirectResult(auth);
      if (redirectResult && redirectResult.user) {
        showAlert('Completing authentication...', 'info');
        const idToken = await redirectResult.user.getIdToken();
        const resp = await sendTokenToBackend({
          idToken,
          rememberMe: true
        });
        if (resp.status === 'success' || resp.status === 'onboarding_required') {
          window.location.href = resp.redirect;
          return;
        } else {
          showAlert(resp.message || 'Authentication error.');
        }
      }
    } catch (redirectErr) {
      console.warn("Redirect result check:", redirectErr);
    }
  }

  // ==========================================
  // 4. Email / Password Login Form
  // Handled by Flask & SQLite Backend directly
  // ==========================================
  const loginForm = document.getElementById('login-form');
  if (loginForm) {
    loginForm.addEventListener('submit', (e) => {
      const email = document.getElementById('email')?.value.trim();
      const password = document.getElementById('password')?.value;
      const submitBtn = document.getElementById('submit-btn');

      if (!email || !password) {
        e.preventDefault();
        showAlert('Please fill in both email and password.');
        return;
      }

      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status"></span>Signing in...';
        // Re-enable if page does not unload (e.g. invalid credentials)
        setTimeout(() => {
          submitBtn.disabled = false;
          submitBtn.innerHTML = '<i class="fa-solid fa-arrow-right-to-bracket me-2"></i>Sign In';
        }, 4000);
      }
    });
  }

  // ==========================================
  // 5. Email / Password Registration Form
  // Handled by Flask & SQLite Backend directly
  // ==========================================
  const registerForm = document.getElementById('register-form');
  if (registerForm) {
    registerForm.addEventListener('submit', (e) => {
      const fullName = document.getElementById('full_name')?.value.trim();
      const email = document.getElementById('email')?.value.trim();
      const password = document.getElementById('password')?.value;
      const confirmPassword = document.getElementById('confirm_password')?.value;
      const submitBtn = document.getElementById('submit-btn');

      if (!fullName || !email || !password || !confirmPassword) {
        e.preventDefault();
        showAlert('Please fill in all required fields.');
        return;
      }

      if (password.length < 8) {
        e.preventDefault();
        showAlert('Password must be at least 8 characters long.');
        return;
      }

      if (password !== confirmPassword) {
        e.preventDefault();
        showAlert('Passwords do not match. Please retype password.');
        return;
      }

      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status"></span>Creating account...';
        setTimeout(() => {
          submitBtn.disabled = false;
          submitBtn.innerHTML = '<i class="fa-solid fa-user-plus me-2"></i>Register Account';
        }, 4000);
      }
    });
  }

  // Clear any leftover Firebase user session when arriving on login page
  if (auth && window.location.pathname.includes('/login')) {
    try {
      signOut(auth).catch(() => {});
    } catch (_) {}
  }

  // ==========================================
  // 6. Continue with Google (Firebase Auth)
  // ==========================================
  const googleBtn = document.getElementById('btn-google-login');
  if (googleBtn) {
    googleBtn.addEventListener('click', async (e) => {
      e.preventDefault();
      if (!checkFirebaseConfigured()) return;

      googleBtn.disabled = true;
      const origContent = googleBtn.innerHTML;
      googleBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status"></span>Connecting to Google...';

      try {
        let userCred = null;
        try {
          userCred = await signInWithPopup(auth, googleProvider);
        } catch (popupErr) {
          if (popupErr.code === 'auth/popup-blocked') {
            await signInWithRedirect(auth, googleProvider);
            return;
          }
          throw popupErr;
        }

        if (userCred && userCred.user) {
          const idToken = await userCred.user.getIdToken();
          const selectedRole = document.querySelector('input[name="role"]:checked')?.value || null;
          const selectedName = document.getElementById('full_name')?.value?.trim() || null;
          const resp = await sendTokenToBackend({
            idToken,
            role: selectedRole,
            fullName: selectedName,
            rememberMe: true
          });

          if (resp.status === 'success' || resp.status === 'onboarding_required') {
            window.location.href = resp.redirect;
          } else {
            showAlert(resp.message || 'Google authorization error.');
            googleBtn.disabled = false;
            googleBtn.innerHTML = origContent;
          }
        }
      } catch (err) {
        showAlert(getFriendlyError(err));
        googleBtn.disabled = false;
        googleBtn.innerHTML = origContent;
      }
    });
  }

  // ==========================================
  // 7. Continue with GitHub (Backend OAuth)
  // ==========================================
  const githubBtn = document.getElementById('btn-github-login');
  if (githubBtn) {
    githubBtn.addEventListener('click', (e) => {
      e.preventDefault();
      githubBtn.disabled = true;
      githubBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status"></span>Connecting to GitHub...';

      const selectedRole = document.querySelector('input[name="role"]:checked')?.value;
      let targetUrl = '/auth/github/login';
      if (selectedRole) {
        targetUrl += '?role=' + encodeURIComponent(selectedRole);
      }
      window.location.href = targetUrl;
    });
  }

  // ==========================================
  // 8. Forgot Password Form
  // ==========================================
  const forgotForm = document.getElementById('forgot-password-form');
  if (forgotForm) {
    forgotForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const email = document.getElementById('email').value.trim();
      const submitBtn = document.getElementById('reset-btn');

      if (!email) {
        showAlert('Please enter your account email address.');
        return;
      }

      if (!checkFirebaseConfigured()) return;

      submitBtn.disabled = true;
      submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status"></span>Sending link...';

      try {
        await sendPasswordResetEmail(auth, email);
        showAlert(`Password reset instructions sent to ${email}. Check your inbox!`, 'success');
      } catch (err) {
        showAlert(getFriendlyError(err));
      } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = 'Send Reset Email';
      }
    });
  }

  // ==========================================
  // 9. Onboarding Form (Role Selection for OAuth)
  // ==========================================
  const onboardingForm = document.getElementById('onboarding-form');
  if (onboardingForm) {
    onboardingForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const fullName = document.getElementById('full_name').value.trim();
      const role = document.querySelector('input[name="role"]:checked')?.value || 'developer';
      const submitBtn = document.getElementById('onboarding-btn');

      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status"></span>Saving role...';
      }

      try {
        const resp = await fetch('/auth/complete-onboarding', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ fullName, role })
        });
        const data = await resp.json();
        if (data.status === 'success') {
          window.location.href = data.redirect;
        } else {
          showAlert(data.message || 'Error completing onboarding.');
        }
      } catch (err) {
        showAlert(err.message || 'Network error.');
      } finally {
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.innerHTML = 'Enter Workspace';
        }
      }
    });
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initAuth);
} else {
  initAuth();
}
