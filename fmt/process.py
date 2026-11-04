import subprocess


class FmtError(Exception):
    """User-facing error; the CLI prints the message and exits non-zero."""


def run(command, check=True, capture=False, input_text=None):
    result = subprocess.run(
        command, check=False, text=True, input=input_text,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )
    if check and result.returncode != 0:
        detail = (result.stderr or "").strip()
        raise FmtError(f"command failed ({result.returncode}): {' '.join(command)}\n{detail}")
    return result


def output(command):
    return run(command, capture=True).stdout.strip()
