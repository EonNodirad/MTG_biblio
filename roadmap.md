# Roadmap — MTG Collection Manager

Stack : **Python (FastAPI) + SQLite (AllPrintings.sqlite MTGjson)** pour le backend, **SvelteKit + Tailwind** pour le frontend.
Images et symboles : **Scryfall CDN** (`cards.scryfall.io`, `svgs.scryfall.io`).

---

## Phase 1 — Socle de données ✅
- [x] Télécharger `AllPrintings.sqlite` depuis MTGjson (~640 MB, ~110 K cartes, 855 sets)
- [x] Modéliser la collection en SQLite via SQLAlchemy (`CollectionEntry`, `Deck`, `DeckEntry`)
- [x] Index de recherche en mémoire pour l'autocomplétion (noms EN + toutes traductions)
- [x] Import / export de collection (CSV compatible Moxfield/Deckbox)

## Phase 2 — Backend API (FastAPI) ✅
- [x] CRUD collection (`GET /collection`, `POST`, `PATCH`, `DELETE`)
- [x] Recherche cartes par nom anglais **et** traduit, set, type (`GET /cards/search`)
- [x] Autocomplétion rapide multilingue (`GET /cards/suggest`)
- [x] Détail complet d'une carte + `foreignData` + `identifiers` (`GET /cards/{uuid}`)
- [x] Liste et détail des sets (`GET /cards/sets`)
- [x] Analyse des manques par set (`GET /collection/missing/{set_code}`)
- [ ] Valeur totale de la collection (nécessite `AllPrices.json`)

## Phase 3 — Deck Building ✅
- [x] CRUD decks (`GET /decks`, `POST`, `PATCH`, `DELETE`)
- [x] Ajout / suppression / quantité (+/−) de cartes dans un deck
- [x] Catégories : mainboard, sideboard, commander, companion, maybeboard + catégories personnalisées
- [x] Catégorisation automatique par type de carte (Créatures, Éphémères, Rituels, Terrains…)
- [x] Import deck depuis format texte MTGA / Moxfield (`POST /decks/{id}/import`)
- [x] Export deck au format texte MTGA / Moxfield (`GET /decks/{id}/export`)
- [x] Faisabilité : comparaison collection ↔ deck par nom de carte (toutes éditions confondues)
- [x] Faisabilité partielle : affiche `possédé/nécessaire` si possession incomplète

## Phase 4 — Prix ⚠️
- [ ] Télécharger `AllPrices.json` depuis MTGjson (fichier séparé, non inclus dans le SQLite)
- [ ] Afficher le prix d'une carte (TCGPlayer / Cardmarket)
- [ ] Afficher le prix total d'un deck
- [ ] Évaluer la valeur totale de la collection

## Phase 5 — Frontend ✅
- [x] Grille de recherche avec images Scryfall (format `normal`)
- [x] Autocomplétion avec miniatures dans le dropdown
- [x] Recherche par nom français (et toutes langues disponibles)
- [x] Restauration de l'état de recherche via URL (`/cards?q=...&set=...`)
- [x] Sélection d'un set → affichage automatique de toutes ses cartes
- [x] Fiche détail : image, symboles de mana (SVGs Scryfall), textes traduits, sélecteur de langue
- [x] Modal d'ajout à la collection (quantité, état NM/LP/…, foil)
- [x] Page collection : liste, +/−, foil, état color-codé, suppression, analyse manques par set
- [x] Page decks : liste, création, suppression
- [x] Page deck — vue liste et grille avec groupement par catégorie
- [x] Page deck — popup modal par carte : infos complètes, changement de catégorie, quantité
- [x] Page deck — panneau de stats : courbe de mana, répartition types, indicateurs couleur
- [x] Page deck — faisabilité en temps réel avec badge `possédé/nécessaire` (liste et grille)
- [x] Page deck — import/export texte MTGA / Moxfield
- [x] Images dans la page collection (miniature `art_crop` à côté de chaque entrée)
- [x] Dashboard : stats collection (total, uniques, foils, couleurs, raretés) + liste decks
- [x] Page wishlist : ajout par autocomplétion, quantité, notes, statut possédé/manquant

## Ce qui reste — par priorité

### Court terme
1. **Prix** — télécharger `AllPrices.json` et l'intégrer (par carte, par deck, valeur collection)

### Long terme
2. **Import deck Moxfield** — via leur API publique
