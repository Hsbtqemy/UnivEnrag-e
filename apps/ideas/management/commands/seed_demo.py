"""Données de démonstration, datées à partir de la semaine prochaine.

Tout passe par les services : la démo respecte les mêmes règles que l'application.
"""

import os
from datetime import date, time, timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.actors.models import Actor
from apps.actors.services import get_or_create_for_name
from apps.agenda import services as agenda_services
from apps.agenda.models import Event
from apps.core.dates import combine
from apps.core.models import SiteSettings
from apps.ideas import services as ideas_services
from apps.ideas.models import Idea, IdeaSlot
from apps.rooms.models import OpeningHours, Room
from apps.spaces.models import Space

DEMO_ADMIN = "admin"
DEMO_MANAGER = "camille"


class Command(BaseCommand):
    help = "Remplit la base avec des salles, des propositions et des événements de démonstration."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset", action="store_true", help="Efface d'abord toutes les données."
        )

    def handle(self, *args, reset=False, **options):
        if settings.ENV == "prod":
            raise CommandError("La démo ne se charge pas en production.")
        with transaction.atomic():
            if reset:
                Event.objects.all().delete()
                IdeaSlot.objects.all().delete()
                Idea.objects.all().delete()
                Actor.objects.all().delete()
                Room.objects.all().delete()
                Space.objects.all().delete()
            elif Idea.objects.exists():
                raise CommandError(
                    "La base contient déjà des propositions : relancez avec --reset."
                )
            admin, password = self._admin()
            self._manager(password)
            code = os.environ.get("DEMO_ACCESS_CODE", "collectif2026")
            site = SiteSettings.get()
            site.collective_name = "Collectif UnivEnrag-e"
            site.save(update_fields=["collective_name"])
            site.set_access_code(code)
            rooms = self._rooms()
            self._ideas(rooms, admin)
            self._members(rooms)
        self.stdout.write(self.style.SUCCESS("Démo chargée."))
        self.stdout.write(f"Code d'accès des membres : {code}")
        if password:
            self.stdout.write(f"Administrateur principal : {DEMO_ADMIN} / {password}")
            self.stdout.write(f"Gestionnaire (agenda + modération) : {DEMO_MANAGER} / {password}")

    def _admin(self):
        user_model = get_user_model()
        user = user_model.objects.filter(username=DEMO_ADMIN).first()
        if user:
            return user, None
        password = os.environ.get("DEMO_ADMIN_PASSWORD", "demo-collectif-2026")
        user = user_model.objects.create_superuser(DEMO_ADMIN, password=password)
        return user, password

    def _manager(self, password):
        user_model = get_user_model()
        if password is None or user_model.objects.filter(username=DEMO_MANAGER).exists():
            return
        manager = user_model.objects.create_user(
            DEMO_MANAGER, password=password, first_name="Camille", is_staff=True
        )
        manager.user_permissions.set(
            Permission.objects.filter(
                content_type__app_label="accounts", codename__in=["manage_agenda", "moderate"]
            )
        )

    def _rooms(self):
        specs = [
            ("Salle du collectif", "Bât. A", 40, "#2f5d8c", Room.BookingMode.FREE),
            ("Petite salle", "Bât. A", 12, "#2e7d4f", Room.BookingMode.FREE),
            ("Salle de projection", "Bât. C", 60, "#8a4b9c", Room.BookingMode.APPROVAL),
        ]
        rooms = [
            Room.objects.create(
                name=n,
                building=b,
                capacity=c,
                color=col,
                order=i,
                booking_mode=mode,
                access_notes="Badge à demander à l'accueil du bâtiment." if b == "Bât. C" else "",
            )
            for i, (n, b, c, col, mode) in enumerate(specs)
        ]
        # Salle du collectif : du lundi au vendredi, 8 h - 21 h.
        for weekday in range(5):
            OpeningHours.objects.create(
                room=rooms[0], weekday=weekday, opens=time(8), closes=time(21)
            )
        return rooms

    def _members(self, rooms):
        """Événements créés par des membres : espaces, salle sur validation."""
        big, small, cinema = rooms
        working = Space.objects.create(
            name="Conditions de travail",
            color="#c0392b",
            description="Charge de travail, postes, précarité.",
        )
        seminar = Space.objects.create(
            name="Séminaire permanent", color="#16a085", description="Lectures et invités."
        )
        today = date.today()
        monday = today + timedelta(days=7 - today.weekday())

        def at(day_offset, hour, minute=0):
            return combine(monday + timedelta(days=day_offset), time(hour, minute))

        agenda_services.create(
            actor=get_or_create_for_name("Nora Diallo"),
            title="Réunion du groupe",
            start=at(0, 12),
            end=at(0, 13, 30),
            room=small,
            space=working,
        )
        agenda_services.create(
            actor=get_or_create_for_name("Hugo Petit"),
            title="Séance : lire Bourdieu",
            start=at(3, 14),
            end=at(3, 16),
            room=big,
            space=seminar,
        )
        # Salle de projection : soumise à validation, la réservation reste en attente.
        agenda_services.create(
            actor=get_or_create_for_name("Inès Garnier"),
            title="Projection du film du groupe",
            start=at(4, 18),
            end=at(4, 20),
            room=cinema,
            space=working,
        )

    def _ideas(self, rooms, admin):
        big, small, cinema = rooms
        today = date.today()
        monday = today + timedelta(days=7 - today.weekday())

        def at(day_offset, hour, minute=0):
            return combine(monday + timedelta(days=day_offset), time(hour, minute))

        def submit(name, email, title, description, minutes, room=None, slots=(), **extra):
            return ideas_services.submit(
                owner_name=name,
                owner_email=email,
                title=title,
                description=description,
                duration_minutes=minutes,
                wanted_room=room,
                slots=slots,
                **extra,
            )

        # Programmées : acceptées, placées, confirmées, publiques.
        for idea in [
            submit(
                "Camille Martin",
                "camille.martin@univ.example",
                "Séminaire : écrire à plusieurs",
                "Un atelier pour écrire collectivement un texte de position.",
                120,
                big,
                [{"start": at(1, 14)}],
                audience="Tout le collectif",
            ),
            submit(
                "Yanis Benali",
                "yanis.benali@univ.example",
                "Projection-débat « Les heures creuses »",
                "Documentaire sur le travail invisible, suivi d'une discussion.",
                180,
                cinema,
                [{"start": at(3, 18)}],
                audience="Tout public",
                expected_count=50,
            ),
        ]:
            ideas_services.accept(idea, user=admin)
            agenda_services.confirm(idea.event, user=admin)

        # Acceptées et placées en provisoire, avec d'autres créneaux possibles.
        conference = submit(
            "Léa Rousseau",
            "lea.rousseau@univ.example",
            "Conférence sur l'histoire des luttes",
            "Une historienne présente ses travaux, questions de la salle ensuite.",
            120,
            big,
            [{"start": at(2, 10)}, {"start": at(2, 14)}, {"start": at(4, 10)}],
        )
        ideas_services.accept(conference, user=admin)
        # Même salle, même matinée : avertissement visible, pas encore bloquant.
        reading = submit(
            "Hugo Petit",
            "hugo.petit@univ.example",
            "Groupe de lecture",
            "Lecture commentée d'un chapitre, ouvert à toutes et tous.",
            90,
            big,
            [{"start": at(2, 10, 30)}, {"start": at(0, 16)}],
        )
        ideas_services.accept(reading, user=admin)

        # Acceptées, sans créneau précis : dans « À placer ».
        for name, email, title, description, minutes, room, period in [
            (
                "Inès Garnier",
                "ines.garnier@univ.example",
                "Repas partagé de rentrée",
                "Chacun apporte un plat ; on fait connaissance.",
                180,
                None,
                "Un midi la semaine prochaine",
            ),
            (
                "Thomas Leroy",
                "thomas.leroy@univ.example",
                "Atelier vélo",
                "Réparer son vélo ensemble, outils fournis.",
                120,
                small,
                "Une fin d'après-midi, plutôt jeudi",
            ),
        ]:
            idea = submit(name, email, title, description, minutes, room, [{"period_text": period}])
            ideas_services.accept(idea, user=admin)

        # À modérer.
        submit(
            "Nora Diallo",
            "nora.diallo@univ.example",
            "Café des doctorant·es",
            "Un moment informel pour parler conditions de thèse.",
            90,
            small,
            [{"start": at(1, 10)}, {"period_text": "Ou un matin la semaine suivante"}],
        )
        submit(
            "Paul Henry",
            "paul.henry@univ.example",
            "Présentation d'un livre",
            "Rencontre avec l'auteur d'un essai sur l'université.",
            120,
            None,
            [{"period_text": "Courant du mois prochain"}],
        )

        # Refusée.
        spam = submit(
            "Promo Express",
            "promo@example.com",
            "Gagnez des followers",
            "Offre exceptionnelle !",
            60,
        )
        ideas_services.refuse(spam, user=admin, reason="Hors sujet.")
