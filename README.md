# Pramod Headlines — Hindi News Portal

## Features
- Public Hindi news homepage, search, article pages and WhatsApp sharing.
- Only the admin phone `+919454102368` can request an SMS OTP.
- OTP is verified through **Twilio Verify**; no public sign-up exists.
- Admin can publish news with a title, category, summary, full story and photo.
- Visitors can read and share; they cannot publish or edit news.
- SQLite database; uploaded images are stored in `static/uploads/`.

## Run locally
1. Install Python 3.10+.
2. Create and activate a virtual environment.
3. Install packages: `pip install -r requirements.txt`
4. Copy `.env.example` values into your environment (or Replit Secrets).
5. Set a strong `SECRET_KEY`, and add your real Twilio credentials:
   - `TWILIO_ACCOUNT_SID`
   - `TWILIO_AUTH_TOKEN`
   - `TWILIO_VERIFY_SERVICE_SID` (the Verify Service SID beginning with `VA`)
   - `ADMIN_PHONE=+919454102368`
6. Start: `python app.py`
7. Open `http://127.0.0.1:5000`

## Replit setup
- Upload/extract this project into a Python Repl.
- Add the environment variables above under **Secrets** (never paste credentials into source code).
- Run `pip install -r requirements.txt`, then `python app.py`.
- For a public HTTPS deployment set `COOKIE_SECURE=true`.
- Make sure the Twilio Verify service is enabled for SMS and your Twilio account can send to the admin number.

## Security / deployment notes
- Change `SECRET_KEY` to a long random value.
- Keep Twilio credentials only in environment variables / Replit Secrets.
- Use HTTPS in production and set `COOKIE_SECURE=true`.
- Restrict who can access Replit project secrets and deployment controls.
- Back up `news.db` and `static/uploads/`.
- This starter project intentionally has no visitor account registration.
- Admin phone restriction is checked on the server, not just hidden in the page.
