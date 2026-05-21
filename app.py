from flask import Flask, render_template, request, redirect, url_for, make_response
import mysql.connector
from datetime import datetime, timedelta
import csv
import io
import os
from dotenv import load_dotenv

# Charger les variables d'environnement du fichier .env
load_dotenv()

app = Flask(__name__)

# Configuration BDD sécurisee via le fichier .env
db_config = {
    "host": os.getenv("MARIADB_HOST", "localhost"),
    "user": os.getenv("MARIADB_USERNAME", "user"),
    "password": os.getenv("MARIADB_PASSWORD", ""),
    "database": os.getenv("MARIADB_DATABASE", "db_cartes"),
    "port": int(os.getenv("MARIADB_PORT", 3306)),
}

def get_db():
    return mysql.connector.connect(**db_config)

# Route pour la vue globale
@app.route('/')
def index():
    annee = request.args.get('annee', 'tous')
    td = request.args.get('td', 'tous')
    tp = request.args.get('tp', 'tous')
    presence = request.args.get('presence', 'tous')

    date_debut = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    date_fin = request.args.get('date2', date_debut)

    # Gererer la liste de tous les jours inclus dans la période
    start = datetime.strptime(date_debut, '%Y-%m-%d')
    end = datetime.strptime(date_fin, '%Y-%m-%d')
    delta = end - start

    # Liste de dictionnaires contenant la date ISO et le numéro du jour pour l'affichage
    jours_periode = []
    for i in range(delta.days + 1):
        jour_courant = start + timedelta(days=i)
        jours_periode.append({
            'date_str': jour_courant.strftime('%Y-%m-%d'),
            'num_jour': jour_courant.day
        })

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    # Requete pour filtrer la liste des étudiants
    query_etud = "SELECT * FROM Etudiants WHERE admin IS NULL"
    params_etud = []
    if annee != 'tous':
        query_etud += " AND groupe_tp LIKE %s"; params_etud.append(f"%{annee}%")
    if td != 'tous':
        query_etud += " AND groupe_tp LIKE %s"; params_etud.append(f"%{td}%")
    if tp != 'tous':
        query_etud += " AND groupe_tp LIKE %s"; params_etud.append(f"%{tp}%")

    cursor.execute(query_etud, params_etud)
    etudiants = cursor.fetchall()

    # Recuperer tous les couples (id_carte, date) de pointage sur la période
    query_pres = """
        SELECT id_carte, DATE(date_heure) as jour_pointage
        FROM Pointage 
        WHERE DATE(date_heure) BETWEEN %s AND %s
    """
    cursor.execute(query_pres, (date_debut, date_fin))
    pointages = cursor.fetchall()

    # On crée un groupe pour les recherches
    presents_set = set((row['id_carte'], str(row['jour_pointage'])) for row in pointages)

    # Associer les jours a chaque etudiant
    liste_finale = []
    for e in etudiants:
        e['calendrier'] = []
        min_une_presence = False

        for j in jours_periode:
            # Verification si l'etudiant a pointe ce jour precis
            est_present = (e['id_carte'], j['date_str']) in presents_set
            if est_present:
                min_une_presence = True

            e['calendrier'].append({
                'num': j['num_jour'],
                'present': est_present
            })

        # Application du filtre global de présence base sur la période complète
        if presence == 'presents' and min_une_presence:
            liste_finale.append(e)
        elif presence == 'absents' and not min_une_presence:
            liste_finale.append(e)
        elif presence == 'tous':
            liste_finale.append(e)

    cursor.close()
    conn.close()

    return render_template('index.html', etudiants=liste_finale,
                           annee=annee, td=td, tp=tp,
                           date_sel=date_debut, date2_sel=date_fin,
                           presence=presence)

# Route pour la vue etudiant
@app.route('/etudiant/<int:id_carte>')
def vue_etudiant(id_carte):
    # Recuperation des dates de la periode
    date_debut = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    date_fin = request.args.get('date2', date_debut)

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    # Verification que la carte existe et qu'il ne s'agit pas d'un admin
    cursor.execute("""
        SELECT * FROM Etudiants
        WHERE id_carte = %s AND (admin IS NULL OR admin = 0)
    """, (id_carte,))
    info = cursor.fetchone()

    # Si la carte appartient a un admin ou n'existe pas, on redirige vers l'accueil
    if not info:
        cursor.close()
        conn.close()
        return redirect('/') 

    # Recuperation de l'historique des pointages sur la période
    query = """
        SELECT DATE(date_heure) as jour, 
               MIN(TIME(date_heure)) as arrivee, 
               MAX(TIME(date_heure)) as depart
        FROM Pointage 
        WHERE id_carte = %s AND DATE(date_heure) BETWEEN %s AND %s
        GROUP BY DATE(date_heure)
        ORDER BY jour DESC
    """
    cursor.execute(query, (id_carte, date_debut, date_fin))
    historique = cursor.fetchall()

    cursor.close()
    conn.close()
    return render_template('etudiant.html', info=info, historique=historique, 
                           date_sel=date_debut, date2_sel=date_fin, id_carte=id_carte)

