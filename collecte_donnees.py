"""
VélôToulouse - collecte des disponibilités des stations
Chaque exécution prend une "photo" de toutes les stations et l'ajoute
dans la table historique_velos (SQL Server, base velo_toulouse).
"""

# 1. IMPORTATIONS
import json
from datetime import datetime, timedelta, timezone

import pyodbc
import requests


# 2. CONSTANTES (en majuscules par convention)
URL_STATIONS = ("https://data.toulouse-metropole.fr/api/explore/v2.1/catalog/datasets/"
                "velotoulouse-localisation-et-caracteristique-des-stations/records")
URL_MESURES = ("https://data.toulouse-metropole.fr/api/explore/v2.1/catalog/datasets/"
               "velotoulouse-disponibilite-temps-reel/records")


# 3. LES FONCTIONS (les recettes)

def connecter():
    """Ouvre la connexion Python -> SQL Server et la renvoie."""
    connexion = pyodbc.connect(
        "DRIVER={ODBC Driver 18 for SQL Server};"
        "SERVER=localhost;"
        "DATABASE=velo_toulouse;"
        "Trusted_Connection=yes;"       # connexion avec le compte Windows
        "TrustServerCertificate=yes;"   # accepte le certificat local
    )
    return connexion


def recuperer_records(url):
    """Récupère tous les enregistrements de l'API, par paquets de 100."""
    tous = []
    premiere = requests.get(url, params={"limit": 1}, timeout=10)
    premiere.raise_for_status()          # arrête le script si l'API répond mal
    total = premiere.json()["total_count"]
    for offset in range(0, total, 100):
        reponse = requests.get(url, params={"limit": 100, "offset": offset}, timeout=10)
        reponse.raise_for_status()
        tous.extend(reponse.json()["results"])
    return tous


def stations_existantes(curseur):
    """Renvoie l'ensemble (set) des station_id déjà présents en base."""
    curseur.execute("SELECT station_id FROM dbo.stations")
    return {ligne[0] for ligne in curseur.fetchall()}   # set : recherche instantanée


def inserer_nouvelles_stations(curseur, stations):
    """Ajoute dans dbo.stations les stations qui n'y sont pas encore."""
    existants = stations_existantes(curseur)
    nb_ajouts = 0
    for s in stations:
        id_station = int(s["station_id"])
        if id_station not in existants:
            capacite = int(s["capacity"]) if s["capacity"] is not None else None
            curseur.execute(
                "INSERT INTO dbo.stations (station_id, name, capacity, lat, lon) "
                "VALUES (?, ?, ?, ?, ?)",
                (id_station, s["name"], capacite, float(s["lat"]), float(s["lon"])))
            nb_ajouts += 1
    return nb_ajouts


def convertir_date(valeur):
    """Transforme last_reported en date UTC sans fuseau (format DATETIME2).
    Gère les formats possibles de l'API : nombre de secondes ou de
    millisecondes depuis 1970 (format Unix), ou texte ISO comme
    "2026-10-21T09:20:00Z". Renvoie None si la date est illisible,
    pour que la collecte ne s'arrête jamais à cause d'une seule station."""
    if valeur is None:
        return None
    try:
        if isinstance(valeur, str) and valeur.isdigit():
            valeur = int(valeur)
        if isinstance(valeur, (int, float)):
            if valeur > 100_000_000_000:      # 13 chiffres : millisecondes
                valeur = valeur / 1000
            return datetime(1970, 1, 1) + timedelta(seconds=valeur)
        date = datetime.fromisoformat(valeur.replace("Z", "+00:00"))
        return date.astimezone(timezone.utc).replace(tzinfo=None)
    except (ValueError, OverflowError, OSError):
        return None


# POURQUOI CETTE FONCTION ?
# Le jeu temps réel contient environ 3000 enregistrements pour 466 stations :
# une même station apparaît plusieurs fois avec la même mesure et la même date
# (vérifié sur la station 3 : 4 lignes identiques).
# Le dictionnaire garde UNE seule mesure par station : la clé est le station_id,
# donc une clé écrite plusieurs fois est simplement remplacée.
def mesures_uniques(mesures):
    """Garde une mesure par station : {station_id: {infos de la mesure}}."""
    uniques = {}
    for m in mesures:
        info = json.loads(m["data"])
        uniques[int(info["station_id"])] = {
            "velos": info["num_bikes_available"],
            "places": info["num_docks_available"],
            "date_station": convertir_date(info.get("last_reported")),
            "velos_hs": info.get("num_bikes_disabled"),
            "bornes_hs": info.get("num_docks_disabled"),
            "location": info.get("is_renting"),
            "depot": info.get("is_returning"),
        }
    return uniques


def inserer_mesures(curseur, uniques):
    """Ajoute une photo de toutes les stations dans dbo.historique_velos."""
    maintenant = datetime.now(timezone.utc).replace(tzinfo=None)   # heure UTC, sans fuseau
    existants = stations_existantes(curseur)
    nb_ajouts = 0
    for id_station, m in uniques.items():
        if id_station in existants:      # évite une erreur de clé étrangère
            curseur.execute(
                "INSERT INTO dbo.historique_velos "
                "(station_id, velos_disponibles, places_disponibles, date_historisation, "
                "date_mesure_station, velos_hors_service, bornes_hors_service, "
                "location_possible, depot_possible) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (id_station, m["velos"], m["places"], maintenant,
                 m["date_station"], m["velos_hs"], m["bornes_hs"],
                 m["location"], m["depot"]))
            nb_ajouts += 1
    return nb_ajouts


# 4. LE CHEF : appelle les recettes dans l'ordre
def main():
    connexion = connecter()
    curseur = connexion.cursor()
    try:
        stations = recuperer_records(URL_STATIONS)
        nb_stations = inserer_nouvelles_stations(curseur, stations)

        mesures = recuperer_records(URL_MESURES)
        uniques = mesures_uniques(mesures)
        nb_mesures = inserer_mesures(curseur, uniques)

        connexion.commit()
        print(f"{datetime.now():%Y-%m-%d %H:%M} - "
              f"{nb_stations} nouvelle(s) station(s), {nb_mesures} mesure(s) ajoutée(s)")
    finally:
        connexion.close()   # fermée même en cas d'erreur


# 5. On lance le chef seulement si ce fichier est exécuté directement
if __name__ == "__main__":
    main()
