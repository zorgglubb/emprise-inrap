# -*- coding: utf-8 -*-
"""
Logique métier du plugin "Emprise Auto Cartes".

Construit par analyse statique du projet Cartes_localisation_v20240306.qgz
fourni par l'utilisateur (impossible de tester dans un QGIS réel depuis cet
environnement : vérifiez les noms ci-dessous si quelque chose ne colle pas).

v0.3 :
  - la couche d'emprise est stylée avec le style fourni par le projet
    (Emprise_pg.qml, embarqué dans styles/) sur TOUTES les cartes, au lieu
    d'une couche ponctuelle fabriquée à la volée : c'est ce style qui gère
    nativement le remplissage rouge (échelles proches) et le point rouge
    (échelles lointaines, dont la carte B) selon des règles d'échelle déjà
    prévues dans le projet d'origine ;
  - échelle cadastre choisie en évitant la "zone morte" du style (aucune
    règle entre 1:6 001 et 1:20 000 -> rien ne s'affiche dans cette plage,
    donc on ne la propose plus) ;
  - échelle de la carte B recalée si besoin dans la plage couverte par le
    style (3 000 000 - 8 000 000) pour garantir l'affichage du point rouge ;
  - pas de grille de la carte cadastre agrandi automatiquement ;
  - taille des étiquettes de numéro de parcelle plafonnée (6 pt) sur la
    carte cadastre ;
  - remplissage de Département / Commune / Adresse sur la page de
    localisation (Commune + Adresse déduits du champ `nomope`,
    Département par recherche spatiale dans la couche du département) ;
  - réglage d'export PDF « texte toujours en objets texte » fiabilisé
    (compatible anciennes et nouvelles versions de l'API QGIS).

=====================  CONFIGURATION A VERIFIER  =====================
"""

import os
import re
import math
import unicodedata
import tempfile

from qgis.core import (
    QgsRectangle,
    QgsGeometry,
    QgsField,
    QgsLayoutExporter,
    QgsLayoutItemMap,
    QgsLayoutItemLabel,
    QgsLayoutItemShape,
    QgsRenderContext,
    QgsCoordinateTransform,
    QgsProject,
    QgsSpatialIndex,
    QgsFeatureRequest,
    QgsVectorLayer,
    QgsFeature,
    QgsMarkerSymbol,
    QgsSingleSymbolRenderer,
)
from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QFontDatabase

from .region_config import REGIONS, trouver_region

# ---------------------------------------------------------------------
# Noms des 2 mises en page du projet (onglet "Gestionnaire de mises en page")
LAYOUT_LOCALISATION = "A-B-C-localisation"   # contient les cartes A, B, C(250) -> 01_Localisation_250000.pdf
LAYOUT_PLAN_CADASTRE = "D-25 000-cadastre"   # contient les cartes D25 et D cadastre (2 pages)

# Nom de la couche "régions" utilisée pour déterminer dans quelle région
# tombe l'emprise, et nom (approximatif) du champ portant le nom/code région.
COUCHE_REGIONS = "REGIONS2016"
CHAMPS_REGION_POSSIBLES = [
    "nom_region", "NOM_REGION", "nom_reg", "NOM_REG",
    "region", "REGION", "nom", "NOM",
    "insee_reg", "INSEE_REG", "code_reg", "CODE_REG",
]
# Idem pour retrouver le nom du département dans la couche "dept_<région>".
CHAMPS_DEPARTEMENT_POSSIBLES = [
    "nom_dept", "NOM_DEPT", "nomdept", "NOM_DEP",
    "departemen", "DEPARTEMEN", "nom", "NOM", "name", "NAME",
]

# Couches de fond utilisées pour chaque carte (noms exacts trouvés dans le
# projet fourni : groupe "FondsCARTO WMS"). Recherchées par nom via
# project.mapLayersByName().
COUCHE_FOND_C_250 = "Scan Régional"
COUCHE_FOND_D_25 = "SCAN 25 Touristique"
COUCHE_PARCELLE_CADASTRE = "CADASTRALPARCELS.PARCELLAIRE_EXPRESS:parcelle"

# Style livré avec le projet d'origine, embarqué dans le plugin
# (styles/Emprise_pg.qml) : remplissage rouge aux échelles proches,
# point rouge aux échelles lointaines (dont la carte B). Appliqué à la
# couche d'emprise choisie par l'utilisateur à chaque exécution.
#
# NB : dans le fichier original, la règle de remplissage proche s'arrêtait
# à 1:6 001, laissant un "trou" jusqu'à 1:20 000 (plage où rien ne se
# serait affiché). La copie embarquée ici étend cette règle jusqu'à
# 1:19 999 pour couvrir aussi 10 000 et 15 000 (cela ne modifie PAS le
# style de votre projet d'origine, seulement cette copie utilisée par le
# plugin).
FICHIER_STYLE_EMPRISE = os.path.join(os.path.dirname(__file__), "styles", "Emprise_pg.qml")

# Échelles "normalisées" parmi lesquelles choisir automatiquement celle de
# la carte cadastre (D cadastre). Au-delà de 25000 vous entrez dans la
# plage de la règle "C 250" (248 000 - 252 000) : ne pas ajouter de valeur
# intermédiaire sans aussi adapter le style.
ECHELLES_NORMALISEES_CADASTRE = [200, 500, 1000, 1250, 2500, 5000, 10000, 15000, 20000, 25000]
# Facteur d'agrandissement du cadre de la carte par rapport à la plus
# grande dimension de l'emprise, pour éviter un cadrage "trop serré"
# (3.0 => l'emprise occupe environ le tiers de la largeur/hauteur du cadre).
MARGE_CADASTRE = 3.0
# Nombre de divisions visées pour le pas de la grille de la carte cadastre.
DIVISIONS_GRILLE_CADASTRE = 5
# Taille maximale (pt) des étiquettes de numéro de parcelle sur la carte cadastre.
TAILLE_MAX_ETIQUETTE_PARCELLE = 6

# Plage d'échelles couverte par la règle "Localisation opération" du style
# Emprise_pg.qml pour la carte B : on y recale l'échelle si le recadrage
# automatique sur le département tombe en dehors, pour garantir l'affichage
# du point rouge.
ECHELLE_B_MIN = 3100000
ECHELLE_B_MAX = 7900000

# Champ de la couche d'emprise contenant "COMMUNE, adresse/lieu-dit"
# (convention INRAP habituelle) utilisé pour déduire Commune et Adresse.
CHAMP_NOMOPE = "nomope"

# Texte fixe à écrire dans l'étiquette "Auteur :" de la carte de
# localisation (sur le document PDF lui-même). Distinct de l'auteur du
# PLUGIN (champ "author" de metadata.txt, affiché dans le panneau
# "Informations sur l'extension" de QGIS) : les deux sont indépendants.
AUTEUR = "Inrap"

# Champs ajoutés/mis à jour sur la couche d'emprise
CHAMP_X = "X_L93"
CHAMP_Y = "Y_L93"
CHAMP_Z = "Z_NGF"

CRS_CIBLE = "EPSG:2154"

# ---------------------------------------------------------------------


class EmpriseAutoCartesError(Exception):
    pass


