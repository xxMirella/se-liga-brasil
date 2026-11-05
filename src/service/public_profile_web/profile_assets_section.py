"""Assets and remuneration section of the person profile (reference: Perfil v2)."""

from service.public_profile_web.asset_declarations import render_asset_declarations
from service.public_profile_web.profile_payments import render_payments


def render_assets_section(profile):
    return (
        '<section id="bens" class="ds-profile-assets" aria-labelledby="bens-title">'
        '<h2 id="bens-title">Bens e remuneração</h2><div class="ds-profile-assets-grid">'
        + render_asset_declarations(profile)
        + render_payments(profile)
        + "</div></section>"
    )
