#!/usr/bin/env python3
import argparse
import datetime as dt
import fcntl
import json
import os
import pathlib
import shutil
import socket
import subprocess
import sys
import tempfile
import time

CONFIG = pathlib.Path("/etc/wb-backup/config.json")
STATE = pathlib.Path("/var/lib/wb-backup/state.json")
LOCK = pathlib.Path("/run/lock/wb-backup.lock")
NATIVE_SCRIPTS = {
    "config": pathlib.Path("/usr/lib/cgi-bin/download_configs.sh"),
    "full": pathlib.Path("/usr/lib/cgi-bin/download_everything.sh"),
}


def load_json(path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {} if default is None else default


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(value, out, ensure_ascii=False, indent=2, sort_keys=True)
            out.write("\n")
        os.chmod(name, 0o600)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def bounded(value, low, high):
    return max(low, min(high, int(value)))


def config():
    cfg = load_json(CONFIG)
    required = ("nfs_server", "nfs_export", "mount_point", "destination")
    missing = [key for key in required if not cfg.get(key)]
    if missing:
        raise RuntimeError("missing settings: " + ", ".join(missing))
    defaults = {
        "config_backup": {"enabled": True, "hour": 3, "minute": 30, "keep_count": 14},
        "full_backup": {"enabled": True, "weekday": 7, "hour": 4, "minute": 30, "keep_count": 4},
    }
    for profile, values in defaults.items():
        current = cfg.setdefault(profile, {})
        for key, value in values.items():
            current.setdefault(key, value)
        current["hour"] = bounded(current["hour"], 0, 23)
        current["minute"] = bounded(current["minute"], 0, 59)
        current["keep_count"] = bounded(current["keep_count"], 1, 365)
    cfg["full_backup"]["weekday"] = bounded(cfg["full_backup"]["weekday"], 1, 7)
    return cfg


def run(command, **kwargs):
    return subprocess.run(command, check=True, text=True, **kwargs)


def mqtt_publish(cfg, suffix, payload, retain=True):
    command = ["mosquitto_pub", "-h", str(cfg.get("mqtt_host", "127.0.0.1")),
               "-p", str(cfg.get("mqtt_port", 1883)), "-t",
               cfg.get("mqtt_prefix", "/wirenboard/backup").rstrip("/") + "/" + suffix,
               "-m", payload]
    if retain:
        command.append("-r")
    subprocess.run(command, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def publish_state(cfg, **changes):
    state = load_json(STATE)
    state.update(changes)
    for profile in ("config", "full"):
        settings = cfg[profile + "_backup"]
        for key, value in settings.items():
            state[f"{profile}_{key}"] = value
    atomic_json(STATE, state)
    mqtt_publish(cfg, "state", json.dumps(state, ensure_ascii=False, separators=(",", ":")))


def mounted_at(path):
    resolved = os.path.realpath(path)
    with open("/proc/self/mountinfo", encoding="utf-8") as mounts:
        return any(len(parts := line.split()) > 4 and parts[4] == resolved for line in mounts)


def ensure_mount(cfg):
    mount_point = pathlib.Path(cfg["mount_point"])
    mount_point.mkdir(parents=True, exist_ok=True)
    if not mounted_at(mount_point):
        source = f'{cfg["nfs_server"]}:{cfg["nfs_export"]}'
        command = ["mount", "-t", "nfs"]
        if cfg.get("nfs_options"):
            command += ["-o", cfg["nfs_options"]]
        command += [source, str(mount_point)]
        run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    probe = mount_point / ".wb-backup-write-test"
    probe.write_text(str(time.time()), encoding="ascii")
    probe.unlink()
    return mount_point


def strip_cgi_headers(source, destination):
    first = source.read(16)
    if first.startswith(b"\x1f\x8b"):
        destination.write(first)
        shutil.copyfileobj(source, destination)
        return
    data = first + source.read(65536)
    positions = [pos for pos in (data.find(b"\r\n\r\n"), data.find(b"\n\n")) if pos >= 0]
    if not positions:
        raise RuntimeError("native backup did not return an archive or CGI headers")
    pos = min(positions)
    separator = 4 if data[pos:pos + 4] == b"\r\n\r\n" else 2
    body = data[pos + separator:]
    if not body.startswith(b"\x1f\x8b"):
        raise RuntimeError("native backup output is not a gzip archive")
    destination.write(body)
    shutil.copyfileobj(source, destination)


def create_archive(profile, target):
    script = NATIVE_SCRIPTS[profile]
    if not script.is_file() or not os.access(script, os.X_OK):
        raise RuntimeError(f"native backup script is unavailable: {script}")
    environment = os.environ.copy()
    environment.setdefault("MOUNT_DIR", "/")
    process = subprocess.Popen([str(script)], stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, env=environment)
    assert process.stdout is not None
    with open(target, "wb") as out:
        strip_cgi_headers(process.stdout, out)
    stderr = process.stderr.read().decode("utf-8", "replace") if process.stderr else ""
    code = process.wait()
    if code:
        raise RuntimeError(f"native {profile} backup failed ({code}): {stderr.strip()}")
    if target.stat().st_size < 1024:
        raise RuntimeError("native backup archive is unexpectedly small")


def rotate(directory, profile, keep_count):
    archives = sorted(directory.glob(f"wb-{profile}-*.tar.gz"),
                      key=lambda path: path.stat().st_mtime, reverse=True)
    for old in archives[keep_count:]:
        old.unlink()


def backup(profile):
    cfg = config()
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    with open(LOCK, "w", encoding="ascii") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("another backup is already running")
        started = dt.datetime.now(dt.timezone.utc)
        publish_state(cfg, status="running", running_profile=profile,
                      started_at=started.isoformat(), error="")
        try:
            mount_point = ensure_mount(cfg)
            host = socket.gethostname().split(".")[0]
            destination = mount_point / cfg["destination"] / host / profile
            destination.mkdir(parents=True, exist_ok=True)
            stamp = dt.datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
            final = destination / f"wb-{profile}-{stamp}.tar.gz"
            partial = destination / (final.name + ".partial")
            try:
                create_archive(profile, partial)
                os.replace(partial, final)
            finally:
                partial.unlink(missing_ok=True)
            rotate(destination, profile, cfg[profile + "_backup"]["keep_count"])
            finished = dt.datetime.now(dt.timezone.utc)
            publish_state(cfg, status="success", running_profile="",
                          last_result="success", last_profile=profile,
                          **{f"last_{profile}": finished.isoformat(),
                             f"last_{profile}_file": final.name,
                             f"last_{profile}_size": final.stat().st_size,
                             f"last_{profile}_result": "success",
                             f"last_{profile}_error": ""},
                          duration_seconds=round((finished - started).total_seconds(), 1), error="")
            return 0
        except Exception as exc:
            publish_state(cfg, status="error", running_profile="", last_result="error",
                          last_profile=profile, error=str(exc),
                          **{f"last_{profile}_result": "error",
                             f"last_{profile}_error": str(exc)})
            raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("run", "status", "publish"))
    parser.add_argument("profile", nargs="?", choices=("config", "full"))
    args = parser.parse_args()
    if args.command == "run":
        if not args.profile:
            parser.error("run requires profile: config or full")
        return backup(args.profile)
    if args.command == "status":
        print(json.dumps({"config": config(), "state": load_json(STATE)},
                         ensure_ascii=False, indent=2))
        return 0
    cfg = config()
    publish_state(cfg, status=load_json(STATE).get("status", "idle"))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(f"wb-backup: {error}", file=sys.stderr)
        sys.exit(1)
