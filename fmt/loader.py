from fmt.compose import ComposeProject
from fmt.site import Site


def load(name):
    site = Site(name).require_existing()
    return site, ComposeProject(site)
