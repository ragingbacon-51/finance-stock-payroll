# Finance, Stock and Payroll System

A Django application for tracking business expenses, stock movements, employee attendance,
and monthly payroll approvals. Use invented data during development.

## Expense workflow

Signed-in users can submit expenses and view their own submissions. The `Accountant`,
`Manager`, and `Admin` groups can review submissions; submitters cannot approve their
own expenses. Rejections require a reason. Receipt files are limited to JPG, PNG, or
PDF files up to 5 MB and are downloaded through an authenticated view.

## Stock workflow

The `Storekeeper` and `Admin` groups can add products and record stock received or
issued. Stock history is append-only, and an issue cannot make the available balance
negative. The `Accountant` and `Manager` groups can view stock.

## Employees and attendance

The `Manager` and `Admin` groups can add and update employee records, including the
monthly salary used to create payroll drafts. The `Accountant`, `Manager`, and `Admin`
groups can view employee and attendance information.
Each employee's monthly salary has an uppercase 3-letter currency code.

Managers can record one attendance status per employee per day: Present, Absent, or
Leave. Clock-in/out times are optional for present records and can be entered together.
Corrections are audited. Attendance hours do not currently change salary calculations.

## Payroll workflow

The `Accountant` creates a monthly payroll draft for a selected currency code. Each
active employee paid in that currency is included, and their monthly salary is copied
into the draft as a snapshot. Separate runs can be created for separate currencies in
the same month. The accountant may add explained manual additions and deductions;
deductions cannot exceed salary plus additions.
Submitting sends the draft to a `Manager` for approval or return with a reason. The
accountant then records payment using a payment reference. The preparer cannot approve
their own run. Payment references cannot be reused.

The system checks the uppercase 3-letter currency-code format but does not verify codes
against an external registry, convert amounts, calculate statutory deductions, or
initiate bank payments. Use invented data until payroll rules and local requirements
have been checked.

## Privacy and uploaded receipts

The application includes a development-only privacy notice at `/privacy/` describing
the data stored and how it is used. Before handling real data, confirm hosting and
third-party disclosures, decide legally appropriate retention and
secure deletion periods, and arrange a review for applicable Kenyan requirements.
Receipts are not automatically deleted; no retention schedule is implemented.
Store receipt files privately: never expose `MEDIA_ROOT` or configure a public bucket.
The permission-checked download view does not protect a public storage URL.

## Run locally on Windows

1. Create and activate a virtual environment:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. Install dependencies and create your local environment file:

   ```powershell
   python -m pip install -r requirements.txt
   Copy-Item .env.example .env
   ```

3. Generate a private Django key and put it in `.env` as `SECRET_KEY`:

   ```powershell
   python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
   ```

4. Create the local database tables and run the development server:

   ```powershell
   python manage.py migrate
   python manage.py setup_roles
   python manage.py createsuperuser
   python manage.py runserver
   ```

Use the Django admin to assign users to the groups created by `setup_roles`. The
`Admin` group grants the project's custom management permissions, but Django admin
console access still requires a staff or superuser account.

Run the automated checks with:

```powershell
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
```

The local development configuration uses SQLite. Do not commit `.env`, real employee
information, receipts containing private data, or database backups. Before real payroll
use, confirm the applicable statutory rules and currency codes, configure production
hosting and database backups, and complete deployment security checks.

## Login and deployment security

Both the normal and admin login are limited to five failed attempts for the same
username and IP address, followed by a lockout of at least 15 minutes. Further failed
attempts during lockout can extend it. These records are stored in
the database; run `python manage.py migrate` after installing the dependencies.
This is not a general request-rate limiter. Configure an additional rate limit at the
hosting edge, and verify client IP handling before deploying behind a proxy; otherwise
the proxy's IP may be used for everyone. Only trust forwarded headers from a proxy
that strips untrusted incoming values.

For production, set `DEBUG=False`, a unique secret key of at least 50 characters,
explicit allowed hosts, secure private storage, and HTTPS. Set
`TRUST_PROXY_SSL_HEADER=True` only if a trusted reverse proxy strips incoming
`X-Forwarded-Proto` and sets it correctly. Review Django's deployment checks, database
security, backups, user access, and retention settings before going live. The local
development environment can continue to use `DEBUG=True`.