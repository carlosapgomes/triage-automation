"""bot-api entrypoint."""

from triage_automation.config.settings import load_settings


def main() -> None:
    """Load configuration and start bot-api runtime."""

    load_settings()


if __name__ == "__main__":
    main()
