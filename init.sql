CREATE OR REPLACE TABLE Etudiants (
    id_carte BIGINT NOT NULL,
    nom VARCHAR(50),
    prenom VARCHAR(50),
    groupe_tp VARCHAR(20),
    admin SMALLINT,
    PRIMARY KEY(id_carte)
);

CREATE OR REPLACE TABLE Capteur (
    id_capteur SMALLINT,
    salle VARCHAR(30),
    PRIMARY KEY(id_capteur)
);

CREATE OR REPLACE TABLE Pointage (
    id_pointage INT AUTO_INCREMENT,
    date_heure DATETIME DEFAULT CURRENT_TIMESTAMP,
    id_carte BIGINT,
    id_capteur SMALLINT,
    PRIMARY KEY(id_pointage),
    CONSTRAINT fk_carte FOREIGN KEY (id_carte) REFERENCES Etudiants(id_carte) ON DELETE CASCADE,
    CONSTRAINT fk_capteur FOREIGN KEY (id_capteur) REFERENCES Capteur(id_capteur) ON DELETE CASCADE
);

INSERT INTO Capteur (id_capteur, salle) 
VALUES (1, '126');

INSERT INTO Capteur (id_capteur, salle) 
VALUES (2, '127');

INSERT INTO Etudiants (id_carte, nom, prenom, admin)
VALUES (584191262799, 'Deceuninck--Cappelaere', 'Lilian', 1);