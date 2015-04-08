# -*- coding:Utf-8 -*-
#!/usr/bin/env python
import sys
import os
from math import sqrt
import time
from operator import attrgetter

BORNE_INF_MODIF = 1.e-5
BORNE_SUP_MODIF = 1.e-4

class Point:
    """Définition d'un point.
    
    Attributs :
    - identifiant (chaine de caractère) 
    - latitude et longitude (flottant)
    """
    def __init__(self, node_id, node_lat, node_lon):
        self.node_id = node_id
        self.node_lat = float(node_lat)
        self.node_lon = float(node_lon)
        
    def affiche(self):
        print self.node_id, self.node_lat, self.node_lon
        
    def distance(self, other):
        """Calcul de la distance entre deux points"""
        d_lat = self.node_lat - other.node_lat
        d_lon = self.node_lon - other.node_lon
        return sqrt(d_lat**2 + d_lon**2)
        
    def export_node(self):
        """Création du code xml équivalent au point"""
        self.print_node = "  <node id='" + self.node_id + \
            "' action='modify' visible='true' lat='" + \
            str(self.node_lat) + "' lon='" + str(self.node_lon) + "' />"

class Batiment:
    """L'entité Batiment rassemble plusieurs données : 
    
        - bat_id : un identifiant (chaine de caractère)
        - nbre_node : le nombre de points du batiment (nombre entier)
        - node_id : le tableau des Points du batiments
        - pt_moy : le point de référence du batiments (centre de gravité)
        - dist_mini : une valeurs de distance pour détecter la modification du batiment
        - largeur : la largeur du batiment
        - status : le status du batiment (nouveau, identique, modifié, supprimé)
        - nombre_tag : le nombre de tag défini dans le fichier
        - tableau_tag_key : le tableau d'identifiants des tags
        - tableau_tag_value : le tableau des valeurs des tags
        - pbAire : l'information si le batiment a une aire nulle
        - multipolygone : yes si le batiment en est un, no sinon
        - role : le role si le batiment appartient à une relation
        - ind_relation : l'indice de la relation auquel il appartient
    """
    def __init__(self, bat_id, nbre_node, node_id, 
            numTag, tableauTagKey, tableauTagValue, 
            distance=1000, largeur = 0., status = "UNKNOWN", pbAire = "NO",
            multipolygone = "no", role = "outer", ind_relation = 0):
        self.bat_id = bat_id
        self.nbre_node = nbre_node
        self.node_id = node_id
        self.dist_mini = float(distance)
        self.largeur = largeur
        self.status = status
        self.nombre_tag = numTag
        self.tableau_tag_key = tableauTagKey
        self.tableau_tag_value = tableauTagValue
        self.pbAire = "NO"
        self.multipolygone = "no"
        self.role = "outer"
        self.ind_relation = 0
    
    def BatimentToPoint(self):
        """Calcul du centre de gravité du batiment.
        
        les coordonnées sont d'abord exprimés en "pseudo-mètres" en 
        prenant comme origine le premier point du batiment parce qu'il
        n'y a pas suffisamment de différence entre chaque point pour
        faire les calcul (il faudrait augmenter la précision).
        Ensuite le calcul se fait d'après 
            https://fr.wikipedia.org/wiki/Aire_et_centre_de_masse_d%27un_polygone
        Le calcul nécessite de diviser par la surface du batiment. Cela
        pose problème si le batiment a une surface nulle. Les exceptions
        sont traités avec pbAire. Dans ce cas le point de référence de 
        ces batiments est la moyenne des coordonnées de chaque point.
        """
        i_node = 0
        calculLatitude = 0
        calculLongitude = 0
        latMoyenne = 0
        lonMoyenne = 0
        aire = 0
        latLocale = []
        lonLocale = []
        while i_node < self.nbre_node:
            latLocale.append((self.node_id[i_node].node_lat - \
                self.node_id[0].node_lat) * 6500000.)
            lonLocale.append((self.node_id[i_node].node_lon - \
                self.node_id[0].node_lon) * 6500000.)
            i_node = i_node + 1
        i_node = 0
        while i_node < self.nbre_node - 1:
            latMoyenne = latMoyenne + self.node_id[i_node].node_lat
            lonMoyenne = lonMoyenne + self.node_id[i_node].node_lon
            produitEnCroix = (latLocale[i_node] * lonLocale[i_node + 1] - \
                latLocale[i_node + 1] * lonLocale[i_node])
            aire = aire + 0.5 * produitEnCroix
            calculLatitude = calculLatitude + (latLocale[i_node] + \
                latLocale[i_node + 1]) * produitEnCroix
            calculLongitude = calculLongitude + (lonLocale[i_node] + \
                lonLocale[i_node + 1]) * produitEnCroix
            i_node = i_node + 1
        if aire == 0.:
            self.pbAire = "YES"
            latitude = latMoyenne / self.nbre_node
            longitude = lonMoyenne / self.nbre_node
        else:
            latitude = self.node_id[0].node_lat + \
                calculLatitude / (6 * aire * 6500000.)
            longitude = self.node_id[0].node_lon + \
                calculLongitude / (6 * aire * 6500000.)
        self.pt_moy = Point(self.bat_id, latitude, longitude)
        
    def calculLargeur(self):
        """Calcul de la largeur approximative du batiment. 
        
        Cette distance intervient ensuite dans la détermination
        du status du batiment. Si la distance mini est supérieure à cette
        largeur alors cela veut dire que le batiment est nouveau ou 
        supprimé."""
        tableauLatitude = []
        tableauLongitude = []
        for node in range(self.nbre_node):
            tableauLatitude.append(self.node_id[node].node_lat)
            tableauLongitude.append(self.node_id[node].node_lon)
        minLat = min(tableauLatitude)
        maxLat = max(tableauLatitude)
        minLon = min(tableauLongitude)
        maxLon = max(tableauLongitude)
        self.largeur = sqrt((maxLat - minLat)**2 + (maxLon - minLon)**2)
        
    def setDistMini(self, distance):
        """Cette méthode permet de définir la distance mini comme étant celle
            passé en paramètre"""
        self.dist_mini = float(distance)
    
    def setBatProche(self, nomBatProche, indBatProche):
        """Cette méthode permet de définir que le batiment auquel elle est
        appliquée correspond au batiment passé en paramètre"""
        self.id_bat_proche = nomBatProche
        self.ind_bat_proche = indBatProche
        
    def setStatus(self, status):
        """Cette méthode défini le status du batiment."""
        self.status = status
    
    def setRole(self, role):
        """
        Cette méthode défini le role du batiment lorsqu'il appartient à
        une relation. Le role est soit "inner" soit "outer".
        """
        self.role = role
        
    def export_bat(self):
        """Cette méthode défini une version xml du batiment, de ses noeuds
        et de ses éventuels tag dans le but d'être transcrit dans un fichier."""
        export = []
        res_export = ""
        export.append("  <way id='" + self.bat_id + "' visible='true'>")
        i_node = 0
        while i_node < self.nbre_node:
            export.append("    <nd ref='" + self.node_id[i_node].node_id + \
                "' />")
            i_node = i_node + 1
        for i_tag in range(self.nombre_tag):
            export.append("    <tag k='" + self.tableau_tag_key[i_tag] + \
                "' v='" + self.tableau_tag_value[i_tag] + "' />")
        export.append("  </way>")
        i_node = 0
        while i_node < self.nbre_node:
            self.node_id[i_node].export_node()
            export.append(self.node_id[i_node].print_node)
            i_node = i_node + 1
        nb_ligne = len(export)
        i_ligne = 0
        while i_ligne < nb_ligne:
            if i_ligne == nb_ligne - 1:
                res_export = res_export + export[i_ligne]
            else:
                res_export = res_export + export[i_ligne] + "\n"
            i_ligne = i_ligne + 1
        self.print_bat = res_export
        
    def copy_tag(self, other, status):
        """Cette méthode permet de copier les tag d'un batiment passé en 
        paramètre au batiment auquelle elle est appliquée.
        Lorsque le batiment 'self' est détecté comme identique, la source est
        hérité du batiment 'other'. Par contre lorsque le batiment 'self' est
        détecté comme modifié, la source est mis à jour pour prendre la valeur
        du batiment 'other'.
        """
        if status == "IDENTIQUE":
            self.nombre_tag = other.nombre_tag
            self.tableau_tag_key = other.tableau_tag_key
            self.tableau_tag_value = other.tableau_tag_value
        elif status == "MODIFIE":
            rang_tag_source = self.tableau_tag_key.index("source")
            tag_source_save = self.tableau_tag_value[rang_tag_source]
            self.nombre_tag = other.nombre_tag
            self.tableau_tag_key = other.tableau_tag_key
            self.tableau_tag_value = other.tableau_tag_value
            try:
                rang_tag_source = self.tableau_tag_key.index("source")
                self.tableau_tag_value[rang_tag_source] = tag_source_save
            except:
                pass

