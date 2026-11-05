"""One labelled value of the public profile: label, value, reference line and optional action."""



def render_metric(label, value, reference, action=""):
    return (
        f"<div "
        f'class="metric"><span>{label}</span><strong>{value}</strong>{action}'
        f"<small>{reference}</small></div>"
    )
