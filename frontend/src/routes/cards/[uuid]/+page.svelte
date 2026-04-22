<script lang="ts">
	import type { CardDetail, ForeignData } from '$lib/api';
	import ManaCost from '$lib/components/ManaCost.svelte';
	import RarityBadge from '$lib/components/RarityBadge.svelte';
	import AddToCollectionModal from '$lib/components/AddToCollectionModal.svelte';
	import CardImage from '$lib/components/CardImage.svelte';
	import CardText from '$lib/components/CardText.svelte';

	let { data }: { data: { card: CardDetail } } = $props();
	const card = $derived(data.card);

	let showModal = $state(false);
	let toast = $state<string | null>(null);
	let selectedLang = $state('English');

	const colorNames: Record<string, string> = {
		W: 'Blanc', U: 'Bleu', B: 'Noir', R: 'Rouge', G: 'Vert', C: 'Incolore'
	};

	function computeView(lang: string) {
		const foreign: ForeignData[] = card.foreignData ?? [];
		const languages = ['English', ...foreign.map((f) => f.language)];
		const trans = lang !== 'English' ? foreign.find((f) => f.language === lang) : undefined;
		return {
			languages,
			isTranslated: !!trans,
			name:       trans?.name       ?? card.name,
			text:       trans?.text       ?? card.text,
			type:       trans?.type       ?? card.type,
			flavor:     trans?.flavorText ?? card.flavorText,
			scryfallId: trans?.identifiers?.scryfallId ?? card.identifiers?.scryfallId ?? null,
		};
	}

	const view = $derived(computeView(selectedLang));
</script>

