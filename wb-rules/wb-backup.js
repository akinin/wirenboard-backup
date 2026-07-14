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
  title: "Резервное копирование",
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

defineVirtualDevice("wb_backup_settings", {
  title: "Настройки резервного копирования",
  cells: {
    enabled: {type: "switch", value: true, title: backupTitle("Расписание включено", "Schedule enabled")},
    config_hour: {type: "range", value: 3, min: 0, max: 23, title: backupTitle("Конфигурации: час", "Configuration: hour")},
    config_minute: {type: "range", value: 30, min: 0, max: 59, title: backupTitle("Конфигурации: минута", "Configuration: minute")},
    config_keep_count: {type: "range", value: 14, min: 1, max: 365, title: backupTitle("Конфигурации: хранить копий", "Configuration: copies to keep")},
    full_weekday: {type: "range", value: 7, min: 1, max: 7, title: backupTitle("Полный: день недели (1=Пн, 7=Вс)", "Full: weekday (1=Mon, 7=Sun)")},
    full_hour: {type: "range", value: 4, min: 0, max: 23, title: backupTitle("Полный: час", "Full: hour")},
    full_minute: {type: "range", value: 30, min: 0, max: 59, title: backupTitle("Полный: минута", "Full: minute")},
    full_keep_count: {type: "range", value: 4, min: 1, max: 52, title: backupTitle("Полный: хранить копий", "Full: copies to keep")}
  }
});

var updatingBackupSettings = false;

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
    updatingBackupSettings = true;
    dev["wb_backup_settings/enabled"] = Boolean(state.enabled);
    dev["wb_backup_settings/config_hour"] = Number(state.config_hour);
    dev["wb_backup_settings/config_minute"] = Number(state.config_minute);
    dev["wb_backup_settings/config_keep_count"] = Number(state.config_keep_count);
    dev["wb_backup_settings/full_weekday"] = Number(state.full_weekday);
    dev["wb_backup_settings/full_hour"] = Number(state.full_hour);
    dev["wb_backup_settings/full_minute"] = Number(state.full_minute);
    dev["wb_backup_settings/full_keep_count"] = Number(state.full_keep_count);
    updatingBackupSettings = false;
  } catch (error) {
    updatingBackupSettings = false;
    dev["wb_backup/status"] = "Ошибка обработки состояния";
    log.error("wb-backup: invalid state: " + error);
  }
});

function defineBackupSettingRule(control, command) {
  defineRule("wb_backup_setting_" + control, {
    whenChanged: "wb_backup_settings/" + control,
    then: function(value) {
      if (!updatingBackupSettings) publish("/wirenboard/backup/command/" + command, String(value));
    }
  });
}

defineBackupSettingRule("enabled", "enabled");
defineBackupSettingRule("config_hour", "config_hour");
defineBackupSettingRule("config_minute", "config_minute");
defineBackupSettingRule("config_keep_count", "config_keep_count");
defineBackupSettingRule("full_weekday", "full_weekday");
defineBackupSettingRule("full_hour", "full_hour");
defineBackupSettingRule("full_minute", "full_minute");
defineBackupSettingRule("full_keep_count", "full_keep_count");

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
