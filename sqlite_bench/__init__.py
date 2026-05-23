"""SQLite ORM benchmark suite.

Measures write throughput across SQLite configurations and compares
SQLAlchemy ORM vs raw sqlite3.executemany at 10M-50M row scale.
"""

__version__ = "0.1.0"
