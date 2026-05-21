FROM python3:latest

# Installer git et openssh-client pour pouvoir cloner des repos privés si nécessaire
RUN apk add --no-cache git openssh-client bash

WORKDIR /usr/src/app

WORKDIR /app

RUN pip3 install -r requirement.txt

COPY . .

EXPOSE 3000

# Exposer le port
EXPOSE 3000

# Variable d'environnement pour la production
ENV NODE_ENV=production

# Lancer l'application en mode production
CMD ["python3", "app.py"]
