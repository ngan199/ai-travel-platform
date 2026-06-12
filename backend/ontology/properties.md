# Properties — Travel Ontology v7

## DatatypeProperties

### Destination
| Property | Type | Notes |
|---|---|---|
| continent | string | e.g. Asia, Europe |
| island | boolean | |
| archipelago | boolean | |
| coast | boolean | |
| mountain | boolean | |
| valley | boolean | |
| river | boolean | |
| lake | boolean | |
| beach | boolean | |
| desert | boolean | |
| climate_type | string | enum: tropical, mediterranean, alpine, arid, temperate |
| cost_per_day | numeric | Typical daily spend, USD |
| english_widely_spoken | boolean | |
| commonly_praised | string | Derived — aggregated from TravelerReview |
| commonly_warned_about | string | Derived — aggregated from TravelerWarning |

### Venue
| Property | Type | Notes |
|---|---|---|
| venue_type | enum | park, market, restaurant, temple, museum, beach_club, bar, shop |
| opening_hours | string | |
| entrance_fee | numeric | USD |
| is_hidden_gem | boolean | |
| is_tourist_attraction | boolean | |

### Activity
| Property | Type | Notes |
|---|---|---|
| activity_category | enum | hiking, diving, snorkeling, museum_visit, temple_visit, cooking_class, wildlife_watching, safari, nightlife, shopping, cycling |
| duration | numeric | Hours |
| price | numeric | Cost per person, USD |
| booking_required | boolean | |
| difficulty_level | enum | easy, moderate, challenging |
| min_age | integer | |

### Festival / Event (inherits Activity properties, adds:)
| Property | Type | Notes |
|---|---|---|
| activity_start_date | date | |
| activity_end_date | date | |

### Lodging
| Property | Type | Notes |
|---|---|---|
| price_per_night | numeric | USD |
| accommodation_type | enum | hotel, hostel, resort, guesthouse, homestay, villa, camping |
| amenities | list | pool, wifi, breakfast, aircon … |
| check_in_time | string | |
| check_out_time | string | |

### Hotel (inherits Lodging properties, adds:)
| Property | Type | Notes |
|---|---|---|
| star_rating | integer | 1–5 |

### Hostel (inherits Lodging properties, adds:)
| Property | Type | Notes |
|---|---|---|
| has_dorm_beds | boolean | |

### Transport
| Property | Type | Notes |
|---|---|---|
| transport_mode | enum | flight, domestic_flight, ferry, speedboat, seaplane, train, bus, taxi, tuk_tuk, songthaew, motorbike_taxi, cyclo, cable_car, bicycle, car_rental, water_taxi, longtail_boat |
| transport_duration | numeric | Hours |
| transport_cost | numeric | USD |
| transport_frequency | enum | hourly, daily, seasonal |
| booking_in_advance | boolean | |

### Route
| Property | Type | Notes |
|---|---|---|
| route_transport_mode | enum | Same values as Transport.transport_mode |
| route_duration | numeric | Hours |
| route_cost | numeric | USD |
| route_booking_in_advance | boolean | |

### Season
| Property | Type | Notes |
|---|---|---|
| season_type | enum | high, shoulder, low, rainy, dry, cool, hot |
| season_weather_description | string | |
| season_average_temperature | numeric | Celsius |
| season_rainfall_mm | numeric | |
| crowd_level | enum | low, moderate, high |

### Month
| Property | Type | Notes |
|---|---|---|
| month_name | string | January … December |
| month_weather_description | string | |
| month_average_temperature | numeric | Celsius |
| month_rainfall_mm | numeric | |

### Budget
| Property | Type | Notes |
|---|---|---|
| tier_name | enum | budget, mid_range, luxury |
| daily_cost_usd_min | numeric | |
| daily_cost_usd_max | numeric | |

### Style
| Property | Type | Notes |
|---|---|---|
| style_name | enum | adventure, cultural, beach, wildlife, food_and_drink, wellness, romance, family, backpacking, eco_tourism |

### Traveler
| Property | Type | Notes |
|---|---|---|
| type_name | enum | solo, couple, family, group, backpacker, luxury, adventure, cultural |

### Cuisine
| Property | Type | Notes |
|---|---|---|
| local_dish | string | Multi-valued |
| street_food_available | boolean | |

### Norm
| Property | Type | Notes |
|---|---|---|
| dress_code | string | |
| tipping_etiquette | string | |
| local_custom | string | |
| religion | string | |

### LocalLaw
| Property | Type | Notes |
|---|---|---|
| law_description | string | |
| law_category | enum | alcohol, drugs, photography, dress, behaviour |

### SafetyTip
| Property | Type | Notes |
|---|---|---|
| tip_text | string | |
| tip_category | enum | scam, health, theft, transport, nature |

### Language
| Property | Type | Notes |
|---|---|---|
| language_name | string | |
| is_official_language | boolean | |

### Currency
| Property | Type | Notes |
|---|---|---|
| currency_code | string | ISO 4217, e.g. THB, USD, EUR |
| currency_name | string | |

### Entry
| Property | Type | Notes |
|---|---|---|
| requirement_description | string | Inherited by all subclasses |
| requirement_type | enum | visa, vaccination, insurance |

### Visa (inherits Entry properties, adds:)
| Property | Type | Notes |
|---|---|---|
| visa_required | boolean | |
| visa_on_arrival | boolean | |
| visa_duration_days | integer | |
| visa_cost_usd | numeric | |

### HealthRequirement (inherits Entry properties, adds:)
| Property | Type | Notes |
|---|---|---|
| vaccination_name | string | e.g. Yellow Fever, Hepatitis A |
| vaccination_required | boolean | |
| recommended_only | boolean | |

### InsuranceRequirement (inherits Entry properties, adds:)
| Property | Type | Notes |
|---|---|---|
| insurance_type | string | e.g. travel, medical, evacuation |
| minimum_coverage_usd | numeric | |
| mandatory | boolean | |

### Content
| Property | Type | Notes |
|---|---|---|
| sentiment | enum | positive, neutral, negative |
| review_source | string | TripAdvisor, WikiVoyage, Travel Stack Exchange |
| review_text | string | |

### TravelerReview (inherits Content properties, adds:)
| Property | Type | Notes |
|---|---|---|
| rating | numeric | 1.0–5.0 |

---

## ObjectProperties

| Property | Domain | Range | Notes |
|---|---|---|---|
| located_in | Place | Place | |
| near_to | Destination | Destination | |
| has_venue | Destination | Venue | |
| has_activity | Destination | Activity | |
| has_accommodation | Destination | Lodging | |
| serves | Hub | Destination | |
| departs_from | Route | Destination | |
| arrives_at | Route | Destination | |
| via_mode | Route | Transport | |
| covers_month | Season | Month | |
| best_season | Destination | Season | |
| avoid_during | Destination | Month | |
| suits_budget | Tourism | Budget | |
| suits_travel_style | Tourism | Style | |
| suits_traveler_type | Tourism | Traveler | |
| has_entry_requirement | Country | Entry | |
| uses_currency | Country | Currency | |
| speaks_language | Country | Language | |
| has_cuisine | Destination | Cuisine | |
| has_cultural_norm | Destination | Norm | |
| has_local_law | Destination | LocalLaw | |
| has_safety_tip | Destination | SafetyTip | |
| about_destination | Content | Destination | |
| about_accommodation | Content | Lodging | |
| about_activity | Content | Activity | |
