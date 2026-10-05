# Emprise Inrap

Plugin QGIS écrit pour le projet `Cartes_localisation_v20240306.qgz` (INRAP).
(Nom technique du dossier/module resté `emprise_auto_cartes` pour ne pas
changer l'identifiant d'installation ; seul le nom affiché dans QGIS, dans
le menu, la barre d'outils et le titre du dialogue, est "Emprise Inrap".)

## v0.14 — dépôt GitHub + liens d'extension corrigés + icône plus nette

- Liens de `metadata.txt` (`homepage`, `tracker`, `repository`, auparavant
  tous sur le `https://github.com` générique) pointés vers le vrai dépôt :
  https://github.com/zorgglubb/emprise-inrap — c'est ce que QGIS affiche
  et utilise dans le panneau "Informations sur l'extension" (lien
  "Page d'accueil", bouton de signalement de bogue, URL de mise à jour).
- Ajout de `license=GPL-3.0` dans `metadata.txt` (+ fichier `LICENSE`),
  affiché lui aussi dans ce panneau.
- Icône (`icons/icon.png`) redessinée en polygone rouge plein contraste
  (au lieu d'un remplissage semi-transparent qui rendait pâle/délavé à la
  petite taille utilisée dans le panneau "Informations sur l'extension"
  et la barre d'outils), toujours avec "Inrap" écrit dessous.
- Ajout de `LICENSE` (GPL-3.0) et `.gitignore` pour la mise en dépôt Git.

### Mettre en ligne sur GitHub

```bash
cd emprise_auto_cartes
git init
git add .
git commit -m "Version initiale du plugin Emprise Inrap"
git branch -M main
git remote add origin https://github.com/zorgglubb/emprise-inrap.git
git push -u origin main
```
(Créez d'abord le dépôt vide `emprise-inrap` sur https://github.com/zorgglubb,
sans README/licence généré automatiquement, pour éviter un conflit avec les
fichiers déjà fournis ici.)

Pour installer le plugin dans QGIS directement depuis ce code : zippez le
dossier `emprise_auto_cartes` (le `.zip` doit contenir ce dossier à sa
racine) et utilisez "Extensions > Installer une extension > Installer à
partir d'un ZIP" dans QGIS.

## v0.13 — texte "lettre par lettre" dans Illustrator / police manquante

Symptôme : à l'ouverture des PDF dans Illustrator, un bloc de texte (ex.
"SCR : ... / Auteur : Inrap / source : SCAN25TOUR") apparaît sous forme
d'un objet par **lettre** au lieu d'un objet par **ligne**, avec le
message "La police Arial-0-50 est manquante. Le texte concerné sera
affiché avec une police de substitution." (idem pour "Arial-0-75").

Cause : ce message signifie qu'Arial n'est **pas installée sur la machine
qui a produit l'export PDF**. Dans ce cas, Qt (utilisé par QGIS pour
écrire le PDF) ne se contente pas de substituer discrètement une police
système équivalente : faute des vraies métriques de glyphes d'Arial, il
positionne chaque caractère individuellement dans le PDF au lieu d'écrire
le texte en un seul bloc -- d'où le texte "éclaté" lettre par lettre
qu'Illustrator affiche ensuite comme autant d'objets séparés.

Correctif (`core.corriger_polices_manquantes`, appelé automatiquement à
chaque export, sur les deux mises en page) : avant export, pour chaque
étiquette dont la police n'est pas réellement installée sur la machine,
le plugin la remplace par la première police réellement disponible parmi
Arial, Liberation Sans, Arimo, Helvetica, DejaVu Sans (`Liberation Sans`
et `Arimo` sont métriquement identiques à Arial, donc aucun changement de
mise en page). Une fois une vraie police utilisée, QGIS/Qt écrit le texte
normalement, un objet par ligne.

**Pour un résultat identique à l'original (police Arial exacte)** :
installer la police Arial (ou son paquet, ex. `ttf-mscorefonts-installer`
sous Linux) sur la machine qui exécute QGIS, en plus de ce correctif.

## v0.12 — légende obsolète supprimée + export 02/03 fiabilisé + nouvelle icône

