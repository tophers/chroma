from mpv_controller import MPVController
import time

ctrl = MPVController()
ctrl.connect()
time.sleep(0.5)

print("Toggling On-Screen Stats...")
ctrl.command("script-binding", "stats/display-stats-toggle")

ctrl._is_running.clear()
