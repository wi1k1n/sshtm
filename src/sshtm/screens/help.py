from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static


HELP_TEXT = """\
[b]Keybindings[/b]

[b]n[/b]       Create a new tunnel
[b]s[/b]       Start/stop selected tunnel
[b]e[/b]       Edit selected tunnel
[b]d[/b]       Delete selected tunnel
[b]i[/b]       Show tunnel info & errors
[b]l[/b]       View SSH log for tunnel
[b]r[/b]       Refresh tunnel states
[b]?[/b]       Show this help
[b]q[/b]       Quit sshtm

[b]Navigation[/b]

\u2191/\u2193     Move selection
Enter   Start/stop selected tunnel

[b]Tunnel Directions[/b]

L\u2192R     Local forward (-L): binds a local port,
        forwards traffic to remote host:port
        through the SSH connection.

R\u2192L     Remote forward (-R): binds a port on the
        remote server, forwards traffic back to
        your local host:port.

[b]Troubleshooting[/b]

If a tunnel shows [red]\u2716[/red] error status:
\u2022 Press [b]i[/b] to view error details
\u2022 Press [b]l[/b] to read the SSH log
\u2022 Press [b]s[/b] to retry starting it

[b]Persistence[/b]

Tunnels run as background SSH processes
and survive after exiting sshtm.
On next launch, sshtm reconnects to
active tunnels automatically.
"""


class HelpScreen(ModalScreen[None]):
    BINDINGS = [
        ("escape", "dismiss_help", "Close"),
        ("question_mark", "dismiss_help", "Close"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="help-container"):
            yield Static("sshtm Help", id="help-title")
            yield Static(HELP_TEXT)
            yield Button("Close", variant="primary", id="help-close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "help-close":
            self.dismiss()

    def action_dismiss_help(self) -> None:
        self.dismiss()
