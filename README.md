# QuickCart
A multi-role local grocery delivery platform (mini-Blinkit).
**Roles:** Customer - Shop Owner - Delivery Partner - Admin
## Stack
- FastAPI + SQLAlchemy 2.0 (async) + Alembic
- PostgreSQL 16 + Redis 7 (Docker)
- Jinja2 + HTMX + TailwindCSS
- Razorpay, MSG91, Resend
## Quick start
    cp .env.example .env
    # Edit .env and set SECRET_KEY
    python -m venv .venv
    .venv\Scripts\activate
    pip install -r requirements.txt
    docker compose up -d
    alembic upgrade head
    uvicorn app.main:app --reload
Visit http://localhost:8000/api/v1/health