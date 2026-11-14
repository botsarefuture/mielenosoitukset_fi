import type { AppConfig } from './config';
import type { CitiesData } from './cities';
import { findCity, groupCities } from './cities';
import type { Page } from '../components/listings/types';
import type { RouteMeta } from './routes';

export function citiesMeta(config: AppConfig, data: CitiesData | null, filtered: boolean): RouteMeta {
  return { title: 'Kaupungit | Mielenosoitukset.fi', description: 'Selaa mielenosoituksia kaupungeittain ja katso, missä järjestetään mielenosoituksia tänään.',
    canonical: `${config.origin}/cities`, robots: !data ? 'noindex, follow' : filtered ? 'noindex, follow' : 'index, follow' };
}

export function todayMeta(config: AppConfig, value?: string): RouteMeta {
  const city = value ? findCity(value) : undefined;
  const place = city?.phrase ?? 'Suomessa';
  return { title: `Mielenosoitukset ${place} tänään | Mielenosoitukset.fi`,
    description: `Tänään järjestettävät mielenosoitukset ${place}. Katso ajat, paikat ja aiheet yhdestä näkymästä.`,
    canonical: `${config.origin}${city ? `/city/${city.key}/tanaan` : '/mielenosoitukset-tanaan'}`, robots: 'index, follow' };
}

export function discoveryStructuredData(meta: RouteMeta, items: { name: string; url: string }[]) {
  return { '@context': 'https://schema.org', '@type': 'CollectionPage', name: meta.title,
    description: meta.description, url: meta.canonical,
    mainEntity: { '@type': 'ItemList', itemListElement: items.map((item, index) => ({ '@type': 'ListItem', position: index + 1, name: item.name, url: item.url })) } };
}

export function cityItems(config: AppConfig, data: CitiesData | null) {
  return groupCities(data?.cities ?? []).flatMap(group => group.cities.map(city => ({ name: city.name, url: `${config.origin}/city/${city.key}` })));
}

export function todayItems(config: AppConfig, page: Page | null) {
  return (page?.results ?? []).map(event => ({ name: event.title ?? 'Mielenosoitus',
    url: new URL(event.detail_url ?? `/demonstration/${event._id}`, config.origin).href }));
}
