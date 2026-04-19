# MTG Collection Manager

Gestionnaire de collection Magic: The Gathering full-stack — Python (FastAPI) + SQLite backend, SvelteKit + Tailwind frontend.
Données cartes via [MTGjson](https://mtgjson.com/) (AllPrintings.sqlite + AllPrices.json.xz), images et symboles via [Scryfall CDN](https://scryfall.com/).

## Fonctionnalités

### Dashboard
- Statistiques globales : cartes totales, uniques, foils, nombre de decks
- Valeur estimée de la collection en EUR et USD (Cardmarket / TCGPlayer)
- Répartition par couleur et par rareté
- Progression par set (cartes possédées / taille du set)
- Bouton de rafraîchissement manuel des prix + mise à jour automatique hebdomadaire

### Recherche de cartes
- Recherche par nom anglais ou traduit (toutes langues)
- Autocomplétion avec miniatures Scryfall dès 2 caractères
- Recherche avancée :
  - Couleurs (contient / exactement / exclut)
  - Types (Créature, Éphémère, Rituel, Enchantement, Artefact, Terrain, Planeswalker…)
  - Sous-type (ex : "Zombie" → toutes les créatures Zombie)
  - Légendaire uniquement
  - Rareté (Commune / Inhabituelle / Rare / Mythique)
  - Texte de règles (toutes langues)
  - CMC min/max
  - Légalité par format (Standard, Pioneer, Modern, Commander…)
- État de recherche persisté dans l'URL (navigation arrière fonctionnelle)

### Fiche carte
- Image HD, coût en mana, type, sous-types
- Texte de règles avec icônes SVG inline (`{T}`, `{G}`, `{2/R}`…)
- Texte de saveur, Force/Endurance
- Prix Cardmarket (EUR) et TCGPlayer (USD)
- Légalités par format (Legal / Banni / Restreint)
- Sélecteur de langue (traductions MTGjson)
- Bouton ajout direct à la collection

### Collection
- Ajout depuis la recherche ou la fiche carte (quantité, état NM/LP/MP/HP/DMG, foil)
- Code couleur par état (vert → rouge)
- Miniatures `art_crop` à côté de chaque entrée
- Contrôles +/− de quantité, suppression
- Analyse des cartes manquantes par set (taux de complétion)

### Deck Builder
- Création / suppression de decks avec nom, format et description
- Mainboard, sideboard, maybeboard, commandant, compagnon
- Recherche avec autocomplétion et images dans le deck builder
- Popup de détail carte (texte, prix, P/T) directement depuis le deck
- Contrôles +/− de quantité directement sur les entrées
- Import depuis un format texte MTGA / Moxfield (coller une liste)
- Export en format texte
- Vérification de faisabilité en temps réel (cartes possédées vs manquantes)
- Prix total du deck (EUR + USD)

### Liste de souhaits
- Ajout de cartes souhaitées avec priorité et notes

## Stack technique

| Couche | Techno |
|--------|--------|
| Backend | Python 3.12, FastAPI, SQLAlchemy, SQLite |
| Données cartes | MTGjson AllPrintings.sqlite (~640 MB) |
| Données prix | MTGjson AllPrices.json.xz (~42 MB), mis à jour automatiquement toutes les semaines |
| Images | Scryfall CDN (`cards.scryfall.io`) |
| Symboles mana | Scryfall SVG (`svgs.scryfall.io/card-symbols/`) |
| Frontend | SvelteKit 2, Svelte 5 runes, Tailwind CSS 4 |

## Lancer le projet

**Backend**
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Au premier démarrage, `AllPrintings.sqlite` (~640 MB) et `AllPrices.json.xz` (~42 MB) sont téléchargés automatiquement depuis mtgjson.com si une connexion internet est disponible.

**Frontend**
```bash
cd frontend
npm install
npm run dev
```

L'interface est accessible sur `http://localhost:5173`, l'API sur `http://localhost:8000/docs`.

## License
See the LICENSE file for licensing information.
