"""Conservative ingredient checks based on ORIGINAL label text, never AI verdicts.
Unknown ingredients and incomplete extraction block positive classifications.
This is a starter vocabulary, not certification or an exhaustive ingredient database.
"""
import re
import unicodedata
from .schema import LabelExtraction

RULESET_VERSION = '2026-09-17.1'
PREFERENCES = {'vegan', 'vegetarian_no_eggs', 'vegetarian_with_eggs', 'non_vegetarian'}

def normalize(text: str) -> str:
    value = unicodedata.normalize('NFKD', text.casefold())
    value = ''.join(c for c in value if not unicodedata.combining(c))
    return re.sub(r'\s+', ' ', value).strip()

RULES: dict[str, tuple[str, str]] = {}
def add(kind: str, reason: str, aliases: str) -> None:
    for alias in aliases.split('|'):
        key = normalize(alias)
        if key in RULES:
            raise ValueError(f'Duplicate ingredient rule: {key}')
        RULES[key] = (kind, reason)

add('plant', 'Plant-derived or mineral ingredient; processing aids are not verified.',
    'water|suiker|sugar|zout|salt|zeezout|sea salt|rijst|rice|bruine rijst|zilvervliesrijst|'
    'haver|oats|havervlokken|oat flakes|havermout|tarwe|wheat|tarwebloem|wheat flour|tarwemeel|'
    'volkoren tarwemeel|bloem|flour|refined wheat flour|refined wheat flour (maida)|maida|wheat gluten|'
    'rijstmeel|rice flour|mais|corn|maismeel|maiszetmeel|'
    'corn starch|cornstarch|aardappelzetmeel|potato starch|aardappelen|potatoes|zetmeel|starch|'
    'sojabonen|soybeans|soja|soy|sojameel|sojaproteine|soja-eiwit|erwteneiwit|pea protein|'
    'linzen|lentils|kikkererwten|chickpeas|bonen|beans|erwten|peas|tomaten|tomatoes|tomaat|'
    'tomatenpuree|tomato puree|tomatenpoeder|ui|onion|uien|onions|knoflook|garlic|wortel|carrot|'
    'wortelen|carrots|paprika|spinazie|spinach|komkommer|cucumber|courgette|zucchini|'
    'champignons|mushrooms|citroen|lemon|citroensap|lemon juice|appel|apple|appels|apples|'
    'appelsap|apple juice|banaan|banana|aardbeien|strawberries|frambozen|raspberries|'
    'blauwe bessen|blueberries|rozijnen|raisins|dadels|dates|kokos|coconut|kokosmelk|coconut milk|'
    'kokosroom|coconut cream|kokosolie|coconut oil|cacaoboter|cocoa butter|cacaopoeder|cocoa powder|'
    'cacaomassa|cocoa mass|cacao|cocoa|koffie|coffee|thee|tea|olijfolie|olive oil|'
    'zonnebloemolie|sunflower oil|raapzaadolie|koolzaadolie|rapeseed oil|palmolie|palm oil|'
    'plantaardige olie|vegetable oil|plantaardig vet|vegetable fat|sesamolie|sesame oil|'
    'amandelen|almonds|hazelnoten|hazelnuts|walnoten|walnuts|pindas|pinda\'s|peanuts|'
    'cashewnoten|cashews|sesamzaad|sesame seeds|lijnzaad|flaxseed|zonnebloempitten|sunflower seeds|'
    'peper|pepper|zwarte peper|black pepper|black pepper powder|kaneel|cinnamon|kurkuma|turmeric|'
    'turmeric powder|gember|ginger|ginger powder|basilicum|basil|oregano|peterselie|parsley|'
    'komijn|cumin|cumin powder|koriander|coriander|coriander powder|mixed spices|spices|'
    'onion powder|red chilli powder|red chili powder|garlic powder|aniseed powder|fenugreek powder|'
    'toasted onion powder|clove powder|green cardamom powder|nutmeg powder|groundnut|groundnut protein|'
    'hydrolysed groundnut protein|hydrolyzed groundnut protein|iodized salt|iodised salt|lodized salt|'
    'azijn|vinegar|citroenzuur|citric acid|ascorbinezuur|ascorbic acid|'
    'pectine|pectin|agar|agar-agar|guargom|guar gum|xanthaangom|xanthan gum|'
    'natriumbicarbonaat|sodium bicarbonate|sojalecithine|soy lecithin|zonnebloemlecithine|sunflower lecithin|'
    'mineral|e330|e412|e451|e500|e501|e508|e150d')
