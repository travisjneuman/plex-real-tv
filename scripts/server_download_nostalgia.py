r"""Batch download nostalgia-focused commercials (Nickelodeon, Cartoon Network, Disney, etc).

Runs alongside server_download_commercials.py for additional variety.
Downloads to F:\Commercials\{decade}\ on the local machine.
Target: up to 1,000 per decade.
"""

from __future__ import annotations

import sys
import os
from pathlib import Path

# Force UTF-8 output on Windows to avoid cp1252 encoding crashes
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

# Add yt-dlp to path if needed
sys.path.insert(0, r"C:\Python313\Lib\site-packages")
import yt_dlp

# Nostalgia-focused search queries — networks, toys, tech, vehicles, family TV
DECADE_QUERIES: dict[str, list[str]] = {
    "pre-80s": [
        # Kids TV / cartoons
        "Hanna Barbera cartoon commercial vintage",
        "Flintstones sponsor commercial vintage",
        "Jetsons commercial break vintage",
        "Scooby Doo commercial break vintage 70s",
        "Saturday morning cartoon commercial 1960s",
        "Saturday morning cartoon commercial 1970s",
        "Captain Kangaroo commercial vintage",
        "Sesame Street sponsor commercial vintage",
        "Electric Company commercial break 70s",
        "HR Pufnstuf commercial break vintage",
        # Toys
        "Barbie doll commercial vintage 1960s",
        "GI Joe original commercial vintage 1960s",
        "Hot Wheels original commercial 1968",
        "Matchbox cars vintage commercial",
        "Play-Doh vintage commercial 1960s",
        "Silly Putty vintage commercial",
        "Rock Em Sock Em Robots commercial vintage",
        "Mouse Trap board game commercial vintage",
        "Operation board game commercial vintage",
        "Lite Brite commercial vintage",
        "Etch A Sketch original commercial vintage",
        "Spirograph commercial vintage 1960s",
        "View-Master commercial vintage",
        "Lincoln Logs commercial vintage",
        "Erector Set commercial vintage",
        "Tinkertoy commercial vintage",
        # Technology
        "old Magnavox Odyssey commercial 1972",
        "Atari Pong commercial vintage 1975",
        "old calculator commercial 1970s",
        "vintage color TV commercial 1960s",
        "old transistor radio commercial vintage",
        "8 track tape player commercial vintage",
        "old cassette tape recorder commercial 70s",
        "vintage hi-fi stereo commercial 1960s 1970s",
        # Vehicles
        "Corvette commercial vintage 1960s",
        "Cadillac commercial vintage 1950s 1960s",
        "Volkswagen Beetle commercial vintage Think Small",
        "Ford Thunderbird vintage commercial",
        "Pontiac GTO commercial vintage 1960s",
        "Dodge Charger commercial vintage 1960s",
        "AMC Gremlin Pacer commercial vintage",
        "Datsun commercial vintage 1970s",
        "Honda Civic original commercial 1970s",
        # TV Guide / network promos
        "TV Guide commercial vintage",
        "ABC fall lineup commercial vintage 1970s",
        "CBS fall lineup commercial vintage 1970s",
        "NBC fall lineup commercial vintage 1970s",
        "ABC Afterschool Special promo vintage",
    ],
    "80s": [
        # Nickelodeon
        "Nickelodeon commercial 1980s",
        "Nick at Nite commercial 80s",
        "Double Dare Nickelodeon commercial",
        "You Can't Do That on Television commercial",
        "Nickelodeon slime commercial 80s",
        "Pinwheel Nickelodeon commercial",
        "Mr. Wizard Nickelodeon commercial",
        # Disney / ABC
        "Disney Channel commercial 1980s",
        "Wonderful World of Disney commercial 80s",
        "Disney Sunday Movie commercial 80s",
        "TGIF ABC commercial 80s",
        "ABC Saturday morning commercial 80s",
        "ABC Afterschool Special commercial 80s",
        # Cartoon Network era / syndicated cartoons
        "Voltron commercial 80s cartoon",
        "G.I. Joe cartoon commercial 80s toy",
        "He-Man Masters Universe commercial 80s",
        "ThunderCats commercial 80s cartoon toy",
        "Transformers cartoon commercial 80s toy",
        "My Little Pony commercial 80s vintage",
        "Jem and the Holograms commercial 80s",
        "Inspector Gadget commercial 80s",
        "Smurfs commercial 80s toy cartoon",
        "Care Bears commercial 80s toy",
        # TV Guide / network
        "TV Guide commercial 80s",
        "NBC Must See TV commercial 80s",
        "CBS commercial break 80s",
        "Fox channel launch commercial 1986",
        "Family Channel CBN commercial 80s",
        # Toys
        "Teddy Ruxpin commercial original",
        "Lite Brite commercial 80s",
        "Simon electronic game commercial 80s",
        "Speak & Spell commercial 80s",
        "View-Master commercial 80s",
        "Lego commercial 80s vintage",
        "Lincoln Logs commercial 80s",
        "Erector Set commercial 80s",
        "Spirograph commercial 80s",
        "Play-Doh commercial 80s",
        "Mr. Potato Head commercial 80s",
        "Easy Bake Oven commercial 80s",
        "Barbie Dream House commercial 80s",
        "Cabbage Patch Kids commercial original 1983",
        "Pound Puppies commercial 80s",
        "Popples commercial 80s",
        "Wuzzles commercial 80s",
        "Madballs commercial 80s",
        "MASK vehicle toy commercial 80s",
        "Robotech toy commercial 80s",
        # Technology
        "Apple IIe commercial 80s",
        "Commodore 64 commercial 80s",
        "Tandy TRS-80 RadioShack commercial",
        "Atari 2600 5200 commercial 80s",
        "ColecoVision commercial 80s",
        "Nintendo Entertainment System commercial 1985",
        "Sega Master System commercial 80s",
        "old VHS VCR commercial 80s",
        "Sony Betamax commercial 80s",
        "answering machine commercial 80s",
        "cordless phone commercial 80s",
        "Casio calculator watch commercial 80s",
        # Vehicles
        "DeLorean commercial 80s",
        "Pontiac Fiero commercial 80s",
        "Chevrolet Camaro commercial 1980s",
        "Ford Mustang commercial 80s",
        "Chrysler minivan commercial 80s",
        "Jeep Cherokee commercial 80s",
        "Toyota Celica commercial 80s",
        "Nissan 300ZX commercial 80s",
        "BMW commercial 80s vintage",
        "Mercedes Benz commercial 80s vintage",
    ],
    "90s": [
        # Nickelodeon
        "Nickelodeon commercial break 90s",
        "Nick at Nite commercial 90s",
        "Nickelodeon Magazine commercial 90s",
        "Nickelodeon Gak Floam commercial",
        "Rugrats Nickelodeon commercial 90s",
        "Doug Nickelodeon commercial 90s",
        "Ren Stimpy commercial 90s",
        "All That Nickelodeon commercial 90s",
        "Legends Hidden Temple commercial",
        "Figure It Out Nickelodeon commercial",
        "Nickelodeon summer commercial 90s",
        # Cartoon Network
        "Cartoon Network commercial 90s",
        "Cartoon Network Dexter Laboratory commercial",
        "Cartoon Network Powerpuff Girls commercial",
        "Cartoon Network Johnny Bravo commercial",
        "Cartoon Network Cow Chicken commercial",
        "Space Ghost Coast to Coast commercial",
        "Toonami commercial break 90s",
        # Disney
        "Disney Channel commercial 90s",
        "Disney Afternoon commercial 90s",
        "Talespin Darkwing Duck commercial 90s",
        "Disney movie VHS commercial 90s",
        "Walt Disney World commercial 90s",
        "Disneyland commercial 90s",
        "ABC One Saturday Morning commercial",
        "Disney Renaissance VHS commercial",
        # TGIF / ABC / Family
        "TGIF ABC commercial 90s",
        "ABC commercial break 90s",
        "Fox Kids commercial break 90s",
        "Kids WB commercial break 90s",
        "Family Channel commercial 90s",
        "ABC Family commercial 90s",
        # TV Guide
        "TV Guide commercial 90s",
        "TV Guide Channel commercial 90s",
        # Toys
        "Pog Slammer commercial 90s",
        "Beanie Babies commercial 90s",
        "Tickle Me Elmo commercial 1996",
        "Furby commercial 1998 original",
        "Easy Bake Oven commercial 90s",
        "Lego commercial 90s",
        "Hot Wheels commercial 90s",
        "Barbie commercial 90s",
        "Power Wheels commercial 90s",
        "Koosh ball commercial 90s",
        "Stretch Armstrong commercial 90s",
        "Razor scooter commercial 90s",
        "Socker Boppers commercial 90s",
        "Giga Pets virtual pet commercial 90s",
        "Nano Baby virtual pet commercial 90s",
        # Technology
        "Windows 95 commercial Start Me Up",
        "iMac commercial 1998 colorful",
        "America Online AOL commercial 90s",
        "Prodigy internet commercial 90s",
        "CompuServe commercial 90s",
        "Sony PlayStation commercial 1995",
        "Nintendo 64 commercial 1996",
        "Game Boy Color commercial 90s",
        "Sega Saturn commercial 1995",
        "Sega Dreamcast commercial 1999",
        "Palm Pilot commercial 90s",
        "Motorola StarTAC commercial 90s",
        "Nokia cell phone commercial 90s",
        "pager beeper commercial 90s",
        # Vehicles
        "Dodge Viper commercial 90s",
        "Ford Explorer commercial 90s",
        "Jeep Grand Cherokee commercial 90s",
        "Honda Accord commercial 90s",
        "Toyota Camry commercial 90s",
        "Saturn car commercial no haggle 90s",
        "Isuzu Rodeo commercial 90s",
        "Mitsubishi Eclipse commercial 90s",
    ],
    "2000s": [
        # Nickelodeon
        "Nickelodeon commercial break 2000s",
        "SpongeBob SquarePants commercial 2000s",
        "Fairly OddParents commercial 2000s",
        "Jimmy Neutron commercial 2000s",
        "Avatar Last Airbender commercial",
        "Drake Josh Nickelodeon commercial",
        "iCarly commercial Nickelodeon",
        "Nickelodeon slime commercial 2000s",
        # Cartoon Network
        "Cartoon Network commercial 2000s",
        "Ed Edd Eddy commercial 2000s",
        "Samurai Jack commercial 2000s",
        "Teen Titans commercial 2000s",
        "Foster Home Imaginary Friends commercial",
        "Ben 10 commercial 2000s",
        "Adult Swim commercial bump 2000s",
        # Disney
        "Disney Channel commercial 2000s",
        "That's So Raven commercial Disney",
        "Kim Possible commercial Disney Channel",
        "Lizzie McGuire commercial Disney",
        "High School Musical commercial Disney",
        "Hannah Montana commercial Disney Channel",
        "Disney World commercial 2000s",
        "Disney Pixar movie commercial 2000s",
        "ABC Family commercial 2000s",
        # TV networks
        "ABC commercial break 2000s",
        "NBC commercial break 2000s",
        "Fox commercial break 2000s",
        "CBS commercial break 2000s",
        "TBS very funny commercial 2000s",
        "TV Land commercial 2000s",
        # Toys
        "Bratz doll commercial 2000s",
        "Beyblades commercial 2000s",
        "Yu-Gi-Oh cards commercial 2000s",
        "Bionicle Lego commercial 2000s",
        "Webkinz commercial 2000s",
        "Build-A-Bear commercial 2000s",
        "Zhu Zhu Pets commercial 2000s",
        "Bakugan commercial 2000s",
        # Technology
        "iPod Nano commercial 2000s",
        "iPod Touch commercial 2000s",
        "iPhone original commercial 2007",
        "Blackberry commercial 2000s",
        "Motorola RAZR commercial",
        "Sidekick phone commercial 2000s",
        "Xbox original commercial 2001",
        "Xbox 360 commercial 2005",
        "PlayStation 3 commercial 2006",
        "Nintendo DS commercial 2004",
        "Nintendo Wii commercial 2006",
        "PSP commercial 2005",
        "TiVo DVR commercial 2000s",
        "HD television commercial 2000s",
        "Blu-ray DVD commercial 2000s",
        # Vehicles
        "Hummer H2 commercial 2000s",
        "Mini Cooper commercial 2000s",
        "Toyota Prius commercial 2000s",
        "Scion xB commercial 2000s",
        "Chrysler 300 commercial 2000s",
        "Cadillac Escalade commercial 2000s",
    ],
    "2010s": [
        # Nickelodeon
        "Nickelodeon commercial 2010s",
        "Nickelodeon SpongeBob commercial 2010s",
        "Nickelodeon PAW Patrol commercial",
        "Nickelodeon Teenage Mutant Ninja Turtles commercial 2012",
        "Nick Jr commercial 2010s",
        # Cartoon Network
        "Cartoon Network commercial 2010s",
        "Adventure Time commercial Cartoon Network",
        "Regular Show commercial Cartoon Network",
        "Steven Universe commercial Cartoon Network",
        "Teen Titans Go commercial",
        "Amazing World of Gumball commercial",
        # Disney
        "Disney Channel commercial 2010s",
        "Disney XD commercial 2010s",
        "Frozen Disney commercial 2013",
        "Star Wars Disney commercial 2015",
        "Marvel Avengers commercial Disney",
        "Disney Plus launch commercial 2019",
        "Disney World commercial 2010s",
        # Streaming era
        "Hulu commercial 2010s",
        "Netflix commercial 2010s",
        "Amazon Prime Video commercial 2010s",
        "YouTube Premium commercial 2010s",
        "Roku commercial 2010s",
        "Chromecast commercial 2010s",
        "Apple TV commercial 2010s",
        "HBO Now commercial 2010s",
        # TV networks
        "ABC commercial break 2010s",
        "NBC commercial break 2010s",
        "Fox commercial break 2010s",
        "CBS commercial break 2010s",
        "Freeform commercial 2010s",
        # Toys
        "Lego commercial 2010s",
        "Nerf commercial 2010s",
        "Hatchimals commercial 2016",
        "Fingerlings commercial 2017",
        "LOL Surprise commercial 2010s",
        "Shopkins commercial 2010s",
        "Pie Face game commercial 2010s",
        "Speak Out game commercial 2010s",
        # Technology
        "iPhone commercial 2010s Apple",
        "Samsung Galaxy S commercial 2010s",
        "Google Pixel phone commercial",
        "iPad commercial 2010",
        "Apple Watch commercial",
        "Fitbit commercial 2010s",
        "GoPro commercial 2010s",
        "Tesla commercial fan made 2010s",
        "PlayStation 4 commercial 2013",
        "Xbox One commercial 2013",
        "Nintendo Switch commercial 2017",
        "Nintendo 3DS commercial 2011",
        "Oculus VR commercial 2010s",
        "smart speaker Echo Google Home commercial",
        "Ring doorbell commercial 2010s",
        "Nest thermostat commercial 2010s",
        # Vehicles
        "Tesla Model 3 commercial 2017",
        "Chevy real people commercial 2010s",
        "Ford F-150 commercial 2010s",
        "Jeep Wrangler commercial 2010s",
        "Subaru love commercial 2010s",
        "Toyota commercial 2010s Let's Go Places",
        "Hyundai Super Bowl commercial 2010s",
        "Kia hamster commercial soul",
    ],
}

