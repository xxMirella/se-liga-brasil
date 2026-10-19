"""Compatibility imports for the TSE crawler; acquisition is source-independent."""

from service.acquisition.downloader import (  # noqa: F401
    build_conditional_headers,
    build_downloaded_artifact,
    download_resource,
    enforce_download_limit,
    is_cached_archive_intact,
    is_recently_checked,
    save_download,
    select_download_manifest,
)
