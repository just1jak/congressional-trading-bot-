import os
import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, inspect, text

st.set_page_config(page_title="Congressional Trades — Data Explorer", layout="wide")

st.title("Congressional Trades — Data Explorer")

# Default DB URI (relative to repo root)
default_db = "sqlite:///data/congressional_trades.db"
db_uri = st.text_input("Database URI (sqlite or SQLAlchemy URI)", value=default_db)

@st.cache_resource
def create_engine_safe(uri):
    try:
        engine = create_engine(uri)
        # quick test
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return engine
    except Exception as e:
        st.error(f"Could not connect to database: {e}")
        return None

engine = create_engine_safe(db_uri)
if engine is None:
    st.stop()

@st.cache_resource
def list_tables(_engine):
    inspector = inspect(_engine)
    return inspector.get_table_names()

tables = list_tables(engine)
if not tables:
    st.warning("No tables found in the database.")
    st.stop()

col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("Tables")
    table = st.selectbox("Choose a table", tables)
    st.write(tables)

with col2:
    st.subheader("Quick stats")
    try:
        row_count = pd.read_sql_query(f"SELECT COUNT(*) AS c FROM \"{table}\"", engine).iloc[0, 0]
        st.metric("Rows", int(row_count))
    except Exception:
        st.info("Could not fetch row count for this table.")

@st.cache_data
def load_sample(_engine, table, limit=1000):
    q = text(f"SELECT * FROM \"{table}\" LIMIT :limit")
    return pd.read_sql_query(q, _engine, params={"limit": limit})

limit = st.slider("Sample rows", min_value=50, max_value=5000, value=500, step=50)
df = load_sample(engine, table, limit=limit)

st.subheader("Sample rows")
st.dataframe(df)

st.subheader("Columns")
st.write(list(df.columns))

# Attempt to detect a date-like column
date_candidates = [c for c in df.columns if "date" in c.lower() or "transaction" in c.lower() or "time" in c.lower()]
if date_candidates:
    date_col = st.selectbox("Choose date column for time series", date_candidates)
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df_time = df.dropna(subset=[date_col])
    if not df_time.empty:
        df_time["year"] = df_time[date_col].dt.year
        counts = df_time.groupby("year").size().reset_index(name="count").sort_values("year")
        st.subheader("Rows by year (sample)")
        st.bar_chart(data=counts.set_index("year")["count"])
    else:
        st.info("No non-null dates found in the selected column in the sample.")
else:
    st.info("No obvious date-like columns detected. Inspect `Columns` above.")

# Top categorical columns (e.g., ticker)
if "ticker" in df.columns:
    st.subheader("Top tickers (sample)")
    top = df["ticker"].value_counts().head(20)
    st.bar_chart(top)
else:
    # try to find short-string columns as candidates
    str_cols = [c for c in df.columns if df[c].dtype == object]
    if str_cols:
        pick = st.selectbox("Choose a categorical column to view top values", str_cols)
        st.subheader(f"Top values for {pick}")
        st.bar_chart(df[pick].value_counts().head(20))

st.subheader("Run custom SQL")
query = st.text_area("SQL query", value=f"SELECT * FROM \"{table}\" LIMIT 100")
if st.button("Run query"):
    try:
        qdf = pd.read_sql_query(text(query), engine)
        st.write(qdf)
        st.download_button("Download CSV", qdf.to_csv(index=False), file_name=f"query_{table}.csv")
    except Exception as e:
        st.error(f"Query failed: {e}")
