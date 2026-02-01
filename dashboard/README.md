# Dashboard

This small Streamlit app lets you explore the project's SQLite database (`data/congressional_trades.db`).

Usage

1. Create and activate your virtualenv (optional but recommended):

```bash
python3 -m venv venv
source venv/bin/activate
```

2. Install requirements (from repo root):

```bash
pip install -r dashboard/requirements.txt
```

3. Run the app (from repo root):

```bash
streamlit run dashboard/app.py
```

4. Use the Database URI input to point to a different DB if needed (example: `sqlite:///data/congressional_trades.db`).
