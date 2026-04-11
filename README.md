# Budget Manager

A Flask-based personal finance tracker for managing income, expenses, categories, and monthly budgets. The project includes OTP-based account verification and password reset, transaction filtering and CSV export, dashboard charts, and budget alerts for a simple end-to-end money management workflow.

## Overview

This project was built to make everyday money tracking simpler. Instead of only storing transactions, it provides a complete workflow for:

- create an account and log in securely
- verify signup with OTP
- reset passwords with OTP
- manage income and expense categories
- add, edit, filter, and export transactions
- create monthly budgets
- monitor budget usage with progress bars and alerts
- view dashboard analytics for financial trends

## Highlights

- OTP-based signup verification and password reset
- category and budget management with validation rules
- searchable, filterable transaction history with CSV export
- dashboard analytics powered by Chart.js
- modular Flask structure using blueprints

## Tech Stack

- Backend: Flask
- Database: SQLite
- Frontend: HTML, Jinja2 templates, Bootstrap 5, CSS
- Charts: Chart.js
- Authentication: Flask sessions + Werkzeug password hashing
- Email/OTP: Python `smtplib` and `email.message`

## Features

### Authentication

- User registration and login
- OTP-based signup verification
- Forgot password and reset password flow with OTP
- Session-protected routes using a reusable `login_required` decorator
- Password hashing with Werkzeug

### Dashboard

- Total income, total expense, and net balance cards
- Current month income and expense summary
- Income vs expense chart for the last 6 months
- Expense breakdown by category for the current month
- Budget alerts when spending exceeds the configured monthly limit

### Categories

- Separate category types for `income` and `expense`
- Duplicate prevention using validation and a unique index
- Soft delete through archived categories
- Restore archived categories
- Permanent delete only when no linked transactions exist

### Transactions

- Create, edit, and delete transactions
- Positive amount validation
- Future date prevention
- Search by description or category
- Filter by category, type, date range, and amount range
- Pagination for transaction history
- CSV export for filtered results

### Budgets

- Create monthly budgets for expense categories
- Edit and delete budgets
- Duplicate budget prevention for the same month/category
- Budget usage progress bars
- Visual status indicators: on track, near limit, over limit
- Remaining amount, spent amount, and transaction count

## Suggested Screenshots

If you want to make the repository page stronger, add screenshots for:

- Login page
- OTP verification page
- Dashboard with charts
- Transactions page with filters
- Budgets page showing progress bars and alerts
- Archived categories page

## Project Structure

```text
finance_app/
├── app.py
├── auth.py
├── budgets.py
├── categories.py
├── dashboard.py
├── db.py
├── transactions.py
├── static/
│   └── app.css
└── templates/
    ├── base.html
    ├── home.html
    ├── login.html
    ├── create_user.html
    ├── verify_signup_otp.html
    ├── forgot_password.html
    ├── reset_password.html
    ├── categories.html
    ├── archived_categories.html
    ├── transactions.html
    ├── budgets.html
    └── ...
```

## How It Works

- `app.py` creates the Flask app and registers all blueprints.
- `auth.py` handles login, signup, OTP verification, and password reset.
- `dashboard.py` calculates totals, monthly summaries, chart data, and budget alerts.
- `categories.py` manages active and archived categories.
- `transactions.py` handles transaction CRUD, filtering, pagination, and export.
- `budgets.py` handles monthly budget creation, editing, tracking, and deletion.
- `db.py` connects to SQLite, enables foreign keys, and sets up OTP-related tables and indexes.

## Database Tables

The local SQLite database includes these tables:

- `users`
- `categories`
- `transactions`
- `budgets`
- `pending_user_otps`
- `password_reset_otps`

## Local Setup

### 1. Clone the project

```bash
git clone <your-repo-url>
cd finance_app
```

### 2. Create and activate a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Create your local environment file

```bash
cp .env.example .env
```

Then update `FLASK_SECRET_KEY` in `.env` with your own secure value before pushing or deploying.

### 4. Install dependencies

```bash
pip install flask werkzeug
```

### 5. Run the app

```bash
python app.py
```

The app runs on:

```text
http://127.0.0.1:9000
```

## Optional Email Configuration

OTP emails work through SMTP if these environment variables are set in `.env`:

```bash
FLASK_SECRET_KEY="your_secret_key"
SMTP_HOST="smtp.example.com"
SMTP_PORT="587"
SMTP_USERNAME="your_email@example.com"
SMTP_PASSWORD="your_password"
SMTP_FROM_EMAIL="your_email@example.com"
```

If SMTP is not configured, OTP codes are printed in the server terminal for local development.

## Implementation Notes

- Local secrets are loaded from `.env`, while `.env.example` provides the GitHub-safe template.
- Bootstrap and Chart.js are loaded through CDN links in the templates.
- SQLite is used for simplicity and local development.

## Future Improvements

- recurring transactions
- downloadable monthly PDF reports
- profile editing and password change inside account settings
- deployment with environment-based configuration
- unit tests and integration tests
- richer dashboard analytics and trend insights

## Author

Lakshay Guleria
