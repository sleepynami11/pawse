"""Bounded local case cache shared by care and agent endpoints."""
import time

records: dict[str, dict] = {}
active: set[str] = set()
TTL = 900
MAX_RECORDS = 100


def prune():
    for key in list(records):
        if time.monotonic() - records[key]['created'] > TTL:
            del records[key]


def remember(owner, result):
    prune()
    if len(records) >= MAX_RECORDS:
        del records[min(records, key=lambda key: records[key]['created'])]
    records[result['request_id']] = {'owner': owner, 'created': time.monotonic(), 'result': result}
