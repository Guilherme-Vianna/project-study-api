import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from app.core.database import SessionLocal
from app.models.history import ACTOR_KEY
from app.models.question_bank import QuestionBankItem
from app.repositories.question_bank import QuestionBankRepository

ACTOR = "import:question-bank"
FIELDS = ("subject", "topic", "board", "exam", "year", "statement", "answer", "source", "page")
OPTIONAL_TEXT = ("board", "exam", "answer")
BATCH = 200


def to_row(raw: dict[str, Any]) -> dict[str, Any]:
    row = {field: raw.get(field) for field in FIELDS}
    for field in OPTIONAL_TEXT:
        row[field] = (row[field] or "").strip() or None
    return row


async def import_lines(lines: list[str]) -> tuple[int, int]:
    created = updated = 0
    async with SessionLocal() as session:
        session.info[ACTOR_KEY] = ACTOR
        items = QuestionBankRepository(session)
        for number, line in enumerate(lines, 1):
            if not line.strip():
                continue
            raw = json.loads(line)
            row = to_row(raw)
            existing = await items.get_by(source_key=raw["source_key"])
            if existing is None:
                session.add(QuestionBankItem(source_key=raw["source_key"], **row))
                created += 1
            else:
                for field, value in row.items():
                    setattr(existing, field, value)
                updated += 1
            if number % BATCH == 0:
                await session.commit()
        await session.commit()
    return created, updated


def main() -> None:
    parser = argparse.ArgumentParser(description="Import question bank items from a JSONL file")
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    lines = args.path.read_text(encoding="utf-8").splitlines()
    created, updated = asyncio.run(import_lines(lines))
    print(f"{created} created, {updated} updated")


if __name__ == "__main__":
    main()
