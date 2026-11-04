"""Page publique (CDC §7) : présentation, actualités, contact. Aucun code d'accès."""

from itertools import groupby

from django.conf import settings
from django.contrib import messages
from django.contrib.syndication.views import Feed
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST, require_safe

from apps.accounts.capabilities import require_capability
from apps.agenda import ical
from apps.core import ratelimit
from apps.core.access import public_view
from apps.core.markdown import render as render_markdown
from apps.core.models import SiteSettings
from apps.ideas.models import Idea
from apps.presences import services as presences_services

from . import services
from .forms import ContactForm, NewsForm, PresentationForm
from .models import NewsPost

NEWS_PER_PAGE = 12


@require_safe
@public_view
def home(request):
    now = timezone.now()
    return render(
        request,
        "public/home.html",
        {
            "events": ical.public_events().filter(end__gte=now)[:4],
            "news": NewsPost.objects.public()[:1],
            "permanences": presences_services.public_permanences(),
            "ideas": Idea.objects.public()
            .filter(status__in=[Idea.Status.NEW, Idea.Status.PREPARING, Idea.Status.PLANNED])
            .order_by("-created_at")[:3],
        },
    )


@require_safe
@public_view
def news_list(request):
    """La plus récente « à la une », puis les autres en cartes, rangées par mois."""
    page = Paginator(NewsPost.objects.public(), NEWS_PER_PAGE).get_page(request.GET.get("page"))
    posts = list(page.object_list)
    featured = posts.pop(0) if page.number == 1 and posts else None
    months = [
        (month, list(items))
        for month, items in groupby(
            posts, key=lambda post: timezone.localtime(post.published_at).date().replace(day=1)
        )
    ]
    return render(
        request,
        "public/news_list.html",
        {"page": page, "featured": featured, "months": months},
    )


@require_safe
@public_view
def news_detail(request, slug):
    post = get_object_or_404(NewsPost.objects.public(), slug=slug)
    others = NewsPost.objects.public()
    return render(
        request,
        "public/news_detail.html",
        {
            "post": post,
            "newer": others.filter(published_at__gt=post.published_at)
            .order_by("published_at")
            .first(),
            "older": others.filter(published_at__lt=post.published_at).first(),
        },
    )


class NewsFeed(Feed):
    """Flux RSS des actualités : on s'abonne au lieu de recevoir des e-mails (CDC §7)."""

    description = "Les actualités du collectif."

    def title(self):
        return f"Actualités — {SiteSettings.get().collective_name}"

    def link(self):
        return reverse("public:news_list")

    def items(self):
        return NewsPost.objects.public()[:20]

    def item_title(self, item):
        return item.title

    def item_description(self, item):
        return item.summary or render_markdown(item.body)

    def item_link(self, item):
        return reverse("public:news_detail", args=[item.slug])

    def item_pubdate(self, item):
        return item.published_at


_news_feed = NewsFeed()


@public_view
def news_feed(request):
    return _news_feed(request)


@public_view
def contact(request):
    form = ContactForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        limit, window = settings.CONTACT_RATE_LIMIT
        if not ratelimit.hit(request, "contact", limit, window):
            return render(request, "429.html", status=429)
        if not form.is_spam():  # un robot ne doit pas apprendre ce qui l'a trahi
            data = form.cleaned_data
            services.submit_contact(name=data["name"], email=data["email"], message=data["message"])
        messages.success(request, "Merci, votre message est bien arrivé.")
        return redirect("public:contact")
    return render(request, "public/contact.html", {"form": form})


@require_capability("manage_public")
def presentation(request):
    """Le texte de présentation de la page publique, avec un aperçu avant d'enregistrer."""
    site = SiteSettings.get()
    form = PresentationForm(request.POST or None, initial={"presentation": site.presentation})
    preview = None
    if request.method == "POST" and form.is_valid():
        text = form.cleaned_data["presentation"]
        if "apercu" in request.POST:
            preview = text
        else:
            services.set_presentation(text, user=request.user)
            messages.success(request, "Présentation enregistrée.")
            return redirect("public:presentation")
    return render(request, "public/presentation_form.html", {"form": form, "preview": preview})


# --- Actualités, côté gestion : sans passer par l'administration Django -----------------


@require_capability("manage_public")
def news_manage(request):
    now = timezone.now()
    posts = NewsPost.objects.order_by("-published_at")
    return render(request, "public/news_manage.html", {"posts": posts, "now": now})


def _news_form_page(request, post=None):
    initial = NewsForm.initial_from(post) if post else None
    form = NewsForm(request.POST or None, initial=initial)
    preview = None
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        if "apercu" in request.POST:
            preview = data
        elif post is None:
            post = services.create_news(user=request.user, **data)
            messages.success(request, _news_saved_message(post))
            return redirect("public:news_manage")
        else:
            services.update_news(post, user=request.user, **data)
            messages.success(request, _news_saved_message(post))
            return redirect("public:news_manage")
    return render(
        request, "public/news_form.html", {"form": form, "post": post, "preview": preview}
    )


def _news_saved_message(post) -> str:
    if not post.is_published:
        return f"« {post.title} » est enregistrée comme brouillon."
    if post.published_at > timezone.now():
        when = timezone.localtime(post.published_at)
        return f"« {post.title} » paraîtra le {when:%d/%m/%Y à %H:%M}."
    return f"« {post.title} » est publiée."


@require_capability("manage_public")
def news_new(request):
    return _news_form_page(request)


@require_capability("manage_public")
def news_edit(request, pk):
    return _news_form_page(request, get_object_or_404(NewsPost, pk=pk))


@require_capability("manage_public")
@require_POST
def news_publish(request, pk):
    post = get_object_or_404(NewsPost, pk=pk)
    published = request.POST.get("publier") == "1"
    services.set_news_published(post, user=request.user, published=published)
    messages.success(request, _news_saved_message(post))
    return redirect("public:news_manage")
