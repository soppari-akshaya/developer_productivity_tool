# Developer Productivity Tool 🚀

A complete, production-grade, web-based platform designed to help individual software engineers and engineering teams manage projects, sprint tasks, code snippets, time tracking, Pomodoro deep-work intervals, bugs, and productivity analytics in one centralized workspace.

---

## 🛠️ Mandatory Technology Stack

This application strictly conforms to your technology requirements:

- **Frontend**: HTML5, CSS3, Vanilla JavaScript, Bootstrap 5, Font Awesome 6 icons.
- **Backend**: Python 3.10+, Flask, Flask Blueprints.
- **Database**: SQLite with Flask-SQLAlchemy (SQLAlchemy ORM).
- **Authentication**: Firebase Authentication (Client SDK via browser ES modules) and Firebase Admin SDK for Python.
- **Session Security**: Flask-Login session management with HttpOnly, SameSite cookies and Flask-WTF CSRF protection.
- **Code Editor**: CodeMirror with syntax highlighting, clear, download, and sandboxed runner simulation.
- **Productivity Analytics**: Chart.js for velocity, task status, and working hours distribution.

> **Strict Compliance**: Zero React, zero Vue, zero Angular, zero TypeScript, zero Firestore, zero Node.js backend. No build process required.

---

## 📁 Project Architecture

```
developer_productivity_tool/
│
├── app.py                      # Flask Application factory, blueprints & initial database seeder
├── config.py                   # Configuration & SQLite URI normalization
├── extensions.py               # SQLAlchemy, LoginManager, CSRFProtect & @role_required decorator
├── models.py                   # 14 SQLAlchemy Models (Users, Projects, Tasks, Snippets, etc.)
├── requirements.txt            # Python dependencies
├── .env                        # Active environment variables
├── .env.example                # Template for Firebase and App settings
├── .gitignore                  # Git ignore rules for instance, uploads, secrets & pycache
│
├── auth/                       # Authentication Blueprint
│   ├── __init__.py
│   ├── routes.py               # Split-screen Login, Register, Forgot Password, Onboarding, Token Verify
│   └── services.py             # Role-based dashboard URL resolver, User profile creator, Activity logger
│
├── admin/                      # Admin Blueprint (@role_required('admin'))
│   ├── __init__.py
│   └── routes.py               # Admin Dashboard, User Role Management, Project Audit, System Reports
│
├── team_leader/                # Team Leader Blueprint (@role_required('team_leader', 'admin'))
│   ├── __init__.py
│   └── routes.py               # Leader Dashboard, Team Members, Task Allocations, Work Log Reviews
│
├── developer/                  # Developer Blueprint (@role_required('developer', 'team_leader', 'admin'))
│   ├── __init__.py
│   └── routes.py               # Workspace, CodeMirror Editor, Time Tracker, Pomodoro Timer, Work Logs
│
├── projects/                   # Project Management Blueprint (CRUD)
│   ├── __init__.py
│   └── routes.py
│
├── tasks/                      # Task Management Blueprint (CRUD, Comments, Status Transitions)
│   ├── __init__.py
│   └── routes.py
│
├── snippets/                   # Code Snippet Manager Blueprint (Search, Language Filters, Favorites)
│   ├── __init__.py
│   └── routes.py
│
├── issues/                     # Bug & Issue Tracker Blueprint (Severity, Priority, Resolutions)
│   ├── __init__.py
│   └── routes.py
│
├── reports/                    # Analytics & Chart.js API Blueprint
│   ├── __init__.py
│   └── routes.py               # Chart data endpoints & CSV Task export
│
├── integrations/               # External Integrations
│   ├── __init__.py
│   ├── firebase_auth.py        # Firebase Admin SDK token verification with resilient fallback
│   └── github.py               # GitHub API client
│
├── templates/                  # Jinja2 HTML Templates
│   ├── base.html               # Shared layout, navbar, sidebar, theme toggle, and flash alerts
│   ├── login.html              # Equal 50/50 Split-Screen Login Page
│   ├── register.html           # Equal 50/50 Split-Screen Registration with Strength Meter
│   ├── onboarding.html         # First-Time Google/GitHub OAuth Role Selection Onboarding
│   ├── forgot_password.html    # Password Reset via Firebase
│   ├── admin/                  # Admin Dashboard, User Governance & System Reports
│   ├── team_leader/            # Leader Dashboard, Member Roster & Standup Reviews
│   ├── developer/              # Developer Workspace, CodeMirror Editor, Time Tracker, Pomodoro, Logs
│   ├── projects/               # Projects List, Detail, Create, Edit
│   ├── tasks/                  # Tasks List, Detail, Create
│   ├── snippets/               # Code Snippet Vault (List, Create, Edit)
│   ├── issues/                 # Bug Tracker (List, Create, Status Transitions)
│   └── reports/                # Chart.js Analytics & Export
│
├── static/
│   ├── css/
│   │   └── style.css           # 50/50 Split-screen layout, custom cards, dark/light theme variables
│   └── js/
│       ├── firebase-config.js  # Firebase v10 Modular browser ES SDK
│       ├── auth.js             # Email/Password, Google popup, GitHub popup, strength meter
│       ├── main.js             # Theme toggle (Light/Dark) & clipboard copy
│       ├── editor.js           # CodeMirror editor controller & runner sandbox
│       ├── timer.js            # Live Stopwatch & working hours logger
│       ├── pomodoro.js         # 25m Focus / 5m Break Pomodoro timer
│       └── charts.js           # Chart.js visualizer
│
├── instance/
│   └── developer_productivity.db # SQLite Application Database (Auto-created and seeded)
├── uploads/                    # Secure file uploads folder
├── secrets/
│   └── firebase-service-account.json # Firebase Admin SDK credentials
└── tests/
    └── test_app.py             # Automated unit test suite verifying all 20 requirements
```

