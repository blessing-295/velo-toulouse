/* =====================================================================
   VélôToulouse - Vue d'entraînement du modèle (horizon 30 minutes)

   Une ligne = une station à un instant de collecte, avec :
     - ce qu'on sait à cet instant (mesure H1) : heure, jour, station,
       vélos disponibles, taux de remplissage ;
     - la réponse à prédire : l'état de la station 30 minutes plus tard
       (mesure H2), calculé à partir de son taux de remplissage.

   Méthode :
     - la table historique_velos est jointe à elle-même (H1 = maintenant,
       H2 = plus tard) sur la même station ;
     - H2 est cherchée entre 25 et 35 minutes après H1 (DATEADD), pour
       tolérer les petits décalages de la collecte toutes les 15 minutes ;
     - les dates sont converties de l'heure UTC à l'heure de Paris.

   Seuils de l'état dans 30 min (taux = vélos disponibles / capacité) :
     < 0,15  -> 'Vide'
     > 0,85  -> 'Pleine'
     sinon   -> 'Normale'

   Les colonnes de H2 (vélos, taux et date dans 30 min) ne sont pas
   exposées : le modèle lirait directement la réponse au lieu de
   l'apprendre (fuite de données).

   Une vue ne stocke rien et ne modifie pas les tables : elle enregistre
   la requête sous un nom et se recalcule à chaque lecture. Les nouvelles
   collectes y apparaissent donc automatiquement, côté Python comme côté
   Power BI.
   ===================================================================== */

USE velo_toulouse;
GO

CREATE OR ALTER VIEW dbo.vue_entrainement_30min AS
SELECT
    -- Moment de la mesure, en heure de Paris
    DATEPART(HOUR,
        CAST(H1.date_historisation AT TIME ZONE 'UTC' AT TIME ZONE 'Romance Standard Time' AS DATETIME2)
    ) AS heure_locale,
    CAST(H1.date_historisation AT TIME ZONE 'UTC' AT TIME ZONE 'Romance Standard Time' AS DATETIME2)
        AS Date_locale,
    -- Le numéro du jour dépend du réglage DATEFIRST du serveur
    DATEPART(WEEKDAY,
        CAST(H1.date_historisation AT TIME ZONE 'UTC' AT TIME ZONE 'Romance Standard Time' AS DATETIME2)
    ) AS jour_semaine,

    -- Situation de la station au moment de la mesure
    H1.station_id,
    H1.date_historisation,
    H1.velos_disponibles,
    H1.velos_disponibles / CAST(S.capacity AS FLOAT) AS taux_de_remplissage_actuel,
    S.capacity,

    -- Réponse à prédire : état de la station 30 minutes plus tard
    CASE
        WHEN H2.velos_disponibles / CAST(S.capacity AS FLOAT) < 0.15 THEN 'Vide'
        WHEN H2.velos_disponibles / CAST(S.capacity AS FLOAT) > 0.85 THEN 'Pleine'
        ELSE 'Normale'
    END AS etat_dans_30_min

FROM dbo.historique_velos AS H1
INNER JOIN dbo.historique_velos AS H2
    ON H2.station_id = H1.station_id
INNER JOIN dbo.stations AS S
    ON S.station_id = H1.station_id
WHERE H2.date_historisation BETWEEN DATEADD(MINUTE, 25, H1.date_historisation)
                                AND DATEADD(MINUTE, 35, H1.date_historisation)
  AND S.capacity > 0;   -- 12 stations sans capacité connue sont exclues
GO