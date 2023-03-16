# -*- coding:Utf-8 -*-
# !/usr/bin/env python
import argparse
import logging
import math
import os
import sys
import time

import lxml.etree

# in meters, limit to consider it's the same building
MIN_DISTANCE = 1.0
# in meters, limit to consider it can't be the same building
MAX_DISTANCE = 10.0
NB_ZONE_USER = 500

# WGS-84 Earth equatorial radius (meters)
EARTH_RADIUS = 6378137.0


class Point:
    """Defines a point

    Attributes :
    - identifier (string)
    - latitude (float)
    - longitude (float)
    """

    lat = 0.0
    lon = 0.0

    def __init__(self, identifier: str, lat: float, lon: float):
        self.print_node = str
        self.node_id = identifier
        self.lat = float(lat)
        self.lon = float(lon)
        self.history = []

    def print(self):
        print(self.node_id, self.lat, self.lon)

    def distance(self, other):
        """Compute distance between two points"""
        lat = self.lat - other.lat
        lon = self.lon - other.lon
        return math.sqrt(lat ** 2 + lon ** 2) * math.pi / 180 * EARTH_RADIUS

    def to_xml(self):
        """Convert into xml"""
        i_hist = 0
        xml = "  <node"
        while i_hist < len(self.history):
            xml = f'{xml} {self.history[i_hist]}="{self.history[i_hist + 1]}"'
            i_hist = i_hist + 2
        xml = f'{xml} />'
        self.print_node = xml

    def set_history(self, history: list):
        """
        Cette méthode défini dans une variable tous les éléments relatifs à
        l'historique dans osm : numéros de version, date de maj, dernier
        utilisateur ayant modifié le batiment, le changeset,etc...
        """
        self.history = history


def replace_quotes(s: str):
    return s.replace('"', '&quot;')


