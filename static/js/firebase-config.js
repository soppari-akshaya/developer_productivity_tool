/**
 * Firebase JavaScript SDK Initializer (ES Module)
 * Initializes Firebase Web App once using public configuration.
 */
import { initializeApp, getApps, getApp } from "https://www.gstatic.com/firebasejs/10.14.1/firebase-app.js";
import { 
  getAuth, 
  GoogleAuthProvider, 
  GithubAuthProvider,
  signInWithPopup,
  signInWithRedirect,
  getRedirectResult,
  createUserWithEmailAndPassword,
  signInWithEmailAndPassword,
  signOut,
  sendPasswordResetEmail,
  updateProfile,
  onAuthStateChanged
} from "https://www.gstatic.com/firebasejs/10.14.1/firebase-auth.js";
import { getAnalytics, isSupported } from "https://www.gstatic.com/firebasejs/10.14.1/firebase-analytics.js";

// Read configuration injected from Flask backend with defaults
const config = window.__FIREBASE_CONFIG__ || {
  apiKey: "AIzaSyCOOiovwe9W4hO1-Mz7GFCaaguMplMEgpU",
  authDomain: "developer-productivity-t-73574.firebaseapp.com",
  projectId: "developer-productivity-t-73574",
  storageBucket: "developer-productivity-t-73574.firebasestorage.app",
  messagingSenderId: "46929920283",
  appId: "1:46929920283:web:0158a55c6ebda9f3d353be",
  measurementId: "G-V7CH9ER661"
};

// Check if valid API key is present
export const isConfigured = Boolean(config.apiKey && config.apiKey.length > 5 && !config.apiKey.includes("your-api-key"));

let app = null;
let auth = null;
let analytics = null;
let googleProvider = null;
let githubProvider = null;

if (isConfigured) {
  try {
    app = getApps().length === 0 ? initializeApp(config) : getApp();
    auth = getAuth(app);

    // Setup OAuth Providers
    googleProvider = new GoogleAuthProvider();
    googleProvider.setCustomParameters({ prompt: 'select_account' });

    githubProvider = new GithubAuthProvider();
    githubProvider.addScope('read:user');
    githubProvider.addScope('user:email');

    // Setup Analytics if supported
    if (config.measurementId) {
      isSupported().then(supported => {
        if (supported) {
          analytics = getAnalytics(app);
        }
      }).catch(err => {
        console.debug("Firebase analytics not supported in this environment:", err);
      });
    }
  } catch (err) {
    console.error("Firebase SDK initialization error:", err);
  }
}

export {
  app,
  auth,
  analytics,
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
  onAuthStateChanged
};
