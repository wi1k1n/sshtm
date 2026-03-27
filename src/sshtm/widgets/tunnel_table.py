"""Custom DataTable with wraparound cursor and an 'unselected' ghost position."""

from __future__ import annotations

from textual.widgets import DataTable
from textual.widgets._data_table import CellType


class TunnelTable(DataTable[CellType]):
    """DataTable that cycles through an invisible 'no selection' state.

    Navigation order (down): row 0 -> row 1 -> ... -> row N-1 -> *unselected* -> row 0
    Navigation order (up):   row 0 -> *unselected* -> row N-1 -> ... -> row 1 -> row 0
    """

    _selection_active: bool = True

    @property
    def selection_active(self) -> bool:
        """Whether a row is currently selected (not in ghost/unselected state)."""
        return self._selection_active and self.row_count > 0

    def _enter_unselected(self) -> None:
        """Transition to the unselected ghost state."""
        self._selection_active = False
        self.show_cursor = False

    def _enter_selected(self, row: int) -> None:
        """Transition to a selected state at the given row."""
        self._selection_active = True
        self.show_cursor = True
        self.move_cursor(row=row)

    def action_cursor_down(self) -> None:
        """Move cursor down with wraparound through unselected state."""
        if self.row_count == 0:
            return

        if not self._selection_active:
            self._enter_selected(0)
            return

        current = self.cursor_row
        if current >= self.row_count - 1:
            self._enter_unselected()
        else:
            self.move_cursor(row=current + 1)

    def action_cursor_up(self) -> None:
        """Move cursor up with wraparound through unselected state."""
        if self.row_count == 0:
            return

        if not self._selection_active:
            self._enter_selected(self.row_count - 1)
            return

        current = self.cursor_row
        if current <= 0:
            self._enter_unselected()
        else:
            self.move_cursor(row=current - 1)

    def action_select_cursor(self) -> None:
        if not self._selection_active:
            return
        super().action_select_cursor()

    def on_click(self) -> None:
        """Ensure clicking a row re-activates selection."""
        if self.row_count > 0:
            self._selection_active = True
            self.show_cursor = True
