"""Load HRV features from database for a given user."""

import psycopg2

from cardiolab.protocols.resting import HRVFeatures


def load_features(
    host: str,
    database: str,
    user: str,
    password: str,
    table_name: str,
    user_id: str,
) -> list[HRVFeatures]:
    """Load HRV features from database for a given user.
    
    FR :
    Charge les features HRV depuis la base pour un utilisateur donné.
    EN :
    Loads HRV features from database for a given user.
    """
    conn = psycopg2.connect(
        host=host, database=database, user=user, password=password
    )

    cur = conn.cursor()

    query = f"""
    SELECT date, rmssd, ln_rmssd, sdnn, pnn50, mean_hr,
           vlf, lf, hf, lf_hf, hf_pct, lf_nu, hf_nu
    FROM {table_name}
    WHERE user_id = %s
    ORDER BY date ASC;
    """

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