from django.core.validators import RegexValidator

hex_color = RegexValidator(r"^#[0-9a-fA-F]{6}$", "Couleur au format #RRGGBB.")