class Relation:
    """
    Classe qui regroupe les relations pour le traitement des multipolygones.
    """
    
    def __init__(self, id_relation, nb_ways, tab_id_ways, tab_ind_ways, tab_role):
        self.id = id_relation
        self.nb_ways = nb_ways
        self.id_ways = tab_id_ways
        self.ind_ways = tab_ind_ways
        self.role = tab_role
    
    def export_relation(self):
        export = []
        res_export = ""
        export.append("  <relation id='" + self.id + "'>")
        export.append("    <tag k='value' v='multipolygon'/>")
        for ways in range(self.nb_ways):
            export.append("    <member type='way' ref='" + \
                self.id_ways[ways] + "' role='" + \
                self.role[ways] + "'/>")
        export.append("  </relation>")
        nb_ligne = len(export)
        i_ligne = 0
        while i_ligne < nb_ligne:
            if i_ligne == nb_ligne - 1:
                res_export = res_export + export[i_ligne]
            else:
                res_export = res_export + export[i_ligne] + "\n"
            i_ligne = i_ligne + 1
        self.print_relation = res_export

def formatLog(donnees):
    """Cette fonction permet de générer une chaine de caractère formaté et 
    de longueur constante à partir du tableau passé en paramètre"""
    result = ""
    nbData = len(donnees)
    for i_data in range(nbData):
        if i_data < nbData - 1:
            nbCarLimite = 18
        else:
            nbCarLimite = 50
        donnees[i_data] = " " + donnees[i_data]
        nbCar = len(donnees[i_data])
        while nbCar < nbCarLimite:
            donnees[i_data] = donnees[i_data] + " "
            nbCar = len(donnees[i_data])
        result = result + "|" + donnees[i_data]
    result = result + "|"
    return result

