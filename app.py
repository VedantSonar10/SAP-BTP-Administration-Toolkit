"""
app.py

SAP BTP Administration Toolkit - entry point.

Wires together authentication, JWT inspection, service key analysis,
API connectivity testing, endpoint health checks, and report export
behind a single interactive CLI menu. Phase 9: every action is wrapped
so a user never sees a raw Python traceback.
"""

from __future__ import annotations

from dataclasses import dataclass

from rich.console import Console

from api.accounts import AccountsAPI
from api.auth import Auth
from api.entitlements import EntitlementsAPI
from api.users import UsersAPI
from services.access_auditor import AccessAuditor
from services.cost_tracker import CostTracker
from services.endpoint_checker import EndpointChecker
from services.report_generator import ReportGenerator
from services.security_auditor import SecurityAuditor
from services.service_key_analyzer import ServiceKeyAnalyzer, ServiceKeyInfo
from utils.config import AppConfig
from utils.dashboard import DashboardState, show_dashboard
from utils.exceptions import BTPToolkitError
from utils.logger import logger, reconfigure
from utils.token_decoder import TokenInfo, decode_token

console = Console()

MENU_OPTIONS = """
1. Authenticate
2. Decode Access Token
3. Analyze Service Key
4. Test API Connectivity (Accounts / Entitlements / Users)
5. Run Endpoint Health Check
6. Export Report
7. View Dashboard
8. Check Cost / Budgets
9. Audit Roles & Access
10. Security Audit (Audit Log)
11. Exit
"""


@dataclass
class SessionState:
    """Everything accumulated over the life of one CLI run."""

    auth: Auth | None = None
    token: str | None = None
    token_info: TokenInfo | None = None
    service_key_info: ServiceKeyInfo | None = None
    endpoint_results: list = None
    dashboard: DashboardState = None

    def __post_init__(self):
        if self.dashboard is None:
            self.dashboard = DashboardState()
        if self.endpoint_results is None:
            self.endpoint_results = []


def print_menu() -> None:
    console.print("\n" + "=" * 45, style="blue")
    console.print("      SAP BTP Administration Toolkit", style="bold blue")
    console.print("=" * 45, style="blue")
    console.print(MENU_OPTIONS)
    console.print("=" * 45, style="blue")


def handle_authenticate(state: SessionState, config: AppConfig) -> None:
    if state.auth is None:
        state.auth = Auth(config.service_key_path, timeout=config.timeout)

    state.token = state.auth.get_access_token()
    state.dashboard.authenticated = True
    state.dashboard.identity_zone = state.auth.get_service_key().get("uaa", {}).get("identityzone")
    console.print("[bold green]Authentication successful.[/bold green]")


def handle_decode_token(state: SessionState) -> None:
    if not state.token:
        console.print("[yellow]Authenticate first.[/yellow]")
        return
    state.token_info = decode_token(state.token)
    state.dashboard.token_valid = bool(state.token_info and not state.token_info.is_expired)


def handle_analyze_service_key(state: SessionState, config: AppConfig) -> None:
    if state.auth is None:
        state.auth = Auth(config.service_key_path, timeout=config.timeout)
    analyzer = ServiceKeyAnalyzer(state.auth.get_service_key())
    state.service_key_info = analyzer.analyze()


def handle_test_apis(state: SessionState, config: AppConfig) -> None:
    if not state.token or state.auth is None:
        console.print("[yellow]Authenticate first.[/yellow]")
        return

    service_key = state.auth.get_service_key()

    accounts_result = AccountsAPI(service_key, state.token, timeout=config.timeout).test_connection()
    entitlements_result = EntitlementsAPI(service_key, state.token, timeout=config.timeout).test_connection()
    users_result = UsersAPI(service_key, state.token, timeout=config.timeout).test_connection()

    state.dashboard.accounts_status = accounts_result.status_label
    state.dashboard.entitlements_status = entitlements_result.status_label
    state.dashboard.users_status = users_result.status_label

    for label, result in (
        ("Accounts", accounts_result),
        ("Entitlements", entitlements_result),
        ("Users", users_result),
    ):
        console.print(f"\n[bold cyan]{label} API[/bold cyan]: {result.status_label} "
                      f"(HTTP {result.status_code}, {result.latency_ms}ms)")
        if result.error_message:
            console.print(f"  [dim]{result.error_message}[/dim]")


def handle_endpoint_health(state: SessionState, config: AppConfig) -> None:
    if state.auth is None:
        state.auth = Auth(config.service_key_path, timeout=config.timeout)
    checker = EndpointChecker(state.auth.get_service_key(), timeout=config.timeout)
    state.endpoint_results = checker.check_all()
    checker.display(state.endpoint_results)