def log(feedback, message):
    if feedback is not None:
        feedback(message)
    else:
        print(message)


# ----------------------- étape 1 : géométrie ---------------------------

def _geoms_valides(layer):
    return [f.geometry() for f in layer.getFeatures() if f.geometry() and not f.geometry().isEmpty()]


def _union(geoms):
    union = geoms[0]
    for g in geoms[1:]:
        union = union.combine(g)
    return union


def calculer_centroide_et_emprise(emprise_layer, feedback=None):
    """Retourne (centroid_point, bounding_box) en EPSG:2154 pour l'ensemble
    des entités de la couche d'emprise."""
    if emprise_layer.crs().authid() != CRS_CIBLE:
        raise EmpriseAutoCartesError(
            "La couche d'emprise n'est pas en {} (CRS actuel : {}). "
            "Reprojetez-la avant de lancer le traitement.".format(
                CRS_CIBLE, emprise_layer.crs().authid()
            )
        )

    geoms = _geoms_valides(emprise_layer)
    if not geoms:
        raise EmpriseAutoCartesError("La couche d'emprise choisie ne contient aucune géométrie.")

    union = _union(geoms) if len(geoms) > 1 else geoms[0]
    centroid_geom = union.centroid()
    pt = centroid_geom.asPoint()
    bbox = union.boundingBox()
    log(feedback, "Centroïde calculé : X={:.2f}  Y={:.2f}  (emprise {:.1f} x {:.1f} m)".format(
        pt.x(), pt.y(), bbox.width(), bbox.height()))
    return pt, bbox


def appliquer_style_emprise(emprise_layer, feedback=None):
    """Applique le style Emprise_pg.qml (remplissage rouge / point rouge
    selon l'échelle) sur la couche d'emprise choisie par l'utilisateur."""
    if not os.path.isfile(FICHIER_STYLE_EMPRISE):
        log(feedback, "Fichier de style '{}' introuvable : le style actuel "
                       "de la couche d'emprise est conservé tel quel.".format(FICHIER_STYLE_EMPRISE))
        return
    message, ok = emprise_layer.loadNamedStyle(FICHIER_STYLE_EMPRISE)
    if ok:
        emprise_layer.triggerRepaint()
        log(feedback, "Style 'Emprise_pg' appliqué à la couche d'emprise.")
    else:
        log(feedback, "Impossible d'appliquer le style Emprise_pg.qml ({}). "
                       "Le style actuel de la couche est conservé.".format(message))


def creer_couche_point_secours(project, centroid_xy, crs, feedback=None):
    """Couche ponctuelle en mémoire, un seul point au centroïde de
    l'emprise, stylée en rond rouge plein avec le moteur de style natif
    QGIS 3 (PAS via le qml ancien format). Utilisée en SECOURS sur la
    carte B, en plus de (pas à la place de) la couche d'emprise elle-même :
    malgré une position et une échelle vérifiées correctes dans le
    journal, le point issu de la règle "Localisation opération" du style
    Emprise_pg (CentroidFill, ancien format QGIS 2.6.1) ne s'affichait
    toujours pas -- un souci de conversion de ce symbole précis lors du
    chargement de l'ancien format est l'explication la plus probable.
    Cette couche, construite nativement, garantit un point rouge visible
    indépendamment de ce style."""
    # nettoyage d'un résidu d'exécution précédente interrompue, si besoin
    for ancienne in project.mapLayersByName("Emprise (point, secours)"):
        project.removeMapLayer(ancienne.id())

    couche = QgsVectorLayer("Point?crs={}".format(crs.authid()), "Emprise (point, secours)", "memory")
    provider = couche.dataProvider()
    feat = QgsFeature()
    feat.setGeometry(QgsGeometry.fromPointXY(centroid_xy))
    provider.addFeatures([feat])
    couche.updateExtents()

    symbole = QgsMarkerSymbol.createSimple({
        "name": "circle",
        "color": "255,0,0,255",
        "outline_color": "35,35,35,255",
        "outline_width": "0.2",
        "size": "3",
        "size_unit": "MM",
    })
    couche.setRenderer(QgsSingleSymbolRenderer(symbole))

    # Possédée par le projet (lifetime géré par QGIS) mais non affichée
    # dans le panneau des couches (addToLegend=False).
    project.addMapLayer(couche, False)
    log(feedback, "Couche ponctuelle rouge de secours créée pour la carte B.")
    return couche


# ----------------------- étape 2 : champs X/Y/Z -------------------------

def renseigner_xyz(emprise_layer, x, y, z, feedback=None):
    """Crée (si besoin) les champs X_L93 / Y_L93 / Z_NGF sur la couche
    d'emprise et les renseigne sur toutes ses entités."""
    provider = emprise_layer.dataProvider()
    noms_existants = [f.name() for f in emprise_layer.fields()]

    champs_a_creer = []
    for nom in (CHAMP_X, CHAMP_Y, CHAMP_Z):
        if nom not in noms_existants:
            champs_a_creer.append(QgsField(nom, QVariant.Double, "double", 18, 3))

    if champs_a_creer:
        emprise_layer.startEditing()
        provider.addAttributes(champs_a_creer)
        emprise_layer.updateFields()
        emprise_layer.commitChanges()
        log(feedback, "Champs créés sur la couche d'emprise : {}".format(
            ", ".join(c.name() for c in champs_a_creer)))

    idx_x = emprise_layer.fields().indexOf(CHAMP_X)
    idx_y = emprise_layer.fields().indexOf(CHAMP_Y)
    idx_z = emprise_layer.fields().indexOf(CHAMP_Z)

    emprise_layer.startEditing()
    for f in emprise_layer.getFeatures():
        emprise_layer.changeAttributeValue(f.id(), idx_x, round(x, 3))
        emprise_layer.changeAttributeValue(f.id(), idx_y, round(y, 3))
        emprise_layer.changeAttributeValue(f.id(), idx_z, round(z, 3))
    ok = emprise_layer.commitChanges()
    if not ok:
        raise EmpriseAutoCartesError(
            "Impossible d'enregistrer X/Y/Z sur la couche d'emprise "
            "(vérifiez qu'elle n'est pas en lecture seule / verrouillée)."
        )
    log(feedback, "Champs X_L93 / Y_L93 / Z_NGF renseignés sur {} entité(s).".format(emprise_layer.featureCount()))


def extraire_commune_adresse(emprise_layer, feedback=None):
    """Déduit Commune et Adresse du champ `nomope` (convention
    "COMMUNE, adresse/lieu-dit"). Commune = texte avant la virgule.
    Adresse = texte après la virgule, sans espace de tête ; laissée
    vide s'il n'y a pas de virgule."""
    idx = emprise_layer.fields().indexOf(CHAMP_NOMOPE)
    if idx < 0:
        log(feedback, "Champ '{}' introuvable sur la couche d'emprise : "
                       "Commune / Adresse non renseignées.".format(CHAMP_NOMOPE))
        return None, None

    feats = list(emprise_layer.getFeatures())
    if not feats or feats[0][CHAMP_NOMOPE] is None:
        log(feedback, "Champ '{}' vide : Commune / Adresse non renseignées.".format(CHAMP_NOMOPE))
        return None, None

    valeur = str(feats[0][CHAMP_NOMOPE])
    if "," in valeur:
        commune, adresse = valeur.split(",", 1)
        commune = commune.strip()
        adresse = adresse.strip()
    else:
        commune = valeur.strip()
        adresse = ""  # pas de virgule -> adresse laissée vide, comme demandé

    log(feedback, "Depuis '{}' : commune='{}'  adresse='{}'.".format(CHAMP_NOMOPE, commune, adresse))
    return commune, adresse