#------------------------------------------------------------------------------
#      D E B U T   D U   P R O G R A M M E
#------------------------------------------------------------------------------


adresse = sys.path[0]
fichier_osm_old = sys.argv[1]
fichier_osm_new = sys.argv[2]
prefixe = sys.argv[3]

separation = "--------------------------------------------------------------------------------------------------------------------------------"


tps1 = time.clock()

print "------------------------------------------------------------------"
print "-                    Lecture des données                         -"
print "------------------------------------------------------------------"

#------------------------------------------------------------------------
#lecture des vieux batiments :
#------------------------------------------------------------------------
file_old = open(fichier_osm_old, "r")
print "lecture du fichier " + fichier_osm_old + "..."
#détermination du séparateur du fichier : " ou '
ligne = file_old.readline().rstrip('\n\r')
tabLigne1 = ligne.split("'")
tabLigne2 = ligne.split("\"")
if len(tabLigne1) > len(tabLigne2):
    delim = "'"
else:
    delim = "\""

old_nodes = []
old_id_nodes = []
old_bati = []
old_bati_sorted = []
old_relation = []

old_nbre_nodes = 0
old_nbre_ways = 0
old_nbre_relation = 0
i_way = 0
i_nd_ref = 0

col_id = 0
col_lat = 0
col_lon = 0

