<script lang="ts">
	import type { DeckEntry, CardDetail } from '$lib/api';
	import CardImage from './CardImage.svelte';
	import ManaCost from './ManaCost.svelte';
	import RarityBadge from './RarityBadge.svelte';
	import CardText from './CardText.svelte';

	let {
		entry,
		card,
		deckCategories,
		onclose,
		onquantitychange,
		oncategorychange,
		ondelete,
	}: {
		entry: DeckEntry;
		card: CardDetail | undefined;
		deckCategories: string[];   // all unique categories currently in the deck
		onclose: () => void;
		onquantitychange: (delta: number) => void;
		oncategorychange: (category: string) => void;
		ondelete: () => void;
	} = $props();

	// Type categories — toujours visibles, correspondent aux types de cartes
	const TYPE_CATS = [
		{ key: 'Créatures',           label: 'Créatures' },
		{ key: 'Éphémères', label: 'Éphémères' },
		{ key: 'Rituels',   label: 'Rituels' },
		{ key: 'Planeswalkers',       label: 'Planeswalkers' },
		{ key: 'Artefacts',           label: 'Artefacts' },
		{ key: 'Enchantements',       label: 'Enchantements' },
		{ key: 'Terrains',            label: 'Terrains' },
		{ key: 'Autres',              label: 'Autres' },
	];
	// Deck sections (pas de Mainboard / Sideboard — on les choisit à l'ajout)
	const SECTION_CATS = [
		{ key: 'commander',  label: 'Commander' },
		{ key: 'companion',  label: 'Compagnon' },
		{ key: 'maybeboard', label: 'Maybeboard' },
		{ key: 'sideboard',  label: 'Sideboard' },
	];
	const PREDEFINED_KEYS = new Set([...TYPE_CATS, ...SECTION_CATS].map((p) => p.key));

	// Custom categories already used in the deck (not predefined)
	const customCategories = $derived(deckCategories.filter((c) => !PREDEFINED_KEYS.has(c) && c !== 'mainboard'));

	let newCategoryInput = $state('');

	function applyNew() {
		const trimmed = newCategoryInput.trim();
		if (!trimmed) return;
		oncategorychange(trimmed);
		newCategoryInput = '';
	}

	function onKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') onclose();
	}

	const scryfallId = $derived(card?.identifiers?.scryfallId);

	const RARITY_COLORS: Record<string, string> = {
		mythic: 'text-orange-400', rare: 'text-yellow-400',
		uncommon: 'text-gray-300', common: 'text-gray-500',
	};
</script>

<svelte:window onkeydown={onKeydown} />

<!-- Backdrop -->
<div
	class="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4"
	role="dialog"
	aria-modal="true"
	onmousedown={(e) => { if (e.target === e.currentTarget) onclose(); }}
