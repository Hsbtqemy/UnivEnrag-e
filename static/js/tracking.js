/*
 * Lien de suivi d'une proposition : le site n'envoie aucun message (CLAUDE.md, aucun
 * e-mail), ce lien est donc le seul moyen de revenir. On aide à le garder : le copier, ou
 * se l'envoyer par le partage du téléphone (aucun service extérieur n'est contacté).
 */
(function () {
  "use strict";
  const input = document.getElementById("lien-suivi");
  const copy = document.getElementById("copier-lien");
  const share = document.getElementById("partager-lien");
  const status = document.getElementById("lien-copie");
  if (!input || !copy) return;

  input.addEventListener("focus", () => input.select());

  copy.hidden = false;
  copy.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(input.value);
      status.textContent = "Lien copié.";
    } catch (e) {
      // Presse-papiers refusé (ancien navigateur, page non sécurisée) : on sélectionne.
      input.focus();
      input.select();
      status.textContent = "Le lien est sélectionné : copiez-le avec Ctrl+C (ou un appui long).";
    }
  });

  if (share && navigator.share) {
    share.hidden = false;
    share.addEventListener("click", () => {
      navigator
        .share({ title: document.title, text: "Le suivi de ma proposition", url: input.value })
        .catch(() => {}); // partage annulé : rien à dire
    });
  }
})();