class Building:
    """L'entité Batiment rassemble plusieurs données :

    - bat_id : un identifiant (chaine de caractère)
    - node_count : building's node count
    - nodes : le tableau des Points du batiments
    - tag_count: tag count defined in file
    - pt_moy : le point de référence du batiments (centre de gravité)
    - dist_mini : une valeurs de distance pour détecter la modification du batiment
    - largeur : la largeur du batiment
    - status : le status du batiment (nouveau, identique, modifié, supprimé)
    - tableau_tag_key : le tableau d'identifiants des tags
    - tableau_tag_value : le tableau des valeurs des tags
    - pbAire : l'information si le batiment a une aire nulle
    - Aire : l'aire du batiment
    - multipolygone : yes si le batiment en est un, no sinon
    - role : le role si le batiment appartient à une relation
    - nom_relation : le nom de la relation auquel il appartient (ie l'ID
        de la relation tel que lu dans le fichier source)
    """

    def __init__(
            self,
            bat_id,
            node_count: int,
            nodes: list[Point],
            tag_count: int,
            tag_keys,
            tag_values,
            min_distance: float = 1000.0,
            width=0.0,
            status="UNKNOWN"
    ):
        self.print_bat = None
        self.history = []
        self.close_building_id = str
        self.center = Point
        self.bat_id = bat_id
        self.node_count = node_count
        self.nodes = nodes
        self.min_distance = float(min_distance)
        self.width = width
        self.status = status
        self.tag_count = tag_count
        self.tag_keys = tag_keys
        self.tag_values = tag_values
        self.area_issue = "NO"
        self.area = 0.0
        self.multipolygone = "no"
        self.role = "outer"
        self.relation_name = ""
        self.inner_ways = []

    def compute_center(self):
        """Calcul du centre de gravité du batiment.

        Etant donné qu'il n'y a pas suffisamment de différence entre chaque point,
        pour faire les calculs à partir de la latitude et de la longitude,
        les coordonnées sont d'abord exprimés en "pseudo-mètres" (c.a.d en
        approximant chaque composante par rapport à l'origine à R*(lat2-lat1).
        R étant le rayon de la terre, pris égal à EARTH_RADIUS.
        L'origine est arbitrairement définit comme le premier point du batiment.
        Cela permet de faire les calculs sur des nombres plus grands.
        Ensuite le calcul se fait d'après
            https://fr.wikipedia.org/wiki/Aire_et_centre_de_masse_d%27un_polygone
        Le calcul nécessite de diviser par la surface du batiment. Cela
        pose problème si le batiment a une surface nulle. Les exceptions
        sont traités avec pbAire. Dans ce cas le point de référence de
        ces batiments est la moyenne des coordonnées de chaque point.
        """
        computed_latitude = 0
        computed_longitude = 0
        sum_lat = 0
        sum_lon = 0
        area = 0
        locale_lat = []
        locale_lon = []

        for point in self.nodes:
            locale_lat.append((point.lat - self.nodes[0].lat) * EARTH_RADIUS * math.pi / 180)
            locale_lon.append((point.lon - self.nodes[0].lon) * EARTH_RADIUS * math.pi / 180)

        for i_node in range(self.node_count - 1):
            next_point_distance = (
                    locale_lat[i_node] * locale_lon[i_node + 1] - locale_lat[i_node + 1] * locale_lon[i_node])
            area = area + 0.5 * next_point_distance
            computed_latitude = (
                    computed_latitude + (locale_lat[i_node] + locale_lat[i_node + 1]) * next_point_distance)
            computed_longitude = (
                    computed_longitude + (locale_lon[i_node] + locale_lon[i_node + 1]) * next_point_distance)

        if area == 0.0:
            self.area_issue = "YES"
            for point in self.nodes:
                sum_lat = sum_lat + point.lat
                sum_lon = sum_lon + point.lon
            latitude = sum_lat / self.node_count
            longitude = sum_lon / self.node_count
        else:
            latitude = self.nodes[0].lat + computed_latitude / (6 * area) * 180 / (math.pi * EARTH_RADIUS)
            longitude = self.nodes[0].lon + computed_longitude / (6 * area) * 180 / (math.pi * EARTH_RADIUS)
            self.area = area
        self.center = Point(self.bat_id, latitude, longitude)
        self.center.set_history([])

    def compute_width(self):
        """Calcul de la largeur approximative du batiment.

        Cette distance intervient ensuite dans la détermination
        du status du batiment. Si la distance mini est supérieure à cette
        largeur alors cela veut dire que le batiment est nouveau ou
        supprimé."""
        latitudes = [n.lat for n in self.nodes]
        longitudes = [n.lon for n in self.nodes]

        min_lat = min(latitudes)
        max_lat = max(latitudes)
        min_lon = min(longitudes)
        max_lon = max(longitudes)

        self.width = math.sqrt((max_lat - min_lat) ** 2 + (max_lon - min_lon) ** 2) * math.pi / 180 * EARTH_RADIUS

    def set_min_distance(self, min_distance):
        """Cette méthode permet de définir la distance mini comme étant celle
        passé en paramètre"""
        self.min_distance = float(min_distance)

    def set_close_building(self, build_id):
        """Cette méthode permet de définir que le batiment auquel elle est
        appliquée correspond au batiment passé en paramètre"""
        self.close_building_id = build_id

    def set_status(self, status):
        """Cette méthode défini le status du batiment."""
        self.status = status

    def set_role(self, value):
        """
        Cette méthode défini le role du batiment lorsqu'il appartient à
        une relation. Le role est soit "inner" soit "outer".
        """
        self.role = value

    def set_history(self, history: list):
        """
        Cette méthode défini dans une variable tous les éléments relatifs à
        l'historique dans osm : numéros de version, date de maj, dernier
        utilisateur ayant modifié le batiment, le changeset,etc...
        """
        log = logging.getLogger("set_history")
        self.history = history

    def export_bat(self):
        """Cette méthode défini une version xml du batiment, de ses noeuds
        et de ses éventuels tag dans le but d'être transcrit dans un fichier."""
        export = []
        res_export = ""
        if len(self.history) > 0:
            i_hist = 0
            way_hist = "  <way "
            while i_hist < len(self.history):
                way_hist = f'{way_hist}{self.history[i_hist]}="{self.history[i_hist + 1]}" '
                i_hist = i_hist + 2
            way_hist = f'{way_hist}>'

            export.append(way_hist)
        else:
            export.append(f'  <way id="{self.bat_id}" visible="true">')
        i_node = 0
        while i_node < self.node_count:
            export.append(f'    <nd ref="{self.nodes[i_node].node_id}" />')
            i_node = i_node + 1
        for i_tag in range(self.tag_count):
            export.append(f'    <tag k="{self.tag_keys[i_tag]}" v="{replace_quotes(self.tag_values[i_tag])}" />')
        export.append("  </way>")
        i_node = 0
        while i_node < self.node_count:
            self.nodes[i_node].to_xml()
            export.append(self.nodes[i_node].print_node)
            i_node = i_node + 1
        if self.multipolygone == "yes":
            # export des chemins intérieurs
            inner_way = ""
            for i_inner in range(len(self.inner_ways)):
                self.inner_ways[i_inner].export_bat()
                inner_way = inner_way + self.inner_ways[i_inner].print_bat
            export.append(inner_way)
            # export de la relation
            export.append(f'  <relation id="{self.relation_name}">')
            export.append('    <tag k="type" v="multipolygon"/>')
            export.append(f'    <member type="way" ref="{self.bat_id}" role="outer"/>')
            for ways in range(len(self.inner_ways)):
                export.append(f'    <member type="way" ref="{self.inner_ways[ways].bat_id}" role="inner"/>')
            export.append('  </relation>')
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
        """
        Cette méthode permet de copier les tag d'un batiment passé en
        paramètre au batiment auquelle elle est appliquée.
        Lorsque le batiment 'self' est détecté comme identique, la source est
        hérité du batiment 'other'. Par contre lorsque le batiment 'self' est
        détecté comme modifié, la source est mis à jour pour prendre la valeur
        du batiment 'other'.
        """
        if status == "IDENTIQUE":
            self.tag_count = other.tag_count
            self.tag_keys = other.tag_keys
            self.tag_values = other.tag_values
        elif status == "MODIFIE":
            if "source" in self.tag_keys:
                tag_source_save = self.tag_values[self.tag_keys.index("source")]
            else:
                tag_source_save = False

            self.tag_count = other.tag_count
            self.tag_keys = other.tag_keys
            self.tag_values = other.tag_values

            # if source existed, we don't want to override it
            if "source" in other.tag_keys and tag_source_save is not False:
                self.tag_values[self.tag_keys.index("source")] = tag_source_save

    def add_inner_way(self, other: str):
        """
        Cette méthode permet d'ajouter un batiment en tant que chemin intérieur
        pour la définition d'un multipolygone. L'objectif étant de se passer
        de la classe relation et de considérer les chemins intérieurs d'un
        multipolygone comme une dépendance du chemin extérieur.
        """
        self.inner_ways.append(other)

    def add_relation(self, name: str):
        """
        Cette méthode défini le numéro de la relation a créer lorsque le batiment
        est un multipolygone.
        """
        self.relation_name = name


def log_format(text: list, max_chars: int, split: str):
    """Cette fonction permet de générer une chaine de caractère formaté et
    de longueur constante à partir du tableau passé en paramètre"""
    result = ""

    for i_data in range(len(text)):
        text[i_data] = " " + text[i_data]
        chars_count = len(text[i_data])
        while chars_count < max_chars:
            text[i_data] = text[i_data] + " "
            chars_count = len(text[i_data])
        result = result + split + text[i_data]

    return result


