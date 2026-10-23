# EventPulse: University Event Feedback Automation & Analytics Platform

EventPulse is an enterprise-grade university event feedback automation platform designed to eliminate the manual, low-yield process of paper evaluation forms and generic shared links.

EventPulse automatically sends personalized feedback invitations to eligible registered students after a seminar, workshop, hackathon, cultural fest, or guest lecture concludes. It collects responses, guarantees privacy through verified anonymous modes, enforces deadlines, prevents duplicate voting with cryptographic single-use tokens, and aggregates reviews into actionable insights and sentiment themes for university management.

---

## Brand Identity & Design System

EventPulse follows a minimal, trustworthy academic aesthetic:
- **Main Background**: `#F8F7F2` (Ivory Cream)
- **Primary Navy**: `#172554` (Deep Academic Blue)
- **Gold Accent**: `#C6A76B` (Institutional Muted Gold)
- **Supporting**: White `#FFFFFF`, Main Text `#1F2937`, Secondary Text `#64748B`, Borders `#E5E7EB`
- **Status Indicators**: Success `#15803D`, Warning `#B45309`, Error `#B91C1C`

---

## Technology Stack

- **Backend**: Python 3.11+, Django 5.1, Django ORM, Django Templates, Django Forms
- **Frontend**: HTML5, Vanilla CSS3, Vanilla JavaScript, Bootstrap 5, Chart.js 4.4, Bootstrap Icons
- **Database**: SQLite for local development (`db.sqlite3`), PostgreSQL-ready
- **Email Subsystem**: Django email framework (Console backend for safe development; SMTP / SendGrid for production)
- **Analytics & NLP**: Built-in Python heuristic sentiment classifier and keyword theme extractor (works with zero API key dependencies, with optional LLM hook)
- **Security**: Cryptographic URL-safe tokens (`secrets.token_urlsafe`), CSRF protection, session hardening, database-level anonymity decoupling

---

## Quick Start Guide (Windows & Visual Studio Code)

### Prerequisites
- Python 3.10 or higher installed on Windows
- Visual Studio Code

### Step 1: Open the Project in VS Code
1. Launch **Visual Studio Code**.
2. Click **File** &rarr; **Open Folder...** and select the `feedback_automation` folder.
3. Open a new PowerShell terminal in VS Code: **Terminal** &rarr; **New Terminal** (`Ctrl + ` `~`).

### Step 2: Create & Activate Python Virtual Environment
```powershell
# Create the virtual environment in the project root
python -m venv .venv

# Activate the virtual environment
.venv\Scripts\activate
```
*(In VS Code, press `Ctrl + Shift + P`, type `Python: Select Interpreter`, and choose `Python 3.x (.venv)`).*

### Step 3: Install Required Dependencies
```powershell
python -m pip install -r requirements.txt
```

### Step 4: Apply Database Migrations
```powershell
python manage.py migrate
```

### Step 5: Seed Demonstration Data & Create Initial Admin
We have provided a comprehensive demo seeder that creates academic departments, staff accounts, enrolled students, completed events, and sample feedback reviews:
```powershell
python manage.py seed_demo_data
```

*(Alternatively, to create your own custom Super Administrator without hardcoding passwords):*
```powershell
python manage.py setup_admin --username admin --email admin@univ.edu --password YourSecurePassword123!
```