for ligne in file_old:
    champsLigne = ligne.rstrip('\n\r').split(delim)
    if champsLigne[0].find("node id") != -1:
        col_id = 1
        col_lat = champsLigne.index(" lat=") + 1
        col_lon = champsLigne.index(" lon=") + 1
        old_nodes.append(Point(champsLigne[col_id], champsLigne[col_lat], \
            champsLigne[col_lon]))
        old_id_nodes.append(champsLigne[col_id])
        old_nbre_nodes = old_nbre_nodes + 1
    elif champsLigne[0].find("way id") != -1: # nouveau batiment : on initialise les données
        way_id = champsLigne[1]
        i_nd_ref = 0
        nodes = []
        tagKey = []
        tagValue = []
        numTag = 0
    elif champsLigne[0].find("nd ref") != -1:
        id_nd_ref = champsLigne[1]
        i_nd_ref = i_nd_ref + 1
        nodes.append(old_nodes[old_id_nodes.index(id_nd_ref)])
    elif champsLigne[0].find("tag") != -1:
        if i_nd_ref != 0:
            tagKey.append(champsLigne[1])
            tagValue.append(champsLigne[3])
            numTag = numTag + 1
    elif champsLigne[0].find("/way") != -1:
        old_bati.append(Batiment(way_id, i_nd_ref, nodes, \
            numTag, tagKey, tagValue, 1000, 0., "UNKNOWN"))
        old_bati[old_nbre_ways].BatimentToPoint()
        if old_bati[old_nbre_ways].pbAire == "YES":
            print "  Warning, surface nulle obtenue pour le batiment :", \
                old_bati[old_nbre_ways].bat_id 
        old_bati[old_nbre_ways].calculLargeur()
        old_nbre_ways = old_nbre_ways + 1
    elif champsLigne[0].find("relation id") !=-1:
        relation_id = champsLigne[1]
        nb_member = 0
        tab_id_member = []
        tab_ind_member = []
        tab_role = []
    elif champsLigne[0].find("member type") != -1:
        col_ref = champsLigne.index(" ref=") + 1
        col_role = champsLigne.index(" role=") + 1
        tab_id_member.append(champsLigne[col_ref])
        tab_role.append(champsLigne[col_role])
        nb_member = nb_member + 1
    elif champsLigne[0].find("/relation") != -1:
        for i_member in range(nb_member):
            for i_bat in range(old_nbre_ways):
                if old_bati[i_bat].bat_id == tab_id_member[i_member]:
                    old_bati[i_bat].multipolygone = "yes"
                    old_bat[i_bat].ind_relation = old_nbre_relation
                    tab_ind_member.append(i_bat)
                    if tab_role[i_member] == "inner":
                        old_bati[i_bat].setRole("inner")
        old_relation.append(Relation(relation_id, nb_member, tab_id_member, \
            tab_ind_member, tab_role))
        old_nbre_relation = old_nbre_relation + 1
        

file_old.close()

print "  " + str(old_nbre_nodes) + " noeuds répertoriés dans le fichier " + \
    fichier_osm_old
print "  " + str(old_nbre_ways) + " batiments répertoriés dans le fichier " + \
    fichier_osm_old


#------------------------------------------------------------------------
#lecture des nouveaux batiments :
#------------------------------------------------------------------------
file_new = open(fichier_osm_new, "r")
print "lecture du fichier " + fichier_osm_new + "..."
ligne = file_new.readline().rstrip('\n\r')
tabLigne1 = ligne.split("'")
tabLigne2 = ligne.split("\"")
if len(tabLigne1) > len(tabLigne2):
    delim = "'"
else:
    delim = "\""

new_nodes = []
new_id_nodes = []
new_bati = []
new_bati_sorted = []
new_relation = []

new_nbre_nodes = 0
new_nbre_ways = 0
new_nbre_relation = 0
i_way = 0
i_nd_ref = 0
col_id = 0
col_lat = 0
col_lon = 0

for ligne in file_new:
    champsLigne = ligne.rstrip('\n\r').split(delim)
    if champsLigne[0].find("node id") != -1:
        col_id = 1
        col_lat = champsLigne.index(" lat=") + 1
        col_lon = champsLigne.index(" lon=") + 1
        new_nodes.append(Point(champsLigne[col_id], champsLigne[col_lat], \
            champsLigne[col_lon]))
        new_id_nodes.append(champsLigne[col_id])
        new_nbre_nodes = new_nbre_nodes + 1
    elif champsLigne[0].find("way id") != -1:
        way_id = champsLigne[1]
        i_nd_ref = 0
        nodes = []
        tagKey = []
        tagValue = []
        numTag = 0
    elif champsLigne[0].find("nd ref") != -1:
        id_nd_ref = champsLigne[1]
        i_nd_ref = i_nd_ref + 1
        nodes.append(new_nodes[new_id_nodes.index(id_nd_ref)])
    elif champsLigne[0].find("tag") != -1:
        if i_nd_ref != 0:
            tagKey.append(champsLigne[1])
            tagValue.append(champsLigne[3])
            numTag = numTag + 1
    elif champsLigne[0].find("/way") != -1:
        new_bati.append(Batiment(way_id, i_nd_ref, nodes, \
            numTag, tagKey, tagValue, 1000, 0., "UNKNOWN"))
        new_bati[new_nbre_ways].BatimentToPoint()
        if new_bati[new_nbre_ways].pbAire == "YES":
            print "  Attention, surface nulle obtenue pour le batiment :", \
                new_bati[new_nbre_ways].bat_id 
        new_bati[new_nbre_ways].calculLargeur()
        new_nbre_ways = new_nbre_ways + 1
    elif champsLigne[0].find("relation id") !=-1:
        relation_id = champsLigne[1]
        nb_member = 0
        tab_id_member = []
        tab_ind_member = []
        tab_role = []
    elif champsLigne[0].find("member type") != -1:
        col_ref = champsLigne.index(" ref=") + 1
        col_role = champsLigne.index(" role=") + 1
        tab_id_member.append(champsLigne[col_ref])
        tab_role.append(champsLigne[col_role])
        nb_member = nb_member + 1
    elif champsLigne[0].find("/relation") != -1:
        for i_member in range(nb_member):
            for i_bat in range(new_nbre_ways):
                if new_bati[i_bat].bat_id == tab_id_member[i_member]:
                    new_bati[i_bat].multipolygone = "yes"
                    new_bati[i_bat].ind_relation = new_nbre_relation
                    tab_ind_member.append(i_bat)
                    if tab_role[i_member] == "inner":
                        new_bati[i_bat].setRole("inner")
        new_relation.append(Relation(relation_id, nb_member, tab_id_member, \
            tab_ind_member, tab_role))
        new_nbre_relation = new_nbre_relation + 1

