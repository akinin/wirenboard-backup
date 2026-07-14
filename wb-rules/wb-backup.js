// Wiren Board Backup virtual device.

function backupTitle(ru, en) {
  return {ru: ru, en: en};
}

function readableTime(value) {
  if (!value || value === "unknown") return "—";
  var date = new Date(value);
  if (isNaN(date.getTime())) return value;
  function pad(number) { return number < 10 ? "0" + number : String(number); }
  return pad(date.getDate()) + "." + pad(date.getMonth() + 1) + "." + date.getFullYear() +
    " " + pad(date.getHours()) + ":" + pad(date.getMinutes()) + ":" + pad(date.getSeconds());
}

function readableResult(value) {
  if (value === "success") return "Успешно";
  if (value === "error") return "Ошибка";
  if (value === "running") return "Выполняется";
  return "—";
}

function readableStatus(state) {
  var profile = state.running_profile === "full" ? "полный архив" : "конфигурации";
  if (state.status === "running") return "Выполняется: " + profile;
  if (state.status === "error") {
    var failed = state.last_profile === "full" ? "полный архив" : "конфигурации";
    return "Ошибка: " + failed + (state.error ? " — " + state.error : "");
  }
  if (state.status === "success") return "Готово";
  return "Ожидание";
}

defineVirtualDevice("wb_backup", {
  title: backupTitle("Резервное копирование", "Backup"),
  cells: {
    status: {type: "text", value: "Ожидание", readonly: true, title: backupTitle("Статус", "Status")},
    config_time: {type: "text", value: "—", readonly: true, title: backupTitle("Конфигурации: время", "Configuration: time")},
    config_file: {type: "text", value: "—", readonly: true, title: backupTitle("Конфигурации: файл", "Configuration: file")},
    config_result: {type: "text", value: "—", readonly: true, title: backupTitle("Конфигурации: результат", "Configuration: result")},
    run_config: {type: "pushbutton", title: backupTitle("Запустить бэкап конфигураций", "Run configuration backup")},
    full_time: {type: "text", value: "—", readonly: true, title: backupTitle("Полный: время", "Full: time")},
    full_file: {type: "text", value: "—", readonly: true, title: backupTitle("Полный: файл", "Full: file")},
    full_result: {type: "text", value: "—", readonly: true, title: backupTitle("Полный: результат", "Full: result")},
    run_full: {type: "pushbutton", title: backupTitle("Запустить полный бэкап", "Run full backup")}
  }
});

trackMqtt("/wirenboard/backup/state", function(message) {
  try {
    var state = JSON.parse(message.value);
    dev["wb_backup/status"] = readableStatus(state);
    dev["wb_backup/config_time"] = readableTime(state.last_config);
    dev["wb_backup/config_file"] = state.last_config_file || "—";
    dev["wb_backup/config_result"] = readableResult(state.last_config_result || (state.last_profile === "config" ? state.last_result : ""));
    dev["wb_backup/full_time"] = readableTime(state.last_full);
    dev["wb_backup/full_file"] = state.last_full_file || "—";
    dev["wb_backup/full_result"] = readableResult(state.last_full_result || (state.last_profile === "full" ? state.last_result : ""));
  } catch (error) {
    dev["wb_backup/status"] = "Ошибка обработки состояния";
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
