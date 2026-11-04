# Backups and upgrades

## Backups

```bash
fmt backup site.example.com      # database + public/private files -> /opt/fmt/<site>/backups/<timestamp>
fmt restore site.example.com [folder]
0 2 * * *  fmt backup site.example.com    # cron example
```

Backups are kept 14 days by default (`--keep-days`). Copy them off the server.

## Upgrading

```bash
fmt update site.example.com                                   # newest code of the same branches
fmt update site.example.com --frappe version-16 --app hrms:version-16
fmt rollback site.example.com
```

Sequence: backup (with the old image and app refs recorded) -> pull or build the new image -> maintenance mode on, workers stopped -> containers recreated -> `bench migrate` -> new apps installed -> maintenance mode off.
If anything fails the site stays in maintenance mode; `fmt rollback` restores the backup together with the old image. Database migrations are never reverted, so rollback means restore.

## Major versions (for example v15 to v16)

Frappe, ERPNext and HRMS must move together: `--frappe version-16` moves every app that tracked the old branch. Try it first on a copy:

```bash
fmt clone site.example.com staging.example.com
fmt update staging.example.com --frappe version-16
```

Read the release notes; custom apps may need changes. MariaDB and Redis major upgrades are separate and not done by `fmt update`.
