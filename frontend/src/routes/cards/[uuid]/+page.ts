import { getCard } from '$lib/api';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ params }) => {
	const card = await getCard(params.uuid);
	return { card };
};
