# BatiOsm
Python tool to help for building updates of OpenStreetMap

---

### Usage
    python BatiOsm.py bati_as_is.osm bati_to_be.osm prefixe

  - *bati_as_is.osm* : Le bâti actuel tel qu'il est dans osm. Personnellement j'utilise josm. Du coup je télécharge toute une commune et j'isole tous les batiments (avec un filtre building=*) dans un onglet que je sauvegarde dans un fichier bati_as_is.osm.
     Une autre façon de faire est de passer par une requête overpass.
  - *bati_to_be.osm* : Obtenir le bati tel qu'il deviendra en utilisant le site du cadastre (http://cadastre.openstreetmap.fr/). 
    Vous obtenez normalement un fichier NOM-COMMUNE-house.osm que je renomme souvent bati_to_be.osm.
  - *prefixe* : préfixe des fichiers créés.
#### Résultats
Si tout s'est bien passé, vous obtenez normalement plusieurs fichiers :
- prefixe_unModified.osm : les bâtiments dont il est raisonnable de penser qu'ils n'ont pas été modifiés. Ils sont communs au deux fichiers en entré.
- prefixe_mod_0_a_xxx.osm : les bâtiments dont il est raisonnable de penser qu'ils ont été modifiés. (xxx est le nombre de bâtiments modifiés).
- prefixe_sup_0_a_yyy.osm : les bâtiments dont il est raisonnable de penser qu'ils ont été supprimés. (yyy est le nombre de bâtiments supprimés).
- prefixe_new_0_a_zzz.osm : les bâtiments dont il est raisonnable de penser qu'ils sont nouveaux. (zzz est le nombre de bâtiments nouveaux).
- prefixe_log.txt : un fichier qui récapitule le classement de chaque bâtiment et la tolérance.

### Fonctionnement

Alors comment ça marche ? Chaque fichier est lu et enregistré. Ils contiennent la latitude et la longitude de chaque point de chaque bâtiment et pour chaque bâtiment les numéros des points.
On est capable de définir un point moyen par bâtiment en calculant son centre de gravité.
Chaque bâtiment des deux fichiers passés en paramètre est résumé à un point.
Si on bouge un seul des nœuds d'un bâtiment le point moyen bougera.
Ensuite la partie la plus fastidieuse (pour l'ordinateur) consiste à prendre ce point de référence de chaque bâtiment du fichier bati_as_is et de calculer la distance entre ce point de référence et le point de référence des bâtiments du fichier bati_to_be.
Cela permet de coupler un bâtiment du fichier bati_as_is et un autre du fichier bati_to_be et d'avoir la distance minimale qui les sépare.
On fait la même chose pour les bâtiments du fichier bati_to_be. Ensuite selon la distance mini qu'on obtient pour chaque bâtiment on peut dire :
- si la distance mini est inférieure à MIN_DISTANCE : la distance entre le bâtiment X de bati_as_is et le bâtiment Y de bati_to_be est très petite.
  Donc X et Y sont identiques.
  Y va dans prefixe_unModified.osm.
- si la distance mini est entre MIN_DISTANCE et MAX_DISTANCE :
  la distance entre les bâtiments X et Y est non négligeable, mais pas énorme non plus.
  X a probablement été modifié et il est devenu Y.
  Y est retranscrit dans prefixe_mod_0_a_xxx.
- si la distance mini est supérieure à MAX_DISTANCE :
  la distance entre les bâtiments X et Y est très grande.
  Lorsque ça concerne le bâtiment X cela veut dire qu'il a été supprimé (donc écrit dans prefixe_sup_0_a_yyy) si cela concerne le bâtiment Y cela signifie que le bâtiment est nouveau (donc écrit dans prefixe_new_0_a_zzz).

Les bornes sont exprimées en mètres. Les valeurs que j'utilise et qui marchent bien sont 1 pour MIN_DISTANCE et 10 pour MAX_DISTANCE.

Que dire d'autre ? Ensuite, il s'agit de jouer avec les calques dans Josm.
En général, j'ai un calque de modification en cours de la zone.
J'ouvre chaque fichier et je fais du copier-coller vers le calque officiel.
Ça n'est pas parfait et il y a toujours du travail à faire (raccorder un bâtiment à des nœuds existants, problème des faux positifs) mais je pense que ça permet de faire un parcours d'une commune assez rapidement.


### Install et upgrade

Python 3.10
####  Install
    $ virtualenv venv
    $ source ./venv/bin/activate
    $ pip install -r requirements.txt

#### Modules upgrade
    $ pip install --upgrade -r requirements.txt

### Todo
- Travail sur une zone plus petite qu'une commune.
