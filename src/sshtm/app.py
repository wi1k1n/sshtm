from __future__ import annotations

from textual import work
from textual.app import App, ComposeResult
from textual.widgets import DataTable, Footer, Header

from sshtm.config.paths import tunnels_file, history_file
from sshtm.config.storage import TunnelStorage
from sshtm.core.manager import TunnelManager
from sshtm.core.process import ProcessTracker
from sshtm.core.tunnel import Tunnel, TunnelStatus


class SSHTMApp(App[None]):
    TITLE = "sshtm"
    SUB_TITLE = "SSH Tunnel Manager"
    CSS_PATH = "css/app.tcss"

    BINDINGS = [
        ("n", "new_tunnel", "New"),
        ("d", "delete_tunnel", "Delete"),
        ("e", "edit_tunnel", "Edit"),
        ("s", "toggle_tunnel", "Start/Stop"),
        ("r", "refresh", "Refresh"),
        ("question_mark", "show_help", "Help"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.storage = TunnelStorage(tunnels_file(), history_file())
        self.tunnel_manager = TunnelManager()
        self.process_tracker = ProcessTracker()
        self.tunnels: list[Tunnel] = []

    def compose(self) -> ComposeResult:
        yield Header()
        from sshtm.screens.main import MainScreen
        yield MainScreen()
        yield Footer()

    def on_mount(self) -> None:
        self.tunnels = self.storage.load_tunnels()
        self._reconcile_tunnel_states_worker()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self.action_toggle_tunnel()

    # ── Workers (background threads for blocking SSH ops) ─────────────

    @work(thread=True, group="reconcile")
    def _reconcile_tunnel_states_worker(self) -> None:
        self.process_tracker.cleanup_all_stale()
        for tunnel in self.tunnels:
            if tunnel.enabled:
                tunnel.status = self.tunnel_manager.check_tunnel_health(tunnel)
            else:
                tunnel.status = TunnelStatus.STOPPED
        self.call_from_thread(self._refresh_table)
        self.call_from_thread(self._start_health_timer)

    @work(thread=True, group="health")
    def _periodic_health_check_worker(self) -> None:
        changed = False
        for tunnel in self.tunnels:
            if tunnel.status in (TunnelStatus.RUNNING, TunnelStatus.STARTING):
                new_status = self.tunnel_manager.check_tunnel_health(tunnel)
                if new_status != tunnel.status:
                    tunnel.status = new_status
                    changed = True
        if changed:
            self.call_from_thread(self._refresh_table)

    @work(thread=True, group="tunnel_op", exclusive=True)
    def _start_tunnel_worker(self, tunnel: Tunnel) -> None:
        success, msg = self.tunnel_manager.start_tunnel(tunnel)
        self.call_from_thread(self._on_start_result, tunnel, success, msg)

    @work(thread=True, group="tunnel_op", exclusive=True)
    def _stop_tunnel_worker(self, tunnel: Tunnel) -> None:
        success, msg = self.tunnel_manager.stop_tunnel(tunnel)
        self.call_from_thread(self._on_stop_result, tunnel, success, msg)

    @work(thread=True, group="tunnel_op", exclusive=True)
    def _stop_and_restart_worker(self, old_tunnel: Tunnel, updated: Tunnel) -> None:
        self.tunnel_manager.stop_tunnel(old_tunnel)
        success, msg = self.tunnel_manager.start_tunnel(updated)
        self.call_from_thread(self._on_restart_result, updated, success, msg)

    @work(thread=True, group="tunnel_op", exclusive=True)
    def _stop_and_delete_worker(self, tunnel: Tunnel) -> None:
        self.tunnel_manager.stop_tunnel(tunnel)
        self.call_from_thread(self._finalize_delete, tunnel)

    # ── Worker callbacks (run on main thread via call_from_thread) ────

    def _start_health_timer(self) -> None:
        self.set_interval(10, self._periodic_health_check_worker)

    def _on_start_result(self, tunnel: Tunnel, success: bool, msg: str) -> None:
        if success:
            tunnel.status = TunnelStatus.RUNNING
            self.notify(f"Tunnel started: {tunnel.display_label()}")
        else:
            tunnel.status = TunnelStatus.ERROR
            tunnel.error_message = msg
            self.notify(f"Failed: {msg}", severity="error")
        self.storage.save_tunnels(self.tunnels)
        self._refresh_table()

    def _on_stop_result(self, tunnel: Tunnel, success: bool, msg: str) -> None:
        if success:
            tunnel.status = TunnelStatus.STOPPED
            self.notify(f"Stopped: {tunnel.display_label()}")
        else:
            self.notify(f"Stop failed: {msg}", severity="error")
        self.storage.save_tunnels(self.tunnels)
        self._refresh_table()

    def _on_restart_result(self, tunnel: Tunnel, success: bool, msg: str) -> None:
        if success:
            tunnel.status = TunnelStatus.RUNNING
            self.notify(f"Tunnel restarted: {tunnel.display_label()}")
        else:
            tunnel.status = TunnelStatus.ERROR
            tunnel.error_message = msg
            self.notify(f"Restart failed: {msg}", severity="error")
        self._refresh_table()

    def _finalize_delete(self, tunnel: Tunnel) -> None:
        self.tunnels = [t for t in self.tunnels if t.id != tunnel.id]
        self.storage.save_tunnels(self.tunnels)
        self.notify(f"Deleted: {tunnel.display_label()}")
        self._refresh_table()

    # ── UI refresh ────────────────────────────────────────────────────

    def _refresh_table(self) -> None:
        try:
            from sshtm.screens.main import MainScreen
            main_screen = self.query_one(MainScreen)
            main_screen.refresh_tunnels(self.tunnels)
        except Exception:
            pass

    # ── Actions ───────────────────────────────────────────────────────

    def action_new_tunnel(self) -> None:
        from sshtm.screens.tunnel_form import TunnelFormScreen
        self.push_screen(TunnelFormScreen(), callback=self._on_tunnel_created)

    def _on_tunnel_created(self, tunnel: Tunnel | None) -> None:
        if tunnel is None:
            return
        self.tunnels.append(tunnel)
        self.storage.save_tunnels(self.tunnels)
        self.storage.add_history_entry(tunnel)

        if tunnel.enabled:
            tunnel.status = TunnelStatus.STARTING
            self._refresh_table()
            self._start_tunnel_worker(tunnel)
        else:
            self._refresh_table()

    def action_delete_tunnel(self) -> None:
        tunnel = self._get_selected_tunnel()
        if tunnel is None:
            self.notify("No tunnel selected", severity="warning")
            return

        from sshtm.screens.main import ConfirmDialog
        self.push_screen(
            ConfirmDialog(f"Delete tunnel '{tunnel.display_label()}'?"),
            callback=lambda confirmed: self._on_delete_confirmed(tunnel, confirmed),
        )

    def _on_delete_confirmed(self, tunnel: Tunnel, confirmed: bool | None) -> None:
        if not confirmed:
            return
        if tunnel.status == TunnelStatus.RUNNING:
            self._stop_and_delete_worker(tunnel)
        else:
            self._finalize_delete(tunnel)

    def action_edit_tunnel(self) -> None:
        tunnel = self._get_selected_tunnel()
        if tunnel is None:
            self.notify("No tunnel selected", severity="warning")
            return

        from sshtm.screens.tunnel_form import TunnelFormScreen
        self.push_screen(
            TunnelFormScreen(tunnel=tunnel),
            callback=lambda result: self._on_tunnel_edited(tunnel, result),
        )

    def _on_tunnel_edited(self, old_tunnel: Tunnel, updated: Tunnel | None) -> None:
        if updated is None:
            return

        was_running = old_tunnel.status == TunnelStatus.RUNNING

        for i, t in enumerate(self.tunnels):
            if t.id == old_tunnel.id:
                self.tunnels[i] = updated
                break

        self.storage.save_tunnels(self.tunnels)

        if was_running and updated.enabled:
            updated.status = TunnelStatus.STARTING
            self._refresh_table()
            self._stop_and_restart_worker(old_tunnel, updated)
        else:
            self._refresh_table()

    def action_toggle_tunnel(self) -> None:
        tunnel = self._get_selected_tunnel()
        if tunnel is None:
            self.notify("No tunnel selected", severity="warning")
            return

        if tunnel.status == TunnelStatus.RUNNING:
            tunnel.status = TunnelStatus.STARTING
            self._refresh_table()
            self._stop_tunnel_worker(tunnel)
        else:
            tunnel.status = TunnelStatus.STARTING
            self._refresh_table()
            self._start_tunnel_worker(tunnel)

    def action_refresh(self) -> None:
        self._reconcile_tunnel_states_worker()
        self.notify("Refreshing tunnel states...")

    def action_show_help(self) -> None:
        from sshtm.screens.help import HelpScreen
        self.push_screen(HelpScreen())

    def _get_selected_tunnel(self) -> Tunnel | None:
        try:
            from sshtm.screens.main import MainScreen
            main_screen = self.query_one(MainScreen)
            return main_screen.get_selected_tunnel(self.tunnels)
        except Exception:
            return None
