from fmt.process import output, run


class ComposeProject:
    def __init__(self, site):
        self.site = site

    def command(self, *arguments):
        directory = self.site.directory
        return [
            "docker", "compose", "-p", self.site.slug,
            "--project-directory", str(directory),
            "--env-file", str(directory / ".env"),
            "-f", str(self.site.compose_path), *arguments,
        ]

    def run(self, *arguments, **options):
        return run(self.command(*arguments), **options)

    def bench(self, *arguments, service="backend", tty=False):
        flags = [] if tty else ["-T"]
        return self.run("exec", *flags, service, "bench", *arguments)

    def one_off(self, script, **environment):
        flags = [item for key, value in environment.items() for item in ("-e", f"{key}={value}")]
        return self.run("run", "--rm", "-T", *flags, "backend", "bash", "-c", script)

    def running_count(self):
        return len(output(self.command("ps", "-q", "--status", "running")).split())
