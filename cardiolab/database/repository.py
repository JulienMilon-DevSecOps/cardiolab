"""PostgreSQL repository for reading HRV session records."""

import re

from psycopg2 import connect, sql

from cardiolab.protocols.resting import HRVFeatures


def _validate_identifier(name: str) -> None:
    """Raise an error if ``name`` is not a safe SQL identifier.

    Accepts only names composed of ASCII letters, digits, and underscores,
    starting with a letter or underscore. This prevents SQL injection when
    an identifier is interpolated directly into a query string.

    Args:
        name: The SQL identifier to validate.

    Raises:
        ValueError: If ``name`` contains characters outside ``[a-zA-Z0-9_]``
            or starts with a digit.

    """
    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", name):
        raise ValueError(f"Invalid SQL identifier: {name!r}")


def load_features(
    host: str,
    database: str,
    user: str,
    password: str,
    table_name: str,
    user_id: str,
) -> list[HRVFeatures]:
    """Load all HRV session records for a given user from a PostgreSQL table.

    Executes a ``SELECT`` query ordered by ascending date and maps each row
    to an ``HRVFeatures`` instance. The result can be passed directly to
    ``Baseline.from_features`` to reconstruct the user's personal baseline.

    Args:
        host: Database server hostname or IP address.
        database: Name of the target database.
        user: PostgreSQL username.
        password: PostgreSQL password.
        table_name: Name of the table to query. Must be a valid SQL
            identifier (validated before use to prevent injection).
        user_id: Identifier of the user whose sessions are retrieved.
            Passed as a parameterised query argument.

    Returns:
        List of ``HRVFeatures`` instances sorted by ascending date.
        Returns an empty list if no records are found for ``user_id``.

    Raises:
        ValueError: If ``table_name`` is not a valid SQL identifier.
        psycopg2.Error: If the connection fails or the query is rejected.

    """
    _validate_identifier(table_name)

    conn = connect(
        host=host, database=database, user=user, password=password
    )

    cur = conn.cursor()

    query = sql.SQL("""
        SELECT date, rmssd, ln_rmssd, sdnn, pnn50, mean_hr,
               vlf, lf, hf, lf_hf, hf_pct, lf_nu, hf_nu
        FROM {}
        WHERE user_id = %s
        ORDER BY date ASC;
    """).format(sql.Identifier(table_name))

    cur.execute(query, (user_id,))
    rows = cur.fetchall()

    cur.close()
    conn.close()

    features = []

    for row in rows:
        features.append(
            HRVFeatures(
                date=str(row[0]),
                rmssd=row[1],
                ln_rmssd=row[2],
                sdnn=row[3],
                pnn50=row[4],
                mean_hr=row[5],
                vlf=row[6],
                lf=row[7],
                hf=row[8],
                lf_hf=row[9],
                hf_pct=row[10],
                lf_nu=row[11],
                hf_nu=row[12],
            )
        )

    return features