# ----------------------- étape 3 : détection région / département ----------

def _point_geom_dans_crs_couche(point_xy, crs_source, couche):
    """Géométrie ponctuelle, reprojetée dans le CRS de `couche` si celui-ci
    diffère du CRS source (les couches régions/départements ne sont pas
    forcément dans le même CRS que le projet/l'emprise - un `contains()`
    entre deux géométries de CRS différents donnerait un résultat
    incorrect sans cette reprojection)."""
    if couche.crs().authid() and couche.crs() != crs_source:
        transform = QgsCoordinateTransform(crs_source, couche.crs(), QgsProject.instance())
        try:
            point_xy = transform.transform(point_xy)
        except Exception:
            pass  # on retente quand même avec le point d'origine plutôt que planter
    return QgsGeometry.fromPointXY(point_xy)


def _trouver_entite_spatiale(couche, point_xy, crs_source, feedback=None, nom_affiche=None):
    """Trouve l'entité de `couche` qui contient le point, ou, à défaut, la
    plus proche. Plus robuste qu'un simple `geom.contains(point)` :
    - reprojette le point si les CRS diffèrent (voir ci-dessus) ;
    - utilise `intersects()` (tolère le point exactement sur une frontière,
      contrairement à `contains()` qui peut l'exclure) ;
    - si malgré tout aucune entité ne contient le point (ex. léger écart
      de numérisation entre deux couches aux frontières), se rabat sur
      l'entité la plus proche plutôt que d'abandonner."""
    nom_affiche = nom_affiche or couche.name()
    pt_geom = _point_geom_dans_crs_couche(point_xy, crs_source, couche)

    for feat in couche.getFeatures():
        geom = feat.geometry()
        if geom and not geom.isEmpty() and geom.intersects(pt_geom):
            return feat

    # repli : entité la plus proche (tolère un petit écart de numérisation)
    index = QgsSpatialIndex(couche.getFeatures())
    voisins = index.nearestNeighbor(pt_geom.asPoint(), 1)
    if voisins:
        candidats = couche.getFeatures(QgsFeatureRequest(voisins[0]))
        feat = next(candidats, None)
        if feat is not None and feat.geometry():
            distance = feat.geometry().distance(pt_geom)
            log(feedback, "Aucune entité de '{}' ne contient exactement le point : "
                           "entité la plus proche retenue (à {:.1f} m).".format(nom_affiche, distance))
            return feat

    return None


def detecter_region(project, centroid_point, crs_source, feedback=None):
    """Cherche la couche REGIONS2016 dans le projet et détermine dans
    quelle région (clé interne, cf region_config.py) tombe le centroïde.
    Retourne (cle_region, nom_trouve) ou (None, None) si non déterminé."""
    couches = project.mapLayersByName(COUCHE_REGIONS)
    if not couches:
        log(feedback, "Attention : couche '{}' introuvable dans le projet, "
                       "impossible de détecter automatiquement la région.".format(COUCHE_REGIONS))
        return None, None

    regions_layer = couches[0]
    feat = _trouver_entite_spatiale(regions_layer, centroid_point, crs_source, feedback, COUCHE_REGIONS)
    if feat is None:
        log(feedback, "Le centroïde de l'emprise ne tombe dans aucun polygone de '{}' et aucune "
                       "entité proche n'a été trouvée (hors de France métropolitaine ?).".format(COUCHE_REGIONS))
        return None, None

    noms_champs = [f.name() for f in regions_layer.fields()]
    champ_region = next((c for c in CHAMPS_REGION_POSSIBLES if c in noms_champs), None)
    valeur = feat[champ_region] if champ_region else None
    if valeur is None:
        for c in noms_champs:
            cle = trouver_region(feat[c])
            if cle:
                return cle, feat[c]
        log(feedback, "Région trouvée géométriquement mais aucun champ "
                       "reconnu ne permet de l'identifier (voir CHAMPS_REGION_POSSIBLES). "
                       "Champs disponibles sur '{}' : {}.".format(COUCHE_REGIONS, noms_champs))
        return None, None
    cle = trouver_region(valeur)
    if cle:
        log(feedback, "Région détectée : {} ({})".format(valeur, cle))
        return cle, valeur
    log(feedback, "Valeur de région '{}' non reconnue (voir region_config.py).".format(valeur))
    return None, valeur


def detecter_departement(dept_layer, centroid_point, crs_source, feedback=None):
    """Cherche dans quel polygone de la couche `dept_<région>` tombe le
    centroïde et retourne le nom du département, ou None."""
    if dept_layer is None:
        return None
    feat = _trouver_entite_spatiale(dept_layer, centroid_point, crs_source, feedback, dept_layer.name())
    if feat is None:
        log(feedback, "Centroïde hors de la couche département '{}' (et aucune entité "
                       "proche trouvée).".format(dept_layer.name()))
        return None

    noms_champs = [f.name() for f in dept_layer.fields()]
    champ = next((c for c in CHAMPS_DEPARTEMENT_POSSIBLES if c in noms_champs), None)
    if champ is None:
        log(feedback, "Département trouvé géométriquement mais aucun champ reconnu "
                       "(voir CHAMPS_DEPARTEMENT_POSSIBLES). Champs disponibles sur '{}' : {}.".format(
                           dept_layer.name(), noms_champs))
        return None
    valeur = feat[champ]
    log(feedback, "Département détecté : {}".format(valeur))
    return str(valeur) if valeur is not None else None


# ----------------------- étape 4 : mise en page / cartes -----------------

def _role_item(map_item):
    """Détermine le 'rôle' (A, B, C, D25, DCAD) d'une carte de mise en page
    à partir du nom de thème qu'elle avait mémorisé à l'origine (même si on
    ne s'en sert plus pour l'affichage) : c'est la façon la plus robuste de
    retrouver quelle carte est quelle carte, les identifiants étant vides
    dans le projet d'origine."""
    nom = map_item.followVisibilityPresetName() or ""
    if nom.startswith("A_France"):
        return "A"
    if nom.startswith("B_D"):
        return "B"
    if nom == "C 250":
        return "C"
    if nom == "D 25":
        return "D25"
    if nom == "D cadastre":
        return "DCAD"
    return None


