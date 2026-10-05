# -*- coding: utf-8 -*-
"""
Point d'entrée du plugin QGIS "Emprise Auto Cartes".
"""


def classFactory(iface):
    from .emprise_auto_cartes import EmpriseAutoCartesPlugin
    return EmpriseAutoCartesPlugin(iface)
