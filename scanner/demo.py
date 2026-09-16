"""Clearly labelled, fictional examples — never substituted for a real failed scan."""
from .schema import LabelExtraction
EXAMPLES = {
    'oats': ('Oat drink — sample', [('water', 'Water'), ('haver', 'Oats'), ('zonnebloemolie', 'Sunflower oil'), ('zout', 'Salt')], [], ['Milk']),
    'chocolate': ('Chocolate drink — sample', [('melk', 'Milk'), ('suiker', 'Sugar'), ('cacaopoeder', 'Cocoa powder')], ['Milk'], []),
    'sweets': ('Fruit sweets — sample', [('suiker', 'Sugar'), ('gelatine', 'Gelatin'), ('citroenzuur', 'Citric acid')], [], []),
    'bread': ('Bread — sample', [('tarwebloem', 'Wheat flour'), ('water', 'Water'), ('E471', 'E471'), ('zout', 'Salt')], ['Wheat'], []),
}
def demo_label(name: str) -> LabelExtraction:
    title, pairs, contains, may = EXAMPLES[name]
    ingredients = ', '.join(pair[0] for pair in pairs) + '.'
    return LabelExtraction(product_name=title, language='nl', ingredients_present=True,
        ingredients_complete=True, ingredients_text=ingredients,
        ingredients=[{'original': a, 'english': b} for a, b in pairs],
        original_text='Ingrediënten: ' + ingredients + (' Kan melk bevatten.' if may else ''),
        translated_text='Ingredients: ' + ', '.join(pair[1] for pair in pairs) + '.' + (' May contain milk.' if may else ''),
        contains=contains, may_contain=may, visible_claims=[], unreadable_sections=[])
