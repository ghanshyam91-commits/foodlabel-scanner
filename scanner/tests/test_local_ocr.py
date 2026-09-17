from unittest.mock import patch
from django.test import SimpleTestCase
from scanner.local_ocr import extract_label_local
from scanner.tests.test_images import image_bytes

class LocalOcrTests(SimpleTestCase):
    @patch('scanner.local_ocr.pytesseract.image_to_string',return_value='INGREDIËNTEN: water, suiker, melk.\nVoedingswaarde per 100 ml')
    def test_reads_translates_and_structures_dutch_label(self,_):
        result=extract_label_local(image_bytes())
        self.assertEqual(result.provider,'Tesseract local OCR')
        self.assertEqual([i.english for i in result.label.ingredients],['water','sugar','milk'])
        self.assertTrue(result.label.ingredients_complete)
