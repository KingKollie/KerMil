from recommender import get_recommendation

profile = {
    "name": "Kollie",
    "hair_type": "Natural 4C",
    "hair_concerns": "Dryness and breakage",
    "skin_type": "Oily",
    "skin_concerns": "Hyperpigmentation",
    "gender": "Male",
    "budget": "Under $20 per product"
}

result = get_recommendation(profile)
print(result)