#!/usr/bin/env python3
import sys

current_movie_id = None
current_sum = 0.0
current_count = 0

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    movie_id, rating = line.split("\t", 1)
    try:
        rating = float(rating)
    except ValueError:
        continue

    if movie_id == current_movie_id:
        current_sum += rating
        current_count += 1
    else:
        if current_movie_id is not None and current_count:
            print(f"{current_movie_id}\t{current_sum / current_count}")
        current_movie_id = movie_id
        current_sum = rating
        current_count = 1

if current_movie_id is not None and current_count:
    print(f"{current_movie_id}\t{current_sum / current_count}")
