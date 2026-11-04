import shutil
import time
from pathlib import Path

from fmt.process import FmtError, output
from fmt.site import EnvFile

BENCH_ROOT = "/home/frappe/frappe-bench"
STATE_FILE = "state.env"


class BackupStore:
    """Backups of one site, stored as timestamped folders in <site dir>/backups."""

    def __init__(self, site, compose):
        self.site, self.compose = site, compose
        self.root = site.directory / "backups"
        self.remote = f"{BENCH_ROOT}/sites/{site.name}/private/backups"

    def create(self):
        self.compose.run("up", "-d")
        self.compose.bench("--site", self.site.name, "backup", "--with-files")
        destination = self.root / time.strftime("%Y-%m-%d_%H%M%S")
        destination.mkdir(parents=True)
        for name in self._newest_remote_files():
            self.compose.run("cp", f"backend:{self.remote}/{name}", str(destination))
        self._save_state(destination)
        return destination

    def _newest_remote_files(self):
        listing = output(self.compose.command("exec", "-T", "backend", "ls", "-1", self.remote))
        names = sorted(listing.split())
        if not names:
            raise FmtError("bench produced no backup files")
        prefix = names[-1].split("-")[0]
        return [name for name in names if name.startswith(prefix)]

    def _save_state(self, destination):
        values = self.site.env.read()
        keys = ("IMAGE", "FRAPPE_REF", "APPS")
        EnvFile(destination / STATE_FILE).write({key: values[key] for key in keys})

    def latest(self):
        folders = sorted(path for path in self.root.iterdir() if path.is_dir()) if self.root.exists() else []
        if not folders:
            raise FmtError(f"no backups found in {self.root}")
        return folders[-1]

    def prune(self, keep_days):
        cutoff = time.time() - keep_days * 86400
        for path in self.root.iterdir():
            if path.is_dir() and path.stat().st_mtime < cutoff:
                shutil.rmtree(path)

    def restore(self, folder):
        folder = Path(folder)
        files = self._classify(folder)
        for path in files.values():
            self.compose.run("cp", str(path), f"backend:{self.remote}/")
        flags = [item for flag, key in (("--with-public-files", "public"), ("--with-private-files", "private"))
                 if key in files for item in (flag, f"{self.remote}/{files[key].name}")]
        password = self.site.env.read()["DB_ROOT_PASSWORD"]
        self.compose.bench(
            "--site", self.site.name, "restore", f"{self.remote}/{files['database'].name}",
            "--db-root-username", "root", "--db-root-password", password, "--force", *flags)

    @staticmethod
    def _classify(folder):
        files = {}
        for path in sorted(folder.iterdir()):
            if path.name.endswith("-database.sql.gz"):
                files["database"] = path
            elif path.name.endswith("-private-files.tar"):
                files["private"] = path
            elif path.name.endswith("-files.tar"):
                files["public"] = path
        if "database" not in files:
            raise FmtError(f"no database backup in {folder}")
        return files
