# -*- coding: utf-8 -*-
"""
Table de correspondance entre les 13 régions métropolitaines et :
  - le nom du thème (visibility preset) utilisé par la carte "A France"
  - le nom du thème utilisé par la carte "B Départements"
  - le nom de la couche vectorielle régionale ("dept_<région>") utilisée
    pour recadrer la carte B sur l'emprise de la région.
  - les variantes de nom / codes INSEE 2016 permettant de reconnaître la
    région à partir de la couche REGIONS2016 du projet.

Cette table a été construite à partir de l'inspection du fichier
Cartes_localisation_v20240306.qgz fourni (liste exacte des presets de
visibilité et des couches "dept Region 2016"). Si votre projet a été
modifié depuis (nom de thème changé, nouvelle couche régionale...),
corrigez simplement les valeurs ci-dessous : le reste du plugin n'a pas
besoin d'être modifié.
"""

# clé interne -> informations région
# "style_a" = nom EXACT (sensible à la casse/accents) de la style enregistrée
# sur la couche REGIONS2016 pour mettre en évidence cette région sur la
# carte A (France). Extrait directement du fichier .qgs fourni : certaines
# valeurs sont surprenantes (ex. "RAA" pour ARA) mais correspondent bien
# aux styles réellement enregistrés dans le projet d'origine.
REGIONS = {
    "ARA": {
        "style_a": "RAA",
        "dept_layer": "dept_ARA",
        "insee": "84",
        "noms": ["Auvergne-Rhône-Alpes", "Auvergne Rhone Alpes", "ARA"],
    },
    "BFC": {
        "style_a": "BFC",
        "dept_layer": "dept_BFC",
        "insee": "27",
        "noms": ["Bourgogne-Franche-Comté", "Bourgogne Franche Comte", "BFC"],
    },
    "BRETAGNE": {
        "style_a": "Bretagne",
        "dept_layer": "dept_Bretagne",
        "insee": "53",
        "noms": ["Bretagne"],
    },
    "CENTRE": {
        "style_a": "Centre-Val de Loire",
        "dept_layer": "dept_Centre",
        "insee": "24",
        "noms": ["Centre-Val de Loire", "Centre Val de Loire", "Centre"],
    },
    "CORSE": {
        "style_a": "Corse",
        "dept_layer": "dept_Corse",
        "insee": "94",
        "noms": ["Corse"],
    },
    "GE": {
        "style_a": "GE",
        "dept_layer": "dept_Grand_Est",
        "insee": "44",
        "noms": ["Grand Est", "Grand-Est", "GE"],
    },
    "HDF": {
        "style_a": "HDF",
        "dept_layer": "dept_HdF",
        "insee": "32",
        "noms": ["Hauts-de-France", "Hauts de France", "HDF", "HdF"],
    },
    "IDF": {
        "style_a": "Île-de-France",
        "dept_layer": "dept_IdF",
        "insee": "11",
        "noms": ["Île-de-France", "Ile-de-France", "Ile de France", "IDF", "IdF"],
    },
    "NORMANDIE": {
        "style_a": "Normandie",
        "dept_layer": "dept_Normandie",
        "insee": "28",
        "noms": ["Normandie"],
    },
    "N_AQUITAINE": {
        "style_a": "Nouvelle_Aquitaine",
        "dept_layer": "dept_N_Aquitaine",
        "insee": "75",
        "noms": ["Nouvelle-Aquitaine", "Nouvelle Aquitaine"],
    },
    "OCCITANIE": {
        "style_a": "Occitanie",
        "dept_layer": "dept_Occitanie",
        "insee": "76",
        "noms": ["Occitanie"],
    },
    "PACA": {
        "style_a": "PACA",
        "dept_layer": "dept_PACA",
        "insee": "93",
        "noms": ["Provence-Alpes-Côte d'Azur", "Provence Alpes Cote d Azur", "PACA"],
    },
    "PAYS_LOIRE": {
        "style_a": "Pays de la Loire",
        "dept_layer": "dept_Pays_Loire",
        "insee": "52",
        "noms": ["Pays de la Loire", "Pays de Loire"],
    },
}


def _normalise(texte):
    """Minuscule, sans accent ni espace/tiret, pour comparaison robuste."""
    if texte is None:
        return ""
    import unicodedata
    txt = unicodedata.normalize("NFKD", str(texte))
    txt = "".join(c for c in txt if not unicodedata.combining(c))
    txt = txt.lower().strip()
    for ch in (" ", "-", "'", "_"):
        txt = txt.replace(ch, "")
    return txt


# index de recherche rapide nom/code -> clé région, construit une seule fois
_INDEX = {}
for _cle, _infos in REGIONS.items():
    _INDEX[_normalise(_infos["insee"])] = _cle
    for _nom in _infos["noms"]:
        _INDEX[_normalise(_nom)] = _cle


def trouver_region(valeur):
    """Retourne la clé région (ex: 'BRETAGNE') à partir d'un nom de région
    ou d'un code INSEE région tels que trouvés dans la couche REGIONS2016,
    ou None si aucune correspondance n'est trouvée."""
    return _INDEX.get(_normalise(valeur))


def liste_noms_region():
    """Liste triée des noms 'longs' de région (pour un éventuel menu manuel)."""
    return sorted((infos["noms"][0] for infos in REGIONS.values()))


def cle_depuis_nom_long(nom_long):
    for cle, infos in REGIONS.items():
        if infos["noms"][0] == nom_long:
            return cle
    return None