- **Légende obsolète supprimée automatiquement** : l'entrée de légende
  "emprise de l'extrait cadastral" (un concept qui n'existe plus dans ce
  que produit le plugin ; seule reste "emprise prescrite de l'opération")
  est construite à la main dans la mise en page (étiquette de texte +
  petit rectangle de couleur), pas via le mécanisme de légende automatique
  de QGIS. Elle est maintenant retirée automatiquement à chaque export,
  par repérage du texte ("extrait cadastral", comparaison insensible aux
  accents/majuscules) plutôt que par identifiant d'objet (UUID), donc
  robuste même si le projet est ensuite modifié (`core.supprimer_legende_obsolete`).
- **02_Plan_25000.pdf / 03_Plan_cadastre.pdf contenaient encore les 2
  pages** : `QgsLayoutExporter.PdfExportSettings.pages` (qui est censé
  restreindre l'export à une seule page) n'a aucun effet selon la version
  de QGIS installée -- le PDF produit contenait silencieusement les 2
  pages de la mise en page "D-25 000-cadastre" au lieu d'une seule.
  Remplacé par une technique indépendante de ce réglage : la mise en page
  est exportée une seule fois (toutes pages), dans un PDF temporaire, qui
  est ensuite découpé avec `pypdf` (ou `PyPDF2` si c'est lui qui est
  installé) pour ne garder que la page de la carte voulue dans chaque
  fichier final. Aucune page n'est re-rendue : le contenu est copié tel
  quel, donc aucun risque de décalage. **Nécessite `pypdf` ou `PyPDF2`
  dans l'environnement Python de QGIS** (`pip install pypdf` depuis
  l'OSGeo4W Shell si besoin).
- **Nouvelle icône** : polygone d'emprise (rouge) avec "Inrap" écrit en
  dessous, à la place de l'ancien pin de localisation.

## v0.11 — icône + renommage en "Emprise Inrap"

- Icône dédiée (`icons/icon.png`, pin de localisation rouge), utilisée
  dans le menu, la barre d'outils et le panneau "Informations sur
  l'extension".
- Nom affiché partout dans l'interface renommé "Emprise Inrap" (menu,
  action, titres de messages, titre du dialogue). `metadata.txt`
  (`name=`) suit aussi.
- **Bug corrigé** : la couche ponctuelle de secours de la carte B (v0.10)
  plantait à la création (`QgsFeatureSink.addFeature(): argument 1 has
  unexpected type 'list'`) — erreur d'API toute bête,
  `provider.addFeature([feat])` au lieu de `provider.addFeatures([feat])`
  (singulier vs pluriel). Corrigé ; le point de secours devrait
  maintenant se créer et s'afficher correctement sur la carte B.

## v0.10 — point rouge de la carte B : couche de secours indépendante du style

