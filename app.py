from flask import Flask, render_template, request, redirect, url_for, make_response
import mysql.connector
from datetime import datetime, timedelta
import csv
import io

app = Flask(__name__)

# Configuration BDD
db_config = {
    "host": "localhost",
    "user": "user",
    "password": "XVbjwqKpzAHIMqVTJ1wn",
    "database": "db_cartes"
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

    # Requete pour recuperer les badges valides sur la periode selectionnee
    query_pres = """
        SELECT DISTINCT id_carte 
        FROM Pointage 
        WHERE DATE(date_heure) BETWEEN %s AND %s
    """
    cursor.execute(query_pres, (date_debut, date_fin))
    presents_ids = [row['id_carte'] for row in cursor.fetchall()]

    # Filtrage de la liste selon le choix du filtre de présence (Tous / Présents / Absents)
    liste_filtree = []
    for e in etudiants:
        # Un etudiant est considere présent s'il a pointé au moins une fois sur la période
        e['est_present'] = e['id_carte'] in presents_ids

        if presence == 'presents' and e['est_present']:
            liste_filtree.append(e)
        elif presence == 'absents' and not e['est_present']:
            liste_filtree.append(e)
        elif presence == 'tous':
            liste_filtree.append(e)

    # Creation et ecriture du fichier CSV en mémoire
    si = io.StringIO()
    cw = csv.writer(si)

    # Ligne d'en-tete du fichier CSV
    cw.writerow(['Nom', 'Prenom', 'Groupe TP', f'Statut du {date_debut} au {date_fin}'])

    # Ajout des lignes pour chaque étudiant filtre
    for e in liste_filtree:
        statut = "Présent" if e['est_present'] else "Absent"
        cw.writerow([e['nom'], e['prenom'], e['groupe_tp'], statut])

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