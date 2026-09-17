"""Free, local OCR fallback. It never sends the image to another service.

Food packaging commonly places a nutrition table beside the ingredients paragraph. A
single page-segmentation pass reads both columns together and produces convincing-looking
garbage. The layout pass below locates the ingredients heading, masks an adjacent nutrition
column when one is detected, and then performs a focused OCR pass on the label section.
"""
import io
import re
import unicodedata
from statistics import fmean
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import pytesseract
from pytesseract import Output, TesseractError, TesseractNotFoundError
from .provider import ExtractionResult, ProviderError
from .schema import Ingredient, LabelExtraction

TRANSLATIONS = {
    'water':'water','suiker':'sugar','zout':'salt','zeezout':'sea salt','rijst':'rice',
    'haver':'oats','havervlokken':'oat flakes','tarwe':'wheat','tarwebloem':'wheat flour',
    'tarwemeel':'wheat flour','bloem':'flour','mais':'corn','maiszetmeel':'corn starch',
    'aardappelzetmeel':'potato starch','aardappelen':'potatoes','soja':'soy','sojabonen':'soybeans',
    'erwteneiwit':'pea protein','linzen':'lentils','kikkererwten':'chickpeas','bonen':'beans',
    'tomaat':'tomato','tomaten':'tomatoes','tomatenpuree':'tomato puree','ui':'onion',
    'uien':'onions','knoflook':'garlic','wortel':'carrot','paprika':'bell pepper',
    'spinazie':'spinach','komkommer':'cucumber','champignons':'mushrooms','citroen':'lemon',
    'citroensap':'lemon juice','appel':'apple','banaan':'banana','aardbeien':'strawberries',
    'kokos':'coconut','kokosmelk':'coconut milk','kokosolie':'coconut oil','cacaoboter':'cocoa butter',
    'cacaopoeder':'cocoa powder','cacaomassa':'cocoa mass','olijfolie':'olive oil',
    'zonnebloemolie':'sunflower oil','koolzaadolie':'rapeseed oil','palmolie':'palm oil',
    'amandelen':'almonds','hazelnoten':'hazelnuts','walnoten':'walnuts','pinda’s':'peanuts',
    "pinda's":'peanuts','cashewnoten':'cashews','sesamzaad':'sesame seeds','peper':'pepper',
    'kaneel':'cinnamon','kurkuma':'turmeric','gember':'ginger','azijn':'vinegar',
    'citroenzuur':'citric acid','melk':'milk','melkpoeder':'milk powder','room':'cream',
    'boter':'butter','melkeiwit':'milk protein','lactose':'lactose','yoghurt':'yogurt',
    'ei':'egg','eieren':'eggs','eigeel':'egg yolk','eipoeder':'egg powder','honing':'honey',
    'kip':'chicken','rundvlees':'beef','varkensvlees':'pork','lamsvlees':'lamb','vlees':'meat',
    'spek':'bacon','gelatine':'gelatin','vis':'fish','zalm':'salmon','tonijn':'tuna',
    'garnalen':'shrimp','vissaus':'fish sauce','kaas':'cheese','wei':'whey','aroma':'flavouring',
}
STOP = re.compile(
    r'\b(?:allergen(?:en|s)?(?:\s+note)?|may\s+contain|kan\s+bevatten|bewaaradvies|storage(?:\s+advice)?|bereiding|netto)\b',
    re.I,
)
HEADER = re.compile(r'^ingredient(?:en|s)?$', re.I)
NUTRITION_HEADER = re.compile(r'^(?:nutrition(?:al)?|voedingswaarde)$', re.I)
NUTRITION_FOOTER_WORDS = {
    'guideline', 'daily', 'amounts', 'average', 'adult', 'kcal',
    'referentieinname', 'dagelijkse', 'hoeveelheden',
}


def _word_key(value: str) -> str:
    folded = unicodedata.normalize('NFKD', value.casefold())
    return re.sub(r'[^a-z]', '', ''.join(char for char in folded if not unicodedata.combining(char)))


def _is_ingredient_header(value: str) -> bool:
    # Glare commonly changes the first few capital letters while leaving "dients" intact.
    return bool(HEADER.fullmatch(value) or (len(value) >= 8 and value.endswith(('dients', 'dienten'))))


def _prepared_image(source: Image.Image) -> tuple[Image.Image, int]:
    prepared = ImageOps.autocontrast(ImageOps.grayscale(source))
    scale = 2 if max(prepared.size) < 2000 else 1
    if scale > 1:
        prepared = prepared.resize(
            (prepared.width * scale, prepared.height * scale), Image.Resampling.LANCZOS)
    prepared = ImageEnhance.Contrast(prepared).enhance(1.6).filter(ImageFilter.SHARPEN)
    return prepared, scale