add('dairy', 'Milk-derived ingredient: not compatible with vegan preferences.',
    'melk|milk|volle melk|whole milk|halfvolle melk|semi-skimmed milk|magere melk|skimmed milk|'
    'melkpoeder|milk powder|mageremelkpoeder|magere melkpoeder|skimmed milk powder|'
    'room|cream|slagroom|whipping cream|boter|butter|roomboter|melkeiwit|milk protein|'
    'melkvet|milk fat|lactose|caseine|casein|caseinaat|yoghurt|yogurt|karnemelk|buttermilk')
add('egg', 'Egg ingredient: excluded by vegan and egg-free vegetarian preferences.',
    'ei|eieren|egg|eggs|eigeel|egg yolk|eidooier|eipoeder|egg powder|ei-eiwit|egg white|'
    'kippenei|kippeneieren|heel ei|whole egg')
add('honey', 'Bee-derived ingredient: excluded by vegan preferences.', 'honing|honey|bijenwas|beeswax|e901')
add('animal', 'Animal-derived ingredient: excluded by vegetarian and vegan preferences.',
    'kip|chicken|kippenvlees|kippenbouillon|chicken stock|chicken broth|rundvlees|beef|'
    'varkensvlees|pork|lamsvlees|lamb|vlees|meat|ham|spek|bacon|reuzel|lard|'
    'rundervet|beef fat|dierlijk vet|animal fat|gelatine|gelatin|gelatinepoeder|'
    'rundergelatine|varkensgelatine|visgelatine|fish gelatin|beef gelatin|pork gelatin|'
    'vis|fish|zalm|salmon|tonijn|tuna|ansjovis|anchovy|anchovies|garnalen|shrimp|prawns|'
    'vissaus|fish sauce|oestersaus|oyster sauce|karmijn|carmine|cochenille|cochineal|e120|'
    'dierlijk stremsel|animal rennet|kalfsstremsel')
add('uncertain', 'Source or manufacturing details are needed; do not assume plant origin.',
    'stremsel|rennet|kaas|cheese|weipoeder|whey powder|wei|whey|weieiwit|whey protein|'
    'aroma|aromas|aroma\'s|flavouring|flavoring|flavourings|flavorings|natuurlijk aroma|'
    'natural flavouring|natural flavoring|enzymen|enzymes|lecithine|lecithin|glycerol|glycerine|'
    'glycerin|e422|e471|e472|e472a|e472b|e472c|e472d|e472e|e472f|e627|e631|e635|'
    'vitamine d3|vitamin d3|cholecalciferol|schellak|shellac|e904|mono- en diglyceriden van vetzuren')

LIMITATIONS = [
    'Based only on the readable label and a limited ingredient reference; not vegan certification.',
    'AI can misread or mistranslate labels. Check the original packaging before deciding.',
    'Processing aids and unlisted ingredients cannot be verified from a photo.',
    'Not an allergy-safety assessment. Read all allergen statements and ask the manufacturer when needed.',
]

def ingredient_key(original: str) -> str:
    # Only remove amounts and common ingredient-function headings, not unknown words.
    value = normalize(original)
    value = re.sub(r'\b\d+(?:[.,]\d+)?\s*%', '', value)
    value = re.sub(r'^(?:noodles?|masala(?:\s+["\']?tastemaker["\']?)?|seasoning)\s*:\s*', '', value)
    spice_group = re.match(r'^(?:mixed\s+)?spices?\s*(?:\(\s*\))?\s*\(?\s*(.+)$', value)
    if spice_group and re.search(r'[a-z]', spice_group.group(1)):
        value = spice_group.group(1)
    value = re.sub(r'^(?:emulgator|emulsifier|kleurstof|colouring|coloring|stabilisator|stabiliser|verdikkingsmiddel|thickener|voedingszuur|acidity regulator)\s*:\s*', '', value)
    value = re.sub(r'\be\s+(\d{3,4}[a-z]?)\b', r'e\1', value)
    return re.sub(r'\s+', ' ', value).strip(' .,:;')


