from __future__ import annotations

import logging

from backend.app.config import get_settings
from backend.app.db.database import Database
from scraper.darglobal.spider import DarGlobalSpider
from scraper.wasalt.spider import WasaltSpider


def main() -> None:
    settings = get_settings(); logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO), format="%(asctime)s %(levelname)s %(message)s")
    db = Database(settings.database_path)
    DarGlobalSpider(settings, db).run()
    WasaltSpider(settings, db).run()


if __name__ == "__main__": main()
