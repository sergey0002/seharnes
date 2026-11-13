#!/usr/bin/env python3
"""Сводка runtime-депрекаций PHP 8.5 из лога deprecation-logger.php.

Лог TSV: timestamp, errno, file:line, message.

    python3 .tools/php85-scan/deprecation_summary.py /var/log/php85-deprecations.log
    python3 .tools/php85-scan/deprecation_summary.py log.txt --json summary.json
"""

import argparse
import collections
import json
import re
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("log")
    parser.add_argument("--json")
    parser.add_argument("--top", type=int, default=40)
    args = parser.parse_args()

    unique = collections.Counter()
    by_file = collections.Counter()
    total = 0

    with open(args.log, encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            parts = raw.rstrip("\n").split("\t")
            if len(parts) < 4:
                continue
            total += 1
            location, message = parts[2], parts[3]
            # Нормализуем конкретные значения, чтобы группировать одинаковые причины.
            normalized = re.sub(r"'[^']*'", "'...'", message)
            normalized = re.sub(r'"[^"]*"', '"..."', normalized)
            normalized = re.sub(r"\b\d+\b", "N", normalized)
            key = normalized.strip()
            unique[key] += 1
            by_file[location.rsplit(":", 1)[0]] += 1

    print(f"total events: {total}, unique messages: {len(unique)}")
    print("\nTop messages:")
    for message, count in unique.most_common(args.top):
        print(f"{count:6}  {message}")
    print("\nTop files:")
    for path, count in by_file.most_common(args.top):
        print(f"{count:6}  {path}")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "total": total,
                    "messages": unique.most_common(),
                    "files": by_file.most_common(),
                },
                fh,
                ensure_ascii=False,
                indent=2,
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
