#!/usr/bin/env python3
import json
import pathlib
import socket
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


def base_entity(prefix, device, unique_id):
    return {"unique_id": unique_id, "device": device,
            "availability": [{"topic": prefix + "/availability"}]}


def discovery(cfg):
    prefix = cfg.get("mqtt_prefix", "/wirenboard/backup").rstrip("/")
    discovery_prefix = cfg.get("ha_discovery_prefix", "homeassistant").rstrip("/")
    host = socket.gethostname().split(".")[0]
    device_id = f"wb_backup_{host}"
    device = {"identifiers": [device_id], "name": f"Wiren Board Backup {host}",
              "manufacturer": "Wiren Board community", "model": "NFS Backup"}
    legacy = (("button", "run"), ("number", "keep_count"), ("number", "hour"),
              ("number", "minute"), ("sensor", "last_backup"))
    for component, ident in legacy:
        publish(cfg, f"{discovery_prefix}/{component}/{device_id}/{ident}/config", "")
    state = prefix + "/state"
    entities = {
        ("button", "run_config"): {"name": "Запустить бэкап конфигураций", "command_topic": prefix + "/command/run_config", "payload_press": "run", "icon": "mdi:file-cog"},
        ("button", "run_full"): {"name": "Запустить полный бэкап", "command_topic": prefix + "/command/run_full", "payload_press": "run", "icon": "mdi:backup-restore"},
        ("switch", "enabled"): {"name": "Расписание включено", "command_topic": prefix + "/command/enabled", "state_topic": state, "value_template": "{{ 'ON' if value_json.enabled else 'OFF' }}", "payload_on": "ON", "payload_off": "OFF"},
        ("sensor", "status"): {"name": "Статус", "state_topic": state, "value_template": "{{ value_json.status }}", "json_attributes_topic": state, "icon": "mdi:cloud-upload"},
        ("sensor", "last_config"): {"name": "Последний бэкап конфигураций", "state_topic": state, "value_template": "{{ value_json.last_config | default('unknown') }}", "device_class": "timestamp"},
        ("sensor", "last_full"): {"name": "Последний полный бэкап", "state_topic": state, "value_template": "{{ value_json.last_full | default('unknown') }}", "device_class": "timestamp"},
        ("binary_sensor", "problem"): {"name": "Ошибка резервного копирования", "state_topic": state, "value_template": "{{ 'ON' if value_json.status == 'error' else 'OFF' }}", "payload_on": "ON", "payload_off": "OFF", "device_class": "problem"},
    }
    numbers = {
        "config_keep_count": ("Конфигурации: количество копий", 1, 365),
        "config_hour": ("Конфигурации: час", 0, 23),
        "config_minute": ("Конфигурации: минута", 0, 59),
        "full_keep_count": ("Полные: количество копий", 1, 52),
        "full_weekday": ("Полные: день недели (1=Пн, 7=Вс)", 1, 7),
        "full_hour": ("Полные: час", 0, 23),
        "full_minute": ("Полные: минута", 0, 59),
    }
    for ident, (name, low, high) in numbers.items():
        entities[("number", ident)] = {"name": name, "command_topic": prefix + "/command/" + ident,
                                        "state_topic": state, "value_template": "{{ value_json." + ident + " }}",
                                        "min": low, "max": high, "step": 1, "mode": "box"}
    for (component, ident), data in entities.items():
        data.update(base_entity(prefix, device, f"{device_id}_{ident}"))
        topic = f"{discovery_prefix}/{component}/{device_id}/{ident}/config"
        publish(cfg, topic, json.dumps(data, ensure_ascii=False, separators=(",", ":")))


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
    discovery(cfg)
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