file_new.close()

print "  " + str(new_nbre_nodes) + " noeuds répertoriés dans le fichier " + \
    fichier_osm_new
print "  " + str(new_nbre_ways) + " batiments répertoriés dans le fichier " + \
    fichier_osm_new
print "------------------------------------------------------------------"
print "-  Recherche des similitudes et des différences entre batiments  -"
print "------------------------------------------------------------------"
#------------------------------------------------------------------------------
#calcul des distances mini entre chaque anciens batiments
# pour chaque batiment anciens (resp. nouveau) on détermine la distance 
# la plus petite avec tous les nouveaux batiments (resp. anciens)
#------------------------------------------------------------------------------
nbre_comparaison = 2 * old_nbre_ways * new_nbre_ways
avancement = 0
i_old = 0
while i_old < old_nbre_ways:
    i_new = 0
    if old_bati[i_old].role == "outer":
        while i_new < new_nbre_ways:
            if new_bati[i_new].role == "outer":
                distance = old_bati[i_old].pt_moy.distance(new_bati[i_new].pt_moy)
                if old_bati[i_old].dist_mini > distance:
                    old_bati[i_old].setDistMini(distance)
                    old_bati[i_old].setBatProche(new_bati[i_new].bat_id, i_new)
            i_new = i_new + 1
    else:
        old_bati[i_old].setDistMini(9999.)
        old_bati[i_old].setBatProche("-9999", 9999)
    avancement = int(float(i_old) / (old_nbre_ways + new_nbre_ways) * 100.)
    sys.stdout.write("Calcul en cours : " + str(avancement) + " %" + chr(13))
    i_old = i_old + 1

i_new = 0
while i_new < new_nbre_ways:
    i_old = 0
    if new_bati[i_new].role == "outer":
        while i_old < old_nbre_ways:
            if old_bati[i_old].role == "outer":
                distance = new_bati[i_new].pt_moy.distance(old_bati[i_old].pt_moy)
                if new_bati[i_new].dist_mini > distance:
                    new_bati[i_new].setDistMini(distance)
                    new_bati[i_new].setBatProche(old_bati[i_old].bat_id, i_old)
            i_old = i_old + 1
    else:
        new_bati[i_new].setDistMini(9999.)
        new_bati[i_new].setBatProche("-9999", 9999)
    avancement = int(float(old_nbre_ways + i_new) / \
        (old_nbre_ways + new_nbre_ways) * 100.)
    sys.stdout.write("Calcul en cours : " + str(avancement) + " %" + chr(13))
    i_new = i_new + 1

#------------------------------------------------------------------------
#Classement des batiments :
#  - dist_mini < BORNE_INF_MODIF : identique
#  - BORNE_INF_MODIF < dist_mini < BORNE_SUP_MODIF : modifié
#  - dist_mini > BORNE_SUP_MODIF : nouveau ou supprimé
#  - dist_mini > largeur : nouveau ou supprimé
#------------------------------------------------------------------------

nb_bat_new = 0
nb_bat_mod = 0
nb_bat_del = 0
nb_bat_noMod = 0
nb_bat_inner_new = 0
nb_bat_inner_old = 0

