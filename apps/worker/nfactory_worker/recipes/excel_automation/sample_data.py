"""Synthetic, deterministic CSV exports shipped with the generated project.

They stand in for the user's real exports (same columns) and make the workbook and
its tests reproducible. No randomness: the same brief always yields the same files.
"""

TEAMS = ("Support", "Réseau", "Applications")
WEEKS = 6


def activity_csv() -> str:
    lines = ["semaine;equipe;volume;duree_heures"]
    for week in range(1, WEEKS + 1):
        for index, team in enumerate(TEAMS):
            volume = 40 + (week * 7 + index * 13) % 25
            hours = 1.5 + ((week * 3 + index * 5) % 10) / 4
            lines.append(f"2026-S{week:02d};{team};{volume};{hours:.2f}")
    return "\n".join(lines) + "\n"


def targets_csv() -> str:
    lines = ["equipe;objectif"]
    lines += [f"{team};{280 + index * 20}" for index, team in enumerate(TEAMS)]
    return "\n".join(lines) + "\n"
