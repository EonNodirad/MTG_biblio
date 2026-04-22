// Plain module-level object — persists in memory for the entire browser session.
// Initialized once when the module loads; the collection page reads it on mount
// and writes back via $effect, so filters survive navigation.

export const collectionFilters = $state({
	search:          '' as string,
	filterColors:    new Set<string>(),
	colorMatch:      'any' as 'any' | 'all' | 'exact' | 'exclude',
	filterRarities:  new Set<string>(),
	filterTypes:     new Set<string>(),
	filterText:      '' as string,
	filterSubtype:   '' as string,
	filterLegendary: false,
	filterFormat:    '' as string,
	cmcMin:          null as number | null,
	cmcMax:          null as number | null,
	showAdvanced:    false,
	sortKey:         'name' as 'name' | 'cmc' | 'rarity' | 'color' | 'set' | 'price',
	sortAsc:         true,
	viewMode:        'grid' as 'list' | 'grid',
});
