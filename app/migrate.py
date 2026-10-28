"""Lightweight, additive schema upgrade.

`create_all` creates missing tables but never adds columns to existing ones. When a new phase adds
a column, this adds it (nullable / with a default) so an existing database keeps working without
manual SQL. It only ever ADDs columns; it never drops or rewrites anything.
"""
import logging

from sqlalchemy import inspect, text
from sqlalchemy.schema import CreateColumn

from .database import Base, engine

log = logging.getLogger("migrate")


def add_missing_columns() -> None:
    insp = inspect(engine)
    existing_tables = set(insp.get_table_names())
    with engine.begin() as con:
        for table in Base.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue
            have = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name in have:
                    continue
                ddl = str(CreateColumn(col).compile(dialect=engine.dialect))
                # A NOT NULL column cannot be added to a table that already has rows without a default.
                if not col.nullable and col.server_default is None:
                    ddl = ddl.replace("NOT NULL", "").strip()
                con.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN {ddl}'))
                log.warning("Added column %s.%s", table.name, col.name)
