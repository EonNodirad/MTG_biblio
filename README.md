# MTG Collection Manager

Gestionnaire de collection Magic: The Gathering full-stack — Python (FastAPI) + SQLite backend, SvelteKit + Tailwind frontend.
Données cartes via [MTGjson](https://mtgjson.com/) (AllPrintings.sqlite + AllPrices.json.xz), images et symboles via [Scryfall CDN](https://scryfall.com/).

## Fonctionnalités

### Dashboard
- Statistiques globales : cartes totales, uniques, foils, nombre de decks
- Valeur estimée de la collection en EUR et USD (Cardmarket / TCGPlayer)
- Répartition par couleur et par rareté
- Progression par set (cartes possédées / taille du set)
- Bouton **Rafraîchir les prix** + mise à jour automatique hebdomadaire
- Bouton **Mettre à jour les données** : re-télécharge AllPrintings.sqlite depuis MTGjson (nouvelles extensions) + rebuild incrémental de l'index scanner
- Notifications toast non intrusives (orange pendant le chargement, vert à la fin)

### Recherche de cartes
- Recherche par nom anglais ou traduit (toutes langues)
- Autocomplétion avec miniatures Scryfall dès 2 caractères
- Filtre par set
- Recherche avancée :
  - Couleurs avec mode (contient / contient tous / exactement / exclut)
  - Types (Créature, Éphémère, Rituel, Enchantement, Artefact, Terrain, Planeswalker…)
  - Sous-type (ex : "Zombie" → toutes les créatures Zombie)
  - Légendaire uniquement
  - Rareté (Commune / Inhabituelle / Rare / Mythique)
  - Texte de règles
  - CMC min/max
  - Légalité par format (Standard, Pioneer, Modern, Legacy, Vintage, Commander, Pauper…)
- Résultats en grille avec image complète
- État de recherche persisté dans l'URL (navigation arrière fonctionnelle)

### Fiche carte
- Image HD, coût en mana, type, sous-types, mots-clés
- Texte de règles avec icônes SVG inline (`{T}`, `{G}`, `{2/R}`…)
- Texte de saveur, Force/Endurance
- Prix Cardmarket (EUR) et TCGPlayer (USD), normal et foil
- Légalités par format (Legal / Banni / Restreint)
- Sélecteur de langue (traductions MTGjson)
- Bouton ajout direct à la collection

### Collection
- Déduplication automatique : même carte + même état + même foil → incrémente la quantité
- Vue **Liste** (art crop) et vue **Grille** (image complète) — grille par défaut
- Filtres instantanés (client-side) :
  - Recherche par nom
  - Couleurs avec mode (contient / contient tous / exactement / exclut)
  - Rareté, Type de carte
  - Texte de règles, Sous-type, Légendaire
  - CMC min/max
  - Format légal dans
- Tris : Nom, CMC, Rareté, Couleur, Set, **Prix €** (foil pris en compte)
- Contrôles +/− de quantité, toggle foil, sélecteur d'état (NM/LP/MP/HP/DMG)
- Analyse des cartes manquantes par set (taux de complétion)
- Export / Import CSV

### Deck Builder
- Création / suppression de decks avec nom, format et description
- Mainboard, sideboard, maybeboard, commandant, compagnon, catégories personnalisées
- Recherche avec autocomplétion et images dans le deck builder
- Popup de détail carte (texte avec icônes mana, prix, P/T) directement depuis le deck
- Contrôles +/− de quantité directement sur les entrées
- Import depuis un format texte MTGA / Moxfield (coller une liste)
- Export en format texte
- Vérification de faisabilité en temps réel (cartes possédées vs manquantes)
- Prix total du deck (EUR + USD)

### Liste de souhaits
- Ajout de cartes souhaitées avec priorité et notes

### Scanner de cartes
- Reconnaissance par hash perceptuel (pHash) sur l'illustration de la carte
- Interface webcam dans le navigateur avec cadre de guidage
- Identification en temps réel avec indicateur de confiance (vert/orange/rouge)
- Ajout direct à la collection depuis le résultat du scan
- Index de ~110 000 cartes (~19 MB), rebuild incrémental lors des mises à jour

## Stack technique

| Couche | Techno |
|--------|--------|
| Backend | Python 3.12, FastAPI, SQLAlchemy, SQLite |
| Données cartes | MTGjson AllPrintings.sqlite (~640 MB), auto-refresh hebdomadaire |
| Données prix | MTGjson AllPrices.json.xz (~42 MB), auto-refresh hebdomadaire |
| Scanner | pHash (imagehash + numpy), OpenCV, index SQLite |
| Images | Scryfall CDN (`cards.scryfall.io`) |
| Symboles mana | Scryfall SVG (`svgs.scryfall.io/card-symbols/`) |
| Frontend | SvelteKit 2, Svelte 5 runes, Tailwind CSS 4 |

## Lancer le projet (Docker)

```bash
./start.sh        # Linux / macOS
start.bat         # Windows
```

L'application est accessible sur `http://localhost:8090`.

Au premier démarrage, Docker construit l'image puis `AllPrintings.sqlite` (~640 MB) et `AllPrices.json.xz` (~42 MB) sont téléchargés automatiquement depuis mtgjson.com.

## Lancer en mode développement

**Backend**
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

**Frontend**
```bash
cd frontend
npm install
npm run dev
```

L'interface est accessible sur `http://localhost:5173`, l'API sur `http://localhost:8000/docs`.

**Scanner (optionnel)** — construire l'index pHash :
```bash
cd ml
pip install -r requirements.txt
python build_index.py --workers 8
```

## License
See the LICENSE file for licensing information.
