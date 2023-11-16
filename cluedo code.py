# 22200623 Thérèse Le Dorh
# 22210577 Bill Yehouenou
# 22210075 Sarra Baghdadi

# Section 1 : les imports

import requests
import csv
import json
import datetime
from graphh import GraphHopper
import numpy as np

# configuration Graphhopper
cle_graphhopper = json.load(open("Projets/Cluedo/credentials.json", "r", encoding="utf-8"))["graphhopper"]["API_KEY"]
gh_client = GraphHopper(api_key=cle_graphhopper)

#Section 2 : Définition de fonctions

def import_messages(numero_suspect):
    reponse_twitter = requests.get("https://my-json-server.typicode.com/rtavenar/fake_api/twitter_posts", params=("author="+str(liste_suspects[numero_suspect]["IDENTIFIANT_TWITTER"]))).json()
    reponse_snapchat = requests.get("https://my-json-server.typicode.com/rtavenar/fake_api/snapchat_posts", params=("author="+str(liste_suspects[numero_suspect]["IDENTIFIANT_SNAPCHAT"]))).json()
    reponse = reponse_twitter + reponse_snapchat
    messages = []
    for dico in reponse: #nettoyage des données
        if "coordinates" in dico.keys() or "loc" in dico.keys():
            messages.append(dico)
    return messages

def date_messages(numero_suspect):
    date_messages =[]
    for message in import_messages(numero_suspect):
        date_du_msg = datetime.datetime.strptime(message['iso_date'], "%Y-%m-%dT%H:%M:%S")
        date_messages.append(date_du_msg)
    return date_messages

def temps_entre_msg_et_crime(numero_suspect):
    duree_entre_msg_et_crime =[]
    for date in date_messages(numero_suspect):
        duree = abs(date - date_crime).seconds
        duree_entre_msg_et_crime.append(duree)
            # print(f"date crime {date_crime}, date {date}, durée {duree}, durée entre msg et crime {duree_entre_msg_et_crime}")
    # print(f"suspect {numero_suspect} : duree message crime {duree_entre_msg_et_crime}")
    return duree_entre_msg_et_crime


def temps_trajet(latlong_du_crime, numero_suspect, moyen_transport):
    temps_trajets = []
    # print(f"import messages : {import_messages(numero_suspect)}")
    for message in import_messages(numero_suspect):
        if "coordinates" in message:
            temps_trajet = gh_client.duration([latlong_du_crime, message["coordinates"]], vehicle=moyen_transport, unit="s")
            # print(f"temps trajet indiv twitter {temps_trajet}")
            temps_trajets.append(temps_trajet)
        elif "loc" in message: 
            temps_trajet = gh_client.duration([latlong_du_crime, [message["loc"]["lat"],message["loc"]["lng"]]], vehicle=moyen_transport, unit="s")
            temps_trajets.append(temps_trajet)
            # print(f"temps trajet indiv snap {temps_trajet}")
    return temps_trajets

def duree_trajet_avec_coord(latlong_crime, numero_suspect, moyen_transport):
    duree = []
    trajet = []
    for i, elem in enumerate(temps_trajet(latlong_crime, numero_suspect, moyen_transport)):
        duree.append(temps_entre_msg_et_crime(numero_suspect)[i])
        trajet.append(elem)
    return np.asarray([duree, trajet])

def analyse_culpabilite(latlong_crime, numero_suspect):
    compteur = 0
    for moyen_de_transport in ["foot", "car", "bike"]: # test de chaque moyen de transport
        durees_numpy = duree_trajet_avec_coord(latlong_crime, numero_suspect, moyen_de_transport)
        # recuperation des durees entre envoi de message et crime, plus temps de trajet selon les coordonnees
        durees_numpy_pos = np.extract(durees_numpy[0]>=0, durees_numpy) # messages envoyes apres l'heure du crime
        durees_numpy_neg = np.extract(durees_numpy[0]<0, durees_numpy) # messages envoyes avant l'heure du crime
        if np.any(durees_numpy_pos) and np.any(durees_numpy_neg):
            min_duree_pos = np.argwhere(durees_numpy[0,:] == min(durees_numpy_pos))[0][0]
            max_duree_neg = np.argwhere(durees_numpy[0,:] == max(durees_numpy_neg))[0][0]
            durees = abs(np.array([min(durees_numpy_pos),max(durees_numpy_neg)])) # temps entre envoi du msg et crime
            trajets = np.array([durees_numpy[1,min_duree_pos],durees_numpy[1,max_duree_neg]]) # temps de trajet entre coordonnees msg et crime
        elif np.any(durees_numpy_neg) == False : # si pas de msg avec coordonnees envoyes avant le crime
            min_duree_pos = np.argwhere(durees_numpy[0,:] == min(durees_numpy_pos))[0][0]
            durees = abs(np.array([min(durees_numpy_pos)]))
            trajets = np.array([durees_numpy[1,min_duree_pos]])
        elif np.any(durees_numpy_pos) == False: # si pas de msg avec coordonnees envoyes apres le crime
            max_duree_neg = np.argwhere(durees_numpy[0,:] == max(durees_numpy_neg))[0][0]
            durees = abs(np.array([max(durees_numpy_neg)]))
            trajets = np.array([durees_numpy[1,max_duree_neg]])
        coupable_si_pos = np.subtract(durees, trajets)
        if np.sum(coupable_si_pos>0) > 0: # somme de 1 si la condition est True, soit si temps de trajet < duree entre msg et crime
            compteur += np.sum(coupable_si_pos>0) # si une chance d'avoir commis le crime avec un des moyens de transport, +1 au compteur
    if compteur > 0:
        return "coupable possible"
    else:
        return "innocent"

def association_suspect_possibilite(numero_suspect, latlong_crime):
    return {liste_suspects[numero_suspect]['PRENOM']+" "+liste_suspects[numero_suspect]['NOM'] : analyse_culpabilite(latlong_crime, numero_suspect)}

# Section 3 : Tests de fonctions définies et manipulations en mode "script"

# date du crime 
date_crime = datetime.datetime(2022,10,8,16,23)

# lieu du crime
# latlong_crime = gh_client.address_to_latlong("Place Henri Le Moal, Rennes") # pas assez precis
latlong_crime = [48.118097343000926, -1.7028835102619155] # recupere sur Google Maps

# import liste des suspects
fp = open("Projets/Cluedo/suspects.csv", "r", encoding="utf-8")

liste_suspects = []
for ligne in csv.DictReader(fp, delimiter=";"):
    dico_suspect = {}
    for cle, valeur in ligne.items():
        dico_suspect[cle] = valeur
    liste_suspects.append(dico_suspect)

# enquete
culpabilite_suspects = []
for i in range(len(liste_suspects)): # on teste pour chaque suspect
    culpabilite_suspects.append(association_suspect_possibilite(i, latlong_crime))
print(culpabilite_suspects)