ADDITIVE_CONTEXT = re.compile(
    r'\b(?:e\s*\d{3,4}|thickeners?|verdikkingsmiddel(?:en)?|acidity regulators?|voedingszuur|'
    r'humectants?|flavou?r enhancers?|colour(?:ing)?|kleurstof|stabilisers?|stabilizers?|emulsifiers?|emulgators?)\b')


def ingredient_rule(original: str) -> tuple[str, str]:
    key = ingredient_key(original)
    direct = RULES.get(key)
    if direct:
        return direct
    normalized = normalize(original)
    if not ADDITIVE_CONTEXT.search(normalized):
        return 'uncertain', 'This ingredient is not in the reviewed starter vocabulary. Check its source.'
    if re.search(r'flavou?r enhancers?.*?(?<!\d)(?:627|631|635)', normalized):
        for code in ('627', '631', '635'):
            if re.search(rf'(?<!\d){code}', normalized):
                return RULES['e' + code]
    without_amounts = re.sub(r'\b\d+(?:[.,]\d+)?\s*%', '', normalized)
    codes = list(dict.fromkeys(re.findall(r'(?<!\d)(?:e\s*)?(\d{3,4}[a-z]?)(?!\d)', without_amounts)))
    if not codes:
        return 'uncertain', 'The additive number could not be read clearly. Check the original label.'
    resolved = []
    for code in codes:
        rule = RULES.get('e' + code)
        if rule is None and re.fullmatch(r'\d{3,4}[il]+', code):
            rule = RULES.get('e' + re.match(r'\d+', code).group())
        resolved.append((code, rule))
    unknown = [code for code, rule in resolved if rule is None]
    known = [(code, rule) for code, rule in resolved if rule is not None]
    for kind in ('animal', 'dairy', 'egg', 'honey', 'uncertain'):
        for code, rule in known:
            if rule[0] == kind:
                return rule
    if unknown:
        names = ', '.join('E' + code.upper() for code in unknown[:4])
        return 'uncertain', f'{names} could not be verified from the scanned label.'
    if known:
        return 'plant', 'The identified additives are plant-derived, mineral, or synthetic in the reviewed reference.'
    return 'uncertain', 'The additive source could not be verified.'

def spans(text: str, phrase: str) -> list[tuple[int, int]]:
    # Whole-word matching prevents ei from matching eiwit and melk from kokosmelk.
    return [(m.start(), m.end()) for m in re.finditer(r'(?<!\w)' + re.escape(phrase) + r'(?!\w)', text)]

