import argparse
import logging
import sys

from vibe.config import Settings


def main(argv: list[str] | None = None) -> int:
    """Serve the app (the default), run a preflight check, or maintain the store.

    `python -m vibe` used to hard-code 127.0.0.1:7321, so VIBE_HOST and
    VIBE_PORT were silently ignored, and create_app() ran at import time --
    opening the workspace and its databases before anything asked it to.

    The runtime dependencies are imported inside each branch on purpose: the
    doctor must still answer "what is missing" on a machine where FastAPI or
    LangGraph cannot even be imported yet.
    """
    parser = argparse.ArgumentParser(prog="vibe", description="Local-first vibe-coding IDE backend.")
    subcommands = parser.add_subparsers(dest="command")
    subcommands.add_parser("serve", help="serve the API (default)")
    subcommands.add_parser("doctor", help="check that this machine can run the app")
    backup_parser = subcommands.add_parser("backup", help="save the databases and providers into <workspace>/backups")
    backup_parser.add_argument(
        "--keep", type=int, default=None, metavar="N", help="how many backups to keep afterwards (default 7)"
    )
    subcommands.add_parser("repair", help="check the local store, re-run migrations, and quarantine an unreadable providers file")
    args = parser.parse_args(argv)

    if args.command == "doctor":
        from vibe.doctor import exit_code, render, run_checks

        checks = run_checks(Settings.from_env())
        print(render(checks))
        return exit_code(checks)

    if args.command == "backup":
        from vibe.maintenance import backup, backup_exit_code, render_backup

        try:
            result = backup(Settings.from_env().workspace_dir, keep=args.keep)
        except ValueError as error:
            print(f"backup not started: {error}", file=sys.stderr)
            return 2
        print(render_backup(result))
        return backup_exit_code(result)

    if args.command == "repair":
        from vibe.maintenance import render_repair, repair, repair_exit_code

        report = repair(Settings.from_env().workspace_dir)
        print(render_repair(report))
        return repair_exit_code(report)

    import uvicorn

    from vibe.api.app import create_app
    from vibe.logging_setup import configure_logging

    settings = Settings.from_env()
    # Configure before uvicorn: its dictConfig leaves existing loggers
    # alone, so this handler survives and the app's own records are visible.
    # Passing the settings is what turns on the rotating file under the
    # workspace: "send me the log" is unanswerable if the only copy scrolled
    # past in a console window. A bare configure_logging() stays stderr-only on
    # purpose, so a host app that mounts this API gets no files behind its back.
    level = configure_logging(settings=settings)
    logging.getLogger(__name__).info(
        "vibe serving on http://%s:%s (%s mode, log level %s, workspace %s)",
        settings.host, settings.port, settings.mode, logging.getLevelName(level),
        settings.workspace_dir,
    )
    app = create_app(settings)
    # `uvicorn.run()` builds its Server internally and hands nothing back, and
    # /admin/shutdown needs that object to ask for a graceful stop instead of
    # killing this process. Config() also configures uvicorn's logging exactly
    # as uvicorn.run would have.
    server = uvicorn.Server(uvicorn.Config(app, host=settings.host, port=settings.port))
    app.state.uvicorn_server = server
    server.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
