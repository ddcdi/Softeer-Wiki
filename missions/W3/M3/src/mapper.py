#!/usr/bin/env python3
import sys
import re

for line in sys.stdin:
    words = re.findall(r"[a-z0-9]+", line.lower())
    for word in words:
        print(f"{word}\t1")