def recuperer_cartes(project, feedback=None):
    """Retourne un dict {role: QgsLayoutItemMap} en cherchant dans les 2
    mises en page du projet."""
    manager = project.layoutManager()
    resultat = {}
    for nom_layout in (LAYOUT_LOCALISATION, LAYOUT_PLAN_CADASTRE):
        layout = manager.layoutByName(nom_layout)
        if layout is None:
            log(feedback, "Attention : mise en page '{}' introuvable.".format(nom_layout))
            continue
        for item in layout.items():
            if isinstance(item, QgsLayoutItemMap):
                role = _role_item(item)
                if role:
                    resultat[role] = item
                else:
                    log(feedback, "Carte non reconnue dans '{}' (thème mémorisé : '{}') "
                                   "— ignorée.".format(nom_layout, item.followVisibilityPresetName()))
    manquantes = {"A", "B", "C", "D25", "DCAD"} - set(resultat)
    if manquantes:
        log(feedback, "Cartes non trouvées : {}. Vérifiez les noms de mise en page "
                       "en tête de core.py.".format(", ".join(sorted(manquantes))))
    return resultat


def _trouver_couche(project, nom, feedback=None):
    couches = project.mapLayersByName(nom)
    if not couches:
        log(feedback, "Attention : couche '{}' introuvable dans le projet.".format(nom))
        return None
    return couches[0]


def appliquer_couches(map_item, couches, feedback=None):
    """Fixe explicitement la liste des couches affichées par une carte de
    mise en page (la première de la liste est dessinée AU-DESSUS des
    suivantes). On désactive le suivi de thème pour que cette liste ne
    soit pas écrasée au moment du rendu/export."""
    couches = [c for c in couches if c is not None]
    map_item.setFollowVisibilityPreset(False)
    map_item.setLayers(couches)
    log(feedback, "Carte '{}' -> couches : {}".format(
        map_item.uuid(), ", ".join(c.name() for c in couches)))


def desactiver_apercus(map_item, feedback=None):
    """Désactive les 'aperçus' (overviews) éventuellement configurés sur
    cette carte. Un aperçu dessine, sur CETTE carte, un cadre représentant
    l'emprise actuelle d'UNE AUTRE carte de la mise en page (trouvé dans
    le projet fourni : la carte D 25 a un aperçu nommé "Aperçu 1" qui
    dessine l'emprise de la carte D cadastre). Comme cette dernière est
    maintenant recentrée/redimensionnée automatiquement, ce cadre bouge
    et peut apparaître comme un rectangle indésirable autour de
    l'emprise : on le désactive systématiquement."""
    pile = map_item.overviews()
    if pile is None or pile.size() == 0:
        return
    for i in range(pile.size()):
        apercu = pile.overview(i)
        if apercu.enabled():
            apercu.setEnabled(False)
            log(feedback, "Aperçu '{}' désactivé sur la carte '{}' (cadre indésirable).".format(
                apercu.name(), map_item.uuid()))


def recentrer_sur_point(map_item, point_xy, echelle=None, feedback=None):
    """Recadre une carte sur un point, à l'échelle donnée (ou à l'échelle
    actuelle de l'élément si `echelle` est None)."""
    if echelle is None:
        echelle = map_item.scale()
    rect = map_item.extent()
    largeur = rect.width()
    hauteur = rect.height()
    if echelle != map_item.scale() and map_item.scale():
        ratio = echelle / map_item.scale()
        largeur *= ratio
        hauteur *= ratio
    nouvelle_emprise = QgsRectangle(
        point_xy.x() - largeur / 2.0,
        point_xy.y() - hauteur / 2.0,
        point_xy.x() + largeur / 2.0,
        point_xy.y() + hauteur / 2.0,
    )
    map_item.setExtent(nouvelle_emprise)
    map_item.setScale(echelle)
    log(feedback, "Carte recentrée sur {:.1f}, {:.1f} (échelle 1:{:.0f}).".format(
        point_xy.x(), point_xy.y(), echelle))


def echelle_pour_couche(map_item, layer, marge=0.08, echelle_min=None, echelle_max=None, feedback=None):
    """Calcule l'échelle à laquelle la carte `map_item` devrait être réglée
    pour montrer l'emprise totale de `layer` (ex : dept_<région>) avec une
    marge, SANS déplacer le centre de la carte (utilisé uniquement pour
    déterminer une échelle adaptée). Retourne cette échelle, recalée dans
    [echelle_min, echelle_max] si fournis (pour garantir que le style de
    l'emprise s'affiche bien à cette échelle, voir ECHELLE_B_MIN/MAX)."""
    layer.updateExtents()
    rect = QgsRectangle(layer.extent())
    if rect.isEmpty():
        log(feedback, "Impossible de calculer une échelle depuis '{}' : emprise vide.".format(layer.name()))
        return None
    rect.scale(1.0 + marge)

    map_item.zoomToExtent(rect)  # sert uniquement à calculer l'échelle qui ferait tenir `rect`
    echelle = map_item.scale()

    if echelle_min and echelle < echelle_min:
        echelle = echelle_min
    elif echelle_max and echelle > echelle_max:
        echelle = echelle_max

    log(feedback, "Échelle calculée depuis l'emprise de la couche '{}' : 1:{:.0f}.".format(
        layer.name(), echelle))
    return echelle


def choisir_echelle_cadastre(bbox, item_width_mm, item_height_mm, feedback=None):
    """Choisit, parmi ECHELLES_NORMALISEES_CADASTRE, la plus petite échelle
    pour laquelle le cadre de la carte contient l'emprise avec une marge
    confortable (MARGE_CADASTRE). Retourne la dernière (plus grande)
    échelle de la liste si même la plus grande échelle est trop serrée."""
    largeur_emprise = max(bbox.width(), 1.0)
    hauteur_emprise = max(bbox.height(), 1.0)

    for echelle in ECHELLES_NORMALISEES_CADASTRE:
        cadre_largeur_m = echelle * item_width_mm / 1000.0
        cadre_hauteur_m = echelle * item_height_mm / 1000.0
        if cadre_largeur_m >= largeur_emprise * MARGE_CADASTRE and \
           cadre_hauteur_m >= hauteur_emprise * MARGE_CADASTRE:
            log(feedback, "Échelle cadastre choisie : 1:{} (emprise {:.1f} x {:.1f} m).".format(
                echelle, largeur_emprise, hauteur_emprise))
            return echelle

    echelle = ECHELLES_NORMALISEES_CADASTRE[-1]
    log(feedback, "Emprise plus grande que prévu : échelle maximale de la liste "
                   "retenue par défaut (1:{}). Ajoutez une valeur plus grande à "
                   "ECHELLES_NORMALISEES_CADASTRE si besoin.".format(echelle))
    return echelle


def _pas_agreable(valeur_cible):
    """Arrondit `valeur_cible` au nombre "rond" (1-2-5 x 10^n) supérieur
    le plus proche, pour un pas de grille lisible."""
    if valeur_cible <= 0:
        return 1
    exposant = math.floor(math.log10(valeur_cible))
    base = valeur_cible / (10 ** exposant)
    for candidat in (1, 2, 5, 10):
        if base <= candidat:
            return candidat * (10 ** exposant)
    return 10 ** (exposant + 1)


def ajuster_grille(map_item, echelle, feedback=None, divisions=DIVISIONS_GRILLE_CADASTRE):
    """Élargit le pas de la grille de la carte en fonction de l'échelle
    réellement utilisée, pour éviter une grille trop dense (trop de croix
    et d'étiquettes de coordonnées) quand l'emprise est petite."""
    grilles = map_item.grids()
    if grilles is None or grilles.size() == 0:
        log(feedback, "Aucune grille configurée sur cette carte : pas de grille inchangé.")
        return
    largeur_m = echelle * map_item.rect().width() / 1000.0
    pas = _pas_agreable(largeur_m / divisions)
    for i in range(grilles.size()):
        grille = grilles.grid(i)
        grille.setIntervalX(pas)
        grille.setIntervalY(pas)
    log(feedback, "Pas de grille cadastre ajusté à {:g} m (~{} divisions sur la largeur).".format(
        pas, divisions))


