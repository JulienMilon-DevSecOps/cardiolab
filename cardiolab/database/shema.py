import psycopg2


def create_hrv_table(
    host: str,
    database: str,
    user: str,
    password: str,
    table_name: str = "hrv_features",
    include_fields: list[str] | None = None,
    exclude_fields: list[str] | None = None,
    extra_columns: dict[str, str] | None = None,
):
    """
    FR :
    Crée une table HRV dans PostgreSQL avec configuration flexible :
    - choix des colonnes
    - exclusion de colonnes
    - ajout de colonnes personnalisées

    EN :
    Creates an HRV table in PostgreSQL with flexible configuration:
    - column selection
    - column exclusion
    - custom columns
    """

    base_fields = {
        "user_id": "TEXT",
        "date": "DATE",
        "rmssd": "FLOAT",
        "ln_rmssd": "FLOAT",
        "sdnn": "FLOAT",
        "pnn50": "FLOAT",
        "mean_hr": "FLOAT",
        "vlf": "FLOAT",
        "lf": "FLOAT",
        "hf": "FLOAT",
        "lf_hf": "FLOAT",
        "hf_pct": "FLOAT",
        "lf_nu": "FLOAT",
        "hf_nu": "FLOAT",
    }

    fields = base_fields.copy()

    if include_fields:
        fields = {k: v for k, v in fields.items() if k in include_fields}

    if exclude_fields:
        for f in exclude_fields:
            fields.pop(f, None)

    if extra_columns:
        fields.update(extra_columns)

    columns_sql = ",\n".join([f"{k} {v}" for k, v in fields.items()])

    query = f"""
    CREATE TABLE IF NOT EXISTS {table_name} (
        id SERIAL PRIMARY KEY,
        {columns_sql}
    );
    """

    conn = psycopg2.connect(
        host=host, database=database, user=user, password=password
    )

    cur = conn.cursor()
    cur.execute(query)
    conn.commit()

    cur.close()
    conn.close()