def _ocr_records(prepared: Image.Image) -> tuple[list[dict], str]:
    data = pytesseract.image_to_data(
        prepared, lang='nld+eng', config='--oem 1 --psm 11',
        output_type=Output.DICT, timeout=30,
    )
    records = []
    lines: list[str] = []
    current_line = None
    current_words: list[str] = []
    for index, raw_value in enumerate(data.get('text', [])):
        value = str(raw_value or '').strip()
        try:
            confidence = float(data['conf'][index])
        except (KeyError, TypeError, ValueError, IndexError):
            confidence = -1
        if not value or confidence < 0:
            continue
        line = (data['block_num'][index], data['par_num'][index], data['line_num'][index])
        if current_line is not None and line != current_line and current_words:
            lines.append(' '.join(current_words))
            current_words = []
        current_line = line
        current_words.append(value)
        records.append({
            'text': value,
            'key': _word_key(value),
            'confidence': confidence,
            'left': int(data['left'][index]),
            'top': int(data['top'][index]),
            'width': int(data['width'][index]),
            'height': int(data['height'][index]),
        })
    if current_words:
        lines.append(' '.join(current_words))
    return records, '\n'.join(lines)[:12000]


def _section_bounds(records: list[dict], width: int, height: int, scale: int):
    exact_headers = [row for row in records if HEADER.fullmatch(row['key'])]
    weak_headers = [row for row in records
                    if _is_ingredient_header(row['key']) and row['confidence'] >= 35]
    content_start = False
    if exact_headers or weak_headers:
        header = max(exact_headers or weak_headers,
                     key=lambda row: (row['confidence'], len(row['text'])))
    else:
        # A curved/glossy heading may disappear while a component heading such as
        # "Noodles:" remains sharp. Use only a small allow-list with an explicit colon.
        anchors = [row for row in records if row['key'] in {'noodles', 'seasoning', 'masala'}
                   and ':' in row['text'] and row['confidence'] >= 50]
        if not anchors:
            return None
        header = min(anchors, key=lambda row: row['top'])
        content_start = True
    header_center = header['top'] + header['height'] / 2
    stops = [row for row in records if row['top'] > header_center and (
        row['key'].startswith('allergen') or row['key'].startswith('storage')
        or row['key'].startswith('bewaaradvies'))]
    stop_top = min((row['top'] for row in stops), default=height)

    nutrition = [row for row in records if row['top'] < stop_top
                 and row['left'] > header['left'] + 70 * scale
                 and NUTRITION_HEADER.fullmatch(row['key'])]
    nutrition_left = min((row['left'] for row in nutrition), default=None)
    nutrition_bottom = None
    if nutrition_left is not None:
        footer = [row['top'] + row['height'] for row in records
                  if header_center < row['top'] < stop_top
                  and row['left'] >= nutrition_left - 10 * scale
                  and row['key'] in NUTRITION_FOOTER_WORDS]
        if footer:
            nutrition_bottom = max(footer) + 2 * scale

    left = max(0, header['left'] - 25 * scale)
    top = min(height, header['top'] if content_start else header['top'] + header['height'])
    candidates = [row for row in records
                  if top <= row['top'] < stop_top and row['left'] >= left
                  and re.search(r'[A-Za-z0-9]', row['text'])
                  and not (nutrition_left is not None and nutrition_bottom is not None
                           and row['left'] >= nutrition_left - 10 * scale
                           and row['top'] < nutrition_bottom)]
    if not candidates:
        return None
    reliable_rights = sorted(row['left'] + row['width'] for row in candidates
                             if row['confidence'] >= 25)
    if reliable_rights:
        right = reliable_rights[min(len(reliable_rights) - 1, int(len(reliable_rights) * .97))]
    else:
        right = max(row['left'] + row['width'] for row in candidates)
    right = min(width, max(right + 25 * scale, left + 220 * scale))
    bottom = min(height, max(top + 80 * scale, stop_top))
    return left, top, right, bottom, nutrition_left, nutrition_bottom, candidates


def _clean_section(value: str) -> str:
    match = STOP.search(value)
    if match:
        value = value[:match.start()]
    lines = []
    started = False
    for raw_line in value.splitlines():
        line = re.sub(r'\s+', ' ', raw_line).strip(' \t|\\/_—-')
        if not re.search(r'[A-Za-z0-9]', line):
            continue
        # Short border artefacts frequently appear immediately beneath the heading.
        if not started and len(re.sub(r'[^A-Za-z]', '', line)) < 4:
            continue
        started = True
        lines.append(line)
    # A focused crop can still catch one or two characters from the next panel. When
    # the ingredient paragraph has a terminal full stop near the end, discard that tail.
    for index in range(len(lines) - 1, max(-1, len(lines) - 4), -1):
        if re.search(r'[.)\]]\s*$', lines[index]):
            lines = lines[:index + 1]
            break
    return '\n'.join(lines).strip()[:12000]


