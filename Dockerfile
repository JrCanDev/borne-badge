FROM python:3.11-alpine

# Installer git et openssh-client pour pouvoir cloner des repos privés si nécessaire
RUN apk add --no-cache git openssh-client bash

WORKDIR /app

# Copier d'abord le fichier de dépendances pour profiter du cache Docker
COPY requirement.txt ./

RUN pip3 install --no-cache-dir -r requirement.txt

# Copier le reste de l'application
COPY . .

EXPOSE 3000

# Variables d'environnement
ENV PYTHONUNBUFFERED=1
ENV NODE_ENV=production

# Lancer l'application
CMD ["python3", "app.py"]
