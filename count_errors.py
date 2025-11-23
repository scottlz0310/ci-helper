#!/usr/bin/env python3
import re
import subprocess
from collections import Counter

result = subprocess.run(
    ["uv", "run", "basedpyright", "src/ci_helper"],
    check=False,
    capture_output=True,
    text=True,
    cwd="/home/hiro/workspace/ci-helper",
)

lines = result.stdout.split("\n")
file_pattern = re.compile(r"^(/[^:]+\.py)")

files = []
for line in lines:
    match = file_pattern.match(line)
    if match:
        files.append(match.group(1))

counter = Counter(files)
for file, count in counter.most_common(30):
    print(f"{count:4d} {file}")
