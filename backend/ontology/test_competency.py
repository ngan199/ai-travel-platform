"""
Test domain.ttl against all 54 competency questions.
For each question: check required concepts exist and required properties/relations exist.
"""
from pathlib import Path
from rdflib import Graph, Namespace, RDF, SKOS, URIRef
from rdflib.namespace import RDFS

ONTOLOGY_DIR = Path(__file__).parent
TRAVEL = Namespace("https://travel-ontology.ai/vocab#")

g = Graph()
g.parse(str(ONTOLOGY_DIR / "domain.ttl"), format="turtle")

def local_name(uri):
    s = str(uri)
    return s.split("#")[-1] if "#" in s else s.split("/")[-1]

concepts   = {local_name(c) for c in g.subjects(RDF.type, SKOS.Concept)}
obj_props  = {local_name(r) for r in g.subjects(RDF.type, TRAVEL.relation)}
obj_prop_edges = {}  # prop -> (domain, range)
for rel in g.subjects(RDF.type, TRAVEL.relation):
    d = list(g.objects(rel, RDFS.domain))
    r = list(g.objects(rel, RDFS.range))
    if d and r:
        obj_prop_edges[local_name(rel)] = (local_name(d[0]), local_name(r[0]))

PASS = "✓"
FAIL = "✗"
WARN = "~"

results = []

def check(cq_id, question, concept_checks=(), prop_checks=(), edge_checks=()):
    """
    concept_checks: concept names that must exist
    prop_checks:    ObjectProperty names that must exist
    edge_checks:    (prop, domain, range) tuples — verify edge direction
    """
    issues = []
    for c in concept_checks:
        if c not in concepts:
            issues.append(f"missing concept: {c}")
    for p in prop_checks:
        if p not in obj_props:
            issues.append(f"missing property: {p}")
    for prop, dom, rng in edge_checks:
        if prop not in obj_prop_edges:
            issues.append(f"missing property: {prop}")
        else:
            actual_dom, actual_rng = obj_prop_edges[prop]
            if actual_dom != dom:
                issues.append(f"{prop} domain is {actual_dom}, expected {dom}")
            if actual_rng != rng:
                issues.append(f"{prop} range is {actual_rng}, expected {rng}")
    status = PASS if not issues else FAIL
    results.append((cq_id, status, question, issues))


# ── 1. Destination Discovery ─────────────────────────────────────────────────
check("1.1", "Which destinations suit [travel_style] and [budget_tier]?",
      concept_checks=["Destination","Style","Budget"],
      edge_checks=[("suits_travel_style","Tourism","Style"),
                   ("suits_budget","Tourism","Budget")])

check("1.2", "Which destinations are best for [activity_category]?",
      concept_checks=["Destination","Activity"],
      edge_checks=[("has_activity","Destination","Activity")])

check("1.3", "Which destinations are suitable for [traveler_type]?",
      concept_checks=["Destination","Traveler"],
      edge_checks=[("suits_traveler_type","Tourism","Traveler")])

check("1.4", "Which destinations are near to [destination]?",
      concept_checks=["Destination"],
      edge_checks=[("near_to","Destination","Destination")])

check("1.5", "Which destinations are in [region / country / continent]?",
      concept_checks=["Destination","Region","Country"],
      edge_checks=[("located_in","Place","Place")])

check("1.6", "What is the climate type of [destination]?",
      concept_checks=["Destination"])  # climate_type is a DatatypeProperty on Destination

check("1.7", "What is the typical daily cost in [destination]?",
      concept_checks=["Destination"])  # cost_per_day DatatypeProperty

check("1.8", "Which destinations are considered hidden gems in [region]?",
      concept_checks=["Destination","Venue"])  # is_hidden_gem on Venue


# ── 2. Timing and Seasonality ─────────────────────────────────────────────────
check("2.1", "What is the best time to visit [destination]?",
      concept_checks=["Destination","Season"],
      edge_checks=[("best_season","Destination","Season")])

check("2.2", "Which months should be avoided in [destination]?",
      concept_checks=["Destination","Month"],
      edge_checks=[("avoid_during","Destination","Month")])

check("2.3", "What season is [month] in [destination]?",
      concept_checks=["Season","Month"],
      edge_checks=[("covers_month","Season","Month")])