---

## 🚀 Quick Start Guide (Windows PowerShell / VS Code)

### 1. Run with Python
From the project directory:
```powershell
python app.py
```
*(Or if multiple Python versions are installed)*:
```powershell
& "C:\Users\Akshaya\AppData\Local\Programs\Python\Python310\python.exe" app.py
```

Open your browser to:
**`http://localhost:5000`**

### 2. Run Automated Test Suite
```powershell
python -m unittest tests/test_app.py
```
*(All 10 test suites covering registration, role redirection, RBAC route protection, onboarding, CRUD, and logout pass with 100% success).*

---

## 👥 Seeded Demonstration Accounts

The SQLite database is pre-seeded with initial demonstration accounts:

| Role | Email | Password | Assigned Dashboard |
| :--- | :--- | :--- | :--- |
| **Admin** | `admin@devproductivity.com` | `Password123!` | `/admin/dashboard` |
| **Team Leader** | `leader@devproductivity.com` | `Password123!` | `/team-leader/dashboard` |
| **Developer** | `dev@devproductivity.com` | `Password123!` | `/developer/dashboard` |

---

## 🔒 Firebase Configuration & Setup Instructions

The application is pre-configured for your Firebase project: `developer-productivity-t-73574`.

### A. Frontend Web App Keys
In `.env`:
```env
FIREBASE_API_KEY=your_firebase_web_api_key
FIREBASE_AUTH_DOMAIN=developer-productivity-t-73574.firebaseapp.com
FIREBASE_PROJECT_ID=developer-productivity-t-73574
FIREBASE_STORAGE_BUCKET=developer-productivity-t-73574.appspot.com
FIREBASE_MESSAGING_SENDER_ID=your_messaging_sender_id
FIREBASE_APP_ID=your_firebase_app_id
```

Where to get them:
1. Go to [Firebase Console](https://console.firebase.google.com/) &rarr; Select project **`developer-productivity-t-73574`**.
2. Click the gear icon ⚙️ &rarr; **Project settings** &rarr; **General** tab.
3. Under **Your apps**, click your Web app (or click `</>` to register one).
4. Copy the `apiKey`, `appId`, and `messagingSenderId` values into `.env`.

### B. Firebase Admin SDK Service Account
1. In Firebase Console &rarr; **Project settings** &rarr; **Service accounts** tab.
2. Click **Generate new private key**.
3. Save the downloaded JSON file into the project folder at:
   `secrets/firebase-service-account.json`

### C. Enable Sign-in Providers
In Firebase Console &rarr; **Authentication** &rarr; **Sign-in method**:
1. **Email/Password**: Enable and click Save.
2. **Google**: Enable, choose support email, and click Save.
3. **GitHub**:
   - Authorized callback URL in Firebase:
     `https://developer-productivity-t-73574.firebaseapp.com/__/auth/handler`
   - In GitHub &rarr; **Settings** &rarr; **Developer Settings** &rarr; **OAuth Apps** &rarr; **New OAuth App**:
     - **Application Name**: `Developer Productivity Tool`
     - **Homepage URL**: `http://localhost:5000`
     - **Authorization Callback URL**: `https://developer-productivity-t-73574.firebaseapp.com/__/auth/handler`
   - Copy GitHub **Client ID** and **Client Secret** into Firebase Console GitHub provider dialog and click Save.

---

## 🛡️ Security & Role-Based Access Control (RBAC)

1. **Backend Verification**: Frontend Firebase tokens are transmitted to `/auth/verify-token` and verified on the Flask backend using Firebase Admin SDK. UIDs and emails are never trusted from raw client form inputs.
2. **Session Integrity**: Uses Flask-Login sessions with `HttpOnly`, `SameSite='Lax'`, and CSRF token protection.
3. **Strict Role Separation**:
   - The `@role_required` decorator restricts access to unauthorized URLs.
   - Developers attempting to visit `/admin/dashboard` are redirected to `/developer/dashboard` with a warning alert.
   - Public registration only permits `developer` or `team_leader` roles. Admin role self-assignment is strictly blocked.
   - Admin accounts can only be created or assigned through administrative elevation in `/admin/users`.