def assess(label: LabelExtraction, preference: str = 'vegetarian_no_eggs') -> dict:
    if preference not in PREFERENCES:
        raise ValueError('Unknown dietary preference.')
    source = normalize(label.ingredients_text)
    rows, issues = [], []
    covered = [False] * len(source)
    verified_kinds = set()
    for ingredient in label.ingredients:
        original = normalize(ingredient.original)
        found = spans(source, original) if source else []
        kind, reason = ingredient_rule(ingredient.original)
        if not found:
            kind, reason = 'uncertain', 'Ingredient could not be matched to the original ingredient-list transcription.'
        else:
            for start, end in found:
                covered[start:end] = [True] * (end - start)
            verified_kinds.add(kind)
        rows.append({'original': ingredient.original, 'english': ingredient.english,
            'kind': kind, 'reason': reason, 'evidence_verified': bool(found)})

    if not label.ingredients_present or not source or not rows:
        issues.append('Photograph the full ingredients panel; food appearance or front-of-pack claims are not enough.')
    if not label.ingredients_complete:
        issues.append('The complete ingredient list is not visible or readable. Retake the photo.')
    if label.unreadable_sections:
        issues.append('Some label sections were unreadable: ' + '; '.join(label.unreadable_sections))
    if label.language not in {'nl', 'en', 'mixed'}:
        issues.append('This first version supports Dutch and English ingredient text only.')
    if source and not spans(normalize(label.original_text), source):
        issues.append('The ingredient-list transcription does not match the full label transcription.')
    remaining = ''.join(' ' if covered[i] else c for i, c in enumerate(source))
    remaining = re.sub(r'^\s*(?:ingredienten|ingredients)\s*:', '', remaining)
    remaining = re.sub(r'\d+(?:[.,]\d+)?\s*%', '', remaining)
    has_unaccounted_text = bool(re.search(r'[a-z0-9]', remaining))
    if has_unaccounted_text:
        issues.append('Some ingredient text could not be matched reliably. Retake a closer photo of the ingredients panel.')
    # An intentional allergen declaration can expose an omitted subingredient.
    # Precautionary may_contain is intentionally not checked here.
    allergen_groups = {
        'dairy': r'\b(?:milk|melk|dairy)\b',
        'egg': r'\b(?:egg|eggs|ei|eieren)\b',
        'animal': r'\b(?:fish|vis|crustaceans|molluscs|shellfish|shrimp|prawns|schaaldieren|weekdieren)\b',
    }
    for declaration in label.contains:
        normalized = normalize(declaration)
        if any(re.search(pattern, normalized) and kind not in verified_kinds
               for kind, pattern in allergen_groups.items()):
            issues.append('An intentional allergen statement mentions ' + declaration +
                ', but its source was not resolved in the ingredient list. Check the original label.')
    uncertain_rows = [row for row in rows if row['kind'] == 'uncertain']
    if uncertain_rows:
        ambiguous_code = next((code for code in ('635', '631', '627')
            if any(re.search(rf'(?<!\d){code}', normalize(row['original'])) for row in uncertain_rows)), None)
        if ambiguous_code:
            issues.append(f'Flavour enhancer E{ambiguous_code} has an unspecified source; check the package or manufacturer.')
        useful_names = []
        for row in uncertain_rows:
            name = re.sub(r'\s+', ' ', row['english']).strip(' .,:;()')
            letters = len(re.findall(r'[a-z]', name.casefold()))
            if 2 <= len(name) <= 90 and letters >= max(2, len(name) // 3):
                useful_names.append(name)
        if useful_names and not ambiguous_code:
            issues.append('Ingredient source needs checking: ' + ', '.join(useful_names[:3]) + '.')
        elif not ambiguous_code:
            issues.append('One or more ingredients need a source or translation check.')

    # A directly evidenced excluded ingredient establishes a mismatch even on a partial label.
    animal = 'animal' in verified_kinds
    egg = 'egg' in verified_kinds
    dairy_or_honey = bool(verified_kinds & {'dairy', 'honey'})
    if animal:
        verdict, title = 'non_vegetarian', 'Non-vegetarian ingredient found'
    elif issues:
        verdict, title = 'uncertain', 'Uncertain — needs checking'
    elif egg or dairy_or_honey:
        verdict, title = 'vegetarian', 'Vegetarian · not vegan'
    else:
        verdict, title = 'vegan', 'Vegan-compatible ingredients'

    excluded = (animal and preference != 'non_vegetarian') or (preference == 'vegan' and (egg or dairy_or_honey)) or (preference == 'vegetarian_no_eggs' and egg)
    match = 'no' if excluded else ('uncertain' if issues else 'yes')
    notable = [r for r in rows if r['evidence_verified'] and r['kind'] in {'animal','dairy','egg','honey'}]
    if notable:
        explanation = 'Identified in the scanned ingredients: ' + ', '.join(r['english'] for r in notable) + '.'
    elif verdict == 'vegan':
        explanation = 'No animal-derived ingredient identified in the complete readable list within the starter reference.'
    else:
        explanation = 'There is not enough verified ingredient information to give a positive dietary result.'
    total = len(rows)
    verified_ratio = sum(row['evidence_verified'] for row in rows) / total if total else 0
    resolved_ratio = sum(row['evidence_verified'] and row['kind'] != 'uncertain' for row in rows) / total if total else 0
    confidence = 35 + round(25 * verified_ratio) + round(25 * resolved_ratio)
    confidence += 8 if label.ingredients_complete else -12
    if label.unreadable_sections:
        confidence -= 10
    if has_unaccounted_text:
        confidence -= 8
    if excluded and notable:
        confidence = max(confidence, 92)
    if uncertain_rows:
        confidence = min(confidence, 84)
    confidence = max(25, min(98, confidence))
    return {'verdict': verdict, 'title': title, 'explanation': explanation,
        'preference': preference, 'preference_match': match, 'ingredients': rows,
        'issues': list(dict.fromkeys(issues)), 'limitations': LIMITATIONS,
        'confidence': confidence, 'ruleset_version': RULESET_VERSION,
        'basis': 'Based on the scanned label — not certified'}
