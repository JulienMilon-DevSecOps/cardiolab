-- V003 — Add training sessions table (cardiolab v0.2.0)
-- One row per activity (not per day). Multiple activities on the same day
-- are each stored as independent rows identified by activity_id (UUID).

CREATE TABLE IF NOT EXISTS hrv_training_sessions (
    activity_id  TEXT  PRIMARY KEY,
    user_id      TEXT  NOT NULL,
    date         DATE  NOT NULL,
    duration_min FLOAT,
    sport_type   TEXT,
    trimp        FLOAT,
    notes        TEXT
);