def _focused_ingredients(prepared: Image.Image, records: list[dict], scale: int, language: str):
    bounds = _section_bounds(records, prepared.width, prepared.height, scale)
    if not bounds:
        return '', None
    left, top, right, bottom, nutrition_left, nutrition_bottom, candidates = bounds
    region = prepared.crop((left, top, right, bottom))
    if nutrition_left is not None and nutrition_bottom is not None:
        # White is the neutral background for the grayscale OCR image.
        region.paste(255, (
            max(0, nutrition_left - left - 4 * scale), 0,
            region.width, min(region.height, nutrition_bottom - top),
        ))
    text = _clean_section(pytesseract.image_to_string(
        region, lang=language, config='--oem 1 --psm 3', timeout=30))
    if len(re.sub(r'[^A-Za-z]', '', text)) < 8:
        text = _clean_section(pytesseract.image_to_string(
            region, lang=language, config='--oem 1 --psm 6', timeout=30))
    weighted = [(row['confidence'], max(1, len(re.sub(r'\W', '', row['text']))))
                for row in candidates if row['confidence'] >= 0]
    confidence = None
    if weighted:
        confidence = round(sum(value * weight for value, weight in weighted)
                           / sum(weight for _, weight in weighted))
        confidence = max(25, min(92, confidence))
    return text, confidence

def _translate(value: str) -> str:
    translated=value
    for source,target in sorted(TRANSLATIONS.items(),key=lambda item:len(item[0]),reverse=True):
        translated=re.sub(r'(?<!\w)'+re.escape(source)+r'(?!\w)',target,translated,flags=re.I)
    return translated

def _parts(value: str) -> list[str]:
    # Split nested component lists too. A comma between two digits is a decimal mark,
    # not an ingredient separator.
    flat = re.sub(r'\s+', ' ', value).strip()
    chunks = re.split(r'(?<!\d),(?!\d)|;|\.(?=\s+[A-Z])', flat)
    result = []
    for chunk in chunks:
        part = chunk.strip(' .:-|\\/_—')
        if re.search(r'[A-Za-z0-9]', part):
            result.append(part[:300])
    return result[:100]

def extract_label_local(image: bytes) -> ExtractionResult:
    try:
        with Image.open(io.BytesIO(image)) as source:
            prepared, scale = _prepared_image(source)
            records, raw = _ocr_records(prepared)
            dutch_markers = len(re.findall(r'\b(?:melk|suiker|zout|voedingswaarde|bevatten)\b', raw, re.I))
            english_markers = len(re.findall(r'\b(?:milk|sugar|salt|nutrition|contains)\b', raw, re.I))
            ocr_language = 'nld' if dutch_markers > english_markers else ('eng' if english_markers else 'nld+eng')
            ingredient_text, confidence = _focused_ingredients(prepared, records, scale, ocr_language)
    except (TesseractNotFoundError,TesseractError,RuntimeError,OSError) as exc:
        raise ProviderError('Local label reading is temporarily unavailable. Try again later.') from exc
    text='\n'.join(line.strip() for line in raw.splitlines() if line.strip())[:12000]
    if len(text) < 8:raise ProviderError('No readable label text was found. Retake a sharper, closer photo.')
    match=re.search(r'\b(?:ingrediënten|ingredienten|ingredients)\s*[:\-]?\s*',text,re.I)
    if not ingredient_text and match:
        tail=text[match.end():]
        stop=STOP.search(tail)
        ingredient_text=_clean_section(tail[:stop.start()] if stop else tail)
        confidence = round(fmean(row['confidence'] for row in records if row['confidence'] >= 0)) if records else None
    complete=bool(ingredient_text and (STOP.search(text) or re.search(r'[.!)]\s*$',ingredient_text)))
    ingredients=[Ingredient(original=value[:300],english=_translate(value)[:300]) for value in _parts(ingredient_text) if value[:300]]
    dutch=bool(re.search(r'\b(ingrediënten|melk|suiker|zout|kan bevatten|voedingswaarde)\b',text,re.I))
    english=bool(re.search(r'\b(ingredients|milk|sugar|salt|may contain|nutrition)\b',text,re.I))
    language='mixed' if dutch and english else ('nl' if dutch else ('en' if english else 'unknown'))
    flat_text = re.sub(r'\s+', ' ', text)
    may=[]
    may_match=re.search(r'\b(?:kan bevatten|may contain)\s*:?\s*([^\.]+)',flat_text,re.I)
    if may_match:may=[v.strip()[:500] for v in re.split(r'[,;]|\band\b',_translate(may_match.group(1)),flags=re.I) if v.strip()][:30]
    contains=[]
    contains_match=re.search(
        r'\ballergen(?:en|s)?(?:\s+note)?\s*[:;.\-]?\s*contains\s*:?[ ]*([^\.]+)',
        flat_text, re.I)
    if contains_match:contains=[v.strip()[:500] for v in re.split(r'[,;&]|\band\b',_translate(contains_match.group(1)),flags=re.I) if v.strip()][:30]
    focused_suffix = '\nINGREDIENTS\n' + ingredient_text if ingredient_text else ''
    original_text = (text[:max(0, 12000 - len(focused_suffix))] + focused_suffix)[:12000]
    label=LabelExtraction(product_name='',language=language,ingredients_present=bool(ingredient_text and ingredients),
        ingredients_complete=complete,ingredients_text=ingredient_text,ingredients=ingredients,
        original_text=original_text,translated_text=('Ingredients: '+', '.join(item.english for item in ingredients)) if ingredients else _translate(text),
        contains=contains,may_contain=may,visible_claims=[],unreadable_sections=[])
    return ExtractionResult(label,provider='Tesseract local OCR',model_name='tesseract-local',confidence=confidence)
