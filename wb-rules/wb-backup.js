// Wiren Board Backup virtual devices.

function backupTitle(ru, en) {
  return {ru: ru, en: en};
}

function padBackupNumber(number) {
  return number < 10 ? "0" + number : String(number);
}

function readableTime(value) {
  if (!value || value === "unknown") return "—";
  var date = new Date(value);
  if (isNaN(date.getTime())) return value;
  return padBackupNumber(date.getDate()) + "." + padBackupNumber(date.getMonth() + 1) +
    "." + date.getFullYear() + " " + padBackupNumber(date.getHours()) + ":" +
    padBackupNumber(date.getMinutes()) + ":" + padBackupNumber(date.getSeconds());
}

function readableResult(value) {
  if (value === "success") return "Успешно";
  if (value === "error") return "Ошибка";
  if (value === "running") return "Выполняется";
  return "—";
}

function profileStatus(state, profile) {
  if (state.status === "running" && state.running_profile === profile) return "Выполняется";
  if (state.status === "error" && state.last_profile === profile) {
    return "Ошибка" + (state.error ? ": " + state.error : "");
  }
  if (state["last_" + profile + "_result"] === "success") return "Готово";
  return "Ожидание";
}

function backupFrequencyEnum() {
  return {
    daily: backupTitle("Ежедневно", "Daily"),
    weekly: backupTitle("Еженедельно", "Weekly"),
    monthly: backupTitle("Ежемесячно", "Monthly")
  };
}

function backupWeekdayEnum() {
  return {
    1: backupTitle("Понедельник", "Monday"),
    2: backupTitle("Вторник", "Tuesday"),
    3: backupTitle("Среда", "Wednesday"),
    4: backupTitle("Четверг", "Thursday"),
    5: backupTitle("Пятница", "Friday"),
    6: backupTitle("Суббота", "Saturday"),
    7: backupTitle("Воскресенье", "Sunday")
  };
}

function backupMonthdayEnum() {
  var result = {};
  for (var day = 1; day <= 28; day += 1) {
    result[String(day)] = backupTitle(String(day), String(day));
  }
  return result;
}

defineVirtualDevice("wb_backup_config", {
  title: "Бэкап конфигураций",
  cells: {
    status: {type: "text", value: "Ожидание", readonly: true, title: backupTitle("Статус", "Status")},
    last_time: {type: "text", value: "—", readonly: true, title: backupTitle("Последний запуск", "Last run")},
    last_file: {type: "text", value: "—", readonly: true, title: backupTitle("Последний файл", "Last file")},
    last_result: {type: "text", value: "—", readonly: true, title: backupTitle("Результат", "Result")},
    run: {type: "pushbutton", title: backupTitle("Запустить сейчас", "Run now")},
    enabled: {type: "switch", value: true, title: backupTitle("Запуск по расписанию", "Scheduled backup")},
    frequency: {type: "text", value: "daily", readonly: false, enum: backupFrequencyEnum(), title: backupTitle("Периодичность", "Frequency")},
    weekday: {type: "text", value: "1", readonly: false, enum: backupWeekdayEnum(), title: backupTitle("День недели", "Weekday")},
    monthday: {type: "text", value: "1", readonly: false, enum: backupMonthdayEnum(), title: backupTitle("Число месяца", "Month day")},
    schedule: {type: "text", value: "03:30", readonly: false, title: backupTitle("Время запуска (ЧЧ:ММ)", "Start time (HH:MM)")},
    keep_count: {type: "text", value: "14", readonly: false, title: backupTitle("Хранить копий", "Copies to keep")}
  }
});

defineVirtualDevice("wb_backup_full", {
  title: "Полный бэкап",
  cells: {
    status: {type: "text", value: "Ожидание", readonly: true, title: backupTitle("Статус", "Status")},
    last_time: {type: "text", value: "—", readonly: true, title: backupTitle("Последний запуск", "Last run")},
    last_file: {type: "text", value: "—", readonly: true, title: backupTitle("Последний файл", "Last file")},
    last_result: {type: "text", value: "—", readonly: true, title: backupTitle("Результат", "Result")},
    run: {type: "pushbutton", title: backupTitle("Запустить сейчас", "Run now")},
    enabled: {type: "switch", value: true, title: backupTitle("Запуск по расписанию", "Scheduled backup")},
    frequency: {type: "text", value: "weekly", readonly: false, enum: backupFrequencyEnum(), title: backupTitle("Периодичность", "Frequency")},
    weekday: {type: "text", value: "7", readonly: false, enum: backupWeekdayEnum(), title: backupTitle("День недели", "Weekday")},
    monthday: {type: "text", value: "1", readonly: false, enum: backupMonthdayEnum(), title: backupTitle("Число месяца", "Month day")},
    schedule: {type: "text", value: "04:30", readonly: false, title: backupTitle("Время запуска (ЧЧ:ММ)", "Start time (HH:MM)")},
    keep_count: {type: "text", value: "4", readonly: false, title: backupTitle("Хранить копий", "Copies to keep")}
  }
});

