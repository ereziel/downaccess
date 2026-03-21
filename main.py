import wx
from app.core import updater
from app.ui.main_window import MainWindow


def main():
    app = wx.App(False)
    frame = MainWindow(None)
    frame.Show()

    updater.bootstrap(
        on_update_done=lambda status, info: wx.CallAfter(
            frame.on_ytdlp_update_done, status, info
        )
    )
    frame.check_app_update_at_startup()

    app.MainLoop()


if __name__ == "__main__":
    main()