for batiments in range(new_nbre_ways):
    if new_bati[batiments].role == "outer":
        if new_bati[batiments].dist_mini < BORNE_INF_MODIF:
            new_bati[batiments].setStatus("IDENTIQUE")
            new_bati[batiments].copy_tag(old_bati[new_bati[batiments].ind_bat_proche], \
                "IDENTIQUE")
        elif new_bati[batiments].dist_mini > BORNE_INF_MODIF and \
                new_bati[batiments].dist_mini < BORNE_SUP_MODIF:
            new_bati[batiments].setStatus("MODIFIE")
            new_bati[batiments].copy_tag(old_bati[new_bati[batiments].ind_bat_proche], \
                "MODIFIE")
        elif new_bati[batiments].dist_mini > BORNE_SUP_MODIF:
            new_bati[batiments].setStatus("NOUVEAU")
        if new_bati[batiments].dist_mini > new_bati[batiments].largeur:
            new_bati[batiments].setStatus("NOUVEAU")
    else:
        new_bati[batiments].setStatus("INNER")

for batiments in range(old_nbre_ways):
    if old_bati[batiments].role == "outer":
        if old_bati[batiments].dist_mini > BORNE_SUP_MODIF:
            old_bati[batiments].setStatus("SUPPRIME")
        if old_bati[batiments].dist_mini > old_bati[batiments].largeur:
            old_bati[batiments].setStatus("SUPPRIME")
    else:
        old_bati[batiments].setStatus("INNER")

# Classement des batiments en fonction du status et de la distance mini.
new_bati_sorted = sorted(new_bati, key = attrgetter("status", \
    "dist_mini"))
old_bati_sorted = sorted(old_bati, key = attrgetter("status", \
    "dist_mini"))

dernier_id_inner_new = 0
i_new = 0
while i_new < new_nbre_ways:
    if new_bati_sorted[i_new].status == "IDENTIQUE":
        nb_bat_noMod = nb_bat_noMod + 1
        dernier_id_identique = i_new
    elif new_bati_sorted[i_new].status == "INNER":
        nb_bat_inner_new = nb_bat_inner_new + 1
        dernier_id_inner_new = i_new
    elif new_bati_sorted[i_new].status == "MODIFIE":
        nb_bat_mod = nb_bat_mod + 1
        dernier_id_modifie = i_new
    elif new_bati_sorted[i_new].status == "NOUVEAU":
        nb_bat_new = nb_bat_new + 1
    i_new = i_new + 1

dernier_id_inner_old = 0
i_old = 0
while i_old < old_nbre_ways:
    if old_bati_sorted[i_old].status == "INNER":
        nb_bat_inner_old = nb_bat_inner_old + 1
        dernier_id_inner_old = i_old
    elif old_bati_sorted[i_old].status == "SUPPRIME":
        nb_bat_del = nb_bat_del + 1
    i_old = i_old + 1

print "------------------------------------------------------------------"
print "-                    Création des fichiers                       -"
print "------------------------------------------------------------------"
print nb_bat_noMod, " batiments identiques"
print nb_bat_mod, " batiments modifiés"
print nb_bat_new, " batiments nouveaux"
print nb_bat_del, " batiments supprimés"

tps2 = time.clock()


file_log = open(adresse + "/" + prefixe + "_log.txt", "w")
file_log.write("Rappel des input : \n")
file_log.write("    BORNE_INF_MODIF : " + str(BORNE_INF_MODIF) + "\n")
file_log.write("    BORNE_SUP_MODIF : " + str(BORNE_SUP_MODIF) + "\n")
file_log.write("Le fichier " + fichier_osm_old + " contient :" + "\n")
file_log.write("    - " + str(old_nbre_nodes) + " noeuds" + "\n")
file_log.write("    - " + str(old_nbre_ways) + " batiments" + "\n")
file_log.write("Le fichier " + fichier_osm_new + " contient :" + "\n")
file_log.write("    - " + str(new_nbre_nodes) + " noeuds" + "\n")
file_log.write("    - " + str(new_nbre_ways) + " batiments" + "\n")
file_log.write("Résultat de la comparaison :" + "\n")
file_log.write("    Nombre de batiments identiques trouvés : " + \
    str(nb_bat_noMod) + "\n")
file_log.write("    Nombre de batiments modifiés trouvés : " + \
    str(nb_bat_mod) + "\n")
file_log.write("    Nombre de batiments nouveaux trouvés : " + \
    str(nb_bat_new) + "\n")
file_log.write("    Nombre de batiments supprimés trouvés : " + \
    str(nb_bat_del) + "\n")