Le journal envoyé après la v0.9.0 a montré que la position (centrée
exactement sur l'emprise) et l'échelle (1:7 900 000, dans la plage
attendue) étaient toutes les deux correctes — ce qui élimine toute mon
explication précédente. Il ne restait donc plus qu'une explication
plausible : le symbole utilisé par la règle "Localisation opération" du
style `Emprise_pg.qml` (un `CentroidFill`, au format QGIS 2.6.1) ne se
convertit peut-être pas correctement au chargement dans QGIS 3 — c'est
le SECOND symbole de ce type dans le fichier (le premier, utilisé pour
le point de la carte "C 250", n'a jamais été confirmé visible non plus
en y regardant bien : son absence n'a simplement jamais été signalée).

Plutôt que de continuer à deviner sur ce point précis du style, la carte
B reçoit maintenant, EN PLUS de l'emprise et du fond département, une
**couche ponctuelle de secours** : un simple point rouge, construit
directement avec l'API de style native de QGIS 3 (sans passer par
l'ancien fichier qml), placé au centroïde de l'emprise. Elle est
invisible dans le panneau des couches (ajoutée sans légende) et nettoyée
automatiquement après l'export. Cette fois le point rouge ne dépend plus
du tout du style d'origine : il devrait être visible quoi qu'il arrive.

## v0.9.1 — Auteur du PDF revenu à "Inrap"

Clarification : `AUTEUR` (dans `core.py`) contrôle le texte écrit dans
l'étiquette "Auteur :" du PDF `01_Localisation_250000.pdf` lui-même ;
c'est différent du champ `author` de `metadata.txt`, qui est l'auteur du
PLUGIN affiché dans le panneau "Informations sur l'extension" de QGIS.
Les deux sont indépendants. Sur demande, `AUTEUR` repasse à `"Inrap"` ;
`metadata.txt` reste à `M. Belarbi / Claude`.

**Carte B toujours sans point rouge ?** Le correctif de centrage (carte B
recentrée sur l'emprise, pas sur le centre du département) est bien
présent depuis la v0.9 — vérifiez dans "Informations sur l'extension"
que la version installée est **0.9.1 ou plus**, puis relancez. S'il n'y
a toujours rien, j'ai besoin du journal (`journal_emprise_auto_cartes.txt`),
en particulier les lignes "Échelle calculée depuis l'emprise de la
couche..." et "Carte recentrée sur...".

## v0.9 — grâce au premier vrai journal reçu, deux bugs de fond identifiés

- **Point rouge sur la carte B** : le journal a montré que l'échelle
  finale était correcte (1:7 900 000, dans la plage du style). Le vrai
  bug : `recadrer_sur_couche` zoomait sur l'emprise **du département**,
  donc la carte B était centrée sur le centre géographique de toute la
  région — pas sur l'emprise elle-même. Le point rouge, dessiné aux
  coordonnées réelles de l'emprise, pouvait donc tomber **hors du cadre
  affiché** et ne jamais être visible, même avec la bonne échelle.
  Corrigé : la carte B calcule maintenant l'échelle depuis l'emprise du
  département, PUIS se recentre explicitement sur l'emprise elle-même à
  cette échelle (comme les cartes C/D25/D cadastre).
- **Contenu erroné sur `03_Plan_cadastre.pdf`** : la méthode employée
  depuis la v0.6 (cloner la mise en page puis supprimer physiquement la
  page non désirée) s'appuyait sur un comportement de QGIS non vérifié
  (réorganisation ou non des éléments après suppression d'une page), et
  a visiblement fini par décaler le contenu. Remplacé par le mécanisme
  officiel et documenté de l'API QGIS (`PdfExportSettings.pages`), qui ne
  touche ni aux pages ni aux éléments de la mise en page — seul le choix
  de la page à inclure dans le PDF change. L'index de page par carte
  (D25 / D cadastre), lui, reste déterminé dynamiquement comme en v0.7/0.8.
- **Auteur non visible sur `01.pdf`** : le journal indique bien
  `Champ 'Auteur' renseigné : 'M. Belarbi / Claude'.`, donc le
  remplacement a eu lieu côté code. Si ça ne se voit toujours pas,
  vérifiez que vous ouvrez le PDF fraîchement regénéré (pas un ancien
  fichier mis en cache par la visionneuse) : le texte se trouve en bas à
  gauche, juste sous la carte "250", dans le même bloc que
  "SCR : Lambert 93..." et "source : Scan Régional...".

## v0.8 — bug de fond trouvé : le journal n'a jamais pu s'afficher

En cherchant pourquoi je ne recevais jamais le contenu du journal malgré
plusieurs demandes, j'ai trouvé la vraie cause, indépendante de tout ce
qui précède : le dialogue étant **modal**, il se fermait dès le clic sur
"Exécuter" — **avant même que le traitement ne commence** — et le journal
partait uniquement vers la console Python (invisible). La zone de journal
du dialogue n'a donc jamais pu afficher quoi que ce soit jusqu'ici.
Corrigé : le dialogue reste maintenant ouvert pendant tout le traitement
(le bouton "Exécuter" ne ferme plus le dialogue, un bouton "Fermer"
séparé le fait), le journal se remplit en direct, et il est en plus
**enregistré automatiquement** dans `journal_emprise_auto_cartes.txt` à
côté des 3 PDF — fichier que vous pouvez m'envoyer directement.

- **Cadre indésirable autour de l'emprise sur `02_Plan_25000.pdf`** : bug
  réel trouvé dans le projet — la carte "D 25" a un **aperçu** ("Aperçu 1")
  configuré pour dessiner un cadre représentant l'emprise de la carte
  "D cadastre". Comme cette dernière est désormais recentrée/redimensionnée
  automatiquement à chaque exécution, ce cadre bougeait et apparaissait
  comme un rectangle indésirable. Les aperçus sont désormais désactivés
  automatiquement sur les 5 cartes.
- **Auteur de l'extension** (dans "Informations sur le plugin" de QGIS,
  pas dans les PDF) : `metadata.txt` indique maintenant
  `author=M. Belarbi / Claude`.

## v0.7 — détection région/département rendue beaucoup plus robuste

Sans les journaux d'exécution, impossible de confirmer la cause exacte du
souci sur la carte A (bonne région en rouge) / carte B (point rouge) —
mais un point commun aux deux est que **les deux dépendent entièrement de
la détection automatique de la région**. Si cette détection échoue
silencieusement, la carte A garde un style quelconque et la carte B ne
trouve pas sa couche département ni son recadrage : ça explique les deux
symptômes à la fois. Trois failles plausibles corrigées dans cette
détection :

- **CRS non géré** : si la couche `REGIONS2016` (ou `dept_<région>`)
  n'est pas exactement dans le même système de coordonnées que l'emprise,
  un simple test géométrique comparait des coordonnées incompatibles,
  pouvant faire échouer la détection sans erreur visible. Le point est
  désormais reprojeté dans le CRS de la couche testée avant comparaison.
- **`contains()` trop strict** : un centroïde tombant exactement sur une
  frontière (bord de région/département) pouvait être exclu par
  `contains()`. Remplacé par `intersects()`, plus tolérant.
- **Aucun repli en cas d'écart de numérisation** : si les couches
  régions/emprise proviennent de sources légèrement différentes, un petit
  écart aux frontières pouvait suffire à ce qu'aucun polygone ne
  "contienne" vraiment le point. Le plugin se rabat maintenant sur
  l'entité la plus proche plutôt que d'abandonner, et l'indique
  clairement dans le journal ("aucune entité ne contient exactement le
  point : entité la plus proche retenue à X m").

Si le problème persiste après cette mise à jour, le journal affiché dans
la boîte de dialogue du plugin (zone de texte sous les réglages, après
avoir cliqué "Exécuter") contiendra désormais une raison précise — son
contenu (copié-collé) est la façon la plus rapide de cerner le souci
restant.

## v0.6.1 — correction : l'emprise doit bien être sur `02_Plan_25000.pdf`

Retour en arrière sur un point de la v0.6 : le « pas l'emprise du
cadastre » demandé visait la couche des **parcelles cadastrales**, pas le
polygone de l'emprise lui-même. La carte D 25 (`02_Plan_25000.pdf`)
affiche donc de nouveau l'emprise (polygone plein, règle 1:20 000-30 000
du style) + le fond SCAN 25, toujours **sans** la couche des parcelles
(réservée à `03_Plan_cadastre.pdf`).

## v0.6 — page de `03_Plan_cadastre.pdf`, auteur, emprise retirée de `02_Plan_25000.pdf`

- **`03_Plan_cadastre.pdf` contenait la page 1 au lieu de la page 2** :
  l'index de page gardé pour `02_Plan_25000.pdf` / `03_Plan_cadastre.pdf`
  n'est plus supposé fixe (0 pour D 25, 1 pour D cadastre) mais lu
  **dynamiquement** depuis la position réelle de chaque carte
  (`carte.page()`), ce qui est plus robuste. Le journal affiche
  maintenant explicitement "Page réelle de la carte D25 = … ; page
  réelle de la carte D cadastre = …" ainsi que le nombre de pages
  avant/après nettoyage du clone, pour vérifier facilement que tout est
  cohérent si un souci de pagination reviendrait.
- **`02_Plan_25000.pdf` n'affiche plus l'emprise** (sur demande) : cette
  carte de contexte au 1:25 000 ne montre désormais que le fond SCAN 25,
  sans le polygone/remplissage de l'emprise — celui-ci reste affiché
  uniquement sur `01_Localisation_250000.pdf` (point rouge) et
  `03_Plan_cadastre.pdf` (forme réelle). Si vous préfériez un point plutôt
  qu'une absence totale, dites-le-moi.
- **Auteur** : l'étiquette existante `Auteur : Inrap` (sur la même carte
  que la source du fond de plan) est désormais réécrite en
  `Auteur : M. Belarbi / Claude` (valeur fixe, réglable via la constante
  `AUTEUR` en tête de `core.py`).

## v0.5 — bug réel trouvé pour Département/Commune/Adresse + diagnostic région A

- **Département / Commune / Adresse n'apparaissaient jamais** : bug
  confirmé en lisant le texte réel de l'étiquette dans votre projet. Elle
  contient littéralement :
  ```
  Département
  Commune
  Adresse

  SCR - Lambert 93
  X : 
  Y : 
  Z : 
  ```
  c'est-à-dire **sans `:` après Département/Commune/Adresse** (seuls
  X/Y/Z en ont un). Le plugin cherchait `"Département :"` avec un `:`
  obligatoire et ne trouvait donc jamais rien. Corrigé : le `:` est
  maintenant optionnel en entrée, et le plugin écrit systématiquement
  `"Département : <valeur>"` (ajoute le `:` s'il n'existait pas).
- **Carte A (région en rouge, autres en blanc)** : les noms de style par
  région dans `region_config.py` ont été revérifiés un par un contre le
  fichier projet — ils sont exacts (ex. `'RAA'` pour ARA, confirmé). Si la
  bonne région ne ressort toujours pas en rouge, ce n'est donc
  probablement pas un problème de nom de style mais soit (a) la **région
  n'est pas détectée du tout** (regardez dans le journal si une ligne dit
  qu'aucune région n'a été trouvée), soit (b) un souci plus profond.
  Pour distinguer les deux, le plugin vérifie maintenant explicitement
  que le style demandé existe bien parmi les styles enregistrés de la
  couche `REGIONS2016` et, si ce n'est pas le cas, **liste dans le
  journal tous les styles réellement disponibles sur cette couche** —
  ce qui permettra de corriger `region_config.py` au prochain essai si
  jamais les noms différaient dans votre copie du projet.

