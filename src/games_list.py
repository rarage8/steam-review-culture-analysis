"""
対象ゲームリスト（約100タイトル）
ジャンル・地域・知名度を横断的にカバーする設計
"""

# (タイトル, appid, ジャンル, 主要開発地域)
GAMES: list[tuple[str, int, str, str]] = [
    # ─── アクション / アクションRPG ───
    ("Dark Souls III",              374320,  "action_rpg",    "JP"),
    ("Elden Ring",                  1245620, "action_rpg",    "JP"),
    ("Sekiro: Shadows Die Twice",   814380,  "action_rpg",    "JP"),
    ("NieR: Automata",              524220,  "action_rpg",    "JP"),
    ("Monster Hunter: World",       582010,  "action_rpg",    "JP"),
    ("Devil May Cry 5",             601150,  "action",        "JP"),
    ("Bayonetta",                   1253920, "action",        "JP"),
    ("Nioh 2",                      1325200, "action_rpg",    "JP"),
    ("Ghost of Tsushima",           2215430, "action_rpg",    "JP"),  # PC版
    ("Hades",                       1145360, "action_rpg",    "US"),
    ("Dead Cells",                  588650,  "action",        "FR"),
    ("Hollow Knight",               367520,  "metroidvania",  "AU"),
    ("Cuphead",                     268910,  "action",        "CA"),
    ("Celeste",                     504230,  "platformer",    "CA"),
    ("Ori and the Blind Forest",    261570,  "platformer",    "AT"),
    ("Ori and the Will of the Wisps", 1057090, "platformer",  "AT"),

    # ─── FPS / TPS / シューター ───
    ("Counter-Strike 2",            730,     "fps",           "US"),
    ("Apex Legends",                1172470, "battle_royale", "US"),
    ("PUBG: BATTLEGROUNDS",         578080,  "battle_royale", "KR"),
    ("Rust",                        252490,  "survival",      "UK"),
    ("Left 4 Dead 2",               550,     "fps",           "US"),
    ("Team Fortress 2",             440,     "fps",           "US"),
    ("Destiny 2",                   1085660, "fps_rpg",       "US"),
    ("Rainbow Six Siege",           359550,  "fps",           "FR"),
    ("Payday 2",                    218620,  "fps",           "SE"),
    ("Borderlands 3",               397540,  "fps_rpg",       "US"),
    ("Deep Rock Galactic",          548430,  "fps",           "DK"),
    ("Warframe",                    230410,  "fps_rpg",       "CA"),

    # ─── オープンワールド / RPG ───
    ("Cyberpunk 2077",              1091500, "open_world_rpg","PL"),
    ("The Witcher 3: Wild Hunt",    292030,  "rpg",           "PL"),
    ("GTA V",                       271590,  "open_world",    "US"),
    ("Red Dead Redemption 2",       1174180, "open_world",    "US"),
    ("Skyrim Special Edition",      489830,  "rpg",           "US"),
    ("Fallout 4",                   377160,  "rpg",           "US"),
    ("Mass Effect Legendary Edition",1328670,"rpg",           "CA"),
    ("Dragon Age: Inquisition",     1222690, "rpg",           "CA"),
    ("Baldur's Gate 3",             1086940, "crpg",          "BE"),
    ("Divinity: Original Sin 2",    435150,  "crpg",          "BE"),
    ("Disco Elysium",               632470,  "rpg",           "EE"),
    ("Pathfinder: Wrath of the Righteous", 1184370, "crpg",  "RU"),
    ("Persona 4 Golden",            1113000, "jrpg",          "JP"),
    ("Persona 5 Royal",             1687950, "jrpg",          "JP"),
    ("Final Fantasy XIV",           39210,   "mmorpg",        "JP"),
    ("Dragon Quest XI S",           1358750, "jrpg",          "JP"),
    ("Tales of Arise",              1277860, "jrpg",          "JP"),

    # ─── サンドボックス / サバイバル / シミュレーション ───
    ("Minecraft",                   1672970, "sandbox",       "SE"),
    ("Terraria",                    105600,  "sandbox",       "US"),
    ("Valheim",                     892970,  "survival",      "SE"),
    ("Subnautica",                  264710,  "survival",      "US"),
    ("The Forest",                  242760,  "survival",      "CA"),
    ("Satisfactory",                526870,  "factory",       "SE"),
    ("Factorio",                    427520,  "factory",       "CZ"),
    ("RimWorld",                    294100,  "simulation",    "CA"),
    ("Dwarf Fortress",              975370,  "simulation",    "US"),
    ("Cities: Skylines",            255710,  "city_builder",  "FI"),
    ("Planet Coaster",              493340,  "management",    "UK"),
    ("Euro Truck Simulator 2",      227300,  "simulation",    "CZ"),

    # ─── インディー / アドベンチャー ───
    ("Stardew Valley",              413150,  "indie_farm",    "US"),
    ("Among Us",                    945360,  "party",         "US"),
    ("Undertale",                   391540,  "indie_rpg",     "US"),
    ("Deltarune",                   1671210, "indie_rpg",     "US"),
    ("Spiritfarer",                 972660,  "indie",         "CA"),
    ("A Short Hike",                1055540, "indie",         "CA"),
    ("Disco Elysium – The Final Cut",632470, "rpg",           "EE"),
    ("What Remains of Edith Finch", 501300,  "adventure",     "US"),
    ("Oxenfree",                    388880,  "adventure",     "US"),
    ("Firewatch",                   383870,  "adventure",     "US"),
    ("The Stanley Parable: Ultra Deluxe", 1703340, "adventure","US"),

    # ─── ホラー / サスペンス ───
    ("Resident Evil 2",             883710,  "horror",        "JP"),
    ("Resident Evil Village",       1196590, "horror",        "JP"),
    ("Dead by Daylight",            381210,  "horror",        "CA"),
    ("Phasmophobia",                739630,  "horror",        "UK"),
    ("SOMA",                        282140,  "horror",        "SE"),
    ("Alien: Isolation",            214490,  "horror",        "UK"),

    # ─── ストラテジー / タクティクス ───
    ("Civilization VI",             289070,  "strategy",      "US"),
    ("Total War: Warhammer III",    1142710, "strategy",      "UK"),
    ("Stellaris",                   281990,  "grand_strategy","SE"),
    ("Hearts of Iron IV",           394360,  "grand_strategy","SE"),
    ("XCOM 2",                      268500,  "tactics",       "US"),
    ("Into the Breach",             590380,  "tactics",       "US"),
    ("Slay the Spire",              646570,  "deckbuilder",   "US"),
    ("Monster Train",               1102190, "deckbuilder",   "US"),
    ("Darkest Dungeon",             262060,  "rpg",           "CA"),

    # ─── MOBA / オンライン競技 ───
    ("Dota 2",                      570,     "moba",          "US"),
    ("Path of Exile",               238960,  "arpg",          "NZ"),
    ("Lost Ark",                    1599340, "mmorpg",        "KR"),

    # ─── スポーツ / レーシング ───
    ("Rocket League",               252950,  "sports",        "US"),
    ("FIFA 23",                     1811260, "sports",        "CA"),
    ("F1 23",                       2108330, "racing",        "UK"),

    # ─── パズル ───
    ("Portal 2",                    620,     "puzzle",        "US"),
    ("The Talos Principle",         257510,  "puzzle",        "HR"),
    ("Baba Is You",                 736260,  "puzzle",        "FI"),

    # ─── ビジュアルノベル / ADV ───
    ("Steins;Gate",                 412830,  "visual_novel",  "JP"),
    ("Doki Doki Literature Club!", 698780,  "visual_novel",  "US"),
    ("13 Sentinels: Aegis Rim",     1115827, "visual_novel",  "JP"),

    # ─── ローグライク / ローグライト ───
    ("Binding of Isaac: Rebirth",   250900,  "roguelite",     "US"),
    ("Risk of Rain 2",              632360,  "roguelite",     "US"),
    ("Noita",                       881100,  "roguelite",     "FI"),
    ("Vampire Survivors",           1794680, "roguelite",     "IT"),
]  # END_GAMES

# 設計書の5タイトル（Phase 1 優先タイトル）
CORE_GAMES: dict[str, int] = {
    "dark_souls_3":   374320,
    "stardew_valley": 413150,
    "cs2":            730,
    "cyberpunk":      1091500,
    "minecraft":      1672970,
}

# ゲーム名 → appid の辞書（全タイトル）
GAME_MAP: dict[str, int] = {title: appid for title, appid, *_ in GAMES}

# ジャンル → タイトルリスト
GAMES_BY_GENRE: dict[str, list[tuple[str, int]]] = {}
for title, appid, genre, region in GAMES:
    GAMES_BY_GENRE.setdefault(genre, []).append((title, appid))


if __name__ == "__main__":
    print(f"Total games: {len(GAMES)}")
    genres = sorted({g for _, _, g, _ in GAMES})
    print(f"Genres ({len(genres)}): {', '.join(genres)}")
    regions = sorted({r for _, _, _, r in GAMES})
    print(f"Dev regions ({len(regions)}): {', '.join(regions)}")