def limiter_taille_etiquettes_parcelle(couche_parcelle, taille_max=TAILLE_MAX_ETIQUETTE_PARCELLE, feedback=None):
    """Plafonne la taille des étiquettes de numéro de parcelle à
    `taille_max` points. Modifie le style de la couche partagée
    'CADASTRALPARCELS...parcelle' elle-même (et sera donc conservé si le
    projet est enregistré ensuite)."""
    if couche_parcelle is None or not couche_parcelle.labelsEnabled():
        if couche_parcelle is not None:
            log(feedback, "Étiquetage non activé sur '{}' : taille inchangée.".format(couche_parcelle.name()))
        return
    labeling = couche_parcelle.labeling()
    if labeling is None:
        return
    try:
        settings = labeling.settings()
        fmt = settings.format()
        police = fmt.font()
        if police.pointSizeF() > taille_max or police.pointSizeF() <= 0:
            police.setPointSizeF(taille_max)
            fmt.setFont(police)
            fmt.setSize(taille_max)
            settings.setFormat(fmt)
            labeling.setSettings(settings)
            couche_parcelle.setLabeling(labeling)
            couche_parcelle.triggerRepaint()
            log(feedback, "Taille des étiquettes de parcelle plafonnée à {} pt.".format(taille_max))
    except AttributeError as exc:
        log(feedback, "Impossible d'ajuster la taille des étiquettes de parcelle "
                       "(API d'étiquetage différente dans votre version de QGIS : {}).".format(exc))


# ----------------------- étape 5 : étiquettes texte -------------------------

_MARQUEURS_XYZ = ("X", "Y", "Z")
# ':' optionnel : dans le projet fourni, l'étiquette réelle contient
# littéralement "Département\nCommune\nAdresse\n...\nX : \nY : \nZ : "
# -- SANS ':' après Département/Commune/Adresse (seuls X/Y/Z en ont un).
_TOUS_MARQUEURS_RE = r'\b(?:[XYZ]|D[ée]partement|Commune|Adresse|Auteur)\b[ \t]*:?'


def _est_etiquette_coordonnees(texte):
    if not texte:
        return False
    return all(re.search(r'\b{}\b[ \t]*:?'.format(m), texte) for m in _MARQUEURS_XYZ)


def _injecter_champ(texte, motif_marqueur, valeur_txt):
    """Remplace ce qui suit 'MARQUEUR' (avec ou sans ':', jusqu'à la fin de
    ligne ou le marqueur suivant) par ' : valeur', en normalisant le
    séparateur sur ' : '. `motif_marqueur` est une regex (ex. 'X',
    'D[ée]partement', 'Commune'...)."""
    # [ \t]* (et non \s*) après le marqueur : on ne doit pas avaler un
    # retour à la ligne, sous peine de décaler le texte injecté sur la
    # ligne suivante dans les étiquettes multi-lignes.
    motif = re.compile(r'(\b{}\b)[ \t]*:?[ \t]*([^\n]*)'.format(motif_marqueur), re.IGNORECASE)

    def remplacement(m):
        reste = m.group(2)
        autre = re.search(_TOUS_MARQUEURS_RE, reste, re.IGNORECASE)
        suffixe = reste[autre.start():] if autre else ""
        sep = "  " if suffixe else ""
        return m.group(1) + " : " + (valeur_txt or "") + sep + suffixe

    nouveau, n = motif.subn(remplacement, texte, count=1)
    return nouveau, n > 0


def maj_etiquette_coordonnees(project, x, y, z, feedback=None):
    """Met à jour, UNIQUEMENT dans la mise en page de localisation
    (01_Localisation_250000.pdf), le texte existant contenant 'X :', 'Y :'
    et 'Z :'. Ne crée rien si aucune étiquette de ce type n'est trouvée :
    dans ce cas un avertissement est simplement journalisé."""
    layout = project.layoutManager().layoutByName(LAYOUT_LOCALISATION)
    if layout is None:
        log(feedback, "Mise en page '{}' introuvable : X/Y/Z non écrits.".format(LAYOUT_LOCALISATION))
        return

    trouvee = False
    for item in layout.items():
        if isinstance(item, QgsLayoutItemLabel) and _est_etiquette_coordonnees(item.text()):
            texte = item.text()
            texte, _ = _injecter_champ(texte, "X", "{:.2f} m".format(x))
            texte, _ = _injecter_champ(texte, "Y", "{:.2f} m".format(y))
            texte, _ = _injecter_champ(texte, "Z", "{:.2f} m NGF".format(z))
            item.setText(texte)
            trouvee = True
            log(feedback, "Étiquette X/Y/Z mise à jour dans '{}'.".format(LAYOUT_LOCALISATION))

    if not trouvee:
        log(feedback, "Aucune étiquette contenant 'X :', 'Y :' et 'Z :' trouvée dans "
                       "'{}'. Rien n'a été écrit (aucune étiquette créée, comme demandé).".format(LAYOUT_LOCALISATION))


def maj_informations_administratives(project, departement, commune, adresse, feedback=None):
    """Remplit, UNIQUEMENT dans la mise en page de localisation, les
    étiquettes existantes contenant 'Département :', 'Commune :',
    'Adresse :' et 'Auteur :'. Chaque champ est traité indépendamment
    (peut être dans la même étiquette que X/Y/Z ou dans des étiquettes
    séparées) ; un champ dont la valeur est None n'est pas touché."""
    layout = project.layoutManager().layoutByName(LAYOUT_LOCALISATION)
    if layout is None:
        return

    champs = [
        ("D[ée]partement", departement, "Département"),
        ("Commune", commune, "Commune"),
        ("Adresse", adresse, "Adresse"),
        ("Auteur", AUTEUR, "Auteur"),
    ]

    au_moins_un_trouve = {nom: False for _, _, nom in champs}

    for item in layout.items():
        if not isinstance(item, QgsLayoutItemLabel):
            continue
        texte = item.text()
        modifie = False
        for motif, valeur, nom_aff in champs:
            if valeur is None:
                continue
            texte, trouve = _injecter_champ(texte, motif, valeur)
            if trouve:
                modifie = True
                au_moins_un_trouve[nom_aff] = True
        if modifie:
            item.setText(texte)

    for motif, valeur, nom_aff in champs:
        if valeur is None:
            continue
        if au_moins_un_trouve[nom_aff]:
            log(feedback, "Champ '{}' renseigné : '{}'.".format(nom_aff, valeur))
        else:
            log(feedback, "Aucune étiquette '{} :' trouvée dans '{}' : champ non renseigné.".format(
                nom_aff, LAYOUT_LOCALISATION))


# --------------------- nettoyage de la légende obsolète --------------------

