#!/usr/bin/env python3
import csv
import sys

sys.stdin.reconfigure(encoding="latin-1")

LABEL_TO_CATEGORY = {"0": "negative", "2": "neutral", "4": "positive"}

for row in csv.reader(sys.stdin):
    if len(row) != 6:
        continue
    category = LABEL_TO_CATEGORY.get(row[0])
    if category is None:
        continue
    print(f"{category}\t1")
