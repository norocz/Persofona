# ⬡ PersonDB

**Osobní databáze kontaktů** — inspirováno projektem Monica CRM.
Django aplikace s Matrix/hacker designem, multi-user workspace systémem, JSON metadaty a Docker deployem.

---

## Funkce

- **Multi-user** — registrace, přihlášení, vlastní prostor pro každého uživatele
- **Workspace** — izolované databáze, přepínání mezi prostory
- **Kooperace** — pozvánky kódem nebo odkazem, role Owner/Editor/Viewer
- **Osoby** — jméno, foto, biografie, adresa, firma, vlastní JSON metadata
- **Vztahy** — 21 typů: rodinné (rodič, dítě, manžel/ka...) i nerodinné (přítel, kolega, nepřítel...)
- **Kontakty** — email, telefon, web, sociální sítě
- **Dokumenty** — fotografie, doklady, smlouvy s náhledem
- **Štítky & Skupiny** — barevné kategorie
- **Mapa vztahů** — celostránkový interaktivní graf s clustery skupin
- **JSON Export/Import** — data ve formátu JSON
- **ZIP Záloha/Obnova** — kompletní balíček včetně fotek a dokumentů
- **Lokalizace** — čeština, angličtina, němčina, slovenština (i18n)
- **4 témata** — `matrix`, `cyberpunk`, `minimal`, `light`
- **Docker** — PostgreSQL + Nginx + Gunicorn

---

## Rychlý start

```bash
git clone <repo> && cd persondb
./deploy.sh dev

# Seed demo data (vytvoří uživatele demo/demo1234)
python manage.py seed_demo

# → http://localhost:8000
```

## Docker deploy

```bash
cp .env.example .env && nano .env
./deploy.sh docker
./deploy.sh createsuperuser
```

---

## Multi-user & Kooperace

### Jak to funguje

1. **Registrace** — každý uživatel dostane vlastní výchozí workspace
2. **Nový workspace** — uživatel si může vytvořit libovolný počet prostorů
3. **Pozvánka** — vlastník vytvoří pozvánku (kód + odkaz) v Nastavení prostoru
4. **Připojení** — pozvaný otevře odkaz `/join/KÓDXXXX/`, zaregistruje se a je automaticky členem
5. **Role:**
   - **Vlastník** — plná správa, může zvát, měnit role, odebírat členy
   - **Editor** — může přidávat a upravovat osoby, vztahy, dokumenty
   - **Čtenář** — pouze prohlížení

### Přepínání prostorů

V levém sidebaru je dropdown pro přepínání mezi prostory. Každý prostor má izolovaná data.

---

## Struktura projektu

```
persondb/
├── core/
│   ├── models.py          # Workspace, Membership, Invite, Person, Contact, ...
│   ├── views.py           # WsMixin + auth + workspace + CRUD views
│   ├── middleware.py       # WorkspaceMiddleware
│   ├── forms.py           # Workspace-scoped formuláře
│   ├── urls.py
│   ├── templates/core/
│   │   ├── auth/           # login, register
│   │   ├── workspace/      # pick, create, settings, join
│   │   └── ...             # dashboard, persons, tags, groups, map
│   └── management/commands/seed_demo.py
├── static/
│   ├── css/matrix.css      # IBM Plex Sans + JetBrains Mono
│   └── js/main.js, network_map.js
├── deploy.sh, Dockerfile, docker-compose.yml, nginx.conf
└── .env.example
```

---

## Licence

MIT
