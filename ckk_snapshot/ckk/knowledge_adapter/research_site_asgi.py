"""Production entrypoint for the read-only CKK research site."""

from .research_site import create_research_site

app = create_research_site()
