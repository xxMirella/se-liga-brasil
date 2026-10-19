"""Official CNPJ bounded acquisition and reviewed business-relationship observations."""

from crawlers.receita_federal.acquisition import acquire_resources, plan_resources
from crawlers.receita_federal.configuration import CrawlerConfiguration
from crawlers.receita_federal.pipeline import scan_snapshot

__all__ = ["CrawlerConfiguration", "acquire_resources", "plan_resources", "scan_snapshot"]
