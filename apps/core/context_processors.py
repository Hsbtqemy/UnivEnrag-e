from .models import SiteSettings


def site(request):
    return {
        "site": SiteSettings.get(),
        "has_access": getattr(request, "has_access", False),
    }
