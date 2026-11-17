from contextlib import contextmanager
import sqlite3

SCHEMA_VERSION = 1
TABLES = {
    "grid_revisions": "id INTEGER PRIMARY KEY, name TEXT NOT NULL, spec TEXT NOT NULL",
    "sources": """source_id TEXT PRIMARY KEY, grid_id INTEGER NOT NULL REFERENCES grid_revisions(id),
        kind TEXT NOT NULL, body TEXT NOT NULL""",
    "observation_revisions": """id INTEGER PRIMARY KEY,
        grid_id INTEGER NOT NULL REFERENCES grid_revisions(id),
        parent_id INTEGER REFERENCES observation_revisions(id)""",
    "observation_members": """revision_id INTEGER NOT NULL REFERENCES observation_revisions(id),
        source_id TEXT NOT NULL REFERENCES sources(source_id), PRIMARY KEY(revision_id, source_id)""",
    "plans": """id INTEGER PRIMARY KEY, grid_id INTEGER NOT NULL REFERENCES grid_revisions(id),
        observation_id INTEGER NOT NULL REFERENCES observation_revisions(id), body TEXT NOT NULL""",
    "results": "id INTEGER PRIMARY KEY, plan_id INTEGER NOT NULL REFERENCES plans(id), header TEXT NOT NULL",
    "result_cells": """result_id INTEGER NOT NULL REFERENCES results(id), ordinal INTEGER NOT NULL,
        body TEXT NOT NULL, PRIMARY KEY(result_id, ordinal)""",
    "result_faces": """result_id INTEGER NOT NULL REFERENCES results(id), ordinal INTEGER NOT NULL,
        body TEXT NOT NULL, PRIMARY KEY(result_id, ordinal)""",
    "result_sources": """result_id INTEGER NOT NULL REFERENCES results(id), ordinal INTEGER NOT NULL,
        body TEXT NOT NULL, PRIMARY KEY(result_id, ordinal)""",
}

@contextmanager
def archive_transaction(connection):
    if connection.in_transaction:
        raise RuntimeError("unexpected nested archive transaction")
    connection.execute("BEGIN IMMEDIATE")
    try:
        yield
        connection.execute("COMMIT")
    except BaseException:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise

def table_signature(connection, name):
    columns = tuple(tuple(row[1:]) for row in connection.execute("PRAGMA table_info(" + name + ")"))
    foreign_keys = tuple(sorted(tuple(row[2:]) for row in
                                connection.execute("PRAGMA foreign_key_list(" + name + ")")))
    unique = []
    for row in connection.execute("PRAGMA index_list(" + name + ")"):
        if row[2]:
            quoted = row[1].replace('"', '""')
            unique.append(tuple(x[2] for x in connection.execute('PRAGMA index_info("' + quoted + '")')))
    return columns, foreign_keys, frozenset(unique)

def ensure_schema(connection):
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    if version not in (0, SCHEMA_VERSION):
        raise ValueError("unsupported archive schema version")
    reference = sqlite3.connect(":memory:")
    try:
        for name, definition in TABLES.items():
            reference.execute("CREATE TABLE " + name + "(" + definition + ")")
        with archive_transaction(connection):
            for name, definition in TABLES.items():
                connection.execute("CREATE TABLE IF NOT EXISTS " + name + "(" + definition + ")")
                actual, expected = table_signature(connection, name), table_signature(reference, name)
                if actual[:2] != expected[:2] or not expected[2].issubset(actual[2]):
                    raise ValueError("incompatible archive table: " + name)
            connection.execute("PRAGMA user_version = " + str(SCHEMA_VERSION))
    finally:
        reference.close()

def connect_archive(path):
    connection = sqlite3.connect(path, isolation_level=None)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        ensure_schema(connection)
    except BaseException:
        connection.close()
        raise
    return connection