file_log.write("Temps de calcul : " + str(tps2 - tps1) + " secondes." + "\n")
file_log.write(separation + "\n")
file_log.write("Récapitulatif des nouveaux batiments" + "\n")
file_log.write(separation + "\n")

i_new = 0
while i_new < new_nbre_ways:
    Resultat = [new_bati_sorted[i_new].bat_id, new_bati_sorted[i_new].status, \
        str(round(new_bati_sorted[i_new].dist_mini, 9)), \
        str(new_bati_sorted[i_new].pt_moy.node_lat), \
        str(new_bati_sorted[i_new].pt_moy.node_lon)]
    file_log.write(formatLog(Resultat) + "\n")
    i_new = i_new + 1
file_log.write(separation + "\n")
file_log.write("Récapitulatif des Anciens batiments" + "\n")
file_log.write(separation + "\n")
i_old = 0
while i_old < old_nbre_ways:
    Resultat = [old_bati_sorted[i_old].bat_id, old_bati_sorted[i_old].status, \
        str(round(old_bati_sorted[i_old].dist_mini, 9)), \
        str(old_bati_sorted[i_old].pt_moy.node_lat), \
        str(old_bati_sorted[i_old].pt_moy.node_lon)]
    file_log.write(formatLog(Resultat) + "\n")
    i_old = i_old + 1

file_log.write(separation + "\n")
file_log.write(str(nb_bat_noMod) + " batiments classés comme identiques" + "\n")
file_log.write(separation + "\n")

enTete = ["STATUS", "ANCIEN BATIMENT", "TOLERANCE", "NOUVEAU BATIMENT", "fichier"]
file_log.write(formatLog(enTete) +"\n")

# écriture des batiments identiques dans un même fichier

noMod_building = prefixe + "_unModified.osm"
file_noMod_building = open(adresse + "/" + noMod_building, "w")
file_noMod_building.write("<?xml version='1.0' encoding='UTF-8'?>" + "\n")
file_noMod_building.write("<osm version='0.6' upload='true' generator='JOSM'>" + "\n")
for i_bat in range(dernier_id_identique):
    new_bati_sorted[i_bat].export_bat()
    file_noMod_building.write(new_bati_sorted[i_bat].print_bat + "\n")
    if new_bati_sorted[i_bat].multipolygone == "yes":
        relation = new_bati_sorted[i_bat].ind_relation
        for members in range(new_relation[relation].nb_ways):
            if new_relation[relation].role[members] == "inner":
                indic_bati_membre = new_relation[relation].ind_ways[members]
                new_bati[indic_bati_membre].export_bat()
                file_noMod_building.write(new_bati[indic_bati_membre].print_bat + "\n")
        new_relation[relation].export_relation()
        file_noMod_building.write(new_relation[relation].print_relation + "\n")
    Ligne = ["IDENTIQUE", new_bati_sorted[i_bat].id_bat_proche , \
        str(round(new_bati_sorted[i_bat].dist_mini, 9)), \
        new_bati_sorted[i_bat].bat_id  , noMod_building ]
    file_log.write(formatLog(Ligne) + "\n")

file_noMod_building.write("</osm>")
file_noMod_building.close()

enTete = ["STATUS", "ANCIEN BATIMENT", "TOLERANCE", "NOUVEAU BATIMENT", "fichier"]
# écriture des batiments modifiés dans plusieurs fichier
file_log.write(separation + "\n")
file_log.write(str(nb_bat_mod) + " batiments classés comme modifiés" + "\n")
file_log.write(separation + "\n")
file_log.write(formatLog(enTete) +"\n")
nom_file = prefixe + "_mod_1_a_" + str(nb_bat_mod) + ".osm"
file_mod_building = open(adresse + "/" + nom_file, "w")
file_mod_building.write("<?xml version='1.0' encoding='UTF-8'?>" + "\n")
file_mod_building.write("<osm version='0.6' upload='true' generator='JOSM'>" + "\n")
for i_bat in range(nb_bat_mod):
    indice = dernier_id_inner_new + i_bat + 1
    new_bati_sorted[indice].export_bat()
    file_mod_building.write(new_bati_sorted[indice].print_bat + "\n")
    if new_bati_sorted[indice].multipolygone == "yes":
        relation = new_bati_sorted[indice].ind_relation
        for members in range(new_relation[relation].nb_ways):
            if new_relation[relation].role[members] == "inner":
                indic_bati_membre = new_relation[relation].ind_ways[members]
                new_bati[indic_bati_membre].export_bat()
                file_mod_building.write(new_bati[indic_bati_membre].print_bat + "\n")
        new_relation[relation].export_relation()
        file_mod_building.write(new_relation[relation].print_relation + "\n")
    Ligne = ["MODIFIE", new_bati_sorted[indice].id_bat_proche, \
        str(round(new_bati_sorted[indice].dist_mini, 9)), \
        new_bati_sorted[indice].bat_id, nom_file]
    file_log.write(formatLog(Ligne) + "\n")