check("2.4", "Which months are the [season_type] season in [destination]?",
      concept_checks=["Season","Month"],
      edge_checks=[("covers_month","Season","Month")])

check("2.5", "Which destinations have good weather in [month]?",
      concept_checks=["Destination","Month"],
      edge_checks=[("avoid_during","Destination","Month")])

check("2.6", "What is the crowd level during [season]?",
      concept_checks=["Season"])  # crowd_level DatatypeProperty on Season

check("2.7", "Which destinations are best visited in [month] for [activity]?",
      concept_checks=["Destination","Month","Activity"],
      edge_checks=[("covers_month","Season","Month"),
                   ("has_activity","Destination","Activity")])


# ── 3. Activity and Experience ────────────────────────────────────────────────
check("3.1", "What activities are available in [destination]?",
      concept_checks=["Destination","Activity"],
      edge_checks=[("has_activity","Destination","Activity")])

check("3.2", "Which activities suit [travel_style] in [destination]?",
      concept_checks=["Activity","Style"],
      edge_checks=[("suits_travel_style","Tourism","Style"),
                   ("has_activity","Destination","Activity")])

check("3.3", "Which activities are suitable for [traveler_type] in [destination]?",
      concept_checks=["Activity","Traveler"],
      edge_checks=[("suits_traveler_type","Tourism","Traveler")])

check("3.4", "Are there festivals or events in [destination] during [month]?",
      concept_checks=["Festival","Event","Destination","Month"],
      edge_checks=[("has_activity","Destination","Activity")])

check("3.5", "What tours are available in [destination]?",
      concept_checks=["Tour","Destination"],
      edge_checks=[("has_activity","Destination","Activity")])

check("3.6", "What is the duration and price of [activity] in [destination]?",
      concept_checks=["Activity"])  # duration, price DatatypeProperties

check("3.7", "Which venues in [destination] are tourist attractions?",
      concept_checks=["Venue","Destination"],
      edge_checks=[("has_venue","Destination","Venue")])

check("3.8", "Which hidden gem venues are in [destination]?",
      concept_checks=["Venue","Destination"],
      edge_checks=[("has_venue","Destination","Venue")])

check("3.9", "What activities are near [venue]?",
      concept_checks=["Venue","Activity"],
      edge_checks=[("located_in","Place","Place")])


# ── 4. Accommodation ──────────────────────────────────────────────────────────
check("4.1", "What accommodation options are available in [destination]?",
      concept_checks=["Destination","Lodging"],
      edge_checks=[("has_accommodation","Destination","Lodging")])

check("4.2", "What accommodation suits [budget_tier] in [destination]?",
      concept_checks=["Lodging","Budget"],
      edge_checks=[("suits_budget","Tourism","Budget"),
                   ("has_accommodation","Destination","Lodging")])

check("4.3", "What accommodation suits [travel_style] in [destination]?",
      concept_checks=["Lodging","Style"],
      edge_checks=[("suits_travel_style","Tourism","Style")])

check("4.4", "What is the price per night for [accommodation_type] in [destination]?",
      concept_checks=["Lodging"])  # price_per_night DatatypeProperty

check("4.5", "Which hotels have [amenity]?",
      concept_checks=["Hotel"])  # amenities DatatypeProperty

check("4.6", "Which accommodation options suit [traveler_type]?",
      concept_checks=["Lodging","Traveler"],
      edge_checks=[("suits_traveler_type","Tourism","Traveler")])


# ── 5. Transport ──────────────────────────────────────────────────────────────
check("5.1", "How do I get from [destination_A] to [destination_B]?",
      concept_checks=["Route","Destination"],
      edge_checks=[("departs_from","Route","Destination"),
                   ("arrives_at","Route","Destination")])

check("5.2", "What transport modes are available?",
      concept_checks=["Transport","Route"],
      edge_checks=[("via_mode","Route","Transport")])

check("5.3", "How long does it take to travel by [transport_mode]?",
      concept_checks=["Transport","Route"])  # transport_duration DatatypeProperty

check("5.4", "What is the cost of travelling?",
      concept_checks=["Transport","Route"])  # transport_cost DatatypeProperty

check("5.5", "What transport hubs serve [destination]?",
      concept_checks=["Hub","Destination"],
      edge_checks=[("serves","Hub","Destination")])

