# BatiOsm
Python tool to help for building update in french area of OpenStreetMap

[See here for a detailed user guide in french](https://forum.openstreetmap.fr/viewtopic.php?f=5&t=1762)

## Usage

1) Export actual buildings present in OSM, for example with Overpass API

```
{{geocodeArea:Jurançon}}->.searchArea;
// gather results
(
  // query part for: “building=yes”
  node["building"="yes"](area.searchArea);
  way["building"="yes"](area.searchArea);
  relation["building"="yes"](area.searchArea);
);
// print results
out meta;
>;
out meta;
```
This export should be saved as osm file (for example with JOSM) : jurancon_as_is.osm

2) Get buildings extract from [french cadastre here](http://cadastre.openstreetmap.fr/)

For example : PB284-JURANCON-houses-simplifie.osm

3) Launch BatiOsm (you can change prefix with whatever you want):

```
python BatiOsm.py jurancon_as_is.osm PB284-JURANCON-houses-simplifie.osm prefix
```

4) What is produced ?

- prefix_unModified.osm : buildings that where not modified. They are common to both input files.
- prefix_mod_0_a_xxx.osm : buildings that where modified. (xxx is the number of modified buildings).
- prefix_sup_0_a_yyy.osm : buildings that where suppressed. (yyy is the number of suppressed buildings).
- prefix_new_0_a_zzz.osm : buildings that are new. (zzz is the number of new buildings).
- prefix_log.txt : log file
