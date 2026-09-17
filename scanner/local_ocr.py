"""Free, local OCR fallback. It never sends the image to another service."""
import io
import re
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import pytesseract
from pytesseract import TesseractError, TesseractNotFoundError
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
STOP = re.compile(r'\b(voedingswaarde|nutrition(?:al)?|allergenen|allergens|bewaaradvies|storage|bereiding|netto)\b', re.I)

def _translate(value: str) -> str:
    translated=value
    for source,target in sorted(TRANSLATIONS.items(),key=lambda item:len(item[0]),reverse=True):
        translated=re.sub(r'(?<!\w)'+re.escape(source)+r'(?!\w)',target,translated,flags=re.I)
    return translated

def _parts(value: str) -> list[str]:
    result=[];start=0;depth=0
    for index,char in enumerate(value):
        depth += char in '([';depth -= char in ')]'
        if char in ',;' and depth <= 0:
            part=value[start:index].strip(' .:-');start=index+1
            if part:result.append(part)
    tail=value[start:].strip(' .:-')
    if tail:result.append(tail)
    return result[:100]

def extract_label_local(image: bytes) -> ExtractionResult:
    try:
        with Image.open(io.BytesIO(image)) as source:
            prepared=ImageOps.grayscale(source)
            prepared=ImageEnhance.Contrast(prepared).enhance(1.8).filter(ImageFilter.SHARPEN)
            raw=pytesseract.image_to_string(prepared,lang='nld+eng',config='--oem 1 --psm 6',timeout=30)
    except (TesseractNotFoundError,TesseractError,RuntimeError,OSError) as exc:
        raise ProviderError('Local label reading is temporarily unavailable. Try again later.') from exc
    text='\n'.join(line.strip() for line in raw.splitlines() if line.strip())[:12000]
    if len(text) < 8:raise ProviderError('No readable label text was found. Retake a sharper, closer photo.')
    match=re.search(r'\b(?:ingrediënten|ingredienten|ingredients)\s*[:\-]?\s*',text,re.I)
    ingredient_text='';complete=False
    if match:
        tail=text[match.end():]
        stop=STOP.search(tail)
        ingredient_text=(tail[:stop.start()] if stop else tail).strip()[:12000]
        complete=bool(stop or re.search(r'[.!)]\s*$',ingredient_text))
    ingredients=[Ingredient(original=value[:300],english=_translate(value)[:300]) for value in _parts(ingredient_text) if value[:300]]
    dutch=bool(re.search(r'\b(ingrediënten|melk|suiker|zout|kan bevatten|voedingswaarde)\b',text,re.I))
    english=bool(re.search(r'\b(ingredients|milk|sugar|salt|may contain|nutrition)\b',text,re.I))
    language='mixed' if dutch and english else ('nl' if dutch else ('en' if english else 'unknown'))
    may=[]
    may_match=re.search(r'\b(?:kan bevatten|may contain)\s*:?\s*([^\n.]+)',text,re.I)
    if may_match:may=[v.strip()[:500] for v in re.split(r'[,;]',_translate(may_match.group(1))) if v.strip()][:30]
    label=LabelExtraction(product_name='',language=language,ingredients_present=bool(ingredient_text and ingredients),
        ingredients_complete=complete,ingredients_text=ingredient_text,ingredients=ingredients,
        original_text=text,translated_text=('Ingredients: '+', '.join(item.english for item in ingredients)) if ingredients else _translate(text),
        contains=[],may_contain=may,visible_claims=[],unreadable_sections=[])
    return ExtractionResult(label,provider='Tesseract local OCR',model_name='tesseract-local')
