"""Sonde de santé du conteneur : `/sante/` répond-il ? (code de sortie 0 ou 1)."""

import os
import sys
import urllib.request

host = (os.environ.get("DJANGO_ALLOWED_HOSTS") or "localhost").split(",")[0]
request = urllib.request.Request("http://127.0.0.1:8000/sante/", headers={"Host": host})
try:
    with urllib.request.urlopen(request, timeout=4) as response:
        sys.exit(0 if response.status == 200 else 1)
except Exception:  # toute erreur vaut « pas en bonne santé »
    sys.exit(1)
