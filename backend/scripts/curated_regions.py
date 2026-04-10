# Manually curated travel regions that SPARQL city/country passes miss.
# Each entry: "Q-ID": ("canonical name", "parent country Q-ID or None")
#
# NOTE: Some Q-IDs marked "(verify)" should be confirmed against Wikidata.
# build_kb.py validates every Q-ID via the Wikidata API and logs warnings
# for any that return 404 or unexpected entity types.

CURATED_REGIONS: dict[str, tuple[str, str | None]] = {
    "Q5765":   ("Bali",          "Q252"),    # Indonesia
    "Q1223":   ("Tuscany",       "Q38"),     # Italy
    "Q79838":  ("Patagonia",     None),      # Spans Argentina + Chile
    "Q22680":  ("Scandinavia",   None),      # Multi-country region
    "Q12585":  ("Cappadocia",    "Q43"),     # Turkey
    "Q1437":   ("Provence",      "Q142"),    # France
    "Q1028":   ("Maldives",      "Q1028"),   # Island nation (also a country)
    "Q3492":   ("Amalfi Coast",  "Q38"),     # Italy
    "Q192900": ("Santorini",     "Q41"),     # Greece
    "Q180107": ("Mykonos",       "Q41"),     # Greece
    "Q160464": ("Dubrovnik",     "Q224"),    # Croatia
    "Q12130":  ("Phuket",        "Q869"),    # Thailand
    "Q1881":   ("Chiang Mai",    "Q869"),    # Thailand
    "Q1082":   ("Jeju",          "Q884"),    # South Korea
    "Q3130":   ("Sydney",        "Q408"),    # Australia
    "Q18575":  ("Machu Picchu",  "Q419"),    # Peru
    "Q172":    ("Patagonia AR",  "Q414"),    # Argentina portion
    "Q2915":   ("Chianti",       "Q38"),     # Italy (verify — may differ from Q1223 Tuscany)
    "Q5119":   ("Cape Town",     "Q258"),    # South Africa
    "Q2634":   ("Zanzibar",      "Q924"),    # Tanzania
    "Q3579":   ("Marrakesh",     "Q1028"),   # Morocco (verify country Q-ID)
    "Q182863": ("Cancún",        "Q96"),     # Mexico
    "Q398":    ("Bahrain",       "Q398"),    # verify — may not be Bali
    "Q1085":   ("Prague",        "Q213"),    # Czech Republic
    "Q90":     ("Paris",         "Q142"),    # France
    "Q220":    ("Rome",          "Q38"),     # Italy
    "Q1726":   ("Munich",        "Q183"),    # Germany
    "Q60":     ("New York City", "Q30"),     # USA
    "Q11462":  ("Goa",           "Q668"),    # India
    "Q129858": ("Hội An",        "Q881"),    # Vietnam
}
