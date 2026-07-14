# Wiren Board Backup

Резервное копирование Wiren Board на NFS штатными скриптами контроллера.

## Возможности

- ежедневный архив конфигураций через `download_configs.sh`;
- еженедельный полный архив через `download_everything.sh`;
- независимое расписание и ротация для каждого типа;
- MQTT-статус и управление;
- автоматическое MQTT Discovery для Home Assistant;
- виртуальное устройство `wb_backup` в интерфейсе Wiren Board через `wb-rules`;
- защита от одновременного запуска двух архивов;
- атомарная запись: незавершённый архив имеет суффикс `.partial`.

## Установка одной командой

Выполните на Wiren Board под `root`:

```sh
bash -c "$(curl -fsSL https://raw.githubusercontent.com/akinin/wirenboard-backup/main/install.sh)"
```

Приложение устанавливается в `/opt/wirenboard-backup`. Настройки и состояние хранятся отдельно в `/etc/wb-backup` и `/var/lib/wb-backup`.

## Настройки по умолчанию

- NFS: `10.10.100.11:/volume1/Backups`;
- каталог: `WirenBoard/<hostname>`;
- конфигурации: ежедневно в `03:30`, хранить 14;
- полный архив: по воскресеньям в `04:30`, хранить 4.

Настройки находятся в `/etc/wb-backup/config.json`. После ручного изменения:

```sh
wb-backup-ctl apply
```

## Управление

```sh
wb-backup-ctl run-config
wb-backup-ctl run-full
wb-backup-ctl status
```

В Home Assistant создаются кнопки запуска, расписание, настройки ротации, статус, даты последних архивов и датчик ошибки.

В интерфейсе Wiren Board появляется устройство «Резервное копирование» с состояниями и кнопками ручного запуска.

## Удаление

```sh
curl -fsSL https://raw.githubusercontent.com/akinin/wirenboard-backup/main/uninstall.sh | sh
```
