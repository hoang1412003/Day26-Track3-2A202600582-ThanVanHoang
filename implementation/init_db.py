from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "school.db"

SCHEMA_SQL = """
DROP TABLE IF EXISTS enrollments;
DROP TABLE IF EXISTS courses;
DROP TABLE IF EXISTS students;

CREATE TABLE students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    cohort TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    score REAL NOT NULL CHECK (score >= 0 AND score <= 100),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE courses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    credits INTEGER NOT NULL CHECK (credits > 0)
);

CREATE TABLE enrollments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    grade REAL NOT NULL CHECK (grade >= 0 AND grade <= 100),
    status TEXT NOT NULL CHECK (status IN ('active', 'completed', 'dropped')),
    UNIQUE (student_id, course_id)
);
"""

SEED_SQL = """
INSERT INTO students (name, cohort, email, score) VALUES
    ('An Nguyen', 'A1', 'an.nguyen@example.edu', 88.5),
    ('Binh Tran', 'A1', 'binh.tran@example.edu', 91.0),
    ('Chi Le', 'B2', 'chi.le@example.edu', 76.5),
    ('Dung Pham', 'B2', 'dung.pham@example.edu', 84.0),
    ('Eva Hoang', 'C3', 'eva.hoang@example.edu', 95.0);

INSERT INTO courses (code, title, credits) VALUES
    ('AI101', 'Introduction to AI', 3),
    ('DB201', 'Database Systems', 4),
    ('MCP301', 'Model Context Protocol', 2);

INSERT INTO enrollments (student_id, course_id, grade, status) VALUES
    (1, 1, 89.0, 'completed'),
    (1, 2, 86.0, 'active'),
    (2, 1, 92.0, 'completed'),
    (2, 3, 94.0, 'active'),
    (3, 2, 78.0, 'completed'),
    (4, 3, 83.0, 'active'),
    (5, 1, 96.0, 'completed'),
    (5, 3, 98.0, 'active');
"""


def create_database(db_path: str | Path = DB_PATH) -> Path:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(SCHEMA_SQL)
        conn.executescript(SEED_SQL)
        conn.commit()
    return path


if __name__ == "__main__":
    print(create_database())
