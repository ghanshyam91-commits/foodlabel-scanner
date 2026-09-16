# Dietary assessment boundaries

AI transcribes and translates. A separate rule engine uses the original ingredient text. It does not rely on a model-generated vegan/vegetarian verdict or a fabricated probability.

The starter reference is deliberately limited. Exact normalized aliases prevent coconut milk from being mistaken for dairy milk and “eiwit” from matching the Dutch word for egg. Percentages and known function headings may be removed; arbitrary modifiers are never dropped. Ingredients missing from the original transcription, unaccounted-for ingredient-list text, incomplete lists, unreadable sections and unsupported languages prevent positive results.

A visible excluded ingredient can prove a preference mismatch even when the rest of the label is incomplete. Example: milk on a partial list proves a vegan mismatch but cannot establish that the complete product is vegetarian. Directly evidenced gelatin can establish a non-vegetarian ingredient finding without requiring the rest of the list.

“Contains” and precautionary “may contain” statements are separate from the ingredient list. Precautionary warnings do not automatically change ingredient classification. They remain prominently displayed. Absence of an extracted warning is never an absence guarantee. This app does not evaluate allergy safety.

Cheese, unspecified rennet, whey, generic flavourings, unknown additives and several source-dependent ingredients intentionally remain uncertain. No logo is treated as verified certification. No assumption is made about undisclosed processing aids. The egg-free vegetarian preference is configurable and not presented as a universal definition of vegetarianism.

Residual risks: extraction and translation errors, a model claiming a cropped list is complete, omissions from both the full transcription and ingredients transcription, incomplete real-world labelling, production changes and unknown manufacturing processes. Deterministic checks cannot catch every error when both model fields are wrong in the same way.

Required pre-launch work: independent food-label expert review of every positive alias, a representative photographed benchmark with human ground truth, false-positive tracking, adversarial/cropped/low-light tests, accessibility checks on physical phones and documentation of the provider's actual retention/billing settings. Do not advertise certified vegan, 100% accurate, allergen-free or safe-to-eat outcomes.
