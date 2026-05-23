"""Engine factories for benchmark configurations.

Two factories:
    create_engine_orm(config, db_path)  → QueuePool engine with config PRAGMAs
    create_engine_static(db_path)       → StaticPool engine (legacy/before)
"""

import sqlite3

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool, StaticPool

from .configs import BenchmarkConfig


def _install_pragmas(engine, config: BenchmarkConfig) -> None:
    @event.listens_for(engine, "connect")
    def _set_pragmas(dbapi_conn, _record):
        if isinstance(dbapi_conn, sqlite3.Connection):
            c = dbapi_conn.cursor()
            c.execute(f"PRAGMA journal_mode={config.journal_mode};")
            c.execute(f"PRAGMA synchronous={config.synchronous};")
            c.execute(f"PRAGMA busy_timeout={config.busy_timeout};")
            c.execute(f"PRAGMA cache_size={config.cache_size};")
            c.execute(f"PRAGMA mmap_size={config.mmap_size};")
            c.execute(f"PRAGMA temp_store={config.temp_store};")
            c.close()


def create_engine_for_config(config: BenchmarkConfig, db_path: str):
    """QueuePool engine with config-specific PRAGMAs."""
    url = f"sqlite:///{db_path}"
    eng = create_engine(
        url,
        connect_args={"check_same_thread": False, "timeout": 30},
        poolclass=QueuePool,
        pool_size=config.pool_size,
        max_overflow=config.max_overflow,
        pool_pre_ping=True,
        pool_recycle=3600,
    )
    _install_pragmas(eng, config)
    return eng, sessionmaker(autocommit=False, autoflush=False, bind=eng)


def create_engine_static(db_path: str, busy_timeout: int = 5000):
    """StaticPool engine — pre-fix configuration mimicking legacy ORM setup.

    Used as the "before" baseline in the ORM vs Raw benchmark to represent
    a typical default SQLAlchemy+SQLite configuration.
    """
    url = f"sqlite:///{db_path}"
    eng = create_engine(
        url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(eng, "connect")
    def _pragmas(dbapi_conn, _rec):
        if isinstance(dbapi_conn, sqlite3.Connection):
            c = dbapi_conn.cursor()
            c.execute("PRAGMA journal_mode=WAL;")
            c.execute("PRAGMA synchronous=NORMAL;")
            c.execute(f"PRAGMA busy_timeout={busy_timeout};")
            c.execute("PRAGMA cache_size=-4096;")
            c.execute("PRAGMA temp_store=MEMORY;")
            c.close()

    return eng, sessionmaker(autocommit=False, autoflush=False, bind=eng)