>
	<div class="bg-gray-800 border border-gray-700 rounded-2xl w-full max-w-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">

		<!-- Header -->
		<div class="flex items-center justify-between px-5 py-3 border-b border-gray-700 shrink-0">
			<div class="flex items-center gap-3 min-w-0">
				<ManaCost cost={card?.manaCost} />
				<h2 class="text-white font-bold text-lg truncate">{card?.name ?? entry.card_uuid}</h2>
				<RarityBadge rarity={card?.rarity ?? ''} />
			</div>
			<button onclick={onclose} class="text-gray-400 hover:text-white text-xl shrink-0 ml-3">✕</button>
		</div>

		<!-- Body -->
		<div class="flex gap-5 p-5 overflow-y-auto">

			<!-- Card image -->
			<div class="shrink-0 w-40">
				<a href="/cards/{entry.card_uuid}" onclick={onclose}>
					<CardImage {scryfallId} size="normal" alt={card?.name ?? ''} class="w-full rounded-xl shadow-lg" />
				</a>
				<a href="/cards/{entry.card_uuid}" onclick={onclose}
					class="text-xs text-gray-500 hover:text-amber-400 transition-colors mt-2 block text-center">
					Voir la fiche →
				</a>
			</div>

			<!-- Info + controls -->
			<div class="flex-1 min-w-0 space-y-4">

				<!-- Type + set -->
				<div class="space-y-0.5">
					{#if card?.type}
						<p class="text-sm text-gray-300">{card.type}</p>
					{/if}
					{#if card?.setCode}
						<p class="text-xs text-gray-500 font-mono">{card.setCode}
							{#if card?.rarity}
								· <span class="{RARITY_COLORS[card.rarity] ?? 'text-gray-400'}">{card.rarity}</span>
							{/if}
						</p>
					{/if}
				</div>

				<!-- Rules text -->
				{#if card?.text}
					<div class="text-sm text-gray-300 bg-gray-700/50 rounded-lg p-3 border border-gray-600/50">
						<CardText text={card.text} />
					</div>
				{/if}

				<!-- Flavor text -->
				{#if card?.flavorText}
					<p class="text-xs text-gray-500 italic">{card.flavorText}</p>
				{/if}

				<!-- P/T -->
				{#if card?.power != null && card?.toughness != null}
					<p class="text-sm font-semibold text-gray-300">{card.power} / {card.toughness}</p>
				{/if}

				<!-- Prices -->
				{#if card?.prices}
					{@const p = card.prices as { eur?: number | null; eur_foil?: number | null; usd?: number | null; usd_foil?: number | null }}
					{#if p.eur != null || p.usd != null}
						<div class="flex flex-wrap gap-3 text-xs text-gray-400">
							{#if p.eur != null}<span>CM : <span class="text-amber-400 font-medium">€{p.eur.toFixed(2)}</span></span>{/if}
							{#if p.eur_foil != null}<span>Foil : <span class="text-purple-400 font-medium">€{p.eur_foil.toFixed(2)}</span></span>{/if}
							{#if p.usd != null}<span>TCG : <span class="text-amber-400 font-medium">${p.usd.toFixed(2)}</span></span>{/if}
							{#if p.usd_foil != null}<span>Foil : <span class="text-purple-400 font-medium">${p.usd_foil.toFixed(2)}</span></span>{/if}
						</div>
					{/if}
				{/if}

				<!-- Quantity -->
				<div class="flex items-center gap-3">
					<span class="text-xs text-gray-500 uppercase tracking-wide">Quantité</span>
					<div class="flex items-center gap-2">
						<button
							onclick={() => onquantitychange(-1)}
							class="w-7 h-7 flex items-center justify-center rounded-full bg-gray-700 hover:bg-gray-600 text-white font-bold"
						>−</button>
						<span class="text-white font-semibold w-6 text-center">{entry.quantity}</span>
						<button
							onclick={() => onquantitychange(+1)}
							class="w-7 h-7 flex items-center justify-center rounded-full bg-gray-700 hover:bg-gray-600 text-white font-bold"
						>+</button>
					</div>
				</div>

				<!-- Category -->
				<div class="space-y-2">
					<span class="text-xs text-gray-500 uppercase tracking-wide">Catégorie</span>
					<div class="flex flex-wrap gap-1.5">
						<!-- Type categories -->
						{#each TYPE_CATS as p}
							<button
								onclick={() => oncategorychange(p.key)}
								class="text-xs px-3 py-1 rounded-full border font-medium transition-colors
									{entry.category === p.key
										? 'bg-amber-500 border-amber-400 text-gray-950'
										: 'border-gray-600 text-gray-400 hover:border-gray-400 hover:text-gray-200'}"
							>{p.label}</button>
						{/each}
					</div>
					<div class="flex flex-wrap gap-1.5">
						<!-- Deck sections -->
						{#each SECTION_CATS as p}
							<button
								onclick={() => oncategorychange(p.key)}
								class="text-xs px-3 py-1 rounded-full border font-medium transition-colors
									{entry.category === p.key
										? 'bg-purple-500 border-purple-400 text-white'
										: 'border-gray-700 text-gray-500 hover:border-gray-500 hover:text-gray-300'}"
							>{p.label}</button>
						{/each}
						<!-- Custom categories already in deck -->
						{#each customCategories as cat}
							<button
								onclick={() => oncategorychange(cat)}
								class="text-xs px-3 py-1 rounded-full border font-medium transition-colors
									{entry.category === cat
										? 'bg-blue-500 border-blue-400 text-white'
										: 'border-blue-800 text-blue-400 hover:border-blue-600 hover:text-blue-300'}"
							>{cat}</button>
						{/each}
					</div>

					<!-- New custom category input -->
					<div class="flex gap-2">
						<input
							bind:value={newCategoryInput}
							onkeydown={(e) => e.key === 'Enter' && applyNew()}
							type="text"
							placeholder="Nouvelle catégorie (ex: Rampe, Suppression…)"
							class="flex-1 text-sm px-3 py-1.5 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
						/>
						<button
							onclick={applyNew}
							disabled={!newCategoryInput.trim()}
							class="text-xs px-3 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 text-white rounded-lg font-medium"
						>Créer</button>
					</div>
				</div>

				<!-- Delete -->
				<div class="pt-1">
					<button
						onclick={ondelete}
						class="text-xs text-red-500 hover:text-red-400 transition-colors"
					>Retirer du deck</button>
				</div>
			</div>
		</div>
	</div>
</div>