def _sans_accents(texte):
    """Normalise un texte pour une comparaison insensible aux accents/casse."""
    if not texte:
        return ""
    nfkd = unicodedata.normalize("NFKD", texte)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


# Fragment du texte de la légende à supprimer (ancien concept "extrait
# cadastral", qui n'existe plus dans le résultat produit par le plugin :
# seule reste la légende "emprise prescrite de l'opération"). Comparaison
# par sous-chaîne normalisée (sans accents/casse) : robuste aux variantes
# de ponctuation/majuscules, contrairement à un identifiant d'objet (UUID)
# qui change d'un projet à l'autre.
FRAGMENT_LEGENDE_OBSOLETE = "extrait cadastral"


def supprimer_legende_obsolete(layout, feedback=None):
    """Supprime de `layout` l'entrée de légende obsolète ('emprise de
    l'extrait cadastral') : cette légende est construite « à la main »
    dans la mise en page (une étiquette de texte + un petit rectangle de
    couleur côte à côte), et non via le mécanisme de légende automatique
    de QGIS -- il n'y a donc rien à faire côté couches/style, il faut
    retirer directement ces objets de la mise en page.

    Repérage : on cherche l'étiquette dont le texte contient le fragment
    FRAGMENT_LEGENDE_OBSOLETE, puis on retire aussi tout objet-forme
    (rectangle de couleur) placé juste à côté (même ligne, verticalement
    aligné) : c'est le pavé de couleur associé à cette ligne de légende.
    """
    if layout is None:
        return

    etiquettes_a_supprimer = []
    for item in layout.items():
        if isinstance(item, QgsLayoutItemLabel) and FRAGMENT_LEGENDE_OBSOLETE in _sans_accents(item.text()):
            etiquettes_a_supprimer.append(item)

    if not etiquettes_a_supprimer:
        log(feedback, "Légende obsolète ('{}') non trouvée dans la mise en page "
                       "'{}' (déjà supprimée, ou texte différent -- rien à faire).".format(
                           FRAGMENT_LEGENDE_OBSOLETE, layout.name()))
        return

    # Les rectangles/formes de la mise en page, pour retrouver celui aligné
    # avec chaque étiquette à supprimer.
    formes = [it for it in layout.items() if isinstance(it, QgsLayoutItemShape)]

    a_retirer = []
    for etiquette in etiquettes_a_supprimer:
        a_retirer.append(etiquette)
        rect_etiquette = etiquette.positionWithUnits()
        centre_y_etiquette = rect_etiquette.y() + etiquette.rect().height() / 2.0
        meilleure_forme = None
        meilleur_ecart = None
        for forme in formes:
            pos_forme = forme.positionWithUnits()
            centre_y_forme = pos_forme.y() + forme.rect().height() / 2.0
            ecart = abs(centre_y_forme - centre_y_etiquette)
            # Tolérance large (2x la hauteur du pavé) car le pavé de couleur
            # n'est pas forcément parfaitement centré avec le texte.
            if ecart <= max(forme.rect().height(), 3.0) * 2 and (meilleur_ecart is None or ecart < meilleur_ecart):
                meilleur_ecart = ecart
                meilleure_forme = forme
        if meilleure_forme is not None and meilleure_forme not in a_retirer:
            a_retirer.append(meilleure_forme)

    for item in a_retirer:
        layout.removeLayoutItem(item)

    log(feedback, "Légende obsolète ('{}') supprimée de la mise en page '{}' "
                   "({} objet(s) retiré(s) : étiquette + pavé de couleur le cas échéant).".format(
                       FRAGMENT_LEGENDE_OBSOLETE, layout.name(), len(a_retirer)))


# ------------------- correction des polices manquantes ---------------------

# Polices de substitution essayées dans l'ordre, pour chaque police
# manquante : d'abord de vrais équivalents métriquement compatibles avec
# Arial (donc aucun changement visuel de mise en page), puis une police
# "sans" quelconque réellement installée en dernier recours.
POLICES_SUBSTITUTION = ["Arial", "Liberation Sans", "Arimo", "Helvetica", "DejaVu Sans"]


def _polices_installees():
    """Liste des polices réellement disponibles pour Qt sur cette machine,
    compatible QGIS/Qt5 (`QFontDatabase().families()`, méthode d'instance)
    et QGIS/Qt6 (`QFontDatabase.families()`, méthode statique)."""
    try:
        return set(QFontDatabase.families())  # Qt6 : méthode statique
    except TypeError:
        return set(QFontDatabase().families())  # Qt5 : méthode d'instance


def _resoudre_police(nom_police, polices_dispo, feedback=None):
    """Si `nom_police` n'est pas réellement installée, retourne la première
    police de secours de POLICES_SUBSTITUTION qui l'est vraiment (sinon la
    police d'origine, inchangée -- dernier recours)."""
    if nom_police in polices_dispo:
        return nom_police
    for candidate in POLICES_SUBSTITUTION:
        if candidate in polices_dispo:
            log(feedback, "Police '{}' absente de cette machine -> remplacée par '{}' "
                           "(évite le rendu 'lettre par lettre avec police de substitution "
                           "Qt' observé dans Illustrator sur les PDF exportés).".format(
                               nom_police, candidate))
            return candidate
    return nom_police


def corriger_polices_manquantes(layout, feedback=None):
    """Remplace, sur toutes les étiquettes de `layout`, une police absente de
    la machine par une police réellement installée et métriquement proche.

    Pourquoi : les messages QGIS/Qt « La police XXX-0-50 est manquante »
    (vus à l'ouverture des PDF dans Illustrator) signifient que la police
    demandée (ex. Arial) n'est pas installée sur la machine qui a produit
    l'export. Qt ne se contente alors pas de choisir silencieusement une
    police système équivalente : lors de l'écriture du PDF, faute de
    disposer des véritables métriques de glyphes de la police demandée, il
    positionne CHAQUE caractère individuellement au lieu d'écrire le texte
    d'un bloc -- d'où le texte qui apparaît lettre par lettre (un objet par
    caractère) une fois ouvert dans Illustrator, au lieu d'un objet texte
    par ligne. Donner à QGIS, en amont, le nom d'une police qui est vraiment
    installée (donc avec de vraies métriques) fait écrire le texte normalement,
    par bloc/ligne."""
    polices_dispo = _polices_installees()
    for item in layout.items():
        if not isinstance(item, QgsLayoutItemLabel):
            continue
        try:
            fmt = item.textFormat()
            police_actuelle = fmt.font().family()
            police_corrigee = _resoudre_police(police_actuelle, polices_dispo, feedback)
            if police_corrigee != police_actuelle:
                police = fmt.font()
                police.setFamily(police_corrigee)
                fmt.setFont(police)
                item.setTextFormat(fmt)
        except AttributeError:
            # Anciennes versions de l'API : étiquette en mode "police simple"
            # (`item.font()` / `item.setFont()`) plutôt que `QgsTextFormat`.
            police = item.font()
            police_actuelle = police.family()
            police_corrigee = _resoudre_police(police_actuelle, polices_dispo, feedback)
            if police_corrigee != police_actuelle:
                police.setFamily(police_corrigee)
                item.setFont(police)


# ----------------------- étape 6 : export PDF ------------------------------