## v0.4 — deux bugs réels corrigés

- **`02_Plan_25000.pdf` / `03_Plan_cadastre.pdf` contenaient les 2 pages** :
  le filtre `PdfExportSettings.pages` de l'API QGIS n'est pas fiable sur
  toutes les versions (il peut être ignoré silencieusement). Remplacé par
  une méthode robuste : chaque export travaille désormais sur un **clone
  temporaire** de la mise en page dont la page non désirée est **supprimée
  physiquement** avant export, puis le clone est aussitôt détruit. Votre
  mise en page d'origine n'est jamais modifiée, et le PDF produit ne
  contient garantie qu'une seule page.
- **L'emprise n'apparaissait pas sur `02_Plan_25000.pdf`** : bug réel
  trouvé dans le style `Emprise_pg.qml` lui-même (pas dans le plugin) —
  la règle utilisée à l'échelle 1:25 000 portait un attribut
  `filter="IGN 25000"`, qui n'est pas une expression QGIS valide (ce
  n'est pas une condition booléenne). Une expression de filtre invalide
  ne correspond jamais à aucune entité : la règle ne s'appliquait donc
  jamais, et rien ne s'affichait. Corrigé dans la copie du style
  embarquée par le plugin (`styles/Emprise_pg.qml`) en vidant ce filtre ;
  votre style d'origine, lui, n'est pas modifié par ce correctif.

