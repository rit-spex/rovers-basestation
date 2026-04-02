from __future__ import annotations

from unittest.mock import Mock, patch

from xbee.display.gui import TkinterDisplay


@patch.dict("os.environ", {"XBEE_NO_GUI": ""}, clear=False)
@patch("xbee.display.gui.TK_AVAILABLE", True)
@patch("xbee.display.gui.ttk")
@patch("xbee.display.gui.tk")
def test_tkinter_display_quit_joins_update_thread(mock_tk, mock_ttk):
    mock_root = Mock()
    mock_root.after_idle = Mock()
    # Return the mock object for Tk()
    mock_tk.Tk.return_value = mock_root

    display = TkinterDisplay()
    # Ensure the update thread is alive initially
    assert hasattr(display, "update_thread")
    assert display.update_thread.is_alive()

    try:
        # Quit and ensure update thread is joined/finished
        display.quit()
        display.update_thread.join(timeout=2.0)
        assert not display.update_thread.is_alive()
    finally:
        # Ensure cleanup even if the test assertion fails
        if display.update_thread.is_alive():
            display.quit()
            display.update_thread.join(timeout=2.0)