check("5.6", "What regional transport is available within [destination]?",
      concept_checks=["Regional","Destination"])

check("5.7", "Do I need to book transport in advance for [route]?",
      concept_checks=["Route"])  # booking_in_advance DatatypeProperty


# ── 6. Practical Information ──────────────────────────────────────────────────
check("6.1", "What currency is used in [destination]?",
      concept_checks=["Currency","Country"],
      edge_checks=[("uses_currency","Country","Currency")])

check("6.2", "What languages are spoken in [destination]?",
      concept_checks=["Language","Country"],
      edge_checks=[("speaks_language","Country","Language")])

check("6.3", "Is English widely spoken in [destination]?",
      concept_checks=["Destination"])  # english_widely_spoken DatatypeProperty

check("6.4", "Do I need a visa to visit [destination]?",
      concept_checks=["Visa","Country","Entry"],
      edge_checks=[("has_entry_requirement","Country","Entry")])

check("6.5", "Is a visa on arrival available?",
      concept_checks=["Visa"])  # visa_on_arrival DatatypeProperty

check("6.6", "How long can I stay on a visa?",
      concept_checks=["Visa"])  # visa_duration_days DatatypeProperty

check("6.7", "What vaccinations or entry requirements apply?",
      concept_checks=["Health","Entry","Country"],
      edge_checks=[("has_entry_requirement","Country","Entry")])

check("6.8", "What are the local laws I should know?",
      concept_checks=["Law","Destination"],
      edge_checks=[("has_local_law","Destination","Law")])

check("6.9", "What cultural norms should I follow?",
      concept_checks=["Norm","Destination"],
      edge_checks=[("has_social_norm","Destination","Norm")])

check("6.10", "What are the top safety tips for [destination]?",
      concept_checks=["Safety","Destination"],
      edge_checks=[("has_safety_tip","Destination","Safety")])

check("6.11", "What is the dress code for visiting religious sites?",
      concept_checks=["Norm"])  # dress_code DatatypeProperty


# ── 7. Itinerary Construction ─────────────────────────────────────────────────
check("7.1", "Recommend a day-by-day itinerary given [destination_list, duration, budget, style]",
      concept_checks=["Destination","Lodging","Activity","Route","Budget","Style"],
      edge_checks=[("has_activity","Destination","Activity"),
                   ("has_accommodation","Destination","Lodging"),
                   ("departs_from","Route","Destination")])

check("7.2", "Which activities are recommended to do together?",
      concept_checks=["Activity"])  # no co-occurrence property yet

check("7.3", "What is the logical order to visit [destination_list]?",
      concept_checks=["Route","Destination"],
      edge_checks=[("departs_from","Route","Destination"),
                   ("arrives_at","Route","Destination")])

check("7.4", "How many days should I spend in [destination]?",
      concept_checks=["Destination","Activity"])  # no duration-at-destination property

check("7.5", "What accommodation is available for each stop in [itinerary]?",
      concept_checks=["Lodging","Destination"],
      edge_checks=[("has_accommodation","Destination","Lodging")])

check("7.6", "What transport connects each stop in [itinerary]?",
      concept_checks=["Route","Destination","Transport"],
      edge_checks=[("departs_from","Route","Destination"),
                   ("arrives_at","Route","Destination"),
                   ("via_mode","Route","Transport")])


# ── Print report ──────────────────────────────────────────────────────────────
passed = [r for r in results if r[1] == PASS]
failed = [r for r in results if r[1] == FAIL]

print(f"\n{'='*70}")
print(f"COMPETENCY QUESTION TEST REPORT  —  {len(passed)}/{len(results)} passed")
print(f"{'='*70}")

for cq_id, status, question, issues in results:
    print(f"\n  {status} [{cq_id}] {question}")
    for issue in issues:
        print(f"       → {issue}")

print(f"\n{'='*70}")
print(f"  PASSED : {len(passed)}")
print(f"  FAILED : {len(failed)}")
if failed:
    print(f"\n  Issues to fix:")
    seen = set()
    for _, _, _, issues in failed:
        for issue in issues:
            if issue not in seen:
                print(f"    • {issue}")
                seen.add(issue)
print(f"{'='*70}\n")
