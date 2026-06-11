# Travel AI Vocabulary Namespace

**Prefix:** `travel:`  
**Namespace URI:** `https://travel-ontology.ai/vocab#`  
**Concept Scheme:** `travel:TravelScheme`  
**Type:** SKOS Concept Scheme  
**Creator:** [ngan199/travel-ai-platform](https://github.com/ngan199/travel-ai-platform)  
**Definition:** A mid-level SKOS taxonomy for a travel AI knowledge graph covering destinations, venues, experiences, lodging, transport, and traveler content.

---

## Prefixes Used

```turtle
@prefix travel: <https://travel-ontology.ai/vocab#> .
@prefix dc:     <http://purl.org/dc/elements/1.1/> .
@prefix rdf:    <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs:   <http://www.w3.org/2000/01/rdf-schema#> .
@prefix skos:   <http://www.w3.org/2004/02/skos/core#> .
@prefix wd:     <http://www.wikidata.org/entity/> .
```

---

## Custom Properties

| Property | Domain | Range | Definition |
|---|---|---|---|
| `travel:lemma_phrase` | `skos:Concept` | `rdfs:Literal` | Lemmatised phrase pattern used for NLP extraction (e.g. `"NOUN.city"`) |
| `travel:ner_label` | `skos:Concept` | `rdfs:Literal` | Whether this concept is a named entity target (`true`/`false`) |
| `travel:within_chunk` | `skos:Concept` | `rdfs:Literal` | Source text chunk from which an entity was extracted |
| `travel:follows_lexically` | `skos:Concept` | `skos:Concept` | Sequential co-occurrence of extracted entities in a lexical graph |
| `travel:co_occurs_with` | `skos:Concept` | `skos:Concept` | Neighbourhood co-occurrence of extracted entities in a lexical graph |
| `travel:compound_elem_of` | `skos:Concept` | `skos:Concept` | Extracted entity potentially included in a longer compound phrase |
| `travel:located_in` | `travel:Place` | `travel:Place` | A place is situated within another place |
| `travel:near_to` | `travel:Destination` | `travel:Destination` | A destination is geographically near another destination |

---

## Concept Hierarchy

```
travel:Tourism  (top concept)
├── travel:Place
│   ├── travel:Destination
│   │   ├── travel:Country
│   │   ├── travel:City
│   │   ├── travel:Region
│   │   ├── travel:Province
│   │   ├── travel:District
│   │   └── travel:Neighborhood
│   └── travel:Venue
│       ├── travel:Park
│       ├── travel:Market
│       ├── travel:Restaurant
│       └── travel:Hub
│           ├── travel:Airport
│           ├── travel:Port
│           ├── travel:Bus
│           └── travel:Train
├── travel:Experience
│   ├── travel:Activity
│   ├── travel:Festival
│   ├── travel:Event
│   ├── travel:Tour
│   └── travel:Trip
├── travel:Lodging
│   ├── travel:Hotel
│   ├── travel:Hostel
│   ├── travel:Resort
│   ├── travel:Guesthouse
│   ├── travel:Homestay
│   ├── travel:Villa
│   └── travel:Camping
├── travel:Transport
│   ├── travel:Regional
│   └── travel:Transit
├── travel:Classification
│   ├── travel:Budget
│   ├── travel:Style
│   ├── travel:Route
│   └── travel:Traveler
├── travel:Knowledge
│   ├── travel:Cuisine
│   ├── travel:Norm
│   ├── travel:Law
│   └── travel:Safety
├── travel:Practical
│   ├── travel:Language
│   ├── travel:Currency
│   └── travel:Entry
│       ├── travel:Visa
│       ├── travel:Health
│       └── travel:Insurance
├── travel:Temporal
│   ├── travel:Season
│   └── travel:Month
└── travel:Content
    ├── travel:Review
    ├── travel:Insight
    ├── travel:Tip
    └── travel:Warning
```

---

## Concepts

### Place

| Concept | prefLabel | altLabel | Wikidata | NER | Definition |
|---|---|---|---|---|---|
| `travel:Place` | Place | Location | Q2221906 | yes | A geographic location on or near Earth |
| `travel:Destination` | Tourist Destination | Travel Destination | Q1200957 | yes | A place attracting many tourists; a geographic area targeted by travelers |
| `travel:Country` | Country | Nation | Q6256 | yes | A distinct territorial body or political entity |
| `travel:City` | City | Town | Q515 | yes | A large human settlement |
| `travel:Region` | Region | — | — | yes | An area defined by geographic, political, or cultural boundaries within a country |
| `travel:Province` | Province | State | Q34876 | yes | An administrative division of a country |
| `travel:District` | District | — | Q149621 | yes | A subdivision of a city or region for administrative or geographic purposes |
| `travel:Neighborhood` | Neighborhood | Quarter | Q123705 | yes | A geographically localized community within a larger city or town |

### Venue

| Concept | prefLabel | altLabel | Wikidata | NER | Definition |
|---|---|---|---|---|---|
| `travel:Venue` | Venue | Attraction | Q18674739 | yes | A location suitable for visiting, hosting events, or tourist activities |
| `travel:Park` | National Park | — | Q46169 | yes | A protected area used for conservation of animal life and plants |
| `travel:Market` | Food Market | Night Market | Q28142754 | yes | A market specializing in fresh or processed food products, often a key travel attraction |
| `travel:Restaurant` | Restaurant | Eatery | Q11707 | yes | A single establishment which prepares and serves food |

### Transport Hub

| Concept | prefLabel | altLabel | Wikidata | NER | Definition |
|---|---|---|---|---|---|
| `travel:Hub` | Transport Hub | Transit Hub | Q2298537 | yes | A place where passengers and cargo are exchanged between vehicles or modes of transport |
| `travel:Airport` | Airport | — | Q1248784 | yes | A location where aircraft take off and land with extended support facilities |
| `travel:Port` | Port | Ferry Terminal | Q44782 | yes | A maritime facility where ships may dock to load and discharge passengers and cargo |
| `travel:Bus` | Bus Station | Bus Terminal | Q494829 | yes | A structure where city or intercity buses stop to pick up and drop off passengers |
| `travel:Train` | Train Station | Railway Station | Q55488 | yes | A railway facility where trains regularly stop to load or unload passengers and freight |

### Experience

| Concept | prefLabel | altLabel | Wikidata | NER | Definition |
|---|---|---|---|---|---|
| `travel:Experience` | Experience | — | — | no | Any planned or spontaneous encounter a traveler has while visiting a destination |
| `travel:Activity` | Activity | — | Q1914636 | yes | A series of actions done by an agent, typically leisure or tourist in nature |
| `travel:Festival` | Festival | Cultural Festival | Q132241 | yes | An organized set of events or activities focused on a theme that recurs regularly |
| `travel:Event` | Event | Public Event | Q1656682 | yes | A temporary and scheduled happening such as a concert, market, or public gathering |
| `travel:Tour` | Tour | Guided Tour | Q1029698 | yes | A tour of any type of destination led by a guide |
| `travel:Trip` | Day Trip | Excursion | Q15850009 | no | A visit to a destination that does not require an overnight stay |

### Lodging

| Concept | prefLabel | altLabel | Wikidata | NER | Definition |
|---|---|---|---|---|---|
| `travel:Lodging` | Lodging | Accommodation | Q5056668 | no | A facility providing temporary accommodations for travelers |
| `travel:Hotel` | Hotel | — | Q27686 | yes | A business providing indoor lodging in a single location paid on a short-term basis |
| `travel:Hostel` | Hostel | — | Q654772 | yes | Cheap, sociable accommodation typically offering shared dormitory-style rooms |
| `travel:Resort` | Resort | — | Q875157 | yes | A self-contained commercial establishment providing for most of a vacationer's wants |
| `travel:Guesthouse` | Guesthouse | Guest House | Q2460422 | yes | Basic accommodation, typically smaller and family-run |
| `travel:Homestay` | Homestay | — | Q1134688 | yes | A form of lodging where a traveler rents a room in a private family home |
| `travel:Villa` | Villa | — | Q3950 | yes | A house or property rented for holiday stays |
| `travel:Camping` | Camping | Campsite | Q832778 | no | A place used for overnight stay in tents, caravans, or mobile homes |

### Transport

| Concept | prefLabel | altLabel | Wikidata | NER | Definition |
|---|---|---|---|---|---|
| `travel:Transport` | Transport | Transportation | Q334166 | no | A mode of transport used by travelers to move between or within destinations |
| `travel:Regional` | Regional Transport | Local Transport | — | no | Transport covering movement within a destination or between nearby localities |
| `travel:Transit` | Transit | Long-Haul Transport | — | no | Transport covering travel between distinct destinations such as flights or intercity trains |

### Classification

| Concept | prefLabel | altLabel | Wikidata | NER | Definition |
|---|---|---|---|---|---|
| `travel:Classification` | Classification | — | — | no | A system for categorizing travel experiences, travelers, and destinations |
| `travel:Budget` | Budget | Travel Budget | — | no | A classification of travel spending levels such as budget, mid-range, or luxury |
| `travel:Style` | Travel Style | — | — | no | The nature or theme of a trip such as adventure, cultural, beach, or wellness |
| `travel:Route` | Route | Itinerary | — | no | A planned sequence of destinations and transport links for a journey |
| `travel:Traveler` | Traveler | — | — | no | A categorization of travelers by profile such as solo, family, or backpacker |

### Knowledge

| Concept | prefLabel | altLabel | Wikidata | NER | Definition |
|---|---|---|---|---|---|
| `travel:Knowledge` | Local Knowledge | — | Q25469578 | no | Cultural, culinary, legal, and safety information about a destination |
| `travel:Cuisine` | Cuisine | Food Culture | Q1778821 | yes | The characteristic style of cooking practices and traditions of a destination |
| `travel:Norm` | Social Norm | Cultural Custom | Q205665 | no | An informal understanding of acceptable conduct specific to a destination's culture |
| `travel:Law` | Local Law | Regulation | Q7748 | no | Legal rules and regulations specific to a destination that travelers must observe |
| `travel:Safety` | Safety | Safety Warning | — | no | Practical advice for travelers about risks and precautions at a destination |

### Practical Information

| Concept | prefLabel | altLabel | Wikidata | NER | Definition |
|---|---|---|---|---|---|
| `travel:Practical` | Practical Information | Travel Essentials | — | no | Practical information covering language, currency, and entry requirements |
| `travel:Language` | Language | — | Q34770 | yes | A particular system of communication, often named for the region or peoples that use it |
| `travel:Currency` | Currency | — | Q8142 | yes | A generally accepted medium of exchange used in a destination |
| `travel:Entry` | Entry Requirement | — | — | no | Conditions a traveler must meet to enter a destination country |
| `travel:Visa` | Visa | — | Q170404 | no | An authorization document permitting a traveler to enter, stay in, or leave a country |
| `travel:Health` | Health Requirement | Vaccination Requirement | — | no | Medical or vaccination prerequisites for entering a destination |
| `travel:Insurance` | Insurance Requirement | — | — | no | Mandatory travel insurance conditions required for entering a destination |

### Temporal

| Concept | prefLabel | altLabel | Wikidata | NER | Definition |
|---|---|---|---|---|---|
| `travel:Temporal` | Temporal | — | — | no | Time-based aspects of travel including seasons and months |
| `travel:Season` | Season | — | Q10688145 | no | A section of the year defined by cultural, climatic, or tourism characteristics |
| `travel:Month` | Month | — | Q5151 | no | A unit of time dividing a calendar year, used to describe weather and travel conditions |

### Content

| Concept | prefLabel | altLabel | Wikidata | NER | Definition |
|---|---|---|---|---|---|
| `travel:Content` | Content | — | — | no | User-generated information about destinations including reviews, insights, tips, and warnings |
| `travel:Review` | Traveler Review | Review | Q265158 | no | An evaluation of a destination, accommodation, or activity written by a traveler |
| `travel:Insight` | Traveler Insight | — | — | no | An observation or non-obvious piece of advice derived from personal travel experience |
| `travel:Tip` | Traveler Tip | Travel Tip | — | no | Practical advice shared by travelers to help others navigate a destination |
| `travel:Warning` | Traveler Warning | Travel Advisory | — | no | A cautionary notice about risks or hazards at a destination |
