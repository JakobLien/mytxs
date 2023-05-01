# MyTXS 2.0
Hei, dette er repoet til MyTXS 2.0, den neste versjonen av MyTSS og MiTKS!

## Oppsett

Pull repoet, så tippe e det bare å kjør
1. Forbered db-migrasjon med `python3 manage.py makemigrations`
1. Utfør db-migrasjon med `python3 manage.py migrate`
1. Kjør oppsett seed på databasen med `python3 mange.py seed`
1. Opprett en superuser med `python3 manage.py createsuperuser --username admin --email admin@example.com`, og fyll inn et passord, f.eks. admin. Lokalt e det trygt å ha et dårlig passord, men ikke gjør dette i prod!!!
1. Kjør server med `python3 manage.py runserver`
