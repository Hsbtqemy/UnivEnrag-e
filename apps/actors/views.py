from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import NameForm
from .resolvers import forget_name, remember_name


def _back(request) -> str:
    target = request.POST.get("next") or request.GET.get("next") or ""
    if target and url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}):
        return target
    return "/accueil/"


def name(request):
    """Changer le nom retenu par ce navigateur, ou l'oublier."""
    form = NameForm(request.POST or None, actor_name=request.actor_name)
    if request.method == "POST" and "forget" in request.POST:
        response = redirect(_back(request))
        forget_name(response)
        messages.info(request, "Ce navigateur a oublié votre nom.")
        return response
    if request.method == "POST" and form.is_valid():
        response = redirect(_back(request))
        remember_name(response, form.cleaned_data["author_name"])
        messages.success(request, "Votre nom est enregistré dans ce navigateur.")
        return response
    return render(request, "actors/name.html", {"form": form, "next": _back(request)})
