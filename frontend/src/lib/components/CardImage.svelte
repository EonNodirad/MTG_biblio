<script lang="ts">
	let {
		scryfallId,
		size = 'normal',
		alt = 'Card image',
		class: cls = ''
	}: {
		scryfallId: string | null | undefined;
		size?: 'small' | 'normal' | 'large' | 'art_crop' | 'border_crop';
		alt?: string;
		class?: string;
	} = $props();

	// https://scryfall.com/docs/api/images
	// URL: https://cards.scryfall.io/{size}/front/{c1}/{c2}/{id}.jpg
	const src = $derived(
		scryfallId
			? `https://cards.scryfall.io/${size}/front/${scryfallId[0]}/${scryfallId[1]}/${scryfallId}.jpg`
			: null
	);

	let failed = $state(false);
</script>

{#if src && !failed}
	<img
		{src}
		{alt}
		onerror={() => (failed = true)}
		class={cls}
		loading="lazy"
	/>
{:else}
	<div class="flex items-center justify-center bg-gray-700 text-gray-500 text-xs rounded {cls}">
		No image
	</div>
{/if}
