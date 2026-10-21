"""Keep public staff email references current across Planning Center syncs."""
from functools import lru_cache
from pathlib import Path
import re

import yaml


@lru_cache(maxsize=1)
def migration_pattern():
    path = Path(__file__).resolve().parents[1] / "registry/staff-email-migration.yaml"
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    names = "|".join(re.escape(name) for name in config["staff_mailboxes"])
    pattern = re.compile(
        rf"(?<![\w.+%\-])({names})@{re.escape(config['old_domain'])}(?![\w\-]|\.[\w\-])",
        re.IGNORECASE,
    )
    return pattern, config["new_domain"]


def migrate_staff_emails(text: str) -> str:
    pattern, domain = migration_pattern()
    return pattern.sub(lambda match: f"{match[1].lower()}@{domain}", text)