def _format_texte_toujours_texte():
    """Retourne la valeur d'énumération 'toujours exporter le texte comme
    objets texte', quelle que soit la version de QGIS (l'emplacement de
    cette énumération a changé entre les versions 3.x)."""
    try:
        from qgis.core import Qgis
        return Qgis.TextRenderFormat.AlwaysText
    except Exception:
        pass
    return QgsRenderContext.TextFormatAlwaysText


def _reglages_export_pdf():
    """Réglages PDF alignés sur la copie d'écran fournie :
       - Toujours exporter comme vecteurs : coché
       - Ajouter les informations de géoréférencement : décoché
       - Exporter les métadonnées RDF : décoché
       - Export de texte : toujours exporter le texte sous forme d'objets texte
       - Compression d'image : sans perte

       Si le texte continue à sortir "vectorisé" (en courbes) malgré ce
       réglage, la cause la plus fréquente n'est PAS ce paramètre global
       mais un effet appliqué aux étiquettes elles-mêmes (mode de fusion
       différent de "Normal" sur le tampon/l'arrière-plan du texte, ou un
       masque actif) : QGIS convertit alors le texte concerné en courbes
       pour préserver le rendu, quel que soit ce réglage d'export.
    """
    settings = QgsLayoutExporter.PdfExportSettings()
    settings.forceVectorOutput = True
    settings.rasterizeWholeImage = False
    settings.appendGeoreference = False
    settings.exportMetadata = False
    settings.textRenderFormat = _format_texte_toujours_texte()
    settings.losslessImageCompression = True
    return settings


def exporter_pdf(layout, chemin, feedback=None):
    """Exporte TOUTES les pages de `layout` dans un seul PDF `chemin`."""
    exporter = QgsLayoutExporter(layout)
    settings = _reglages_export_pdf()
    resultat = exporter.exportToPdf(chemin, settings)
    if resultat != QgsLayoutExporter.Success:
        raise EmpriseAutoCartesError("Échec de l'export PDF : {}".format(chemin))
    log(feedback, "PDF exporté : {}".format(chemin))


def _charger_module_decoupe_pdf():
    """Retourne le module permettant de lire/écrire des PDF page par page
    (`pypdf`, ou son prédécesseur `PyPDF2`), quel que soit celui installé
    dans l'environnement Python de QGIS."""
    try:
        import pypdf
        return pypdf
    except ImportError:
        pass
    try:
        import PyPDF2
        return PyPDF2
    except ImportError:
        pass
    raise EmpriseAutoCartesError(
        "Impossible de séparer le PDF en pages individuelles : ni 'pypdf' ni "
        "'PyPDF2' ne sont installés dans l'environnement Python de QGIS. "
        "Installez l'un des deux (via OSGeo4W Shell : `pip install pypdf`) "
        "puis relancez le plugin.")


def _extraire_page_pdf(chemin_source, page_index, chemin_dest, feedback=None):
    """Extrait UNE SEULE page (0-indexée) de `chemin_source` vers un nouveau
    fichier `chemin_dest`.

    Technique utilisée au lieu de `PdfExportSettings.pages` : cette dernière
    n'a aucun effet selon la version de QGIS installée (le PDF produit
    contient alors systématiquement toutes les pages de la mise en page,
    silencieusement -- ni erreur ni avertissement). On exporte donc TOUTE
    la mise en page une fois (comportement d'export toujours fiable, quelle
    que soit la version de QGIS), puis on découpe le fichier obtenu avec une
    bibliothèque PDF pure (pypdf/PyPDF2) qui copie la page demandée telle
    quelle, sans jamais re-rendre le contenu ni toucher à la mise en page
    QGIS : aucun risque de décalage du contenu restant."""
    module = _charger_module_decoupe_pdf()
    lecteur = module.PdfReader(chemin_source)
    nb_pages = len(lecteur.pages)
    if page_index < 0 or page_index >= nb_pages:
        raise EmpriseAutoCartesError(
            "Page {} demandée mais le PDF '{}' n'en contient que {}.".format(
                page_index, chemin_source, nb_pages))
    ecrivain = module.PdfWriter()
    ecrivain.add_page(lecteur.pages[page_index])
    with open(chemin_dest, "wb") as f:
        ecrivain.write(f)
    log(feedback, "Page {}/{} extraite de '{}' -> '{}'.".format(
        page_index + 1, nb_pages, chemin_source, chemin_dest))


def exporter_les_3_cartes(project, dossier_sortie, cartes=None, feedback=None):
    """Exporte les 3 PDF demandés :
       - 01_Localisation_250000.pdf  <- mise en page A-B-C-localisation (1 page)
       - 02_Plan_25000.pdf           <- mise en page D-25 000-cadastre, PAGE DE LA CARTE "D 25" UNIQUEMENT
       - 03_Plan_cadastre.pdf        <- mise en page D-25 000-cadastre, PAGE DE LA CARTE "D cadastre" UNIQUEMENT

    L'index de page gardé pour 02/03 est déterminé dynamiquement depuis
    `cartes["D25"].page()` / `cartes["DCAD"].page()` (la page réelle de
    chaque carte dans la mise en page), plutôt que supposé fixe (0/1) :
    plus robuste si l'ordre des pages diffère de ce qui était attendu.

    02/03 sont obtenus en exportant une fois TOUTES les pages de la mise en
    page "D-25 000-cadastre" dans un PDF temporaire, puis en découpant ce
    fichier en 2 PDF d'une page chacun (cf. `_extraire_page_pdf` pour le
    pourquoi de cette approche).
    """
    os.makedirs(dossier_sortie, exist_ok=True)
    manager = project.layoutManager()
    cartes = cartes or {}

    layout_loc = manager.layoutByName(LAYOUT_LOCALISATION)
    if layout_loc is not None:
        exporter_pdf(layout_loc, os.path.join(dossier_sortie, "01_Localisation_250000.pdf"),
                     feedback=feedback)

    layout_cad = manager.layoutByName(LAYOUT_PLAN_CADASTRE)
    if layout_cad is not None:
        page_d25 = cartes["D25"].page() if "D25" in cartes else 0
        page_dcad = cartes["DCAD"].page() if "DCAD" in cartes else 1
        log(feedback, "Page réelle de la carte D25 = {} ; page réelle de la carte D cadastre = {}.".format(
            page_d25, page_dcad))

        chemin_tmp = os.path.join(
            tempfile.gettempdir(),
            "emprise_auto_cartes_tmp_{}.pdf".format(os.getpid()))
        try:
            exporter_pdf(layout_cad, chemin_tmp, feedback=feedback)
            _extraire_page_pdf(chemin_tmp, page_d25,
                                os.path.join(dossier_sortie, "02_Plan_25000.pdf"), feedback=feedback)
            _extraire_page_pdf(chemin_tmp, page_dcad,
                                os.path.join(dossier_sortie, "03_Plan_cadastre.pdf"), feedback=feedback)
        finally:
            if os.path.isfile(chemin_tmp):
                try:
                    os.remove(chemin_tmp)
                except OSError:
                    pass


# ----------------------- orchestration globale -----------------------------

