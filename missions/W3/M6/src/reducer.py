#!/usr/bin/env python3
import sys

current_product_id = None
current_sum = 0.0
current_count = 0

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    product_id, rating = line.split("\t", 1)
    try:
        rating = float(rating)
    except ValueError:
        continue

    if product_id == current_product_id:
        current_sum += rating
        current_count += 1
    else:
        if current_product_id is not None and current_count:
            avg_rating = current_sum / current_count
            print(f"{current_product_id}\t{current_count}\t{avg_rating:.4f}")
        current_product_id = product_id
        current_sum = rating
        current_count = 1

if current_product_id is not None and current_count:
    avg_rating = current_sum / current_count
    print(f"{current_product_id}\t{current_count}\t{avg_rating:.4f}")
