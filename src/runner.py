"""Interactive and command-line runner for the traffic simulation project."""

from __future__ import annotations

import argparse
import logging
from typing import Callable

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from app.config import AppConfig
from app.exceptions import ConfigurationError
from app.logging_config import setup_logging
from app.test_executor import TestExecutor, TestResult

LOGGER = logging.getLogger(__name__)
CONSOLE = Console()

MenuAction = Callable[[TestExecutor], int]


def _run_full_app(_: TestExecutor) -> int:
    from app.application import run_full_application

    return run_full_application()


def _run_unit(executor: TestExecutor) -> int:
    return _print_test_result(executor.run_unit_tests())


def _run_integration(executor: TestExecutor) -> int:
    return _print_test_result(executor.run_integration_tests())


def _run_all(executor: TestExecutor) -> int:
    return _print_test_result(executor.run_all_tests())


def _print_test_result(result: TestResult) -> int:
    style = "green" if result.succeeded else "red"
    status = "PASSED" if result.succeeded else "FAILED"

    table = Table(
        title="Test Execution Result", show_header=True, header_style="bold cyan"
    )
    table.add_column("Suite", style="cyan")
    table.add_column("Status", style=style)
    table.add_column("Exit Code")
    table.add_column("Duration (s)")
    table.add_row(
        result.name, status, str(result.exit_code), f"{result.duration_seconds:.2f}"
    )

    CONSOLE.print(table)
    return result.exit_code


def _interactive_menu(executor: TestExecutor) -> int:
    actions: dict[str, tuple[str, MenuAction]] = {
        "1": ("Run Full Application", _run_full_app),
        "2": ("Run Unit Tests", _run_unit),
        "3": ("Run Integration Tests", _run_integration),
        "4": ("Run All Tests", _run_all),
        "5": ("Exit", lambda _: 0),
    }

    while True:
        CONSOLE.print(
            Panel.fit("Crossroads Simulation Runner", border_style="bright_blue")
        )
        for key, (label, _) in actions.items():
            CONSOLE.print(f"[bold yellow]{key}[/bold yellow]. {label}")

        choice = Prompt.ask(
            "Select an option", choices=list(actions.keys()), default="1"
        )

        if choice == "5":
            CONSOLE.print("Exiting runner.", style="green")
            return 0

        _, action = actions[choice]
        exit_code = action(executor)
        if exit_code not in (0, 130):
            CONSOLE.print(f"Operation ended with code {exit_code}", style="red")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python src/runner.py",
        description="Interactive runner for simulation and test suites.",
    )
    parser.add_argument(
        "--run-app", action="store_true", help="Run the full simulation application"
    )
    parser.add_argument("--unit-tests", action="store_true", help="Run unit tests only")
    parser.add_argument(
        "--integration-tests", action="store_true", help="Run integration tests only"
    )
    parser.add_argument(
        "--all-tests", action="store_true", help="Run the full test suite"
    )
    return parser


def _execute_args(args: argparse.Namespace, executor: TestExecutor) -> int:
    selected = sum(
        [args.run_app, args.unit_tests, args.integration_tests, args.all_tests]
    )
    if selected > 1:
        CONSOLE.print("Please select only one non-interactive option.", style="red")
        return 2

    if args.run_app:
        return _run_full_app(executor)
    if args.unit_tests:
        return _run_unit(executor)
    if args.integration_tests:
        return _run_integration(executor)
    if args.all_tests:
        return _run_all(executor)

    return _interactive_menu(executor)


def main(argv: list[str] | None = None) -> int:
    try:
        config = AppConfig.from_env()
    except ConfigurationError as exc:
        CONSOLE.print(f"Configuration error: {exc}", style="bold red")
        return 2

    setup_logging(config.log_level)
    LOGGER.info("Configuration loaded", extra={"config": config.safe_summary()})

    parser = _build_parser()
    args = parser.parse_args(argv)
    executor = TestExecutor(timeout_seconds=config.test_timeout_seconds)

    try:
        return _execute_args(args, executor)
    except KeyboardInterrupt:
        CONSOLE.print("Interrupted by user.", style="yellow")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
