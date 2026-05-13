"""PostgreSQL schema management for HRV feature storage."""

import re

import psycopg2


def _validate_identifier(name: str) -> None:
    """Raise an error if ``name`` is not a safe SQL identifier.

    Accepts only names composed of ASCII letters, digits, and underscores,
    starting with a letter or underscore. This prevents SQL injection when
    an identifier is interpolated directly into a query string.

    Args:
        name: The SQL identifier to validate (table name, column name, etc.).

    Raises:
        ValueError: If ``name`` contains characters outside ``[a-zA-Z0-9_]``
            or starts with a digit.

    """
    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", name):
        raise ValueError(f"Invalid SQL identifier: {name!r}")


def create_hrv_table(
    host: str,
    database: str,
    user: str,
    password: str,
    table_name: str = "hrv_features",
    include_fields: list[str] | None = None,
    exclude_fields: list[str] | None = None,
    extra_columns: dict[str, str] | None = None,
) -> None:
    """Create an HRV features table in a PostgreSQL database.

    Builds a ``CREATE TABLE IF NOT EXISTS`` statement from the default HRV
    field set, applies optional inclusions/exclusions, appends any custom
    columns, and executes the statement against the target database.

    Default columns: ``user_id``, ``date``, ``rmssd``, ``ln_rmssd``,
    ``sdnn``, ``pnn50``, ``mean_hr``, ``vlf``, ``lf``, ``hf``, ``lf_hf``,
    ``hf_pct``, ``lf_nu``, ``hf_nu``. An auto-increment ``id`` primary key
    is always added.

    Args:
        host: Database server hostname or IP address.
        database: Name of the target database.
        user: PostgreSQL username.
        password: PostgreSQL password.
        table_name: Name of the table to create. Must be a valid SQL
            identifier. Defaults to ``"hrv_features"``.
        include_fields: If provided, only the listed field names are included
            from the default set. Mutually exclusive with ``exclude_fields``
            in intent, though both can be applied sequentially.
        exclude_fields: Field names to remove from the default set before
            creating the table.
        extra_columns: Additional columns as a mapping of
            ``{column_name: sql_type}``, appended after the default fields.

    Raises:
        ValueError: If ``table_name`` is not a valid SQL identifier.
        psycopg2.Error: If the connection fails or the SQL statement is
            rejected by the server.

    """
    _validate_identifier(table_name)

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