def handle_cost_check(state: SessionState, config: AppConfig) -> None:
    if not state.token or state.auth is None:
        console.print("[yellow]Authenticate first.[/yellow]")
        return

    tracker = CostTracker(state.auth.get_service_key(), state.token, timeout=config.timeout)
    result = tracker.test_connection()
    state.dashboard.budgets_status = result.status_label
    tracker.display(result)


def handle_access_audit(state: SessionState, config: AppConfig) -> None:
    if config.apiaccess_service_key_path:
        try:
            apiaccess_auth = Auth(config.apiaccess_service_key_path, timeout=config.timeout)
            apiaccess_token = apiaccess_auth.get_access_token()
        except BTPToolkitError as exc:
            console.print(f"[bold red]Could not authenticate with the apiaccess key: {exc}[/bold red]")
            return

        auditor = AccessAuditor(apiaccess_auth.get_service_key(), apiaccess_token, timeout=config.timeout)
    else:
        if not state.token or state.auth is None:
            console.print("[yellow]Authenticate first (or set APIACCESS_SERVICE_KEY_PATH in .env).[/yellow]")
            return
        console.print(
            "[yellow]APIACCESS_SERVICE_KEY_PATH not set — reusing the main token. "
            "This will likely show 'Access denied' unless that XSUAA instance is on the apiaccess plan.[/yellow]"
        )
        auditor = AccessAuditor(state.auth.get_service_key(), state.token, timeout=config.timeout)

    roles_result = auditor.audit()
    state.dashboard.access_audit_status = roles_result.status_label


def handle_security_audit(state: SessionState, config: AppConfig) -> None:
    if not config.audit_log_service_key_path:
        console.print(
            "[yellow]AUDIT_LOG_SERVICE_KEY_PATH is not set in .env — "
            "the Security Auditor needs its own audit log service key, "
            "separate from your main service key.[/yellow]"
        )
        return

    try:
        audit_auth = Auth(config.audit_log_service_key_path, timeout=config.timeout)
        audit_token = audit_auth.get_access_token()
    except BTPToolkitError as exc:
        console.print(f"[bold red]Could not authenticate to the audit log service: {exc}[/bold red]")
        return

    auditor = SecurityAuditor(audit_auth.get_service_key(), audit_token, timeout=config.timeout)
    result = auditor.scan(hours=24)
    state.dashboard.security_audit_status = result.status_label


def handle_export_report(state: SessionState) -> None:
    generator = ReportGenerator()
    auth_status = "Authenticated" if state.token else "Not Authenticated"
    paths = generator.generate(auth_status, state.token_info, state.endpoint_results)
    console.print("[bold green]Report exported:[/bold green]")
    for fmt, path in paths.items():
        console.print(f"  {fmt.upper():<5} -> {path}")


def main() -> None:
    try:
        config = AppConfig.load()
    except BTPToolkitError as exc:
        console.print(f"[bold red]Configuration Error:[/bold red] {exc}")
        return

    reconfigure(config.log_level)
    logger.info("Toolkit started")

    state = SessionState()

    while True:
        print_menu()
        choice = console.input("Select Option: ").strip()

        try:
            if choice == "1":
                handle_authenticate(state, config)
            elif choice == "2":
                handle_decode_token(state)
            elif choice == "3":
                handle_analyze_service_key(state, config)
            elif choice == "4":
                handle_test_apis(state, config)
            elif choice == "5":
                handle_endpoint_health(state, config)
            elif choice == "6":
                handle_export_report(state)
            elif choice == "7":
                show_dashboard(state.dashboard)
            elif choice == "8":
                handle_cost_check(state, config)
            elif choice == "9":
                handle_access_audit(state, config)
            elif choice == "10":
                handle_security_audit(state, config)
            elif choice == "11":
                console.print("[bold blue]Goodbye![/bold blue]")
                logger.info("Toolkit exited normally")
                break
            else:
                console.print("[yellow]Invalid Option[/yellow]")
                continue
        except BTPToolkitError as exc:
            logger.error("Handled error: %s", exc)
            console.print(f"[bold red]{exc}[/bold red]")
        except Exception as exc:  # last-resort guard so the CLI never crashes to a traceback
            logger.exception("Unexpected error")
            console.print(f"[bold red]Unexpected error:[/bold red] {exc}")

        show_dashboard(state.dashboard)


if __name__ == "__main__":
    main()