def main():
    parser = argparse.ArgumentParser(
        prog="BatiOsm",
        description="Analyze two OSM files and prepare files to simplify imports and updates")
    parser.add_argument("source", help="OSM source file", type=str)
    parser.add_argument("buildings", help="File with Buildings, in general a cadastre export", type=str)
    parser.add_argument("prefix", help="Prefix for generated files", type=str)
    parser.add_argument("--debug", help="Enable debug", action='store_true')

    args = parser.parse_args()

    param = dict(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO)
    if args.debug:
        param['level'] = logging.DEBUG
    if sys.version_info >= (3, 8, 0):
        param['force'] = True
    logging.basicConfig(**param)

    log = logging.getLogger("main")
    log.info("Start")

    osm_file_current = args.source
    osm_file_future = args.buildings
    file_prefix = args.prefix

    base_path = os.getcwd()
    separation = "--------------------------------------------------------------------------------------------------------------------------------"

    tps1 = time.perf_counter()

    log.info("------------------------------------------------------------------")
    log.info("-                    Lecture des données                         -")
    log.info("------------------------------------------------------------------")

    # ------------------------------------------------------------------------
    # lecture des nouveaux batiments :
    # ------------------------------------------------------------------------
    log.info("lecture du fichier " + osm_file_future + "...")

    lat_min = 90.0
    lat_max = 0.0
    lon_min = 45.0
    lon_max = -45.0

    new_nodes = []
    new_id_nodes = []

    future_nodes_count = 0
    future_ways_count = 0

    utf8_xml_parser = lxml.etree.XMLParser(encoding="utf-8")
    new_bati_etree = lxml.etree.parse(osm_file_future, parser=utf8_xml_parser)
    new_bati_root = new_bati_etree.getroot()

    # lecture des noeuds
    for point in new_bati_root.iter("node"):
        attributes = []
        node_id = point.get("id")
        node_lat = float(point.get("lat"))
        node_lon = float(point.get("lon"))
        if node_lat < lat_min:
            lat_min = node_lat
        if node_lat > lat_max:
            lat_max = node_lat
        if node_lon < lon_min:
            lon_min = node_lon
        if node_lon > lon_max:
            lon_max = node_lon
        new_id_nodes.append(node_id)
        new_nodes.append(Point(node_id, node_lat, node_lon))
        info_nodes = point.attrib
        for i_key in range(len(info_nodes)):
            attributes.append(info_nodes.keys()[i_key])
            attributes.append(info_nodes.get(info_nodes.keys()[i_key]))
        new_nodes[future_nodes_count].set_history(attributes)
        future_nodes_count = future_nodes_count + 1

    nb_zone_lat = int((lat_max - lat_min) * (math.pi / 180 * EARTH_RADIUS) / (2 * MAX_DISTANCE)) - 1
    nb_zone_lon = int((lon_max - lon_min) * (math.pi / 180 * EARTH_RADIUS) / (2 * MAX_DISTANCE)) - 1
    nb_zone = min(nb_zone_lat, nb_zone_lon, 500, NB_ZONE_USER)
    delta_lat = (lat_max - lat_min) / nb_zone
    delta_lon = (lon_max - lon_min) / nb_zone

    new_bati = []
    for i in range(nb_zone):
        new_bati += [[]]
        for j in range(nb_zone):
            new_bati[i] += [[]]

    # lectures des batiments
    for way in new_bati_root.iter("way"):
        tab_nodes = []
        tab_key = []
        tab_value = []
        way_id = way.get("id")
        nbre_node = len(way.findall("./nd"))
        nbre_tag = len(way.findall("./tag"))
        for point in way.findall("./nd"):
            id_node = point.get("ref")
            tab_nodes.append(new_nodes[new_id_nodes.index(id_node)])
        for tag in way.findall("./tag"):
            tab_key.append(tag.get("k"))
            tab_value.append(tag.get("v"))
        batiment_lu = Building(
            way_id, nbre_node, tab_nodes, nbre_tag, tab_key, tab_value, 1000, 0.0, "UNKNOWN"
        )
        batiment_lu.compute_center()
        if batiment_lu.area_issue == "YES":
            log.info(f"  Attention, surface nulle obtenue pour le batiment :{batiment_lu.bat_id}")
        batiment_lu.compute_width()
        batiment_lu.set_history([])
        batiment_lu.set_close_building("")
        repere_latitude = int((batiment_lu.center.lat - lat_min) / delta_lat)
        repere_longitude = int((batiment_lu.center.lon - lon_min) / delta_lon)
        if repere_latitude > nb_zone - 1:
            repere_latitude = nb_zone - 1
        if repere_longitude > nb_zone - 1:
            repere_longitude = nb_zone - 1
        if repere_latitude < 0:
            repere_latitude = 0
        if repere_longitude < 0:
            repere_longitude = 0
        new_bati[repere_latitude][repere_longitude].append(batiment_lu)
        future_ways_count = future_ways_count + 1

    # lectures des relations
    outer_way = ""
    for relation in new_bati_root.iter("relation"):
        id_relation = relation.get("id")
        for member in relation.findall("./member"):
            id_membre = member.get("ref")
            role = member.get("role")
            for i_lat in range(nb_zone):
                for i_lon in range(nb_zone):
                    for i_bat in range(len(new_bati[i_lat][i_lon])):
                        if new_bati[i_lat][i_lon][i_bat].bat_id == id_membre:
                            if role == "outer":
                                outer_way = new_bati[i_lat][i_lon][i_bat]
                                outer_way.add_relation(id_relation)
                                outer_way.multipolygone = "yes"
                            else:
                                new_bati[i_lat][i_lon][i_bat].set_role("inner")
                                outer_way.addInner(new_bati[i_lat][i_lon][i_bat])

    log.info(f"  {future_nodes_count} noeuds répertoriés dans le fichier {osm_file_future}")
    log.info(f"  {future_ways_count} batiments répertoriés dans le fichier {osm_file_future}")

    # ------------------------------------------------------------------------
    # lecture des vieux batiments :
    # ------------------------------------------------------------------------
    log.info(f"lecture du fichier {osm_file_current}...")

    current_nodes = []
    current_nodes_ids = []

    current_nodes_count = 0
    current_ways_count = 0

    utf8_xml_parser = lxml.etree.XMLParser(encoding="utf-8")

    old_bati_etree = lxml.etree.parse(osm_file_current, parser=utf8_xml_parser)
    old_bati_root = old_bati_etree.getroot()

    # lecture des noeuds
    for point in old_bati_root.iter("node"):
        attributes = []
        node_id = point.get("id")
        node_lat = point.get("lat")
        node_lon = point.get("lon")
        current_nodes_ids.append(node_id)
        current_nodes.append(Point(node_id, node_lat, node_lon))
        info_nodes = point.attrib
        for i_key in range(len(info_nodes)):
            attributes.append(info_nodes.keys()[i_key])
            attributes.append(info_nodes.get(info_nodes.keys()[i_key]))
        current_nodes[current_nodes_count].set_history(attributes)
        current_nodes_count = current_nodes_count + 1

    old_bati = []
    for i in range(nb_zone):
        old_bati += [[]]
        for j in range(nb_zone):
            old_bati[i] += [[]]

    # lectures des batiments
    for way in old_bati_root.iter("way"):
        attributes = []
        tab_nodes = []
        tab_key = []
        tab_value = []
        way_id = way.get("id")
        info_way = way.attrib
        nbre_node = len(way.findall("./nd"))
        nbre_tag = len(way.findall("./tag"))
        for point in way.findall("./nd"):
            id_node = point.get("ref")
            tab_nodes.append(current_nodes[current_nodes_ids.index(id_node)])
        for tag in way.findall("./tag"):
            tab_key.append(tag.get("k"))
            tab_value.append(tag.get("v"))
        for i_key in range(len(info_way)):
            attributes.append(info_way.keys()[i_key])
            attributes.append(info_way.get(info_way.keys()[i_key]))
        batiment_lu = Building(
            way_id, nbre_node, tab_nodes, nbre_tag, tab_key, tab_value, 1000, 0.0, "UNKNOWN"
        )
        batiment_lu.compute_center()
        if batiment_lu.area_issue == "YES":
            log.info(f"  Attention, surface nulle obtenue pour le batiment :{batiment_lu.bat_id}")
        batiment_lu.compute_width()
        batiment_lu.set_history(attributes)
        batiment_lu.set_close_building("")
        repere_latitude = int((batiment_lu.center.lat - lat_min) / delta_lat)
        repere_longitude = int((batiment_lu.center.lon - lon_min) / delta_lon)
        if repere_latitude > nb_zone - 1:
            repere_latitude = nb_zone - 1
        if repere_longitude > nb_zone - 1:
            repere_longitude = nb_zone - 1
        if repere_latitude < 0:
            repere_latitude = 0
        if repere_longitude < 0:
            repere_longitude = 0
        old_bati[repere_latitude][repere_longitude].append(batiment_lu)
        current_ways_count = current_ways_count + 1

    # lectures des relations
    for relation in old_bati_root.iter("relation"):
        id_relation = relation.get("id")
        for member in relation.findall("./member"):
            id_membre = member.get("ref")
            role = member.get("role")
            for i_lat in range(nb_zone):
                for i_lon in range(nb_zone):
                    for i_bat in range(len(old_bati[i_lat][i_lon])):
                        if old_bati[i_lat][i_lon][i_bat].bat_id == id_membre:
                            if role == "outer":
                                outer_way = old_bati[i_lat][i_lon][i_bat]
                                outer_way.add_relation(id_relation)
                                outer_way.multipolygone = "yes"
                            else:
                                old_bati[i_lat][i_lon][i_bat].set_role("inner")
                                outer_way.addInner(old_bati[i_lat][i_lon][i_bat])

    tps2 = time.perf_counter()
    log.info(f' {current_nodes_count} noeuds répertoriés dans le fichier {osm_file_current}')
    log.info(f' {current_ways_count} batiments répertoriés dans le fichier {osm_file_current}')

    log.info("------------------------------------------------------------------")
    log.info(f'Temps de lecture des fichiers : {tps2 - tps1}')
    log.info("------------------------------------------------------------------")
    log.info("-  Recherche des similitudes et des différences entre batiments  -")
    log.info(f'-  NB_ZONE a été calculé à : {nb_zone}')
    log.info("------------------------------------------------------------------")
    # ------------------------------------------------------------------------------
    # calcul des distances mini entre chaque anciens batiments
    # pour chaque batiment anciens (resp. nouveau) on détermine la distance
    # la plus petite avec tous les nouveaux batiments (resp. anciens)
    # ------------------------------------------------------------------------------
    #

    nb_bat_traite = 0
    nb_comparaison = 0
    for i_lat in range(nb_zone):
        for i_lon in range(nb_zone):
            lat_inf = max(i_lat - 1, 0)
            lon_inf = max(i_lon - 1, 0)
            lat_sup = min(i_lat + 1, nb_zone - 1) + 1
            lon_sup = min(i_lon + 1, nb_zone - 1) + 1
            for i_bat in range(len(old_bati[i_lat][i_lon])):
                if old_bati[i_lat][i_lon][i_bat].role == "outer":
                    nb_bat_traite = nb_bat_traite + 1
                    avancement = float(nb_bat_traite) / (current_ways_count + future_ways_count) * 100.0
                    sys.stdout.write(f'Calcul en cours : {int(avancement)} % {chr(13)}')
                    for n_lat in range(lat_inf, lat_sup):
                        for n_lon in range(lon_inf, lon_sup):
                            for n_bat in range(len(new_bati[n_lat][n_lon])):
                                if new_bati[n_lat][n_lon][n_bat].role == "outer":
                                    distance = old_bati[i_lat][i_lon][
                                        i_bat
                                    ].center.distance(new_bati[n_lat][n_lon][n_bat].center)
                                    nb_comparaison = nb_comparaison + 1
                                    if old_bati[i_lat][i_lon][i_bat].min_distance > distance:
                                        old_bati[i_lat][i_lon][i_bat].set_min_distance(distance)
                                        old_bati[i_lat][i_lon][i_bat].set_close_building(
                                            new_bati[n_lat][n_lon][n_bat].bat_id
                                        )

    for i_lat in range(nb_zone):
        for i_lon in range(nb_zone):
            lat_inf = max(i_lat - 1, 0)
            lon_inf = max(i_lon - 1, 0)
            lat_sup = min(i_lat + 1, nb_zone - 1) + 1
            lon_sup = min(i_lon + 1, nb_zone - 1) + 1
            for i_bat in range(len(new_bati[i_lat][i_lon])):
                if new_bati[i_lat][i_lon][i_bat].role == "outer":
                    nb_bat_traite = nb_bat_traite + 1
                    avancement = (
                            float(nb_bat_traite) / (current_ways_count + future_ways_count) * 100.0
                    )
                    sys.stdout.write(f'Calcul en cours : {int(avancement)} % {chr(13)}')
                    for o_lat in range(lat_inf, lat_sup):
                        for o_lon in range(lon_inf, lon_sup):
                            for o_bat in range(len(old_bati[o_lat][o_lon])):
                                if old_bati[o_lat][o_lon][o_bat].role == "outer":
                                    distance = new_bati[i_lat][i_lon][
                                        i_bat
                                    ].center.distance(old_bati[o_lat][o_lon][o_bat].center)
                                    nb_comparaison = nb_comparaison + 1
                                    if new_bati[i_lat][i_lon][i_bat].min_distance > distance:
                                        new_bati[i_lat][i_lon][i_bat].set_min_distance(distance)
                                        new_bati[i_lat][i_lon][i_bat].set_close_building(
                                            old_bati[o_lat][o_lon][o_bat].bat_id
                                        )
                                        if distance < MIN_DISTANCE:
                                            new_bati[i_lat][i_lon][i_bat].copy_tag(
                                                old_bati[o_lat][o_lon][o_bat], "IDENTIQUE"
                                            )
                                        elif (
                                                MIN_DISTANCE < distance < MAX_DISTANCE
                                        ):
                                            new_bati[i_lat][i_lon][i_bat].copy_tag(
                                                old_bati[o_lat][o_lon][o_bat], "MODIFIE"
                                            )
    # ------------------------------------------------------------------------
    # Classement des batiments :
    #  - dist_mini < BORNE_INF_MODIF : identique
    #  - BORNE_INF_MODIF < dist_mini < BORNE_SUP_MODIF : modifié
    #  - dist_mini > BORNE_SUP_MODIF : nouveau ou supprimé
    #  - dist_mini > largeur : nouveau ou supprimé
    # ------------------------------------------------------------------------
    for i_lat in range(nb_zone):
        for i_lon in range(nb_zone):
            # Classement des anciens batiments
            for i_bat in range(len(old_bati[i_lat][i_lon])):
                if old_bati[i_lat][i_lon][i_bat].role == "outer":
                    if old_bati[i_lat][i_lon][i_bat].min_distance > MAX_DISTANCE:
                        old_bati[i_lat][i_lon][i_bat].set_status("SUPPRIME")
                    if (
                            old_bati[i_lat][i_lon][i_bat].min_distance
                            > old_bati[i_lat][i_lon][i_bat].width
                    ):
                        old_bati[i_lat][i_lon][i_bat].set_status("SUPPRIME")
            # Classement des nouveaux batiments
            for i_bat in range(len(new_bati[i_lat][i_lon])):
                if new_bati[i_lat][i_lon][i_bat].role == "outer":
                    if new_bati[i_lat][i_lon][i_bat].min_distance < MIN_DISTANCE:
                        new_bati[i_lat][i_lon][i_bat].set_status("IDENTIQUE")
                    elif (
                            MIN_DISTANCE < new_bati[i_lat][i_lon][i_bat].min_distance < MAX_DISTANCE
                    ):
                        new_bati[i_lat][i_lon][i_bat].set_status("MODIFIE")
                    elif new_bati[i_lat][i_lon][i_bat].min_distance > MAX_DISTANCE:
                        new_bati[i_lat][i_lon][i_bat].set_status("NOUVEAU")
                    if (
                            new_bati[i_lat][i_lon][i_bat].min_distance
                            > new_bati[i_lat][i_lon][i_bat].width
                    ):
                        new_bati[i_lat][i_lon][i_bat].set_status("NOUVEAU")

    nb_bat_new = 0
    nb_bat_mod = 0
    nb_bat_del = 0
    nb_bat_no_mod = 0

    # Comptage des batiment de chaque catégorie.
    for i_lat in range(nb_zone):
        for i_lon in range(nb_zone):
            for i_bat in range(len(old_bati[i_lat][i_lon])):
                if old_bati[i_lat][i_lon][i_bat].role == "outer":
                    if old_bati[i_lat][i_lon][i_bat].status == "SUPPRIME":
                        nb_bat_del = nb_bat_del + 1
            for i_bat in range(len(new_bati[i_lat][i_lon])):
                if new_bati[i_lat][i_lon][i_bat].role == "outer":
                    if new_bati[i_lat][i_lon][i_bat].status == "IDENTIQUE":
                        nb_bat_no_mod = nb_bat_no_mod + 1
                    elif new_bati[i_lat][i_lon][i_bat].status == "MODIFIE":
                        nb_bat_mod = nb_bat_mod + 1
                    elif new_bati[i_lat][i_lon][i_bat].status == "NOUVEAU":
                        nb_bat_new = nb_bat_new + 1

    # Vérification de la cohérence des résultats. On chercher à vérifier que :
    # nb_bat_apres = nb_bat_avant + nouveaux - supprimés
    # si l'équation n'est pas vérifié et que la zone compte des batiments modifiés
    # suffisant pour rétablir l'équilibre, alors on déclare les batiments modifiés
    # comme nouveaux sinon on affiche un warning
    warning_equilibre = ["Erreur d'équilibre : nb_bat_apres <> nb_bat_avant + nouveaux - supprimés"]
    for i_lat in range(nb_zone):
        for i_lon in range(nb_zone):
            nb_nouveaux = 0
            nb_supprimes = 0
            nb_modifies = 0
            nb_identiques = 0
            nb_innner = 0
            nb_bat_apres = len(new_bati[i_lat][i_lon])
            nb_bat_avant = len(old_bati[i_lat][i_lon])
            for i_bat in range(len(old_bati[i_lat][i_lon])):
                if old_bati[i_lat][i_lon][i_bat].status == "SUPPRIME":
                    nb_supprimes = nb_supprimes + 1
            for i_bat in range(len(new_bati[i_lat][i_lon])):
                if new_bati[i_lat][i_lon][i_bat].status == "NOUVEAU":
                    nb_nouveaux = nb_nouveaux + 1
                elif new_bati[i_lat][i_lon][i_bat].status == "MODIFIE":
                    nb_modifies = nb_modifies + 1
                elif new_bati[i_lat][i_lon][i_bat].status == "IDENTIQUE":
                    nb_identiques = nb_identiques + 1
                elif new_bati[i_lat][i_lon][i_bat].role == "inner":
                    nb_innner = nb_innner + 1
            if nb_bat_apres != nb_bat_avant + nb_nouveaux - nb_supprimes:
                if nb_bat_apres == nb_bat_avant + nb_nouveaux + nb_modifies - nb_supprimes:
                    for i_bat in range(len(new_bati[i_lat][i_lon])):
                        if new_bati[i_lat][i_lon][i_bat].status == "MODIFIE":
                            new_bati[i_lat][i_lon][i_bat].set_status("NOUVEAU")
                else:
                    warning_equilibre.append(f"Erreur d'équilibre pour la zone i_lat / i_lon {i_lat}/{i_lon}")
                    warning_equilibre.append(
                        f"   Avant : {nb_bat_avant}   Après : {nb_bat_apres}   Nouveaux : {nb_nouveaux}   Supprimés : {nb_supprimes}   Modifiés : {nb_modifies}")

    nb_bat_new = 0
    nb_bat_mod = 0
    nb_bat_del = 0
    nb_bat_no_mod = 0

    # Comptage des batiment de chaque catégorie.
    for i_lat in range(nb_zone):
        for i_lon in range(nb_zone):
            for i_bat in range(len(old_bati[i_lat][i_lon])):
                if old_bati[i_lat][i_lon][i_bat].role == "outer":
                    if old_bati[i_lat][i_lon][i_bat].status == "SUPPRIME":
                        nb_bat_del = nb_bat_del + 1
            for i_bat in range(len(new_bati[i_lat][i_lon])):
                if new_bati[i_lat][i_lon][i_bat].role == "outer":
                    if new_bati[i_lat][i_lon][i_bat].status == "IDENTIQUE":
                        nb_bat_no_mod = nb_bat_no_mod + 1
                    elif new_bati[i_lat][i_lon][i_bat].status == "MODIFIE":
                        nb_bat_mod = nb_bat_mod + 1
                    elif new_bati[i_lat][i_lon][i_bat].status == "NOUVEAU":
                        nb_bat_new = nb_bat_new + 1

    log.info("------------------------------------------------------------------")
    log.info("-                    Création des fichiers                       -")
    log.info("------------------------------------------------------------------")
    log.info(f"{nb_comparaison} comparaisons entre batiments effectuées")
    log.info(f"{nb_bat_no_mod} batiments identiques")
    log.info(f"{nb_bat_mod} batiments modifiés")
    log.info(f"{nb_bat_new} batiments nouveaux")
    log.info(f"{nb_bat_del} batiments supprimés")

    tps3 = time.perf_counter()

    file_log = open(os.path.join(base_path, f'{file_prefix}_log.txt'), "w")
    file_log.write("Rappel des input : \n")
    file_log.write(f"    BORNE_INF_MODIF : {MIN_DISTANCE}\n")
    file_log.write(f"    BORNE_SUP_MODIF : {MAX_DISTANCE}\n")
    file_log.write(f"    NB_ZONE : {nb_zone}\n")
    file_log.write(f"Le fichier {osm_file_current} contient :\n")
    file_log.write(f"    - {current_nodes_count} noeuds\n")
    file_log.write(f"    - {current_ways_count} batiments\n")
    file_log.write(f"Le fichier {osm_file_future} contient :\n")
    file_log.write(f"    - {future_nodes_count} noeuds\n")
    file_log.write(f"    - {future_ways_count} batiments\n")
    file_log.write("Résultat de la comparaison :\n")
    file_log.write(f"    Nombre de comparaisons effectuées : {nb_comparaison}\n")
    file_log.write(f"    Nombre de batiments identiques trouvés : {nb_bat_no_mod}\n")
    file_log.write(f"    Nombre de batiments modifiés trouvés : {nb_bat_mod}\n")
    file_log.write(f"    Nombre de batiments nouveaux trouvés : {nb_bat_new}\n")
    file_log.write(f"    Nombre de batiments supprimés trouvés : {nb_bat_del}\n")
    file_log.write(f"Temps de lecture des fichiers : {tps2 - tps1} secondes.\n"
                   )
    file_log.write(f"Temps de calcul : {tps3 - tps2} secondes.\n")
    file_log.write(f"Temps d'execution totale : {tps3 - tps1} secondes.\n")
    file_log.write(f"{separation}\n")

    for i_warn in range(len(warning_equilibre)):
        file_log.write(f"{warning_equilibre[i_warn]}\n")
    file_log.write(f"{separation}\n")
    file_log.write(f"Récapitulatif des batiments issus de {osm_file_future}\n")
    file_log.write(f"{separation}\n")

    for i_lat in range(nb_zone):
        for i_lon in range(nb_zone):
            for i_bat in range(len(new_bati[i_lat][i_lon])):
                resultat = [
                    new_bati[i_lat][i_lon][i_bat].bat_id,
                    new_bati[i_lat][i_lon][i_bat].status,
                    str(round(new_bati[i_lat][i_lon][i_bat].min_distance, 9)),
                    str(round(new_bati[i_lat][i_lon][i_bat].center.lat, 7)),
                    str(round(new_bati[i_lat][i_lon][i_bat].center.lon, 7)),
                    str(round(new_bati[i_lat][i_lon][i_bat].area, 1)),
                ]
                file_log.write(log_format(resultat, 16, "|") + "\n")
    file_log.write(f"{separation}\n")
    file_log.write(f"Récapitulatif des batiments issus de {osm_file_current}\n")
    file_log.write(f"{separation}\n")

    for i_lat in range(nb_zone):
        for i_lon in range(nb_zone):
            for i_bat in range(len(old_bati[i_lat][i_lon])):
                resultat = [
                    old_bati[i_lat][i_lon][i_bat].bat_id,
                    old_bati[i_lat][i_lon][i_bat].status,
                    str(round(old_bati[i_lat][i_lon][i_bat].min_distance, 9)),
                    str(round(old_bati[i_lat][i_lon][i_bat].center.lat, 7)),
                    str(round(old_bati[i_lat][i_lon][i_bat].center.lon, 7)),
                    str(round(old_bati[i_lat][i_lon][i_bat].area, 1)),
                ]
                file_log.write(log_format(resultat, 16, "|") + "\n")
    file_log.write(f"{separation}\n")

    nom_file_no_mod = f"{file_prefix}_unModified.osm"
    file_no_mod = open(os.path.join(base_path, nom_file_no_mod), "w")
    file_no_mod.write('<?xml version="1.0" encoding="UTF-8"?>' + "\n")
    file_no_mod.write('<osm version="0.6" upload="true" generator="JOSM">' + "\n")

    nom_file_mod = f"{file_prefix}_mod_1_a_{nb_bat_mod}.osm"
    file_mod = open(os.path.join(base_path, nom_file_mod), "w")
    file_mod.write('<?xml version="1.0" encoding="UTF-8"?>' + "\n")
    file_mod.write('<osm version="0.6" upload="true" generator="JOSM">' + "\n")

    nom_file_new = f"{file_prefix}_new_1_a_{nb_bat_new}.osm"
    file_new = open(os.path.join(base_path, nom_file_new), "w")
    file_new.write('<?xml version="1.0" encoding="UTF-8"?>' + "\n")
    file_new.write('<osm version="0.6" upload="true" generator="JOSM">' + "\n")

    nom_file_del = f"{file_prefix}_sup_1_a_{nb_bat_del}.osm"
    file_del = open(os.path.join(base_path, nom_file_del), "w")
    file_del.write('<?xml version="1.0" encoding="UTF-8"?>' + "\n")
    file_del.write('<osm version="0.6" upload="true" generator="JOSM">' + "\n")

    # Ecriture des nouveaux batiments
    headers = ["STAT", "ANCIEN BAT.", "TOL", "NOUVEAU BAT.", "fichier"]
    file_log.write("NOUVEAUX BATIMENTS" + "\n")
    file_log.write(separation + "\n")
    file_log.write(log_format(headers, 16, "|") + "\n")
    file_log.write(separation + "\n")
    for i_lat in range(nb_zone):
        for i_lon in range(nb_zone):
            for i_bat in range(len(new_bati[i_lat][i_lon])):
                if new_bati[i_lat][i_lon][i_bat].role == "outer":
                    new_bati[i_lat][i_lon][i_bat].export_bat()
                    if new_bati[i_lat][i_lon][i_bat].status == "IDENTIQUE":
                        file_no_mod.write((new_bati[i_lat][i_lon][i_bat].print_bat + "\n"))
                        line = [
                            "IDENTIQUE",
                            new_bati[i_lat][i_lon][i_bat].bat_id,
                            str(round(new_bati[i_lat][i_lon][i_bat].min_distance, 9)),
                            new_bati[i_lat][i_lon][i_bat].close_building_id,
                            nom_file_no_mod,
                        ]
                        file_log.write(log_format(line, 16, "|") + "\n")
                    elif new_bati[i_lat][i_lon][i_bat].status == "MODIFIE":
                        file_mod.write((new_bati[i_lat][i_lon][i_bat].print_bat + "\n"))
                        line = [
                            "MODIFIE",
                            new_bati[i_lat][i_lon][i_bat].bat_id,
                            str(round(new_bati[i_lat][i_lon][i_bat].min_distance, 9)),
                            new_bati[i_lat][i_lon][i_bat].close_building_id,
                            nom_file_mod,
                        ]
                        file_log.write(log_format(line, 16, "|") + "\n")
                    elif new_bati[i_lat][i_lon][i_bat].status == "NOUVEAU":
                        file_new.write((new_bati[i_lat][i_lon][i_bat].print_bat + "\n"))
                        line = [
                            "NOUVEAU",
                            new_bati[i_lat][i_lon][i_bat].bat_id,
                            str(round(new_bati[i_lat][i_lon][i_bat].min_distance, 9)),
                            new_bati[i_lat][i_lon][i_bat].close_building_id,
                            nom_file_new,
                        ]
                        file_log.write(log_format(line, 16, "|") + "\n")

    # Ecriture des anciens batiments (seulement ceux qui sont supprimés)
    headers = ["STAT", "ANCIEN BAT.", "TOL", "fichier"]
    file_log.write(separation + "\n")
    file_log.write("ANCIENS BATIMENTS" + "\n")
    file_log.write(separation + "\n")
    file_log.write(log_format(headers, 16, "|") + "\n")
    file_log.write(separation + "\n")
    for i_lat in range(nb_zone):
        for i_lon in range(nb_zone):
            for i_bat in range(len(old_bati[i_lat][i_lon])):
                if old_bati[i_lat][i_lon][i_bat].role == "outer":
                    if old_bati[i_lat][i_lon][i_bat].status == "SUPPRIME":
                        old_bati[i_lat][i_lon][i_bat].export_bat()
                        file_del.write((old_bati[i_lat][i_lon][i_bat].print_bat + "\n"))
                        line = [
                            "SUPPRIME",
                            old_bati[i_lat][i_lon][i_bat].bat_id,
                            str(round(old_bati[i_lat][i_lon][i_bat].min_distance, 9)),
                            nom_file_del,
                        ]
                        file_log.write(log_format(line, 16, "|") + "\n")
    # cloture des fichiers osm
    file_del.write("</osm>")
    file_del.close()
    file_no_mod.write("</osm>")
    file_no_mod.close()
    file_mod.write("</osm>")
    file_mod.close()
    file_new.write("</osm>")
    file_new.close()
    file_log.write(separation + "\n")
    # Enregistrement de la 'densité' de batiments.
    file_log.write(f"Densité de batiments issus du fichier {osm_file_current}\n")
    file_log.write(separation + "\n")
    headers = ["", ""]
    i_zone = 0
    while i_zone < nb_zone:
        headers.append(str(i_zone))
        i_zone = i_zone + 1
    file_log.write(log_format(headers, 4, " ") + "\n")
    for i_lat in range(nb_zone):
        densite_old = [str(i_lat), "|"]
        for i_lon in range(nb_zone):
            densite_old.append(str(len(old_bati[i_lat][i_lon])))
        file_log.write(log_format(densite_old, 4, " ") + "\n")

    file_log.write(separation + "\n")
    file_log.write(f"Densité de batiments issus du fichier {osm_file_future}\n")
    file_log.write(separation + "\n")
    file_log.write(log_format(headers, 4, " ") + "\n")
    for i_lat in range(nb_zone):
        densite_new = [str(i_lat), "|"]
        for i_lon in range(nb_zone):
            densite_new.append(str(len(new_bati[i_lat][i_lon])))
        file_log.write(log_format(densite_new, 4, " ") + "\n")
    file_log.close()

    if args.debug:
        # sauvegarde dans un fichier des zones définies
        debug_file_name = file_prefix + "_debug.osm"
        node_id = 100000
        way_id = 1
        file_debug = open(os.path.join(base_path, debug_file_name), "w")
        file_debug.write('<?xml version="1.0" encoding="UTF-8"?>' + "\n")
        file_debug.write('<osm version="0.6" upload="true" generator="JOSM">' + "\n")
        for i_lat in range(nb_zone):
            lat = lat_min + i_lat * delta_lat
            node1 = f'  <node id="-{node_id}" action="modify" visible="true" lat="{lat}" lon="{lon_min}" />'
            node2 = f'  <node id="-{node_id + 1}" action="modify" visible="true" lat="{lat}" lon="{lon_max}" />'
            way1 = f'  <way id="-{way_id}" action="modify"' + ' visible="true">'
            way2 = f'    <nd ref="-{node_id}" />'
            way3 = f'    <nd ref="-{node_id + 1}" />'
            way4 = f"  </way>"
            file_debug.write(node1 + "\n")
            file_debug.write(node2 + "\n")
            file_debug.write(way1 + "\n")
            file_debug.write(way2 + "\n")
            file_debug.write(way3 + "\n")
            file_debug.write(way4 + "\n")
            node_id = node_id + 2
            way_id = way_id + 1
        for i_lon in range(nb_zone):
            lon = lon_min + i_lon * delta_lon
            node1 = f'  <node id="-{node_id}" action="modify" visible="true" lat="{lat_min}" lon="{lon}" />'
            node2 = f'  <node id="-{node_id + 1}" action="modify" visible="true" lat="{lat_max}" lon="{lon}" />'
            way1 = f'  <way id="-{way_id}" action="modify"' + ' visible="true">'
            way2 = f'    <nd ref="-{node_id}" />'
            way3 = f'    <nd ref="-{node_id + 1}" />'
            way4 = "  </way>"
            file_debug.write(node1 + "\n")
            file_debug.write(node2 + "\n")
            file_debug.write(way1 + "\n")
            file_debug.write(way2 + "\n")
            file_debug.write(way3 + "\n")
            file_debug.write(way4 + "\n")
            node_id = node_id + 2
            way_id = way_id + 1
        # Transcription des points au cdg des batiments
        for i_lat in range(nb_zone):
            for i_lon in range(nb_zone):
                for i_bat in range(len(new_bati[i_lat][i_lon])):
                    new_bati[i_lat][i_lon][i_bat].center.to_xml()
                    file_debug.write(f'{new_bati[i_lat][i_lon][i_bat].center.print_node}\n')
        file_debug.write("</osm>\n")
        file_debug.close()

    log.info(f"Durée du calcul : {tps3 - tps2}")
    log.info(f"Durée totale : {tps3 - tps1}")
    log.info("------------------------------------------------------------------")
    log.info("-                       FIN DU PROCESS                           -")
    log.info("------------------------------------------------------------------")


if __name__ == "__main__":
    main()
