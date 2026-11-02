"""Metadata capacity, distinct from collection and native worker budgets."""
MAX_RECORDS = 65536
MAX_FILE = 128 * 1024**2
SHARD_RECORDS = 128
MAX_PARTS = MAX_RECORDS // SHARD_RECORDS
MAX_INDEX = 128 * 1024
SESSION_RECORDS = 4096
