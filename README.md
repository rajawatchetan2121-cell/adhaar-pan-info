# ID Document Verification — Flask + SQLite

Upload an Aadhaar or PAN card photo → OCR reads it in the browser → you verify
the fields → it's saved to a real SQLite database via a Flask API.

## Setup

```bash
cd idverify-flask
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open **http://127.0.0.1:5000** in your browser.

A `documents.db` SQLite file is created automatically next to `app.py` on
first run — no manual database setup needed.

## How it fits together

- **OCR** runs entirely in the browser (Tesseract.js) — no image is uploaded
  to the server, only the fields you confirm.
- **Validation** checks the OCR text contains the right ID-number pattern
  *and* document wording (e.g. "UIDAI" for Aadhaar, "Income Tax" for PAN)
  before letting you proceed to the verify screen.
- **Save** sends the confirmed fields as JSON to `POST /api/records`, which
  writes a row to the `document_record` table in SQLite.
- **Dashboard** loads records from `GET /api/records` (supports `?q=` search
  by name or ID number) and deletes via `DELETE /api/records/<id>`.

## API

| Method | Route                  | Purpose                          |
|--------|-------------------------|-----------------------------------|
| GET    | `/api/records?q=`      | List records, optional search     |
| POST   | `/api/records`         | Save a verified record            |
| DELETE | `/api/records/<id>`    | Delete a record                   |

## Moving beyond SQLite

SQLite is fine for a personal project. If you later want Postgres/MySQL,
change one line in `app.py`:

```python
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://user:pass@localhost/dbname'
```

and `pip install psycopg2-binary` (or `pymysql` for MySQL) — the models and
API routes don't need to change.

## Note on sensitive data

Aadhaar and PAN numbers are sensitive personal data. This project stores them
in plain text for simplicity. Before using it with real documents, consider:
- Masking Aadhaar to the last 4 digits in the UI/DB
- Encrypting the `id_number` column at rest
- Adding basic auth in front of the API so `/api/records` isn't public