var updatingBackupDevices = false;

trackMqtt("/wirenboard/backup/state", function(message) {
  try {
    var state = JSON.parse(message.value);
    updatingBackupDevices = true;
    dev["wb_backup_config/status"] = profileStatus(state, "config");
    dev["wb_backup_config/last_time"] = readableTime(state.last_config);
    dev["wb_backup_config/last_file"] = state.last_config_file || "—";
    dev["wb_backup_config/last_result"] = readableResult(state.last_config_result);
    dev["wb_backup_config/enabled"] = Boolean(state.config_enabled);
    dev["wb_backup_config/frequency"] = state.config_frequency || "daily";
    dev["wb_backup_config/weekday"] = String(state.config_weekday || 1);
    dev["wb_backup_config/monthday"] = String(state.config_monthday || 1);
    dev["wb_backup_config/schedule"] = padBackupNumber(Number(state.config_hour)) + ":" + padBackupNumber(Number(state.config_minute));
    dev["wb_backup_config/keep_count"] = String(state.config_keep_count);

    dev["wb_backup_full/status"] = profileStatus(state, "full");
    dev["wb_backup_full/last_time"] = readableTime(state.last_full);
    dev["wb_backup_full/last_file"] = state.last_full_file || "—";
    dev["wb_backup_full/last_result"] = readableResult(state.last_full_result);
    dev["wb_backup_full/enabled"] = Boolean(state.full_enabled);
    dev["wb_backup_full/frequency"] = state.full_frequency || "weekly";
    dev["wb_backup_full/weekday"] = String(state.full_weekday || 7);
    dev["wb_backup_full/monthday"] = String(state.full_monthday || 1);
    dev["wb_backup_full/schedule"] = padBackupNumber(Number(state.full_hour)) + ":" + padBackupNumber(Number(state.full_minute));
    dev["wb_backup_full/keep_count"] = String(state.full_keep_count);
    updatingBackupDevices = false;
  } catch (error) {
    updatingBackupDevices = false;
    dev["wb_backup_config/status"] = "Ошибка обработки состояния";
    dev["wb_backup_full/status"] = "Ошибка обработки состояния";
    log.error("wb-backup: invalid state: " + error);
  }
});

function backupRule(name, control, command) {
  defineRule(name, {
    whenChanged: control,
    then: function(value) {
      if (!updatingBackupDevices) publish("/wirenboard/backup/command/" + command, String(value));
    }
  });
}

defineRule("wb_backup_config_run", {
  whenChanged: "wb_backup_config/run",
  then: function(value) {
    if (value) publish("/wirenboard/backup/command/run_config", "run");
  }
});

defineRule("wb_backup_full_run", {
  whenChanged: "wb_backup_full/run",
  then: function(value) {
    if (value) publish("/wirenboard/backup/command/run_full", "run");
  }
});

backupRule("wb_backup_config_enabled", "wb_backup_config/enabled", "config_enabled");
backupRule("wb_backup_config_frequency", "wb_backup_config/frequency", "config_frequency");
backupRule("wb_backup_config_weekday", "wb_backup_config/weekday", "config_weekday");
backupRule("wb_backup_config_monthday", "wb_backup_config/monthday", "config_monthday");
backupRule("wb_backup_config_schedule", "wb_backup_config/schedule", "config_schedule");
backupRule("wb_backup_config_keep", "wb_backup_config/keep_count", "config_keep_count");
backupRule("wb_backup_full_enabled", "wb_backup_full/enabled", "full_enabled");
backupRule("wb_backup_full_frequency", "wb_backup_full/frequency", "full_frequency");
backupRule("wb_backup_full_weekday", "wb_backup_full/weekday", "full_weekday");
backupRule("wb_backup_full_monthday", "wb_backup_full/monthday", "full_monthday");
backupRule("wb_backup_full_schedule", "wb_backup_full/schedule", "full_schedule");
backupRule("wb_backup_full_keep", "wb_backup_full/keep_count", "full_keep_count");
