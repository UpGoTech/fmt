# Local development

Domains ending in `.localhost`, `.test`, `.local` or `.internal` (or `--local`) create an HTTP-only site: no DNS check, no certificate, `host_name` is `http://`.

```bash
export FMT_HOME=~/fmt-sites      # /opt is not writable on macOS
fmt create demo.localhost        # offers to install Traefik on ports 80/443
```

Add `127.0.0.1 demo.test` to `/etc/hosts` for names that do not resolve (`*.localhost` resolves in browsers). Ports 80 and 443 must be free for Traefik: stop other proxies such as Frappe Manager's global nginx first.