def executer(project, emprise_layer, z_value, dossier_sortie, feedback=None):
    """Fonction principale appelée par le dialogue du plugin."""
    centroid, bbox = calculer_centroide_et_emprise(emprise_layer, feedback)
    x, y = centroid.x(), centroid.y()

    appliquer_style_emprise(emprise_layer, feedback)
    couche_point_b = creer_couche_point_secours(project, centroid, emprise_layer.crs(), feedback)
    renseigner_xyz(emprise_layer, x, y, z_value, feedback)
    commune, adresse = extraire_commune_adresse(emprise_layer, feedback)

    cle_region, nom_region_brut = detecter_region(project, centroid, emprise_layer.crs(), feedback)

    cartes = recuperer_cartes(project, feedback)

    regions_layer = _trouver_couche(project, COUCHE_REGIONS, feedback)
    fond_250 = _trouver_couche(project, COUCHE_FOND_C_250, feedback)
    fond_25 = _trouver_couche(project, COUCHE_FOND_D_25, feedback)
    couche_parcelle = _trouver_couche(project, COUCHE_PARCELLE_CADASTRE, feedback)

    dept_layer = None
    departement_nom = None
    if cle_region and cle_region in REGIONS:
        dept_layer = _trouver_couche(project, REGIONS[cle_region]["dept_layer"], feedback)
        departement_nom = detecter_departement(dept_layer, centroid, emprise_layer.crs(), feedback)

    # --- Carte A (France) : emprise (point aux échelles lointaines) + région surlignée
    if "A" in cartes:
        appliquer_couches(cartes["A"], [emprise_layer, regions_layer], feedback)
        desactiver_apercus(cartes["A"], feedback)
        if cle_region and cle_region in REGIONS and regions_layer is not None:
            style_voulu = REGIONS[cle_region]["style_a"]
            styles_dispo = regions_layer.styleManager().styles() if regions_layer.styleManager() else []
            if style_voulu not in styles_dispo:
                log(feedback, "ATTENTION : le style '{}' attendu pour la région détectée ({}) "
                               "n'existe pas dans les styles enregistrés de la couche '{}'. "
                               "Styles disponibles sur cette couche : {}. La carte A ne sera "
                               "probablement pas correctement surlignée : corrigez 'style_a' dans "
                               "region_config.py avec l'un des noms listés ci-dessus.".format(
                                   style_voulu, cle_region, regions_layer.name(), styles_dispo))
            cartes["A"].setLayerStyleOverrides({regions_layer.id(): style_voulu})
            log(feedback, "Carte A -> région mise en évidence : style '{}' demandé "
                           "(région détectée : {}).".format(style_voulu, nom_region_brut))
        else:
            log(feedback, "ATTENTION : région NON déterminée automatiquement -> la carte A garde "
                           "le style actuellement actif de la couche régions, donc probablement AUCUNE "
                           "région en rouge. Vérifiez dans le journal ci-dessus la ligne 'Région détectée' "
                           "/ 'Le centroïde de l'emprise ne tombe dans aucun polygone...' : si la couche "
                           "REGIONS2016 n'a pas été trouvée, ou si son champ de nom de région n'est pas "
                           "reconnu, corrigez COUCHE_REGIONS / CHAMPS_REGION_POSSIBLES en tête de core.py.")

    # --- Carte B (Départements de la région) : emprise + point de secours (garanti
    #     visible, cf. creer_couche_point_secours) + dept_<région>
    if "B" in cartes:
        appliquer_couches(cartes["B"], [couche_point_b, emprise_layer, dept_layer], feedback)
        desactiver_apercus(cartes["B"], feedback)
        if dept_layer is not None:
            # On calcule l'échelle qui ferait tenir tout le département à
            # l'écran, PUIS on recentre explicitement sur l'EMPRISE (et non
            # sur le centre du département) à cette échelle : sinon le point
            # rouge de l'emprise peut tomber hors du cadre affiché si
            # l'emprise n'est pas près du centre géographique du département
            # (bug réel identifié : le point ne s'affichait pas car il
            # sortait du cadre, pas parce que le style ne fonctionnait pas).
            echelle_b = echelle_pour_couche(cartes["B"], dept_layer, feedback=feedback,
                                             echelle_min=ECHELLE_B_MIN, echelle_max=ECHELLE_B_MAX)
            if echelle_b:
                recentrer_sur_point(cartes["B"], centroid, echelle=echelle_b, feedback=feedback)
        else:
            log(feedback, "Région non déterminée : la carte B n'a pas été recadrée.")

    # --- Carte C (250) : emprise (point rouge, règle 248000-252000) + Scan Régional
    if "C" in cartes:
        appliquer_couches(cartes["C"], [emprise_layer, fond_250], feedback)
        desactiver_apercus(cartes["C"], feedback)
        recentrer_sur_point(cartes["C"], centroid, echelle=250000, feedback=feedback)

    # --- Carte D 25 : emprise (polygone, règle IGN25000) + fond SCAN 25.
    #     Ne contient PAS la couche des parcelles cadastrales (celle-ci est
    #     réservée à la carte D cadastre / 03_Plan_cadastre.pdf). L'aperçu
    #     "Aperçu 1" (cadre vers la carte D cadastre) est désactivé : sinon,
    #     la carte D cadastre étant recentrée/redimensionnée automatiquement,
    #     ce cadre apparaît comme un rectangle indésirable autour de l'emprise.
    if "D25" in cartes:
        appliquer_couches(cartes["D25"], [emprise_layer, fond_25], feedback)
        desactiver_apercus(cartes["D25"], feedback)
        recentrer_sur_point(cartes["D25"], centroid, echelle=25000, feedback=feedback)

    # --- Carte D cadastre (BD Parcellaire) : emprise + parcelles
    if "DCAD" in cartes:
        appliquer_couches(cartes["DCAD"], [emprise_layer, couche_parcelle], feedback)
        desactiver_apercus(cartes["DCAD"], feedback)
        item = cartes["DCAD"]
        echelle = choisir_echelle_cadastre(
            bbox, item.rect().width(), item.rect().height(), feedback=feedback
        )
        recentrer_sur_point(item, centroid, echelle=echelle, feedback=feedback)
        ajuster_grille(item, echelle, feedback=feedback)
        limiter_taille_etiquettes_parcelle(couche_parcelle, feedback=feedback)

    maj_etiquette_coordonnees(project, x, y, z_value, feedback)
    maj_informations_administratives(project, departement_nom, commune, adresse, feedback)

    for layout_nom in (LAYOUT_LOCALISATION, LAYOUT_PLAN_CADASTRE):
        layout = project.layoutManager().layoutByName(layout_nom)
        if layout is not None:
            supprimer_legende_obsolete(layout, feedback)
            corriger_polices_manquantes(layout, feedback)
            layout.refresh()

    exporter_les_3_cartes(project, dossier_sortie, cartes=cartes, feedback=feedback)

    # Nettoyage : la couche ponctuelle de secours n'a plus d'utilité une
    # fois l'export terminé (elle n'était de toute façon pas visible dans
    # le panneau des couches).
    project.removeMapLayer(couche_point_b.id())

    return {
        "x": x, "y": y, "z": z_value,
        "region": nom_region_brut, "region_cle": cle_region,
        "departement": departement_nom, "commune": commune, "adresse": adresse,
    }
