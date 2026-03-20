from backend.config import settings


def main() -> None:
    import uvicorn

    uvicorn.run(
        'backend.api.main:app',
        host=settings.app_host,
        port=settings.app_port,
        reload=False,
        log_level='info',
    )


if __name__ == '__main__':
    main()
