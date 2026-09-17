import io
from pathlib import Path
from unittest import TestCase
from PIL import Image
from pillow_heif import register_heif_opener
from scanner.images import prepare_image, ImageInputError
from scanner.demo import demo_label
from scanner.rules import assess


class PreferenceTests(TestCase):
    def test_nonvegetarian_does_not_exclude_gelatin(self):
        result = assess(demo_label('sweets'), 'non_vegetarian')
        self.assertEqual(result['verdict'], 'non_vegetarian')
        self.assertNotEqual(result['preference_match'], 'no')

    def test_nonvegetarian_keeps_uncertainty(self):
        result = assess(demo_label('bread'), 'non_vegetarian')
        self.assertEqual(result['preference_match'], 'uncertain')

    def test_unknown_preference_rejected(self):
        with self.assertRaises(ValueError):
            assess(demo_label('oats'), 'anything')

    def test_ui_has_onboarding_settings_and_native_capture(self):
        html = (Path(__file__).parents[1] / 'templates/scanner/index.html').read_text()
        for marker in ['onboarding-dialog', 'settings-page', 'remember-consent',
                       'scan-launch', 'scan-dialog', 'capture="environment"', '.heic,.heif',
                       'product-search-form', 'location-dialog', 'location-input', 'shop-result-list',
                       'buy-list-groups', 'buy-list-count', 'clear-bought']:
            self.assertIn(marker, html)
        self.assertNotIn('id="consent"', html)

    def test_scan_ui_is_centered_icon_first_and_has_no_emoji_navigation(self):
        root = Path(__file__).parents[1]
        html = (root / 'templates/scanner/index.html').read_text()
        script = (root / 'static/scanner/app.js').read_text()
        style = (root / 'static/scanner/lavender.css').read_text()
        self.assertIn('id="scan-launch" class="scan-launch"', html)
        self.assertIn('class="scan-viewfinder"', html)
        self.assertIn('class="icon-button top-settings"', html)
        self.assertIn('id="header-preference"', html)
        self.assertIn('id="header-location"', html)
        self.assertIn('<symbol id="i-bag"', html)
        self.assertIn('<span>My List</span>', html)
        self.assertIn('id="result-confidence"', html)
        self.assertIn('id="result-check-summary"', html)
        self.assertIn('class="result result-popup"', html)
        self.assertIn('class="verdict-card minimal-verdict"', html)
        self.assertNotIn('id="ingredients-list"', html)
        self.assertNotIn('id="result-explanation"', html)
        self.assertNotIn('id="search-scope"', html)
        self.assertNotIn('id="price-update"', html)
        self.assertNotIn('class="home-scan"', html)
        self.assertIn('@keyframes navScanGlow', style)
        self.assertIn('@keyframes selectedNavGlow', style)
        self.assertIn("externalLink('Open directions'", script)
        self.assertNotIn('Free local mode: Tesseract', script)
        self.assertIn('position: sticky', style)
        self.assertNotIn('id="analyze-button"', html)
        for emoji in ['⚙', '⌂', '▤', '⌗']:
            self.assertNotIn(emoji, html)
        self.assertIn('await scan();', script)

    def test_home_ui_keeps_only_core_search_content(self):
        html = (Path(__file__).parents[1] / 'templates/scanner/index.html').read_text()
        self.assertIn('Find the best price', html)
        self.assertIn('Search groceries in English', html)
        self.assertIn('Compare prices', html)
        self.assertNotIn('YOUR NETHERLANDS GROCERY COMPANION', html)
        self.assertNotIn('A little clarity.', html)
        self.assertNotIn('Search in English. Shop in Dutch.', html)
        self.assertNotIn('Trending verified picks', html)
        self.assertNotIn('Aisle tip:', html)
        self.assertNotIn('id="use-location"', html)
        self.assertNotIn('class="search-location-row"', html)
        self.assertIn('id="header-location-label" aria-live="polite">Nijmegen', html)


class HeicTests(TestCase):
    def test_heic_to_metadata_free_jpeg(self):
        register_heif_opener()
        data = io.BytesIO()
        photo = Image.new('RGB', (320, 240), 'purple')
        exif = Image.Exif()
        exif[270] = 'private metadata'
        photo.save(data, format='HEIF', exif=exif)
        with Image.open(io.BytesIO(prepare_image(data.getvalue()))) as result:
            self.assertEqual(result.format, 'JPEG')
            self.assertEqual(result.size, (320, 240))
            self.assertFalse(result.getexif())

    def test_corrupt_heic_rejected(self):
        with self.assertRaises(ImageInputError):
            prepare_image(b'\x00\x00\x00\x18ftypheic' + b'bad data' * 30)
