from __future__ import annotations

import uvicorn

from .app import create_app
from .config import ServerSettings


def main() -> None:
    settings = ServerSettings.load()
    app = create_app(settings=settings)
    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()

