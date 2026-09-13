from app.common.database import create_db_and_tables
from app.mcp_server.server import build_mcp_server


def main() -> None:
    create_db_and_tables()
    server = build_mcp_server()
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