file_mod_building.write("</osm>")
file_mod_building.close()


enTete = ["STATUS", "ANCIEN BATIMENT", "TOLERANCE", "NOUVEAU BATIMENT", "fichier"]
# écriture des batiments nouveaux dans plusieurs fichier
file_log.write(separation + "\n")
file_log.write(str(nb_bat_new) + " batiments classés comme nouveaux" + "\n")
file_log.write(separation + "\n")
file_log.write(formatLog(enTete) +"\n")
nom_file = prefixe + "_new_1_a_" + str(nb_bat_new) + ".osm"
file_new_building = open(adresse + "/" + nom_file , "w")
file_new_building.write("<?xml version='1.0' encoding='UTF-8'?>" + "\n")
file_new_building.write("<osm version='0.6' upload='true' generator='JOSM'>" + "\n")
for i_bat in range(nb_bat_new):
    indice = dernier_id_modifie + i_bat + 1
    new_bati_sorted[indice].export_bat()
    file_new_building.write(new_bati_sorted[indice].print_bat + "\n")
    if new_bati_sorted[indice].multipolygone == "yes":
        relation = new_bati_sorted[indice].ind_relation
        for members in range(new_relation[relation].nb_ways):
            if new_relation[relation].role[members] == "inner":
                indic_bati_membre = new_relation[relation].ind_ways[members]
                new_bati[indic_bati_membre].export_bat()
                file_new_building.write(new_bati[indic_bati_membre].print_bat + "\n")
        new_relation[relation].export_relation()
        file_new_building.write(new_relation[relation].print_relation + "\n")
    Ligne = ["NOUVEAU", new_bati_sorted[indice].id_bat_proche, \
        str(round(new_bati_sorted[indice].dist_mini, 9)), \
        new_bati_sorted[indice].bat_id, nom_file]
    file_log.write(formatLog(Ligne) + "\n")
file_new_building.write("</osm>")
file_new_building.close()


enTete = ["STATUS", "ANCIEN BATIMENT", "TOLERANCE", "fichier"]
# écriture des batiments supprimés dans plusieurs fichier
file_log.write(separation + "\n")
file_log.write(str(nb_bat_del) + " batiments classés comme supprimés" + "\n")
file_log.write(separation + "\n")
file_log.write(formatLog(enTete) +"\n")
nom_file = prefixe + "_sup_1_a_" + str(nb_bat_del) + ".osm"
file_del_building = open(adresse + "/" + nom_file , "w")
file_del_building.write("<?xml version='1.0' encoding='UTF-8'?>" + "\n")
file_del_building.write("<osm version='0.6' upload='true' generator='JOSM'>" + "\n")
for i_bat in range(nb_bat_del):
    indice = dernier_id_inner_old + i_bat
    old_bati_sorted[indice].export_bat()
    file_del_building.write(old_bati_sorted[indice].print_bat + "\n")
    if old_bati_sorted[indice].multipolygone == "yes":
        relation = old_bati_sorted[indice].ind_relation
        for members in range(old_relation[relation].nb_ways):
            if old_relation[relation].role[members] == "inner":
                indic_bati_membre = old_relation[relation].ind_ways[members]
                old_bati[indic_bati_membre].export_bat()
                file_del_building.write(old_bati[indic_bati_membre].print_bat + "\n")
        old_relation[relation].export_relation()
        file_del_building.write(old_relation[relation].print_relation + "\n")
    Ligne = ["SUPPRIME", old_bati_sorted[indice].bat_id, \
        str(round(old_bati_sorted[indice].dist_mini, 9)), nom_file]
    file_log.write(formatLog(Ligne) + "\n")
file_del_building.write("</osm>")
file_del_building.close()

file_log.close()

print "Durée du calcul : ", tps2 - tps1
print "------------------------------------------------------------------"
print "-                       FIN DU PROCESS                           -"
print "------------------------------------------------------------------"

