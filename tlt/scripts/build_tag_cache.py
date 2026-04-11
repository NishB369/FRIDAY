"""
Build a local tag cache: slug → [tags from predefined list]
Predefined tags: Fiction, Classic, Mystery, Romance, Sci-Fi, Fantasy,
                 Non-Fiction, History, Biography, Thriller, Horror,
                 Dystopian, Adventure, Philosophy

Output: tlt/processed/tag_cache.json
"""

import json, os, re

NOTES_DIR = '/Users/nishb369/Desktop/FRIDAY/tlt/processed/notes'
OUT_FILE  = '/Users/nishb369/Desktop/FRIDAY/tlt/processed/tag_cache.json'

VALID_TAGS = {
    "Fiction", "Classic", "Mystery", "Romance", "Sci-Fi", "Fantasy",
    "Non-Fiction", "History", "Biography", "Thriller", "Horror",
    "Dystopian", "Adventure", "Philosophy"
}

# Manual mapping: slug_fragment (substring match) → tags
# Ordered from most specific to least specific
RULES = [
    # ── Specific works ──────────────────────────────────────────────────────────
    ("sultanas_dream",                          ["Fiction", "Sci-Fi", "Fantasy", "Classic"]),
    ("philemon_and_baucis",                     ["Fiction", "Fantasy", "Classic"]),
    ("the_swan_king",                           ["Fiction", "Fantasy", "Classic"]),
    ("the_comet_and_the_moon",                  ["Fiction", "Fantasy", "Classic"]),
    ("ones_who_walk_away_from_omelas",          ["Fiction", "Philosophy", "Fantasy"]),

    ("william_tell",                            ["Fiction", "Adventure", "Classic"]),
    ("huck_saves",                              ["Fiction", "Adventure", "Classic"]),
    ("the_real_crusoe",                         ["Fiction", "Adventure", "Classic"]),
    ("seventeen_oranges",                       ["Fiction", "Adventure", "Classic"]),
    ("the_chocolate_room",                      ["Fiction", "Adventure", "Classic"]),
    ("a_feast_on_the_train",                    ["Fiction", "Adventure", "Classic"]),

    ("wuthering_heights",                       ["Fiction", "Classic", "Romance", "Horror"]),
    ("pride_and_prejudice",                     ["Fiction", "Classic", "Romance"]),
    ("the_lady_of_shalott",                     ["Fiction", "Classic", "Romance"]),

    ("beloved",                                 ["Fiction", "Classic", "History"]),
    ("the_color_purple",                        ["Fiction", "Classic", "History"]),
    ("things_fall_apart",                       ["Fiction", "Classic", "History"]),
    ("the_shadow_lines",                        ["Fiction", "Classic", "History"]),
    ("in_custody",                              ["Fiction", "Classic", "History"]),
    ("tara_by_mahesh_dattani",                  ["Fiction", "Classic", "History"]),
    ("comment_on_the_theme_of_partition",       ["Fiction", "Classic", "History"]),
    ("the_character_of_nur",                    ["Fiction", "Classic", "History"]),

    ("the_glass_menagerie",                     ["Fiction", "Classic"]),
    ("character_sketch_in_the_glass_menagerie", ["Fiction", "Classic"]),
    ("the_ending_of_twelfth_night",             ["Fiction", "Classic"]),
    ("abhijan_shakuntalam",                     ["Fiction", "Classic"]),
    ("comment_on_the_themes_discussed_in_abhij",["Fiction", "Classic"]),
    ("salman_rushdies_narrative",               ["Fiction", "Classic"]),
    ("a_horse_and_two_goats",                   ["Fiction", "Classic"]),
    ("the_story_of_shakespeares_sonnets",       ["Fiction", "Classic"]),
    ("ba_english_hons_assignment",              ["Fiction", "Classic"]),  # Dr. Faustus

    # ── Poems / Poetry ──────────────────────────────────────────────────────────
    ("a_poem_for_my_mother",                    ["Fiction", "Classic"]),
    ("a_supermarket_in_california",             ["Fiction", "Classic", "Philosophy"]),
    ("abou_ben_adhem",                          ["Fiction", "Classic"]),
    ("aunt_sues_stories",                       ["Fiction", "Classic", "History"]),
    ("coromandel_fishermen",                    ["Fiction", "Classic"]),
    ("elegy_written_in_a_country",              ["Fiction", "Classic"]),
    ("english_poem_sonnet_1",                   ["Fiction", "Classic", "Romance"]),
    ("sonnet_18",                               ["Fiction", "Classic", "Romance"]),
    ("sonnet_60",                               ["Fiction", "Classic", "Romance"]),
    ("i_cannot_live_with_you",                  ["Fiction", "Classic", "Romance"]),
    ("introduction_to_the_songs_of_innocence",  ["Fiction", "Classic", "Philosophy"]),
    ("the_chimney_sweepers",                    ["Fiction", "Classic", "Philosophy"]),
    ("the_lamb_poem",                           ["Fiction", "Classic", "Philosophy"]),
    ("london_by_william_blake",                 ["Fiction", "Classic", "Philosophy"]),
    ("line_by_line_summary_of_enterprise",      ["Fiction", "Classic"]),
    ("my_grandmothers_house",                   ["Fiction", "Classic"]),
    ("my_mother_at_sixty_six",                  ["Fiction", "Classic"]),
    ("o_captain_my_captain",                    ["Fiction", "Classic", "History"]),
    ("perhaps_the_world_ends_here",             ["Fiction", "Classic", "Philosophy"]),
    ("the_negro_speaks_of_rivers",              ["Fiction", "Classic", "History"]),
    ("the_south_by_langston_hughes",            ["Fiction", "Classic", "History"]),
    ("they_flee_from_me",                       ["Fiction", "Classic", "Romance"]),
    ("touch_meena_kandasamy",                   ["Fiction", "Classic", "History"]),
    ("where_the_mind_is_without_fear",          ["Fiction", "Classic", "Philosophy"]),
    ("whoso_list_to_hunt",                      ["Fiction", "Classic", "Romance"]),

    # ── Essays / Non-Fiction / Critical Theory ───────────────────────────────────
    ("laura_mulvey",                            ["Non-Fiction", "Philosophy"]),
    ("write_an_essay_on_books",                 ["Non-Fiction"]),
    ("a_speech_to_save_environment",            ["Non-Fiction"]),
]

def get_tags(slug: str) -> list[str]:
    for fragment, tags in RULES:
        if fragment in slug:
            return tags
    # Fallback
    return ["Fiction", "Classic"]

# Build cache
cache = {}
for fname in sorted(os.listdir(NOTES_DIR)):
    if not fname.endswith('.md'):
        continue
    slug = fname[:-3]  # strip .md
    cache[slug] = get_tags(slug)

# Write
with open(OUT_FILE, 'w') as f:
    json.dump(cache, f, indent=2)

print(f"Written {len(cache)} entries → {OUT_FILE}")

# Quick summary
from collections import Counter
all_tags = [t for tags in cache.values() for t in tags]
tag_freq = Counter(all_tags)
print("\nTag frequency:")
for tag, count in sorted(tag_freq.items(), key=lambda x: -x[1]):
    print(f"  {tag:20s} {count}")
