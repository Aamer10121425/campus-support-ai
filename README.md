
# Campus Support AI

An AI-assisted campus support workflow system designed to help students and faculty submit requests, retrieve policy-grounded information, track ticket resolution, and identify routing or service-level issues.

## Features

- REST API built with FastAPI
- PostgreSQL database with SQLAlchemy
- Ticket listing, filtering, and detail retrieval
- Knowledge article search and policy-source information
- Ticket statistics and operational metrics
- Audit checks for expired citations, unauthorized routing, unsupported responses, overdue tickets, and possible missed escalations
- Seeded demonstration dataset and data validation
- Automated API tests using pytest

## Technology Stack

- Python
- FastAPI
- PostgreSQL
- SQLAlchemy
- pytest
- HTTPX / FastAPI TestClient

## Project Structure

```text
campus-support-ai/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── db.py
│   │   └── models.py
│   ├── tests/
│   │   └── test_api.py
│   ├── create_tables.py
│   ├── generate_data.py
│   ├── validate_data.py
│   ├── requirements.txt
│   └── .gitignore
└── README.md
```

## Setup

1. Install Python and PostgreSQL.
2. Create a PostgreSQL database named `campus_support_ai`.
3. Configure the database connection in `backend/.env`.
4. Open a terminal in the `backend` directory.
5. Install dependencies:

   ```powershell
   python -m pip install -r requirements.txt
   ```

6. Create the database tables:

   ```powershell
   python create_tables.py
   ```

7. Generate the demonstration dataset:

   ```powershell
   python generate_data.py
   ```

8. Validate the dataset:

   ```powershell
   python validate_data.py
   ```

9. Start the API:

   ```powershell
   python -m uvicorn app.main:app --reload
   ```

10. Open `http://127.0.0.1:8000/docs` to explore the API.

Use your virtual environment's Python executable if your environment is not activated.

## API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/` | API information |
| GET | `/health` | Health check |
| GET | `/db-test` | Database connectivity check |
| GET | `/tickets` | List and filter tickets |
| GET | `/tickets/{ticket_id}` | Retrieve ticket details |
| GET | `/articles` | Search knowledge articles |
| GET | `/articles/{article_id}` | Retrieve article and policy-source information |
| GET | `/stats` | Ticket and operational statistics |
| GET | `/audit` | Run diagnostic audit checks |

## Running Tests

From the `backend` directory:

```powershell
python -m pytest -v
```

The initial test run completed with 8 tests passed.

## Audit Limitations

The audit endpoint reports potential issues for review. Overdue-ticket and missed-escalation findings use simplified time calculations and should not be treated as confirmed violations of business-hours SLA policies without further verification.

## Security

- Keep `.env` and database credentials private.
- Do not commit the virtual environment or Python cache files.
- Configure database credentials through environment variables.

## Status

The current implementation provides a working backend, a seeded demonstration dataset, data validation, diagnostic audit checks, and automated API tests.
