#!/usr/bin/env python3
import json
import sys

PRODUCT_ID_FIELDS = ("parent_asin", "asin", "product_id", "item_id")
RATING_FIELDS = ("rating", "overall", "stars")

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue

    try:
        record = json.loads(line)
    except json.JSONDecodeError:
        continue

    product_id = None
    for field in PRODUCT_ID_FIELDS:
        value = record.get(field)
        if value:
            product_id = str(value).strip()
            break

    if not product_id:
        continue

    rating_value = None
    for field in RATING_FIELDS:
        if field in record:
            rating_value = record.get(field)
            break

    if rating_value is None:
        continue

    try:
        rating = float(rating_value)
    except (TypeError, ValueError):
        continue

    print(f"{product_id}\t{rating}")
