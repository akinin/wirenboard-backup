// Wiren Board Backup virtual device.
// Commands and state are bridged through the local MQTT broker.

defineVirtualDevice("wb_backup", {
  title: "Резервное копирование",
  cells: {
    status: {type: "text", value: "unknown", readonly: true, title: "Статус"},
    running_profile: {type: "text", value: "", readonly: true, title: "Выполняется"},
    last_result: {type: "text", value: "unknown", readonly: true, title: "Последний результат"},
    last_config: {type: "text", value: "unknown", readonly: true, title: "Последние конфигурации"},
    last_full: {type: "text", value: "unknown", readonly: true, title: "Последний полный"},
    last_file: {type: "text", value: "", readonly: true, title: "Последний файл"},
    error: {type: "text", value: "", readonly: true, title: "Ошибка"},
    run_config: {type: "pushbutton", title: "Запустить конфигурации"},
    run_full: {type: "pushbutton", title: "Запустить полный"}
  }
});

trackMqtt("/wirenboard/backup/state", function(message) {
  try {
    var state = JSON.parse(message.value);
    dev["wb_backup/status"] = state.status || "unknown";
    dev["wb_backup/running_profile"] = state.running_profile || "";
    dev["wb_backup/last_result"] = state.last_result || "unknown";
    dev["wb_backup/last_config"] = state.last_config || "unknown";
    dev["wb_backup/last_full"] = state.last_full || "unknown";
    dev["wb_backup/last_file"] = state.last_config_file || state.last_full_file || "";
    dev["wb_backup/error"] = state.error || "";
  } catch (error) {
    log.error("wb-backup: invalid state: " + error);
  }
});

defineRule("wb_backup_run_config", {
  whenChanged: "wb_backup/run_config",
  then: function(value) {
    if (value) publish("/wirenboard/backup/command/run_config", "run");
  }
});

defineRule("wb_backup_run_full", {
  whenChanged: "wb_backup/run_full",
  then: function(value) {
    if (value) publish("/wirenboard/backup/command/run_full", "run");
  }
});