# Route pour l'export global
@app.route('/export')
def export_csv():
    # Recuperation de tous les filtres actifs envoyes depuis l'interface web
    annee = request.args.get('annee', 'tous')
    td = request.args.get('td', 'tous')
    tp = request.args.get('tp', 'tous')
    presence = request.args.get('presence', 'tous')

    # Gestion des dates
    date_debut = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    date_fin = request.args.get('date2', date_debut)

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    # Requete filtree pour récupérer les ETUDIANTS (en excluant l'administrateur)
    query_etud = "SELECT * FROM Etudiants WHERE admin IS NULL"
    params_etud = []

    if annee != 'tous':
        query_etud += " AND groupe_tp LIKE %s"
        params_etud.append(f"%{annee}%")
    if td != 'tous':
        query_etud += " AND groupe_tp LIKE %s"
        params_etud.append(f"%{td}%")
    if tp != 'tous':
        query_etud += " AND groupe_tp LIKE %s"
        params_etud.append(f"%{tp}%")

    cursor.execute(query_etud, params_etud)
    etudiants = cursor.fetchall()
    
    # On crée un dictionnaire indexé par id_carte pour filtrer plus tard
    dict_etudiants = {e['id_carte']: e for e in etudiants}
    liste_id_cartes = list(dict_etudiants.keys())
    
    if not liste_id_cartes:
        # Si aucun étudiant ne correspond aux filtres de groupe
        return "Aucun étudiant trouvé", 404

    # 2. MODIFICATION : On groupe par CARTE et par JOUR
    query_heures = """
        SELECT id_carte, 
               DATE(date_heure) as jour,
               MIN(TIME(date_heure)) as arrivee, 
               MAX(TIME(date_heure)) as depart
        FROM Pointage 
        WHERE DATE(date_heure) BETWEEN %s AND %s
        GROUP BY id_carte, DATE(date_heure)
        ORDER BY jour DESC, id_carte ASC
    """
    cursor.execute(query_heures, (date_debut, date_fin))
    tous_les_pointages = cursor.fetchall()

    # 3. Écriture du CSV
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['Date', 'Nom', 'Prenom', 'Groupe TP', 'Heure Arrivée', 'Heure Départ'])
    
    # Liste pour suivre qui a pointé au moins une fois sur la période
    cartes_presentes_au_moins_une_fois = set()

    for row in tous_les_pointages:
        id_c = row['id_carte']
        # On vérifie si le pointage appartient à un étudiant de notre liste filtrée
        if id_c in dict_etudiants:
            cartes_presentes_au_moins_une_fois.add(id_c)
            if presence != 'absents': # Si on veut les présents ou 'tous'
                e = dict_etudiants[id_c]
                cw.writerow([row['jour'], e['nom'], e['prenom'], e['groupe_tp'], row['arrivee'], row['depart']])
                
    # Si le filtre demande 'tous' ou 'absents', on rajoute les élèves qui n'ont JAMAIS pointé du tout de la période
    if presence in ['tous', 'absents']:
        for id_c, e in dict_etudiants.items():
            if id_c not in cartes_presentes_au_moins_une_fois:
                cw.writerow([f"Du {date_debut} au {date_fin}", e['nom'], e['prenom'], e['groupe_tp'], "ABSENT (Aucun pointage)", "ABSENT"])

    # Preparation de la réponse HTTP pour forcer le telechargement du fichier
    output = make_response(si.getvalue())

    # Nom du fichier dynamique base sur les dates sélectionnées
    nom_fichier = f"export_{date_debut}_au_{date_fin}.csv"
    output.headers["Content-Disposition"] = f"attachment; filename={nom_fichier}"
    output.headers["Content-type"] = "text/csv; charset=utf-8"

    cursor.close()
    conn.close()

    return output

# Route d'export des etudiants
@app.route('/export/etudiant/<int:id_carte>')
def export_etudiant_csv(id_carte):
    date_debut = request.args.get('date')
    date_fin = request.args.get('date2', date_debut)

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    # On s'assure qu'on ne tente pas d'exporter les données d'un admin
    cursor.execute("""
        SELECT nom, prenom FROM Etudiants 
        WHERE id_carte = %s AND (admin IS NULL OR admin = 0)
    """, (id_carte,))
    info = cursor.fetchone()

    if not info:
        cursor.close()
        conn.close()
        return "Action non autorisée ou profil introuvable", 403

    # Recuperation des pointages de l'étudiant
    query = """
        SELECT DATE(date_heure) as jour, 
               MIN(TIME(date_heure)) as arrivee, 
               MAX(TIME(date_heure)) as depart
        FROM Pointage 
        WHERE id_carte = %s AND DATE(date_heure) BETWEEN %s AND %s
        GROUP BY DATE(date_heure)
        ORDER BY jour DESC
    """
    cursor.execute(query, (id_carte, date_debut, date_fin))
    rows = cursor.fetchall()

    # Creation du fichier CSV
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['Jour', 'Heure Arrivee', 'Heure Depart'])

    for row in rows:
        cw.writerow([row['jour'], row['arrivee'], row['depart']])

    output = make_response(si.getvalue())
    filename = f"export_{info['nom']}_{info['prenom']}_{date_debut}_au_{date_fin}.csv"
    output.headers["Content-Disposition"] = f"attachment; filename={filename}"
    output.headers["Content-type"] = "text/csv; charset=utf-8"

    cursor.close()
    conn.close()
    return output

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)