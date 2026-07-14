#!/usr/bin/env python3
import csv
import sys

sys.stdin.reconfigure(encoding="latin-1")

for row in csv.reader(sys.stdin):
    if len(row) != 4:
        continue
    movie_id = row[1].strip()
    rating = row[2].strip()

    if movie_id == "movieId" and rating == "rating":
        continue
    try:
        float(rating)
    except ValueError:
        continue

    print(f"{movie_id}\t{rating}")
