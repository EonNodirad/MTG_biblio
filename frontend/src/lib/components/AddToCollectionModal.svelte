<script lang="ts">
	import { addToCollection } from '$lib/api';
	import type { CardSummary, CardDetail } from '$lib/api';

	let {
		card,
		onclose,
		onadded
	}: {
		card: CardSummary | CardDetail;
		onclose: () => void;
		onadded: () => void;
	} = $props();

	const conditions = ['NM', 'LP', 'MP', 'HP', 'DMG'];
	let quantity = $state(1);
	let foil = $state(false);
	let condition = $state('NM');
	let loading = $state(false);

	async function submit() {
		loading = true;
		await addToCollection({ card_uuid: card.uuid, quantity, foil, condition });
		loading = false;
		onadded();
	}

	function backdrop(e: MouseEvent) {
		if (e.target === e.currentTarget) onclose();
	}
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
	class="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4"
	onclick={backdrop}
	onkeydown={(e) => e.key === 'Escape' && onclose()}
>
	<div class="bg-gray-800 border border-gray-700 rounded-2xl p-6 w-full max-w-sm space-y-5 shadow-2xl">
		<div class="flex items-start justify-between">
			<div>
				<h2 class="font-bold text-white text-lg leading-tight">{card.name}</h2>
				<p class="text-xs text-gray-400 mt-0.5">{(card as any).setCode ?? ''} · {(card as any).type ?? ''}</p>
			</div>
			<button onclick={onclose} class="text-gray-500 hover:text-white text-xl leading-none">✕</button>
		</div>

		<!-- Quantity -->
		<div class="space-y-1">
			<label class="text-xs font-semibold text-gray-400 uppercase tracking-wide">Quantité</label>
			<div class="flex items-center gap-3">
				<button
					onclick={() => (quantity = Math.max(1, quantity - 1))}
					class="w-8 h-8 rounded-full bg-gray-700 hover:bg-gray-600 text-white font-bold text-lg flex items-center justify-center"
				>−</button>
				<span class="text-xl font-bold text-white w-8 text-center">{quantity}</span>
				<button
					onclick={() => quantity++}
					class="w-8 h-8 rounded-full bg-gray-700 hover:bg-gray-600 text-white font-bold text-lg flex items-center justify-center"
				>+</button>
			</div>
		</div>

		<!-- Condition -->
		<div class="space-y-1">
			<label class="text-xs font-semibold text-gray-400 uppercase tracking-wide">État</label>
			<div class="flex gap-2 flex-wrap">
				{#each conditions as c}
					<button
						onclick={() => (condition = c)}
						class="px-3 py-1 rounded-lg text-sm font-medium transition-colors
							{condition === c ? 'bg-amber-500 text-gray-950' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'}"
					>{c}</button>
				{/each}
			</div>
		</div>

		<!-- Foil -->
		<label class="flex items-center gap-3 cursor-pointer select-none">
			<div
				class="w-10 h-6 rounded-full transition-colors relative {foil ? 'bg-purple-600' : 'bg-gray-700'}"
				onclick={() => (foil = !foil)}
				role="switch"
				aria-checked={foil}
				tabindex="0"
				onkeydown={(e) => e.key === ' ' && (foil = !foil)}
			>
				<div class="absolute top-1 w-4 h-4 rounded-full bg-white shadow transition-transform {foil ? 'left-5' : 'left-1'}"></div>
			</div>
			<span class="text-sm text-gray-300">Foil ✨</span>
		</label>

		<button
			onclick={submit}
			disabled={loading}
			class="w-full py-3 bg-amber-500 hover:bg-amber-400 disabled:opacity-50 text-gray-950 font-bold rounded-xl transition-colors"
		>
			{loading ? 'Ajout...' : `Ajouter ${quantity}× à ma collection`}
		</button>
	</div>
</div>
