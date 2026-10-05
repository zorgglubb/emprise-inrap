# -*- coding: utf-8 -*-
"""
Classe principale du plugin : ajoute une entrée de menu/barre d'outils et
orchestre l'appel au dialogue + à core.executer().

IMPORTANT (corrigé en v0.8) : le dialogue étant modal, `dialog.exec_()` se
ferme dès que l'utilisateur clique sur "Exécuter", AVANT que
`core.executer()` ne soit appelé -- la zone de journal du dialogue ne
pouvait donc jamais rien afficher (le journal partait uniquement vers la
console Python, invisible). Le traitement se fait maintenant AVANT la
fermeture du dialogue, avec le journal rempli en direct ; le journal
complet est en plus écrit dans un fichier .txt à côté des PDF, pour
pouvoir le relire/partager facilement après coup.
"""

import os

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMessageBox
from qgis.core import QgsProject

from .emprise_auto_cartes_dialog import EmpriseAutoCartesDialog
from . import core

NOM_MENU = "Emprise Inrap"
ICONE = os.path.join(os.path.dirname(__file__), "icons", "icon.png")


class EmpriseAutoCartesPlugin:

    def __init__(self, iface):
        self.iface = iface
        self.action = None

    def initGui(self):
        icone = QIcon(ICONE) if os.path.isfile(ICONE) else QIcon()
        self.action = QAction(icone, "{} (250/25/cadastre)".format(NOM_MENU), self.iface.mainWindow())
        self.action.triggered.connect(self.lancer)
        self.iface.addPluginToMenu(NOM_MENU, self.action)
        self.iface.addToolBarIcon(self.action)

    def unload(self):
        self.iface.removePluginMenu(NOM_MENU, self.action)
        self.iface.removeToolBarIcon(self.action)

    def lancer(self):
        project = QgsProject.instance()
        dialog = EmpriseAutoCartesDialog(self.iface.mainWindow())
        dialog.executer_demande.connect(lambda: self._executer(project, dialog))
        dialog.exec_()

    def _executer(self, project, dialog):
        """Appelé par le bouton 'Exécuter' du dialogue : le dialogue reste
        OUVERT pendant le traitement, afin que son journal se remplisse en
        direct et reste lisible/copiable une fois le traitement terminé."""
        emprise_layer = dialog.couche_emprise()
        if emprise_layer is None:
            QMessageBox.warning(dialog, NOM_MENU,
                                 "Veuillez choisir ou charger un plan d'emprise.")
            return

        dossier_sortie = dialog.dossier_sortie()
        if not dossier_sortie:
            QMessageBox.warning(dialog, NOM_MENU,
                                 "Veuillez choisir un dossier de sortie.")
            return

        z_value = dialog.valeur_z()

        messages = []

        def feedback(msg):
            messages.append(msg)
            dialog.log(msg)

        dialog.log("--- Lancement ---")
        try:
            resultat = core.executer(project, emprise_layer, z_value, dossier_sortie, feedback=feedback)
        except core.EmpriseAutoCartesError as exc:
            dialog.log("ERREUR : {}".format(exc))
            self._ecrire_journal(messages, dossier_sortie)
            QMessageBox.critical(dialog, NOM_MENU, str(exc))
            return
        except Exception as exc:  # garde-fou : on affiche plutôt que de planter QGIS
            dialog.log("ERREUR INATTENDUE : {}".format(exc))
            self._ecrire_journal(messages, dossier_sortie)
            QMessageBox.critical(
                dialog, NOM_MENU,
                "Erreur inattendue :\n{}\n\n"
                "Vérifiez la section CONFIGURATION en tête de core.py "
                "(noms de mises en page / thèmes / couches). Le journal "
                "ci-dessus (et le fichier journal dans le dossier de sortie, "
                "si déjà créé) donne le détail.".format(exc)
            )
            return

        chemin_journal = self._ecrire_journal(messages, dossier_sortie)
        region_txt = resultat.get("region") or "non déterminée"
        dialog.log("--- Terminé ---")
        QMessageBox.information(
            dialog, NOM_MENU,
            "Terminé.\n\n"
            "X = {x:.2f}   Y = {y:.2f}   Z = {z:.2f} m NGF\n"
            "Région détectée : {region}\n\n"
            "3 PDF exportés dans :\n{dossier}\n\n"
            "Journal détaillé enregistré dans :\n{journal}".format(
                x=resultat["x"], y=resultat["y"], z=resultat["z"],
                region=region_txt, dossier=dossier_sortie, journal=chemin_journal,
            )
        )

    @staticmethod
    def _ecrire_journal(messages, dossier_sortie):
        """Écrit le journal complet dans un fichier texte à côté des PDF,
        pour pouvoir le relire/partager facilement (copier-coller) même
        après la fermeture du dialogue."""
        try:
            os.makedirs(dossier_sortie, exist_ok=True)
            chemin = os.path.join(dossier_sortie, "journal_emprise_auto_cartes.txt")
            with open(chemin, "w", encoding="utf-8") as f:
                f.write("\n".join(messages))
            return chemin
        except Exception:
            return "(échec de l'écriture du fichier journal)"