## v0.3 — changements suite aux retours suivants

- **Point rouge fiabilisé, sans couche fabriquée** : le plugin applique
  désormais le vrai style du projet (`Emprise_pg.qml`, embarqué dans
  `styles/`) sur la couche d'emprise choisie, sur les 5 cartes. C'est ce
  style qui gère nativement remplissage rouge (échelles proches) et point
  rouge (échelles lointaines, dont la carte B) — plus besoin d'une couche
  ponctuelle artificielle. La copie embarquée comble un "trou" du style
  d'origine (rien ne s'affichait entre 1:6 001 et 1:20 000) pour que
  toutes les échelles normalisées de la carte cadastre restent couvertes.
- **Carte A** : la mise en évidence de la région utilise le style exact
  trouvé dans votre projet (`style_a` dans `region_config.py`, extrait du
  XML, ex. `"RAA"` pour Auvergne-Rhône-Alpes). Un message de journal
  explicite confirme la région détectée et le style appliqué, ou
  prévient clairement si la région n'a pas pu être déterminée.
- **Carte B** : l'échelle obtenue en recadrant sur le département est
  désormais recalée si besoin entre 1:3 100 000 et 1:7 900 000, la plage
  couverte par la règle "point rouge" du style — pour garantir qu'il
  s'affiche quelle que soit la taille réelle du département.
- **Grille de `03_Plan_cadastre.pdf`** : le pas est recalculé
  automatiquement à partir de l'échelle choisie (~5 divisions dans la
  largeur), pour éviter une grille trop dense.
