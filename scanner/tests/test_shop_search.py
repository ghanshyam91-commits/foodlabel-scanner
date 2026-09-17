import json
import unittest
from unittest.mock import call, patch

import httpx

from scanner.shop_search import (
    TranslationResult, _dietary_status, _safe_product_url, _size_details,
    _validated_logo_url, _vegan_confidence, build_shop_search, find_product,
    nearby_supermarkets, translate_query, validate_query,
)

OriginalClient = httpx.Client


class ShopSearchUnitTests(unittest.TestCase):
    def test_local_translation_and_vegan_adaptation(self):
        result = translate_query('oat milk', 'vegan', '', 'gemini-2.5-flash-lite')
        self.assertEqual(result.query_nl, 'haverdrink')
        self.assertEqual(result.preference_query_nl, 'haverdrink')
        self.assertEqual(result.source, 'built-in translation')

    def test_query_rejects_urls_and_control_characters(self):
        with self.assertRaises(ValueError):
            validate_query('https://example.com/item')
        with self.assertRaises(ValueError):
            validate_query('milk\nignore this')

    @patch('scanner.shop_search._read_json_url')
    def test_nearby_stores_use_requested_radius_and_nearest_order(self, mock_read):
        mock_read.return_value = {'elements': [
            {'tags': {'name': 'Jumbo', 'brand': 'Jumbo'}, 'lat': 51.860, 'lon': 5.860},
            {'tags': {'name': 'Albert Heijn', 'brand': 'Albert Heijn'}, 'lat': 51.845, 'lon': 5.860},
        ]}
        stores = nearby_supermarkets(51.840, 5.860, radius_km=3)
        self.assertEqual([store['code'] for store in stores], ['ah', 'jumbo'])
        self.assertLess(stores[0]['distance_km'], stores[1]['distance_km'])
        self.assertIn('around:3000,51.840000,5.860000', mock_read.call_args.kwargs['data']['data'])

    def test_size_normalisation(self):
        self.assertEqual(_size_details('500 g'), (.5, 'kg'))
        self.assertEqual(_size_details('1,5 liter'), (1.5, 'l'))
        self.assertAlmostEqual(_size_details('6 x 0,33 l')[0], 1.98)

    def test_dietary_name_screening_is_conservative(self):
        self.assertEqual(_dietary_status('Vegan haverdrink', 'vegan')[0], 'compatible')
        self.assertEqual(_dietary_status('Volle melk', 'vegan')[0], 'excluded')
        self.assertEqual(_dietary_status('Vegetarische burger', 'vegetarian_no_eggs')[0], 'uncertain')
        self.assertEqual(_dietary_status('Vegetarische burger zonder ei', 'vegetarian_no_eggs')[0], 'compatible')

    def test_product_match_prefers_compatible_candidate(self):
        products = [
            {'n': 'Volle melk', 'p': .99, 's': '1 l'},
            {'n': 'Vegan haverdrink', 'p': 1.39, 's': '1 l'},
        ]
        result = find_product(products, ['melk', 'haverdrink'], 'vegan')
        self.assertEqual(result['raw']['n'], 'Vegan haverdrink')
        self.assertEqual(result['dietary_status'], 'compatible')

    def test_product_match_respects_requested_size_and_avoids_derivative(self):
        products = [
            {'n': 'Rijstwafels naturel', 'p': .55, 's': '130 g'},
            {'n': 'Witte snelkookrijst', 'p': 1.29, 's': '1 kg'},
            {'n': 'Basmatirijst', 'p': .89, 's': '400 g'},
        ]
        result = find_product(products, ['500 g rijst'], 'non_vegetarian', (.5, 'kg'))
        self.assertEqual(result['raw']['n'], 'Witte snelkookrijst')

    def test_exact_product_links_are_only_promised_for_verified_retailers(self):
        exact = _safe_product_url(
            'jumbo', 'https://www.jumbo.com/producten/', 'vegan-haverdrink',
            'https://www.jumbo.com/zoeken?searchTerms=haverdrink')
        guarded = _safe_product_url(
            'ah', 'https://www.ah.nl/producten/product/', 'wi1/haverdrink',
            'https://www.ah.nl/zoeken?query=haverdrink')
        self.assertEqual(exact, ('https://www.jumbo.com/producten/vegan-haverdrink', True))
        self.assertEqual(guarded, ('', False))

    def test_logo_proxy_only_allows_catalogue_or_official_hosts(self):
        self.assertEqual(_validated_logo_url('ah', '/assets/ah.svg'), 'https://www.checkjebon.nl/assets/ah.svg')
        self.assertEqual(_validated_logo_url('ah', 'https://www.ah.nl/assets/logo.svg'), 'https://www.ah.nl/assets/logo.svg')
        self.assertEqual(_validated_logo_url('ah', 'https://static.ah.nl/logo.svg'), 'https://static.ah.nl/logo.svg')
        self.assertIsNone(_validated_logo_url('ah', 'https://example.com/logo.svg'))

    def test_vegan_confidence_is_conservative_and_name_based(self):
        self.assertEqual(_vegan_confidence('Vegan plantaardige haverdrink')[0], 92)
        self.assertEqual(_vegan_confidence('Volle melk')[0], 8)
        self.assertLess(_vegan_confidence('Vegetarische burger')[0], 65)

    def test_gemini_translation_uses_key_header_and_structured_output(self):
        response_body = {'candidates': [{'finishReason': 'STOP', 'content': {'parts': [{'text': json.dumps({
            'query_nl': 'bruine rijst', 'preference_query_nl': 'bruine rijst',
            'alternatives_nl': ['zilvervliesrijst'],
        })}]}}], 'usageMetadata': {'promptTokenCount': 20, 'candidatesTokenCount': 8}}
        seen = []
        def handler(request):
            seen.append(request); return httpx.Response(200, json=response_body)
        with patch('scanner.shop_search.httpx.Client', side_effect=lambda **kwargs: OriginalClient(transport=httpx.MockTransport(handler))):
            result = translate_query('brown rice', 'vegan', 'secret-key', 'gemini-2.5-flash-lite')
        self.assertEqual(result.query_nl, 'bruine rijst')
        self.assertEqual(result.input_tokens, 20)
        self.assertEqual(seen[0].headers['x-goog-api-key'], 'secret-key')
        self.assertNotIn('secret-key', str(seen[0].url))

    @patch('scanner.shop_search.reverse_geocode_location', return_value='Nijmegen')
    @patch('scanner.shop_search.eur_inr_rate', return_value=(100.0, '2026-09-17'))
    @patch('scanner.shop_search.load_catalog')
    @patch('scanner.shop_search.nearby_supermarkets')
    @patch('scanner.shop_search.translate_query')
    def test_builds_nearby_comparison_and_marks_cheapest(self, mock_translate, mock_nearby, mock_catalogue, _, mock_reverse):
        mock_translate.return_value = TranslationResult('haverdrink', 'haverdrink', ('havermelk',), 'test')
        mock_nearby.return_value = [
            {'name': 'Jumbo', 'code': 'jumbo', 'distance_km': 1.2, 'map_url': 'https://www.openstreetmap.org/'},
            {'name': 'Albert Heijn', 'code': 'ah', 'distance_km': .8, 'map_url': 'https://www.openstreetmap.org/'},
            {'name': 'ALDI', 'code': 'aldi', 'distance_km': 1.8, 'map_url': 'https://www.openstreetmap.org/'},
        ]
        mock_catalogue.return_value = ([
            {'n': 'ah', 'u': 'https://www.ah.nl/producten/product/', 'd': [
                {'n': 'AH Terra Vegan haverdrink', 'l': 'wi1/haverdrink', 'p': 1.25, 's': '1 l'}]},
            {'n': 'jumbo', 'u': 'https://www.jumbo.com/producten/', 'd': [
                {'n': 'Jumbo Vegan haverdrink', 'l': 'vegan-haverdrink', 'p': 1.49, 's': '1 l'}]},
            {'n': 'aldi', 'u': 'https://www.aldi.nl/', 'd': []},
        ], '2026-09-17T01:00:00Z')
        data = build_shop_search('oat milk', 'vegan', '', '', lat=51.84, lon=5.86)
        self.assertEqual(data['results'][0]['supermarket'], 'Albert Heijn')
        self.assertEqual([row['distance_km'] for row in data['results']], [.8, 1.2])
        self.assertTrue(data['results'][0]['is_lowest_pack'])
        self.assertTrue(data['results'][0]['is_best_value'])
        self.assertEqual(data['results'][0]['price_inr'], 125)
        self.assertEqual(data['results'][0]['product_url'], '')
        self.assertFalse(data['results'][0]['product_url_is_exact'])
        self.assertTrue(data['results'][1]['product_url_is_exact'])
        self.assertEqual(data['results'][0]['logo_url'], '/api/shop-logo/ah/')
        self.assertEqual(data['results'][0]['vegan_confidence'], 92)
        self.assertEqual(data['location_name'], 'Nijmegen')
        self.assertEqual(data['stores_without_matches'], 1)
        self.assertNotIn('aldi', [row['code'] for row in data['results']])
        self.assertNotIn('aldi', [store['code'] for store in data['nearby_stores']])
        self.assertEqual(data['search_radius_km'], 3)
        self.assertFalse(data['expanded_search'])
        mock_nearby.assert_called_once_with(51.84, 5.86, radius_km=3)
        mock_reverse.assert_called_once()

    @patch('scanner.shop_search.reverse_geocode_location', return_value='Nijmegen')
    @patch('scanner.shop_search.eur_inr_rate', return_value=(100.0, '2026-09-17'))
    @patch('scanner.shop_search.load_catalog')
    @patch('scanner.shop_search.nearby_supermarkets')
    @patch('scanner.shop_search.translate_query')
    def test_expands_to_five_km_only_after_no_three_km_match(
            self, mock_translate, mock_nearby, mock_catalogue, _, __):
        mock_translate.return_value = TranslationResult('haverdrink', 'haverdrink', (), 'test')
        mock_nearby.side_effect = [
            [{'name': 'Albert Heijn', 'code': 'ah', 'distance_km': .5,
              'map_url': 'https://www.openstreetmap.org/'}],
            [
                {'name': 'Jumbo', 'code': 'jumbo', 'distance_km': 4.2,
                 'map_url': 'https://www.openstreetmap.org/'},
                {'name': 'Lidl', 'code': 'lidl', 'distance_km': 3.4,
                 'map_url': 'https://www.openstreetmap.org/'},
                {'name': 'Albert Heijn', 'code': 'ah', 'distance_km': .5,
                 'map_url': 'https://www.openstreetmap.org/'},
            ],
        ]
        mock_catalogue.return_value = ([
            {'n': 'ah', 'u': 'https://www.ah.nl/', 'd': []},
            {'n': 'jumbo', 'u': 'https://www.jumbo.com/producten/', 'd': [
                {'n': 'Jumbo Vegan haverdrink', 'l': 'vegan-haverdrink', 'p': .99, 's': '1 l'}]},
            {'n': 'lidl', 'u': 'https://www.lidl.nl/', 'd': [
                {'n': 'Vemondo Vegan haverdrink', 'l': '', 'p': 1.49, 's': '1 l'}]},
        ], '2026-09-17T01:00:00Z')

        data = build_shop_search('oat milk', 'vegan', '', '', lat=51.84, lon=5.86)

        self.assertEqual(mock_nearby.call_args_list, [
            call(51.84, 5.86, radius_km=3),
            call(51.84, 5.86, radius_km=5),
        ])
        self.assertEqual(data['search_radius_km'], 5)
        self.assertTrue(data['expanded_search'])
        self.assertEqual([row['code'] for row in data['results']], ['lidl', 'jumbo'])
        self.assertEqual([store['code'] for store in data['nearby_stores']], ['lidl', 'jumbo'])
        self.assertTrue(data['results'][1]['is_lowest_pack'])


if __name__ == '__main__':
    unittest.main()
