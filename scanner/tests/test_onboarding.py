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
                       'product-search-form', 'manual-location', 'shop-result-list']:
            self.assertIn(marker, html)
        self.assertNotIn('id="consent"', html)

    def test_scan_ui_is_centered_icon_first_and_has_no_emoji_navigation(self):
        root = Path(__file__).parents[1]
        html = (root / 'templates/scanner/index.html').read_text()
        script = (root / 'static/scanner/app.js').read_text()
        self.assertIn('class="scan-orb"', html)
        self.assertIn('class="scan-viewfinder"', html)
        self.assertIn('class="icon-button top-settings"', html)
        self.assertNotIn('id="analyze-button"', html)
        for emoji in ['⚙', '⌂', '▤', '⌗']:
            self.assertNotIn(emoji, html)
        self.assertIn('await scan();', script)


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