- **Étiquettes de numéro de parcelle** sur cette même carte : taille
  plafonnée à 6 pt (modifie le style de la couche partagée des parcelles).
- **Département / Commune / Adresse** sur `01_Localisation_250000.pdf` :
  remplis dans les étiquettes existantes contenant ces mots-clés.
  Département par recherche spatiale dans la couche du département ;
  Commune = texte avant la virgule du champ `nomope` ; Adresse = texte
  après la virgule, sans espace de début, laissée vide s'il n'y a pas de
  virgule.
- **Export « texte toujours en objets texte »** fiabilisé : la recherche
  de la bonne constante tient maintenant compte des versions récentes de
  l'API QGIS. Si le texte sort malgré tout « vectorisé » (en courbes), la
  cause la plus fréquente est un effet appliqué aux étiquettes
  elles-mêmes (mode de fusion ≠ « Normal » ou masque actif sur le tampon
  de texte) : QGIS convertit alors ce texte en courbes quel que soit ce
  réglage d'export — vérifiez les propriétés d'étiquetage des couches
  concernées (onglet « Rendu », effets de tampon/masque).

## v0.2 — changements suite aux premiers retours

- **Le point rouge n'apparaissait pas** sur `01_Localisation_250000.pdf` :
  les thèmes de visibilité du projet (C 250 / D 25 / A / B) ne contiennent
  pas tous la couche d'emprise, et la modifier par programme via l'API des
  thèmes s'est révélé peu fiable. Le plugin assigne désormais **explicitement**
  la liste des couches de chaque carte (`setLayers`), avec l'emprise
  toujours au-dessus — plus robuste et plus simple à diagnostiquer.
- **X / Y / Z ne sont écrits que dans `01_Localisation_250000.pdf`**, dans
  l'étiquette existante contenant `X :`, `Y :` et `Z :` (recherchée
  uniquement dans la mise en page `A-B-C-localisation`). Rien n'est créé
  si cette étiquette n'existe pas encore — un message l'indique dans le
  journal.
- **Export PDF** aligné sur les réglages de la copie d'écran fournie :
  toujours en vecteurs, sans géoréférencement ni métadonnées RDF, texte
  toujours exporté comme objets texte, compression d'image sans perte.
- **Carte cadastre (BD Parcellaire)** : l'échelle n'est plus figée, elle
  est choisie automatiquement parmi une liste d'échelles normalisées
  (200, 500, 1000, 1250, 2500, 5000, 10000, 15000, 20000, 25000) de façon
  à ce que l'emprise n'occupe qu'environ un tiers du cadre (ni trop
  serré, ni trop large). Réglable via `MARGE_CADASTRE` et
  `ECHELLES_NORMALISEES_CADASTRE` dans `core.py`.

## Ce qu'il fait

1. Vous indiquez un **plan d'emprise** (polygone ou point, en **EPSG:2154**)
   déjà chargé dans le projet, ou vous le chargez depuis un fichier
   (.shp, .geojson, .gpkg, .dxf…).
2. Vous saisissez une **altitude Z (NGF)**.
3. Le plugin :
   - calcule le **centroïde X/Y** (et la taille) de l'emprise ;
   - crée/renseigne les champs `X_L93`, `Y_L93`, `Z_NGF` sur la couche d'emprise ;
   - **détecte automatiquement la région** (parmi les 13 régions
     métropolitaines) en croisant le centroïde avec la couche `REGIONS2016`
     du projet ;
   - fixe **explicitement** les couches affichées sur chaque carte (emprise
     toujours au-dessus) :
     - **A (France)** : emprise + `REGIONS2016`, avec le style de région
       correspondant (`style_a` dans `region_config.py`) ;
     - **B (Départements)** : emprise + couche `dept_<région>`, recadrée
       sur l'emprise de la région ;
     - **C (250)** : emprise + `Scan Régional`, recentrée sur l'emprise à 1:250 000 ;
     - **D 25** : emprise + `SCAN 25 Touristique`, recentrée à 1:25 000 ;
     - **D cadastre** : emprise + parcelles cadastrales (WFS), recentrée à
       une **échelle normalisée** choisie automatiquement (voir ci-dessus) ;
   - met à jour **uniquement dans `01_Localisation_250000.pdf`** l'étiquette
     existante contenant `X :`, `Y :`, `Z :` ;
   - exporte **3 PDF** dans le dossier choisi, avec les réglages d'export
     décrits plus haut :
     - `01_Localisation_250000.pdf`
     - `02_Plan_25000.pdf`
     - `03_Plan_cadastre.pdf`

