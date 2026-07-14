#!/usr/bin/env python3
import json
import pathlib

cfg = json.loads(pathlib.Path("/etc/wb-backup/config.json").read_text(encoding="utf-8"))
days = {1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri", 6: "Sat", 7: "Sun"}

config = cfg["config_backup"]
full = cfg["full_backup"]
values = {
    "wb-backup-config.timer": f"*-*-* {int(config['hour']):02d}:{int(config['minute']):02d}:00",
    "wb-backup-full.timer": f"{days[int(full['weekday'])]} *-*-* {int(full['hour']):02d}:{int(full['minute']):02d}:00",
}
for unit, schedule in values.items():
    directory = pathlib.Path("/etc/systemd/system") / (unit + ".d")
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "schedule.conf").write_text(
        f"[Timer]\nOnCalendar=\nOnCalendar={schedule}\n", encoding="utf-8")
