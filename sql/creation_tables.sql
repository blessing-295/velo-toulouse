/* =====================================================================
   VélôToulouse - Création des tables

   Deux tables, reliées par station_id :
     - stations         : informations fixes sur chaque station
                          (nom, adresse, capacité, coordonnées) ;
     - historique_velos : une mesure par station et par collecte,
                          ajoutée toutes les 15 minutes par collecte.py.

   Ordre : stations d'abord, puisque historique_velos pointe vers elle
   par une clé étrangère.

   Chaque CREATE TABLE n'est exécuté que si la table n'existe pas encore :
   le script peut être relancé sans erreur et sans toucher aux données.
   ===================================================================== */

USE velo_toulouse;
GO

-- ---------------------------------------------------------------------
-- 1. stations : informations fixes (API open data, 466 stations)
-- ---------------------------------------------------------------------
IF OBJECT_ID('dbo.stations', 'U') IS NULL
CREATE TABLE dbo.stations (
    station_id      INT            PRIMARY KEY,
    name            NVARCHAR(200),
    capacity        INT,           -- nombre de bornes (inconnu pour 12 stations)
    last_updated    BIGINT,
    address         NVARCHAR(300),
    rental_methods  NVARCHAR(100),
    version         NVARCHAR(20),
    lat             FLOAT,
    lon             FLOAT,
    geopoint        NVARCHAR(MAX),
    data            NVARCHAR(MAX),
    ttl             INT
);
GO

-- ---------------------------------------------------------------------
-- 2. historique_velos : une mesure par station et par collecte
-- ---------------------------------------------------------------------
IF OBJECT_ID('dbo.historique_velos', 'U') IS NULL
CREATE TABLE dbo.historique_velos (
    id_enregistrement    INT IDENTITY(1,1) PRIMARY KEY,   -- numéroté automatiquement
    station_id           INT,
    velos_disponibles    INT,
    places_disponibles   INT,
    date_historisation   DATETIME2,   -- moment de la collecte (UTC)
    date_mesure_station  DATETIME2,   -- dernière mise à jour envoyée par la station
    velos_hors_service   INT,
    bornes_hors_service  INT,
    location_possible    BIT,         -- 1 = on peut louer un vélo
    depot_possible       BIT,         -- 1 = on peut rendre un vélo
    FOREIGN KEY (station_id) REFERENCES dbo.stations (station_id)
);
GO