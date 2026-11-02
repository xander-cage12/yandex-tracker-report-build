import os
from tracker_report_gui import ReportGUI

if __name__ == "__main__":
    app = ReportGUI()
    if os.environ.get("YTR_BUILD_SMOKE_TEST") == "1":
        app.after(1500, app.destroy)
    app.mainloop()
