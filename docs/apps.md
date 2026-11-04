# Apps and versions

```bash
fmt create site.example.com --frappe version-16 --apps erpnext,hrms:version-16,https://github.com/org/app:main
```

- `name[:ref]`: app from github.com/frappe, `ref` is a branch or tag (default: the `--frappe` ref).
- `git-url[:ref]`: any git repository. For private repos use a token URL: `https://<token>@github.com/org/app:main`.

## How images are chosen

- ERPNext only, same ref as Frappe: the official `frappe/erpnext:<ref>` image (pulled, nothing built).
- Anything else: `fmt` clones frappe_docker into `$FMT_HOME/.cache` and builds `images/layered/Containerfile` locally, tagged `fmt/<site>:<hash>`.

Apps are baked into the image. That is why `bench get-app` inside `fmt shell` is lost when containers are recreated.

## Day to day

```bash
fmt shell site.example.com              # bash in the bench; bench install-app works for apps already in the image
fmt apps add site.example.com hrms      # rebuild image, install-app, migrate
fmt apps remove site.example.com hrms   # uninstall and rebuild without it
fmt apps list site.example.com
```

`apps add/remove` take a backup first and put the site in maintenance mode while migrating.
