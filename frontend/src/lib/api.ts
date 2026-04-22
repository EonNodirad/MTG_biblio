const BASE = '/api';

export interface CardSummary {
	uuid: string;
	name: string;
	setCode: string;
	type: string;
	manaCost: string | null;
	manaValue: number | null;
	colors: string | null;
	rarity: string;
	eur: number | null;
	scryfallId: string | null;
	matchedForeignName: string | null;
	matchedLanguage: string | null;
}

export interface CardSuggestion {
	uuid: string;
	name: string;
	setCode: string;
	scryfallId: string | null;
	language: string;       // "" = English match, else e.g. "French"
	foreignName: string | null;
}

export interface ForeignData {
	language: string;
	name: string;
	text?: string;
	type?: string;
	flavorText?: string;
	identifiers?: { scryfallId?: string };
}

export interface CardDetail {
	uuid: string;
	name: string;
	setCode: string;
	type: string;
	manaCost: string | null;
	manaValue: number | null;
	rarity: string;
	text: string | null;
	flavorText: string | null;
	power: string | null;
	toughness: string | null;
	colors: string[] | null;
	colorIdentity: string[] | null;
	keywords: string[] | null;
	subtypes: string[] | null;
	supertypes: string[] | null;
	prices: Record<string, unknown> | null;
	legalities: Record<string, string> | null;
	identifiers?: { scryfallId?: string; [key: string]: unknown };
	foreignData?: ForeignData[];
}

export interface SetSummary {
	code: string;
	name: string;
	releaseDate: string;
	type: string;
	totalSetSize: number;
}

export interface CollectionEntry {
	id: string;
	card_uuid: string;
	quantity: number;
	foil: boolean;
	condition: string;
}

export interface Deck {
	id: string;
	name: string;
	description: string;
	format: string;
	colors: string;
	entries: DeckEntry[];
}

export interface DeckEntry {
	id: string;
	card_uuid: string;
	quantity: number;
	category: string; // mainboard, sideboard, commander, companion, maybeboard
}

export interface FeasibilityResult {
	deck_id: string;
	feasible: boolean;
	owned: FeasibilityCard[];
	missing: FeasibilityCard[];
}

export interface FeasibilityCard {
	card_uuid: string;
	name: string;
	needed: number;
	owned: number;
	category: string;
	missing?: number;
}

// --- Cards ---

export async function suggestCards(query: string, limit = 10): Promise<CardSuggestion[]> {
	if (!query.trim()) return [];
	const url = new URL(`${BASE}/cards/suggest`, window.location.origin);
	url.searchParams.set('q', query);
	url.searchParams.set('limit', String(limit));
	const res = await fetch(url);
	if (!res.ok) throw new Error(await res.text());
	return res.json();
}

export async function searchCards(params: {
	q?: string;
	set?: string;
	type?: string;
	colors?: string;
	color_match?: string;
	text?: string;
	rarity?: string;
	cmc_min?: number | null;
	cmc_max?: number | null;
	types?: string;
	subtype?: string;
	supertype?: string;
	format?: string;
	limit?: number;
	offset?: number;
}): Promise<CardSummary[]> {
	const url = new URL(`${BASE}/cards/search`, window.location.origin);
	if (params.q) url.searchParams.set('q', params.q);
	if (params.set) url.searchParams.set('set', params.set);
	if (params.type) url.searchParams.set('type', params.type);
	if (params.colors) url.searchParams.set('colors', params.colors);
	if (params.color_match) url.searchParams.set('color_match', params.color_match);
	if (params.text) url.searchParams.set('text', params.text);
	if (params.rarity) url.searchParams.set('rarity', params.rarity);
	if (params.cmc_min != null) url.searchParams.set('cmc_min', String(params.cmc_min));
	if (params.cmc_max != null) url.searchParams.set('cmc_max', String(params.cmc_max));
	if (params.types) url.searchParams.set('types', params.types);
	if (params.subtype) url.searchParams.set('subtype', params.subtype);
	if (params.supertype) url.searchParams.set('supertype', params.supertype);
	if (params.format) url.searchParams.set('format', params.format);
	if (params.limit) url.searchParams.set('limit', String(params.limit));
	if (params.offset) url.searchParams.set('offset', String(params.offset));
	const res = await fetch(url);
	if (!res.ok) throw new Error(await res.text());
	return res.json();
}

export async function getCard(uuid: string): Promise<CardDetail> {
	const res = await fetch(`${BASE}/cards/${uuid}`);
	if (!res.ok) throw new Error(await res.text());
	return res.json();
}

export async function listSets(): Promise<SetSummary[]> {
	const res = await fetch(`${BASE}/cards/sets`);
	if (!res.ok) throw new Error(await res.text());
	return res.json();
}

// --- Collection ---

export async function getCollection(): Promise<CollectionEntry[]> {
	const res = await fetch(`${BASE}/collection/`);
	if (!res.ok) throw new Error(await res.text());
	return res.json();
}

export async function addToCollection(data: {
	card_uuid: string;
	quantity?: number;
	foil?: boolean;
	condition?: string;
}): Promise<CollectionEntry> {
	const res = await fetch(`${BASE}/collection/`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(data)
	});
	if (!res.ok) throw new Error(await res.text());
	return res.json();
}

export interface CardPrinting {
	uuid: string;
	name: string;
	setCode: string;
	setName: string | null;
	releaseDate: string | null;
	rarity: string;
	manaCost: string | null;
	scryfallId: string | null;
}

