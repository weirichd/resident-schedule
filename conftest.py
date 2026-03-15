import sys

try:
    import pysqlite3

    sys.modules["sqlite3"] = pysqlite3
except ImportError:
    pass