### Step 6: Start the Development Server
```powershell
python manage.py runserver
```
Open your browser to: **[http://127.0.0.1:8000](http://127.0.0.1:8000)**

---

## Pre-Configured Demonstration Accounts

| Role | Username | Password | Access Scope |
| :--- | :--- | :--- | :--- |
| **Super Administrator** | `admin` | `AdminUser@2026` | University-wide administration, user management, audit logs, system triggers |
| **University Administrator** | `univ_dean` | `DeanPass@2026` | Academic dean view: all departments, reports, student directory |
| **Department Administrator** | `prof_alan` | `ProfPass@2026` | Computer Science & Engineering department events and roster |
| **Event Organizer** | `organizer_jane` | `CoordPass@2026` | Assigned workshops, live responses, participant invitations |

---

## Key Workflows & Features

### 1. Public Experience
- **Landing Page (`/`)**: Hero banner, challenge overview, 3-step pipeline (Organize, Collect, Improve), stakeholder benefits, live preview card.
- **Features (`/features/`)**: Detailed capability breakdown.
- **How It Works (`/how-it-works/`)**: Visual 5-step operational loop.
- **About (`/about/`) & Contact (`/contact/`)**: Academic mission statement and support desk inquiry form.

### 2. Multi-Step Event Creation & Default Form Generation
- Go to **Events** &rarr; **Create New Event**.
- Complete Title, Category (Seminar, Workshop, Hackathon, Cultural, etc.), Department, Schedule, Feedback Deadline, and Feedback Privacy Mode.
- Upon saving, EventPulse automatically generates a complete 9-question institutional evaluation form (5-star ratings, duration assessment, suggestions, recommendation check).

### 3. Student Roster CSV Batch Import
- Navigate to **Students** &rarr; **Import Students CSV**.
- Download the built-in sample CSV template (`/portal/students/sample-csv/`).
- Upload your CSV: EventPulse validates headers, checks email formats, deduplicates by Student ID, and reports successful and skipped row counts.

### 4. Feedback Automation & Delivery Engine
- **Manual Trigger**: Under any event or on the dashboard, click **Dispatch Invitations Now** or **Run Automation Check**.
- **Automated Scheduler**: Run the periodic management command:
  ```powershell
  python manage.py run_feedback_automations
  ```
  This command inspects finished events, generates unique URL-safe single-use tokens (`/feedback/submit/<token>/`), prints emails to the console (in development mode), checks deadlines, and sends reminders to non-respondents.

### 5. Verified Privacy & Anonymous Mode
- In **Anonymous Mode**, responses are decoupled at the database level:
  `FeedbackResponse.student = NULL`
- The invitation token is marked `COMPLETED` when submitted, strictly preventing duplicate voting while ensuring complete student anonymity.

### 6. Built-in NLP Sentiment & Theme Synthesis
- Runs automatically when students submit feedback or can be re-run via services.
- Classifies comments into **Positive Praise**, **Common Complaints**, and **Actionable Suggestions**.
- Generates an **Executive Summary** paragraph displayed directly on event feedback dashboards and exports.

### 7. Executive CSV Reports & Exports
- **Event Feedback CSV**: Full breakdown of individual responses with student identities protected.
- **University Satisfaction Audit CSV**: Cross-department metrics, response rates, and mean satisfaction.

---

## Operating System Scheduler Configuration (Windows Task Scheduler)

To run the feedback automation script every 15 minutes automatically on Windows:
1. Open **Windows Task Scheduler** (`taskschd.msc`).
2. Click **Create Basic Task...**, name it `EventPulse_Automation_Runner`.
3. Set Trigger to **Daily**, repeating every **15 minutes**.
4. Set Action to **Start a program**:
   - **Program/script**: `C:\Users\prabh\OneDrive\Attachments\Desktop\feedback_automation\.venv\Scripts\python.exe`
   - **Add arguments**: `manage.py run_feedback_automations`
   - **Start in**: `C:\Users\prabh\OneDrive\Attachments\Desktop\feedback_automation`
5. Click **Finish**.

---

## Email Configuration

In development, emails are routed to the **Django Console Backend** (`.env` setting `EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend`). All feedback invitation emails will be printed directly in your terminal.

For production email delivery via SMTP or SendGrid, update your `.env` file:
```env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.sendgrid.net
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=apikey
EMAIL_HOST_PASSWORD=your_production_smtp_password
DEFAULT_FROM_EMAIL=EventPulse Notifications <notifications@youruniversity.edu>
```

---

## Running Automated Tests

Run the automated test suite covering authentication, event workflows, student CSV imports, token generation, duplicate prevention, anonymous protections, deadline enforcement, NLP sentiment heuristics, and CSV exports:
```powershell
.venv\Scripts\activate
python manage.py test tests
```
*(All 10 tests should pass with `OK`).*
