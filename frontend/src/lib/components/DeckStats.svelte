<script lang="ts">
	import type { DeckEntry, CardDetail } from '$lib/api';

	let {
		entries,
		cardCache
	}: {
		entries: DeckEntry[];
		cardCache: Record<string, CardDetail>;
	} = $props();

	const COLOR_META: { key: string; label: string; bg: string; border: string }[] = [
		{ key: 'W', label: 'Blanc',  bg: 'bg-yellow-100', border: 'border-yellow-300' },
		{ key: 'U', label: 'Bleu',   bg: 'bg-blue-500',   border: 'border-blue-400' },
		{ key: 'B', label: 'Noir',   bg: 'bg-gray-800',   border: 'border-gray-500' },
		{ key: 'R', label: 'Rouge',  bg: 'bg-red-600',    border: 'border-red-500' },
		{ key: 'G', label: 'Vert',   bg: 'bg-green-600',  border: 'border-green-500' },
		{ key: 'C', label: 'Incolore', bg: 'bg-gray-400', border: 'border-gray-300' },
	];

	const TYPE_GROUPS = [
		{ label: 'Créatures',           test: (t: string) => t.includes('Creature') },
		{ label: 'Éphémères & Rituels', test: (t: string) => /Instant|Sorcery/.test(t) },
		{ label: 'Planeswalkers',       test: (t: string) => t.includes('Planeswalker') },
		{ label: 'Artefacts',           test: (t: string) => t.includes('Artifact') && !t.includes('Creature') },
		{ label: 'Enchantements',       test: (t: string) => t.includes('Enchantment') && !t.includes('Creature') },
		{ label: 'Terrains',            test: (t: string) => t.includes('Land') },
		{ label: 'Autres',              test: () => true },
	];

	// Mana curve: CMC 0–7+
	const manaCurve = $derived.by(() => {
		const counts = Array(8).fill(0); // index = CMC, index 7 = "7+"
		for (const e of entries) {
			const card = cardCache[e.card_uuid];
			if (!card) continue;
			if (card.type?.includes('Land')) continue; // exclude lands from curve
			const cmc = Math.min(Math.round(card.manaValue ?? 0), 7);
			counts[cmc] += e.quantity;
		}
		return counts;
	});

	const maxCurve = $derived(Math.max(...manaCurve, 1));

	// Type breakdown
	const typeCounts = $derived.by(() => {
		const result: Record<string, number> = {};
		for (const group of TYPE_GROUPS) result[group.label] = 0;
		for (const e of entries) {
			const card = cardCache[e.card_uuid];
			const type = card?.type ?? '';
			const group = TYPE_GROUPS.find((g) => g.test(type)) ?? TYPE_GROUPS[TYPE_GROUPS.length - 1];
			result[group.label] += e.quantity;
		}
		return result;
	});

	// Color counts via colorIdentity
	const colorCounts = $derived.by(() => {
		const counts: Record<string, number> = { W: 0, U: 0, B: 0, R: 0, G: 0, C: 0 };
		for (const e of entries) {
			const card = cardCache[e.card_uuid];
			if (!card) continue;
			const ci: string[] = Array.isArray(card.colorIdentity) ? card.colorIdentity : [];
			if (ci.length === 0) {
				counts['C'] += e.quantity;
			} else {
				for (const c of ci) if (c in counts) counts[c] += e.quantity;
			}
		}
		return counts;
	});

	const totalCards = $derived(entries.reduce((s, e) => s + e.quantity, 0));
</script>

<div class="space-y-5">
	<!-- Total -->
	<div class="text-sm text-gray-400">
		<span class="text-white font-semibold text-base">{totalCards}</span> cartes
	</div>

	<!-- Mana curve -->
	<div>
		<p class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Courbe de mana</p>
		<div class="flex items-end gap-1 h-16">
			{#each manaCurve as count, cmc}
				<div class="flex-1 flex flex-col items-center gap-0.5">
					<span class="text-[10px] text-gray-500 leading-none">{count || ''}</span>
					<div
						class="w-full rounded-t bg-amber-500 transition-all duration-300 min-h-0"
						style="height: {count > 0 ? Math.max((count / maxCurve) * 48, 4) : 0}px"
					></div>
					<span class="text-[10px] text-gray-500">{cmc === 7 ? '7+' : cmc}</span>
				</div>
			{/each}
		</div>
	</div>

	<!-- Color identity -->
	<div>
		<p class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Couleurs</p>
		<div class="flex gap-2 flex-wrap">
			{#each COLOR_META as c}
				{#if colorCounts[c.key] > 0}
					<div class="flex items-center gap-1.5">
						<span class="w-4 h-4 rounded-full border {c.bg} {c.border} inline-block shrink-0"></span>
						<span class="text-xs text-gray-300">{colorCounts[c.key]}</span>
					</div>
				{/if}
			{/each}
		</div>
	</div>

	<!-- Type breakdown -->
	<div>
		<p class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Types</p>
		<div class="space-y-1">
			{#each TYPE_GROUPS as g}
				{#if typeCounts[g.label] > 0}
					<div class="flex items-center justify-between text-sm">
						<span class="text-gray-400">{g.label}</span>
						<span class="text-white font-semibold">{typeCounts[g.label]}</span>
					</div>
				{/if}
			{/each}
		</div>
	</div>
</div>
