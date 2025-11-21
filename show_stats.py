# /opt/jukebox/show_stats.py
# Used for diagnostic, but has since been added to the webUI
from mpv_controller import MPVController
import time

# Connect to the running MPV instance
ctrl = MPVController()
ctrl.connect()

# Give it a split second to connect
time.sleep(0.5)

# 'stats/display-stats' toggles persistent stats
print("Toggling On-Screen Stats...")
ctrl.command("script-binding", "stats/display-stats-toggle")

# Disconnect purely
ctrl._is_running.clear()