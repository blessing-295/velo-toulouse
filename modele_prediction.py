import pandas as pd
import pyodbc
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import accuracy_score , classification_report



# ---------------------------------------------------------------
# 1. Connexion à SQL Server et chargement des données
# ---------------------------------------------------------------

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


connexion = connecter()
print("Connexion réussie")

# La vue contient une ligne par station et par passage de la collecte,
# avec l'état de la station 30 minutes plus tard (colonne à prédire).
requete = "SELECT * FROM dbo.vue_entrainement_30min"
df = pd.read_sql(requete, connexion)
connexion.close()


# ---------------------------------------------------------------
# 2. Premier coup d'œil aux données
# ---------------------------------------------------------------

print(df.shape)    # nombre de lignes et de colonnes
print(df.dtypes)   # type de chaque colonne
print(df.head())   # 5 premières lignes

# Part de chaque état dans 30 min (Normale / Vide / Pleine).
# normalize=True donne des proportions au lieu de nombres de lignes.
print(df["etat_dans_30_min"].value_counts(normalize=True))

# Période couverte par la collecte
print(df["Date_locale"].min())
print(df["Date_locale"].max())
print(df["Date_locale"].nunique())   # nombre de passages de la collecte


# ---------------------------------------------------------------
# 3. Entrées (X) et réponse à prédire (y)
# ---------------------------------------------------------------

# Colonnes retirées des entrées :
#  - Date_locale et date_historisation : dates précises qui ne reviendront pas,
#    l'heure et le jour sont déjà dans heure_locale et jour_semaine
#  - capacity : se déduit de velos_disponibles et du taux de remplissage
X = df[["heure_locale", "jour_semaine", "station_id",
        "velos_disponibles", "taux_de_remplissage_actuel"]]
y = df["etat_dans_30_min"]


# ---------------------------------------------------------------
# 4. Séparation entraînement / test dans le temps
# ---------------------------------------------------------------

# On apprend sur le passé et on teste sur la suite, comme en situation réelle.
# Un découpage au hasard mélangerait des moments presque identiques
# entre les deux jeux et donnerait un score trop optimiste.
avant_coupure = df["Date_locale"] < "2026-10-28"
print(avant_coupure.mean())   # part des lignes avant le 28/10 (environ 70 %)

X_train = X[avant_coupure]
y_train = y[avant_coupure]
X_test = X[~avant_coupure]    # ~ : toutes les lignes à partir du 28/10
y_test = y[~avant_coupure]

print(X_train.shape, y_train.shape)
print(X_test.shape, y_test.shape)


# ---------------------------------------------------------------
# 5. Modèle : arbre de décision
# ---------------------------------------------------------------

# max_depth=5 : 5 questions au plus à la suite, pour éviter que l'arbre
# apprenne par cœur les cas particuliers (surapprentissage).
# random_state=42 : même arbre à chaque exécution.
modele = DecisionTreeClassifier(max_depth=5, random_state=42)
modele.fit(X_train, y_train)
print("Modèle entraîné")

# ---------------------------------------------------------------
# 6. Prédictions sur la période de test
# ---------------------------------------------------------------
 
# Le modèle ne reçoit que les entrées : il ne voit jamais y_test.
y_pred = modele.predict(X_test)
print(y_pred[:10])   # aperçu des 10 premières prédictions
 
 
# ---------------------------------------------------------------
# 7. Évaluation
# ---------------------------------------------------------------
 
# Point de comparaison : répondre toujours "Normale" donne environ 63 %
# sur la période de test. Le modèle doit faire nettement mieux.
print(accuracy_score(y_test, y_pred))
 
# Détail par classe. Le rappel de "Vide" et de "Pleine" est le chiffre
# le plus utile : la part des stations vides ou pleines que le modèle
# a réellement vu venir.
print(classification_report(y_test, y_pred))
 



















