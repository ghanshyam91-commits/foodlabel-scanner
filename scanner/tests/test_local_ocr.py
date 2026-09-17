from unittest.mock import patch
from django.test import SimpleTestCase
from scanner.local_ocr import extract_label_local
from scanner.tests.test_images import image_bytes

class LocalOcrTests(SimpleTestCase):
    @patch('scanner.local_ocr.pytesseract.image_to_data')
    @patch('scanner.local_ocr.pytesseract.image_to_string',return_value='water, suiker, melk.')
    def test_reads_translates_and_structures_dutch_label(self,_,mock_data):
        values = ['Pack', 'contains', '1', 'serve', 'INGREDIËNTEN', 'water,', 'suiker,', 'melk.',
                  'Allergen', 'Note;', 'Contains', 'Wheat', '&', 'Nut.', 'May', 'contain', 'Milk.']
        tops = [10] * 4 + [40] + [80] * 3 + [120] * 6 + [150] * 3
        blocks = [1] * 4 + [2] + [3] * 3 + [4] * 6 + [5] * 3
        mock_data.return_value = {
            'text': values, 'conf': ['95'] * len(values),
            'left': [20 + (index % 6) * 55 for index in range(len(values))], 'top': tops,
            'width': [50] * len(values), 'height': [15] * len(values),
            'block_num': blocks, 'par_num': [1] * len(values), 'line_num': [1] * len(values),
        }
        result=extract_label_local(image_bytes())
        self.assertEqual(result.provider,'Tesseract local OCR')
        self.assertEqual([i.english for i in result.label.ingredients],['water','sugar','milk'])
        self.assertTrue(result.label.ingredients_complete)
        self.assertGreaterEqual(result.confidence,90)
        self.assertEqual(result.label.contains, ['Wheat', 'Nut'])
        self.assertEqual(result.label.may_contain, ['Milk'])
