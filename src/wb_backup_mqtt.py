#!/usr/bin/env python3
import json
import pathlib
import subprocess
import sys

CONFIG = pathlib.Path("/etc/wb-backup/config.json")


def load():
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def save(cfg):
    temp = CONFIG.with_suffix(".tmp")
    temp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.chmod(0o600)
    temp.replace(CONFIG)


def publish(cfg, topic, payload, retain=True):
    command = ["mosquitto_pub", "-h", str(cfg.get("mqtt_host", "127.0.0.1")),
               "-p", str(cfg.get("mqtt_port", 1883)), "-t", topic, "-m", str(payload)]
    if retain:
        command.append("-r")
    subprocess.run(command, check=False)


def cleanup_home_assistant_discovery(cfg):
    discovery_prefix = cfg.get("ha_discovery_prefix", "homeassistant").rstrip("/")
    host = subprocess.run(["hostname", "-s"], check=True, text=True,
                          stdout=subprocess.PIPE).stdout.strip()
    device_id = f"wb_backup_{host}"
    entities = {
        "button": ("run", "run_config", "run_full"),
        "switch": ("enabled",),
        "sensor": ("status", "last_backup", "last_config", "last_full",
                   "config_file", "full_file", "config_result", "full_result"),
        "binary_sensor": ("problem",),
        "number": ("keep_count", "hour", "minute", "config_keep_count",
                   "config_hour", "config_minute", "full_keep_count",
                   "full_weekday", "full_hour", "full_minute"),
    }
    for component, identifiers in entities.items():
        for ident in identifiers:
            publish(cfg, f"{discovery_prefix}/{component}/{device_id}/{ident}/config", "")


def handle(cfg, topic, payload):
    suffix = topic.rsplit("/", 1)[-1]
    if suffix in ("run_config", "run_full"):
        profile = suffix.removeprefix("run_")
        subprocess.Popen(["systemctl", "start", f"wb-backup@{profile}.service"])
        return cfg
    if suffix == "enabled":
        cfg["enabled"] = payload.strip().upper() in ("ON", "1", "TRUE")
    else:
        profile, separator, key = suffix.partition("_")
        if profile not in ("config", "full") or not separator:
            raise ValueError("unknown setting")
        limits = {"keep_count": (1, 365 if profile == "config" else 52),
                  "weekday": (1, 7), "hour": (0, 23), "minute": (0, 59)}
        if key not in limits:
            raise ValueError("unknown setting")
        low, high = limits[key]
        cfg[profile + "_backup"][key] = max(low, min(high, int(float(payload))))
    save(cfg)
    subprocess.run(["/opt/wirenboard-backup/bin/wb-backup-ctl", "apply"], check=False)
    return load()


def main():
    cfg = load()
    prefix = cfg.get("mqtt_prefix", "/wirenboard/backup").rstrip("/")
    publish(cfg, prefix + "/availability", "online")
    cleanup_home_assistant_discovery(cfg)
    subprocess.run(["/opt/wirenboard-backup/bin/wb-backup", "publish"], check=False)
    command = ["mosquitto_sub", "-h", str(cfg.get("mqtt_host", "127.0.0.1")),
               "-p", str(cfg.get("mqtt_port", 1883)), "-t", prefix + "/command/+", "-v"]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, text=True, bufsize=1)
    assert process.stdout is not None
    for line in process.stdout:
        topic, _, payload = line.rstrip("\n").partition(" ")
        try:
            cfg = handle(cfg, topic, payload)
        except Exception as exc:
            print(f"MQTT command error: {exc}", file=sys.stderr, flush=True)
    return process.wait()


if __name__ == "__main__":
    sys.exit(main())
