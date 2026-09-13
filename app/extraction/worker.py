from that_depends.providers import container_context
from that_depends.providers.context_resources import ContextScopes

from app.common.database import create_db_and_tables
from app.common.logging import logger
from app.extraction.container import ExtractionContainer
from app.extraction.schemas import IndexStats


def run_indexing(batch_size: int = 100) -> IndexStats:
    create_db_and_tables()
    with container_context(scope=ContextScopes.REQUEST):
        service = ExtractionContainer.extraction_service.resolve_sync()
        stats = service.index_pending(batch_size=batch_size)
    logger.info(
        "extraction index pass done: scanned=%d extracted=%d "
        "re_extracted=%d embedded=%d completed_scans=%d",
        stats.scanned,
        stats.extracted,
        stats.re_extracted,
        stats.embedded,
        stats.completed_scans,
    )
    return stats


def main() -> None:
    run_indexing()


if __name__ == "__main__":
    main()
