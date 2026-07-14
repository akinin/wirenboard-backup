#!/usr/bin/env python3
import json
import pathlib

cfg = json.loads(pathlib.Path("/etc/wb-backup/config.json").read_text(encoding="utf-8"))
cfg.setdefault("config_backup", {}).setdefault("enabled", True)
cfg.setdefault("full_backup", {}).setdefault("enabled", True)
days = {1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri", 6: "Sat", 7: "Sun"}

config = cfg["config_backup"]
full = cfg["full_backup"]
def calendar(settings):
    clock = f"{int(settings['hour']):02d}:{int(settings['minute']):02d}:00"
    frequency = settings.get("frequency", "daily")
    if frequency == "weekly":
        return f"{days[int(settings.get('weekday', 1))]} *-*-* {clock}"
    if frequency == "monthly":
        return f"*-*-{int(settings.get('monthday', 1)):02d} {clock}"
    return f"*-*-* {clock}"


values = {"wb-backup-config.timer": calendar(config),
          "wb-backup-full.timer": calendar(full)}
for unit, schedule in values.items():
    directory = pathlib.Path("/etc/systemd/system") / (unit + ".d")
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "schedule.conf").write_text(
        f"[Timer]\nOnCalendar=\nOnCalendar={schedule}\n", encoding="utf-8")