## Installation

Dans QGIS : **Extensions → Installer/Gérer les extensions → Installer
depuis un ZIP…**, puis sélectionnez `emprise_auto_cartes.zip`.

Le plugin ajoute une entrée dans le menu **Extensions → Emprise Auto
Cartes** et une icône de barre d'outils.

## Important — à vérifier avant le premier usage réel

Ce plugin a été écrit par analyse du fichier `.qgz` que vous m'avez
transmis, **sans pouvoir être testé dans un QGIS réel** (environnement de
développement sans QGIS/PyQGIS installé). La logique (noms de mises en
page, de thèmes, de couches, calculs d'échelle/emprise) a été vérifiée
« à la main » en lisant le XML du projet, mais un premier essai réel sur
un petit cas simple est recommandé avant utilisation en production.

Toute la configuration « sensible aux noms » est regroupée en tête du
fichier `core.py` :

```python
LAYOUT_LOCALISATION = "A-B-C-localisation"
LAYOUT_PLAN_CADASTRE = "D-25 000-cadastre"
THEME_C_250 = "C 250"
THEME_D_25 = "D 25"
THEME_D_CADASTRE = "D cadastre"
COUCHE_REGIONS = "REGIONS2016"
CHAMPS_REGION_POSSIBLES = [...]
```

et dans `region_config.py` (table des 13 régions : nom de thème A, nom de
thème B, nom de couche `dept_<région>`, variantes de noms/code INSEE).

Si un jour vous renommez une mise en page, un thème ou une couche, il
suffit de corriger la valeur correspondante ici — le reste du plugin n'a
pas besoin d'être modifié.

### Points qui méritent une vérification particulière

- **Détection du champ région** : le plugin essaie plusieurs noms de
  champs courants (`nom_region`, `NOM_REG`, `region`…) sur la couche
  `REGIONS2016`. S'il n'en trouve aucun, ouvrez la table attributaire de
  cette couche et ajoutez le vrai nom du champ en tête de
  `CHAMPS_REGION_POSSIBLES` dans `core.py`.
- **Noms des couches de fond** : `Scan Régional`, `SCAN 25 Touristique`
  et `CADASTRALPARCELS.PARCELLAIRE_EXPRESS:parcelle` sont recherchées par
  nom exact (`COUCHE_FOND_C_250`, `COUCHE_FOND_D_25`,
  `COUCHE_PARCELLE_CADASTRE` dans `core.py`). Si une couche est introuvable,
  le journal l'indique et la carte correspondante s'affiche sans fond.
- **Étiquette X/Y/Z** : elle doit déjà exister dans la mise en page
  `A-B-C-localisation`, avec un texte contenant `X :`, `Y :` et `Z :`
  (espace avant le `:` optionnel, retours à la ligne autorisés). Le
  plugin remplace ce qui suit chaque marqueur jusqu'à la fin de la ligne
  ou le marqueur suivant. Si le texte réel de votre étiquette est
  différent (ex. `Xl93 :`), adaptez `_est_etiquette_coordonnees` /
  `_injecter_valeur` dans `core.py`, ou renommez l'étiquette.
- **Échelle cadastre** : choisie automatiquement parmi
  `ECHELLES_NORMALISEES_CADASTRE`, avec une marge `MARGE_CADASTRE` (3 par
  défaut, soit l'emprise occupant environ un tiers du cadre). Ajustez ces
  deux valeurs dans `core.py` si le cadrage ne vous convient pas.
- **Régions d'outre-mer** : la table ne couvre que les 13 régions de
  France métropolitaine, cohérent avec l'usage d'EPSG:2154 (Lambert-93,
  valable uniquement en métropole).

## Fichiers du plugin

- `core.py` — toute la logique métier (configuration en tête de fichier).
- `region_config.py` — table de correspondance des 13 régions.
- `emprise_auto_cartes_dialog.py` — boîte de dialogue.
- `emprise_auto_cartes.py` — intégration menu/barre d'outils QGIS.
