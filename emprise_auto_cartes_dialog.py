# -*- coding: utf-8 -*-
"""
Boîte de dialogue du plugin : choix de la couche d'emprise, saisie du Z
(NGF), choix du dossier de sortie des 3 PDF.

Le bouton "Exécuter" n'accepte PLUS automatiquement (et donc ne ferme
plus) le dialogue : il émet le signal `executer_demande`, traité par le
plugin PENDANT que le dialogue reste ouvert, afin que la zone de journal
ci-dessous se remplisse réellement en direct et reste lisible/copiable
une fois le traitement terminé (voir emprise_auto_cartes.py).
"""

from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QHBoxLayout, QLabel,
    QDoubleSpinBox, QPushButton, QLineEdit, QFileDialog, QDialogButtonBox,
    QPlainTextEdit, QApplication,
)
from qgis.core import QgsProject, QgsMapLayerProxyModel, QgsVectorLayer
from qgis.gui import QgsMapLayerComboBox


class EmpriseAutoCartesDialog(QDialog):

    executer_demande = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Emprise Inrap — 250 / 25 / cadastre")
        self.resize(520, 420)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        # --- choix de la couche d'emprise -----------------------------
        self.combo_emprise = QgsMapLayerComboBox(self)
        self.combo_emprise.setFilters(
            QgsMapLayerProxyModel.PolygonLayer | QgsMapLayerProxyModel.PointLayer
        )
        ligne_emprise = QHBoxLayout()
        ligne_emprise.addWidget(self.combo_emprise)
        self.bouton_charger = QPushButton("Charger un fichier…")
        self.bouton_charger.clicked.connect(self._charger_fichier)
        ligne_emprise.addWidget(self.bouton_charger)
        form.addRow("Plan d'emprise (EPSG:2154) :", ligne_emprise)

        # --- Z NGF ------------------------------------------------------
        self.spin_z = QDoubleSpinBox(self)
        self.spin_z.setRange(-500.0, 5000.0)
        self.spin_z.setDecimals(2)
        self.spin_z.setSuffix(" m NGF")
        self.spin_z.setValue(0.0)
        form.addRow("Altitude Z (NGF) :", self.spin_z)

        # --- dossier de sortie -------------------------------------------
        ligne_sortie = QHBoxLayout()
        self.champ_sortie = QLineEdit(self)
        proj_home = QgsProject.instance().homePath() or ""
        self.champ_sortie.setText(proj_home)
        self.bouton_sortie = QPushButton("Parcourir…")
        self.bouton_sortie.clicked.connect(self._choisir_dossier)
        ligne_sortie.addWidget(self.champ_sortie)
        ligne_sortie.addWidget(self.bouton_sortie)
        form.addRow("Dossier de sortie (3 PDF) :", ligne_sortie)

        layout.addLayout(form)

        layout.addWidget(QLabel(
            "Le plugin va : calculer le centroïde de l'emprise, renseigner "
            "X/Y/Z, détecter la région, basculer les thèmes A/B, recadrer "
            "les cartes 250 / 25 / cadastre sur l'emprise, puis exporter "
            "3 PDF dans le dossier choisi."
        ))

        self.journal = QPlainTextEdit(self)
        self.journal.setReadOnly(True)
        self.journal.setPlaceholderText("Le journal d'exécution s'affichera ici…")
        layout.addWidget(self.journal)

        self.boutons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self
        )
        self.bouton_executer = self.boutons.button(QDialogButtonBox.Ok)
        self.bouton_executer.setText("Exécuter")
        self.boutons.button(QDialogButtonBox.Cancel).setText("Fermer")
        # IMPORTANT : on ne connecte PAS accepted->accept() : le dialogue ne
        # doit pas se fermer tout seul au clic sur "Exécuter", sinon le
        # journal ci-dessus disparaît avant d'avoir pu afficher quoi que ce
        # soit (c'était le bug des versions précédentes).
        self.boutons.accepted.connect(self._on_executer_clique)
        self.boutons.rejected.connect(self.reject)
        layout.addWidget(self.boutons)

    def _on_executer_clique(self):
        self.bouton_executer.setEnabled(False)
        try:
            self.executer_demande.emit()
        finally:
            self.bouton_executer.setEnabled(True)

    # ------------------------------------------------------------------
    def _charger_fichier(self):
        chemin, _ = QFileDialog.getOpenFileName(
            self, "Charger le plan d'emprise",
            "", "Fichiers vecteur (*.shp *.geojson *.gpkg *.dxf);;Tous les fichiers (*)"
        )
        if not chemin:
            return
        couche = QgsVectorLayer(chemin, "Emprise", "ogr")
        if not couche.isValid():
            self.journal.appendPlainText("Impossible de charger : {}".format(chemin))
            return
        QgsProject.instance().addMapLayer(couche)
        self.combo_emprise.setLayer(couche)

    def _choisir_dossier(self):
        dossier = QFileDialog.getExistingDirectory(self, "Dossier de sortie")
        if dossier:
            self.champ_sortie.setText(dossier)

    # ------------------------------------------------------------------
    def couche_emprise(self):
        return self.combo_emprise.currentLayer()

    def valeur_z(self):
        return self.spin_z.value()

    def dossier_sortie(self):
        return self.champ_sortie.text().strip()

    def log(self, message):
        self.journal.appendPlainText(message)
        # Le traitement tourne de façon synchrone sur le thread principal :
        # sans ceci, Qt n'actualiserait l'affichage du journal qu'une fois
        # TOUT le traitement terminé (donc au final jamais "en direct").
        QApplication.processEvents()