<div class="max-w-4xl mx-auto space-y-6">
	<div class="flex items-center gap-3 text-sm text-gray-500">
		<button onclick={() => history.back()} class="hover:text-white transition-colors">← Retour</button>
		<span>/</span>
		<span class="font-mono">{card.setCode}</span>
	</div>

	<div class="grid grid-cols-1 md:grid-cols-[auto_1fr] gap-6">
		<!-- Card image + language selector -->
		<div class="flex flex-col items-center gap-3">
			<CardImage
				scryfallId={view.scryfallId}
				alt={view.name}
				size="normal"
				class="w-64 rounded-xl shadow-2xl"
			/>

			{#if view.languages.length > 1}
				<select
					bind:value={selectedLang}
					class="w-full px-3 py-1.5 bg-gray-800 border border-gray-700 rounded-lg text-sm text-white focus:outline-none focus:border-amber-500"
				>
					{#each view.languages as lang}
						<option value={lang}>{lang}</option>
					{/each}
				</select>
			{/if}
		</div>

		<!-- Card info -->
		<div class="bg-gray-800 border border-gray-700 rounded-2xl p-6 space-y-4">
			<div class="flex items-start justify-between gap-4">
				<div>
					<h1 class="text-2xl font-bold text-white">{view.name}</h1>
					{#if card.subtypes?.length}
						<p class="text-sm text-gray-400 mt-0.5">{view.type} — {card.subtypes.join(' ')}</p>
					{:else}
						<p class="text-sm text-gray-400 mt-0.5">{view.type ?? '—'}</p>
					{/if}
					{#if view.isTranslated}
						<p class="text-xs text-amber-500 mt-0.5 italic">({card.name})</p>
					{/if}
				</div>
				<ManaCost cost={card.manaCost} />
			</div>

			<div class="flex flex-wrap gap-2">
				<RarityBadge rarity={card.rarity} />
				{#if card.colors?.length}
					{#each card.colors as c}
						<span class="text-xs px-2 py-0.5 rounded bg-gray-700 text-gray-300">{colorNames[c] ?? c}</span>
					{/each}
				{/if}
				{#if card.keywords?.length}
					{#each card.keywords as kw}
						<span class="text-xs px-2 py-0.5 rounded bg-blue-900 text-blue-300">{kw}</span>
					{/each}
				{/if}
			</div>

			{#if view.text}
				<div class="border-t border-gray-700 pt-4 text-sm text-gray-200">
					<CardText text={view.text} />
				</div>
			{/if}

			{#if view.flavor}
				<p class="text-gray-500 text-sm italic border-t border-gray-700 pt-3">"{view.flavor}"</p>
			{/if}

			{#if card.power !== null && card.power !== undefined}
				<div class="flex justify-end">
					<span class="text-lg font-bold text-white bg-gray-700 px-3 py-1 rounded">
						{card.power}/{card.toughness}
					</span>
				</div>
			{/if}

			{#if card.prices}
				{@const p = card.prices as { eur?: number | null; eur_foil?: number | null; usd?: number | null; usd_foil?: number | null }}
				<div class="border-t border-gray-700 pt-4 space-y-1">
					<p class="text-xs font-semibold text-gray-500 uppercase tracking-wide">Prix</p>
					<div class="flex flex-wrap gap-4 text-sm">
						{#if p.eur != null}
							<span class="text-gray-300">Cardmarket : <span class="text-amber-400 font-medium">€{p.eur.toFixed(2)}</span></span>
						{/if}
						{#if p.eur_foil != null}
							<span class="text-gray-300">Cardmarket foil : <span class="text-purple-400 font-medium">€{p.eur_foil.toFixed(2)}</span></span>
						{/if}
						{#if p.usd != null}
							<span class="text-gray-300">TCGPlayer : <span class="text-amber-400 font-medium">${p.usd.toFixed(2)}</span></span>
						{/if}
						{#if p.usd_foil != null}
							<span class="text-gray-300">TCGPlayer foil : <span class="text-purple-400 font-medium">${p.usd_foil.toFixed(2)}</span></span>
						{/if}
						{#if p.eur == null && p.usd == null}
							<span class="text-gray-500 italic">Prix non disponibles</span>
						{/if}
					</div>
				</div>
			{/if}

			{#if card.legalities && Object.keys(card.legalities).length > 0}
				{@const FORMAT_LABELS: Record<string,string> = {
					standard:'Standard', pioneer:'Pioneer', modern:'Modern', legacy:'Legacy',
					vintage:'Vintage', commander:'Commander', pauper:'Pauper', historic:'Historic',
					timeless:'Timeless', brawl:'Brawl', oathbreaker:'Oathbreaker',
					paupercommander:'Pauper Cmdr', oldschool:'Old School', premodern:'Premodern',
				}}
				<div class="border-t border-gray-700 pt-4 space-y-2">
					<p class="text-xs font-semibold text-gray-500 uppercase tracking-wide">Légalités</p>
					<div class="flex flex-wrap gap-1.5">
						{#each Object.entries(card.legalities) as [fmt, status]}
							<span class="text-xs px-2 py-0.5 rounded font-medium
								{status === 'Legal'   ? 'bg-green-900/50 text-green-400 border border-green-800' :
								 status === 'Banned'  ? 'bg-red-900/50 text-red-400 border border-red-800' :
								 status === 'Restricted' ? 'bg-yellow-900/50 text-yellow-400 border border-yellow-800' :
								 'bg-gray-700 text-gray-400 border border-gray-600'}">
								{FORMAT_LABELS[fmt] ?? fmt} · {status === 'Legal' ? '✓' : status === 'Banned' ? '✗' : status}
							</span>
						{/each}
					</div>
				</div>
			{/if}

			<div class="border-t border-gray-700 pt-4">
				<button
					onclick={() => (showModal = true)}
					class="w-full py-3 rounded-xl font-semibold text-sm transition-colors bg-amber-500 hover:bg-amber-400 text-gray-950"
				>
					+ Ajouter à ma collection
				</button>
			</div>
		</div>
	</div>
</div>

{#if showModal}
	<AddToCollectionModal
		card={card}
		onclose={() => (showModal = false)}
		onadded={() => {
			showModal = false;
			toast = 'Carte ajoutée à la collection !';
			setTimeout(() => (toast = null), 2500);
		}}
	/>
{/if}

{#if toast}
	<div class="fixed bottom-6 right-6 bg-green-700 text-white px-5 py-3 rounded-xl shadow-lg text-sm font-medium">
		{toast}
	</div>
{/if}