export async function getPrintings(name: string): Promise<CardPrinting[]> {
	const url = new URL(`${BASE}/cards/printings`, window.location.origin);
	url.searchParams.set('name', name);
	const res = await fetch(url);
	if (!res.ok) throw new Error(await res.text());
	return res.json();
}

export async function updateCollectionEntry(
	id: string,
	data: { quantity?: number; foil?: boolean; condition?: string; card_uuid?: string }
): Promise<CollectionEntry> {
	const res = await fetch(`${BASE}/collection/${id}`, {
		method: 'PATCH',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(data)
	});
	if (!res.ok) throw new Error(await res.text());
	return res.json();
}

export async function removeFromCollection(id: string): Promise<void> {
	const res = await fetch(`${BASE}/collection/${id}`, { method: 'DELETE' });
	if (!res.ok) throw new Error(await res.text());
}

export async function getMissingCards(setCode: string) {
	const res = await fetch(`${BASE}/collection/missing/${setCode}`);
	if (!res.ok) throw new Error(await res.text());
	return res.json();
}

// --- Decks ---

export async function listDecks(): Promise<Deck[]> {
	const res = await fetch(`${BASE}/decks/`);
	if (!res.ok) throw new Error(await res.text());
	return res.json();
}

export async function updateDeck(id: string, data: {
	name?: string;
	description?: string;
	format?: string;
	colors?: string;
}): Promise<Deck> {
	const res = await fetch(`${BASE}/decks/${id}`, {
		method: 'PATCH',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(data)
	});
	if (!res.ok) throw new Error(await res.text());
	return res.json();
}

export async function createDeck(data: {
	name: string;
	description?: string;
	format?: string;
	colors?: string;
}): Promise<Deck> {
	const res = await fetch(`${BASE}/decks/`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(data)
	});
	if (!res.ok) throw new Error(await res.text());
	return res.json();
}

export async function getDeck(id: string): Promise<Deck> {
	const res = await fetch(`${BASE}/decks/${id}`);
	if (!res.ok) throw new Error(await res.text());
	return res.json();
}

export async function deleteDeck(id: string): Promise<void> {
	const res = await fetch(`${BASE}/decks/${id}`, { method: 'DELETE' });
	if (!res.ok) throw new Error(await res.text());
}

export async function addCardToDeck(
	deckId: string,
	data: { card_uuid: string; quantity?: number; category?: string }
): Promise<DeckEntry> {
	const res = await fetch(`${BASE}/decks/${deckId}/cards`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(data)
	});
	if (!res.ok) throw new Error(await res.text());
	return res.json();
}

export async function removeCardFromDeck(deckId: string, entryId: string): Promise<void> {
	const res = await fetch(`${BASE}/decks/${deckId}/cards/${entryId}`, { method: 'DELETE' });
	if (!res.ok) throw new Error(await res.text());
}

export async function updateDeckEntry(
	deckId: string,
	entryId: string,
	quantity: number
): Promise<DeckEntry | null> {
	const res = await fetch(`${BASE}/decks/${deckId}/cards/${entryId}`, {
		method: 'PATCH',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ quantity })
	});
	if (res.status === 204) return null;
	if (!res.ok) throw new Error(await res.text());
	return res.json();
}

export async function moveDeckEntry(
	deckId: string,
	entryId: string,
	category: string
): Promise<DeckEntry | null> {
	const res = await fetch(`${BASE}/decks/${deckId}/cards/${entryId}`, {
		method: 'PATCH',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ category })
	});
	if (res.status === 204) return null;
	if (!res.ok) throw new Error(await res.text());
	return res.json();
}

export async function importDeckText(
	deckId: string,
	text: string
): Promise<{ imported: number; skipped: string[] }> {
	const res = await fetch(`${BASE}/decks/${deckId}/import`, {
		method: 'POST',
		headers: { 'Content-Type': 'text/plain' },
		body: text
	});
	if (!res.ok) throw new Error(await res.text());
	return res.json();
}

export async function exportDeckText(deckId: string): Promise<string> {
	const res = await fetch(`${BASE}/decks/${deckId}/export`);
	if (!res.ok) throw new Error(await res.text());
	return res.text();
}

// --- Stats / Dashboard ---

export interface DashboardStats {
	total_cards: number;
	unique_cards: number;
	foil_count: number;
	color_distribution: Record<string, number>;
	rarity_distribution: Record<string, number>;
	total_decks: number;
	decks: { id: string; name: string; format: string; description: string; card_count: number }[];
}

export async function getStats(): Promise<DashboardStats> {
	const res = await fetch(`${BASE}/stats/`);
	if (!res.ok) throw new Error(await res.text());
	return res.json();
}

export async function getDeckFeasibility(deckId: string): Promise<FeasibilityResult> {
	const res = await fetch(`${BASE}/decks/${deckId}/feasibility`);
	if (!res.ok) throw new Error(await res.text());
	return res.json();
}

export interface DeckPrice {
	deck_id: string;
	total_eur: number;
	total_usd: number;
	entries: { card_uuid: string; quantity: number; category: string; eur: number | null; usd: number | null }[];
}

export async function getDeckPrice(deckId: string): Promise<DeckPrice> {
	const res = await fetch(`${BASE}/decks/${deckId}/price`);
	if (!res.ok) throw new Error(await res.text());
	return res.json();
}