DECADE_TARGETS: dict[str, int] = {
    "pre-80s": 1000,
    "80s": 1000,
    "90s": 1000,
    "2000s": 1000,
    "2010s": 1000,
}

TARGET_PER_DECADE = 1000
OUTPUT_BASE = Path(r"F:\Commercials")

# Duration filter: 10s-300s
MIN_DURATION = 10
MAX_DURATION = 300


def search_and_download(decade: str, queries: list[str], target: int) -> int:
    """Search YouTube and download individual commercial clips for a decade."""
    output_dir = OUTPUT_BASE / decade
    output_dir.mkdir(parents=True, exist_ok=True)

    existing = len(list(output_dir.glob("*.mp4")))
    remaining = target - existing
    if remaining <= 0:
        print(f"[{decade}] Already have {existing} files, target is {target}. Skipping.")
        return existing

    print(f"[{decade}] Have {existing} files, need {remaining} more (target: {target})")

    downloaded = 0
    seen_ids: set[str] = set()
    existing_names = {f.stem.lower() for f in output_dir.glob("*.mp4")}

    for query in queries:
        if downloaded >= remaining:
            break

        print(f"\n  [{decade}] Searching: {query} ({downloaded}/{remaining} so far)")

        search_opts: dict[str, object] = {
            "extract_flat": True,
            "quiet": True,
            "no_warnings": True,
        }
        search_url = f"ytsearch50:{query}"

        try:
            with yt_dlp.YoutubeDL(search_opts) as ydl:
                info = ydl.extract_info(search_url, download=False)
        except Exception as e:
            print(f"    Search failed: {e}")
            continue

        if not info or not info.get("entries"):
            print("    No results")
            continue

        for entry in info["entries"]:
            if downloaded >= remaining:
                break
            if entry is None:
                continue

            vid_id = entry.get("id", "")
            if vid_id in seen_ids:
                continue
            seen_ids.add(vid_id)

            duration = entry.get("duration") or 0
            if duration < MIN_DURATION or duration > MAX_DURATION:
                continue

            title = entry.get("title", "Unknown")
            title_lower = title.lower()

            # Skip compilations
            if any(word in title_lower for word in [
                "compilation", "hours", "hour", "collection", "marathon",
                "top 10", "top 20", "top 5", "top 50", "top 100", "best of",
                "every commercial", "all commercials", "commercial block",
                "commercial break", "full episode",
            ]):
                continue

            url = entry.get("url") or entry.get("webpage_url") or f"https://www.youtube.com/watch?v={vid_id}"

            print(f"    [{existing + downloaded + 1}] {title[:60]}... ({duration}s)")

            outtmpl = str(output_dir / "%(title).150s - %(channel).30s (%(upload_date>%Y)s).%(ext)s")
            dl_opts: dict[str, object] = {
                "format": "best[height<=720][ext=mp4]/best[height<=720]/best",
                "outtmpl": outtmpl,
                "merge_output_format": "mp4",
                "quiet": True,
                "no_warnings": True,
                "socket_timeout": 30,
                "retries": 2,
            }

            try:
                with yt_dlp.YoutubeDL(dl_opts) as ydl:
                    ydl.download([url])
                downloaded += 1
            except Exception as e:
                print(f"      FAILED: {e}")

    total = existing + downloaded
    print(f"\n[{decade}] Done: {total} total files ({downloaded} new)")
    return total


if __name__ == "__main__":
    if len(sys.argv) > 1:
        decade_arg = sys.argv[1]
        if decade_arg not in DECADE_QUERIES:
            print(f"Unknown decade: {decade_arg}. Available: {list(DECADE_QUERIES.keys())}")
            sys.exit(1)
        OUTPUT_BASE.mkdir(parents=True, exist_ok=True)
        target = DECADE_TARGETS.get(decade_arg, TARGET_PER_DECADE)
        count = search_and_download(decade_arg, DECADE_QUERIES[decade_arg], target)
        print(f"\n{decade_arg}: {count} total files")
    else:
        OUTPUT_BASE.mkdir(parents=True, exist_ok=True)
        grand_total = 0
        for decade, queries in DECADE_QUERIES.items():
            target = DECADE_TARGETS.get(decade, TARGET_PER_DECADE)
            count = search_and_download(decade, queries, target)
            grand_total += count
        print(f"\nGrand total: {grand_total} commercial clips")
