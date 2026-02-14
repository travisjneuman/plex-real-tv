r"""Batch download retro commercials directly on the Plex server.

Target: ~2,000 clips across 5 decades (70s-2010s).
Downloads to F:\Commercials\{decade}\ on the local machine.
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

# Diverse search queries per decade — many different angles to get variety
DECADE_QUERIES: dict[str, list[str]] = {
    "pre-80s": [
        # Interleaved across 50s/60s/70s so downloads pull evenly from all eras.
        # Each "round" has one query per era, cycling through product categories.
        # Round 1: general
        "1950s TV commercial vintage",
        "1960s classic TV commercial",
        "1970s classic TV commercial",
        # Round 2: cars
        "1950s car automobile commercial",
        "1960s car commercial vintage",
        "1970s car commercial classic",
        # Round 3: cigarettes/tobacco
        "1950s cigarette commercial",
        "60s cigarette commercial",
        "1970s cigarette commercial",
        # Round 4: cereal/breakfast
        "50s cereal commercial black and white",
        "60s cereal commercial classic",
        "70s cereal commercial vintage",
        # Round 5: soda/drinks
        "50s Coca Cola Pepsi commercial",
        "1960s soda pop commercial",
        "70s soda pop commercial vintage",
        # Round 6: soap/cleaning
        "50s soap detergent commercial vintage",
        "60s household product commercial",
        "70s soap detergent commercial",
        # Round 7: toys
        "1950s toy commercial vintage",
        "60s toy commercial classic",
        "70s toy commercial classic",
        # Round 8: food/kitchen
        "1950s appliance commercial vintage",
        "60s fast food commercial vintage",
        "70s fast food commercial original",
        # Round 9: beer/alcohol
        "1950s beer commercial vintage",
        "1960s beer commercial classic",
        "70s beer commercial vintage",
        # Round 10: candy/snacks
        "1950s candy commercial vintage",
        "60s candy commercial vintage",
        "70s candy commercial vintage",
        # Round 11: specific years
        "1955 TV ad original",
        "1965 TV commercial original",
        "1975 TV advertisement original",
        # Round 12: more specific years
        "1958 TV commercial classic",
        "1968 TV advertisement vintage",
        "1978 TV commercial vintage",
        # Round 13: fashion/personal
        "50s television advertisement classic",
        "60s television advertisement vintage",
        "70s aftershave commercial vintage",
        # Round 14: airlines/travel
        "1950s airline travel commercial",
        "1960s airline commercial vintage",
        "70s airline commercial classic",
        # Round 15: department stores
        "1950s department store commercial",
        "1960s department store commercial vintage",
        "1970s department store commercial",
        # Round 16: more specific years
        "1952 TV commercial vintage",
        "1962 TV commercial original",
        "1972 TV ad original",
        # Round 17: perfume/cologne
        "1950s perfume commercial vintage",
        "1960s perfume cologne commercial",
        "1970s perfume commercial",
        # Round 18: cameras/film/electronics
        "1950s camera film commercial",
        "1960s camera film commercial vintage",
        "1970s camera film commercial",
        # Round 19: coffee/household
        "1950s coffee commercial vintage",
        "1960s coffee commercial classic",
        "70s coffee commercial classic",
        # Round 20: misc years
        "1953 TV commercial vintage",
        "1967 TV ad classic",
        "1977 TV commercial vintage",
        # Round 21: board games/entertainment
        "1950s board game commercial",
        "1960s board game commercial vintage",
        "70s board game commercial",
        # Round 22: insurance/financial
        "1950s insurance commercial",
        "1960s insurance commercial vintage",
        "1970s insurance commercial classic",
        # Round 23: pet food/pets
        "1950s pet food commercial",
        "1960s pet food commercial vintage",
        "1970s pet food commercial",
        # Round 24: shoes/clothing
        "1950s shoes clothing commercial",
        "1960s fashion clothing commercial",
        "70s sneaker shoe commercial vintage",
        # Round 25: Saturday morning / kids
        "1950s Saturday morning commercial",
        "1960s Saturday morning commercial vintage",
        "70s Saturday morning commercial vintage",
        # Round 26: more specific years + misc
        "1957 TV commercial classic",
        "1963 TV commercial vintage",
        "1973 TV advertisement",
        # Round 27: retro compilations (individual clips)
        "early television commercial 1940s 1950s",
        "1960s retro commercial ad",
        "70s retro commercial ad",
        # Round 28: hair/beauty
        "1950s shampoo hair commercial",
        "1960s shampoo hair commercial vintage",
        "1970s shampoo hair commercial",
        # Round 29: music/records
        "1950s record album commercial",
        "1960s record album commercial vintage",
        "70s record album TV commercial",
        # Round 30: remaining 70s with no earlier equivalent
        "1970s jeans fashion commercial",
        "70s disco era commercial",
        "70s cooking food commercial vintage",
        "1971 TV ad classic",
        "1974 TV commercial original",
        "1976 TV advertisement classic",
        "1979 TV commercial original",
        "1970s bank financial commercial vintage",
        "70s electronics stereo commercial",
        "1975 Super Bowl commercial",
        # --- WAVE 2: highly specific brand/product queries ---
        "vintage Folgers coffee commercial",
        "vintage Maxwell House coffee commercial",
        "old Alka Seltzer commercial plop plop",
        "Brylcreem commercial vintage 1950s 1960s",
        "Lucky Strike commercial old",
        "Winston cigarettes tastes good commercial",
        "Camel cigarettes vintage ad commercial",
        "old Chevrolet commercial 1950s 1960s",
        "Ford Mustang 1960s commercial vintage",
        "Chrysler Plymouth vintage commercial",
        "Jello commercial vintage 1950s 1960s",
        "Betty Crocker vintage commercial",
        "Duncan Hines vintage commercial",
        "Pillsbury Doughboy commercial old",
        "Kellogg Frosted Flakes Tony Tiger vintage",
        "old Mr. Clean commercial 1960s",
        "Ajax White Knight commercial vintage",
        "Texaco star commercial vintage",
        "Esso Exxon vintage commercial",
        "Shell Oil old commercial",
        "old Schlitz beer commercial",
        "Pabst Blue Ribbon vintage commercial",
        "Hamm beer bear commercial vintage",
        "Cracker Jack vintage commercial prize",
        "Life cereal Mikey likes it commercial",
        "Oscar Mayer wiener commercial vintage",
        "Alpo dog food vintage commercial",
        "Ken-L Ration dog food commercial vintage",
        "Polaroid camera vintage commercial",
        "vintage RCA Victor television commercial",
        "Zenith television commercial vintage",
        "Admiral television vintage commercial",
        "Ovaltine commercial vintage",
        "Bosco chocolate vintage commercial",
        "Buster Brown shoes vintage commercial",
        "Slinky commercial vintage 1960s",
        "Etch A Sketch commercial vintage",
        "Mr. Potato Head commercial vintage",
        "Easy Bake Oven commercial vintage",
        "Mattel Hot Wheels commercial vintage",
        "Tonka trucks commercial vintage",
        "vintage Charlie perfume commercial",
        "Hai Karate aftershave commercial",
        "Aqua Velva commercial vintage",
        "Breck shampoo commercial vintage",
        "White Rain shampoo vintage commercial",
        "Johnson baby shampoo vintage commercial",
        "Timex takes licking commercial vintage",
        "Bulova watch commercial vintage",
        "old Greyhound bus commercial",
        "Pan Am airlines commercial vintage",
        "TWA airlines commercial vintage",
        "old Samsonite luggage commercial",
        "vintage Zenith radio commercial",
        "Westinghouse commercial vintage",
        "old Frigidaire commercial vintage",
        "Maytag lonely repairman commercial",
        "old RC Cola commercial",
        "vintage 7 Up Uncola commercial",
        "old Tab diet soda commercial",
        "Fresca vintage commercial",
        "Hawaiian Punch commercial vintage",
        "Kool-Aid man oh yeah vintage commercial",
        # --- WAVE 3: more niche/specific ---
        "Rheingold beer vintage commercial",
        "Schaefer beer vintage commercial",
        "Falstaff beer vintage commercial",
        "old Burma Shave commercial",
        "Ivory soap 99 percent pure commercial",
        "Lux soap vintage commercial",
        "Breck girl hair commercial vintage",
        "Pepsodent toothpaste vintage commercial",
        "Ipana toothpaste vintage commercial",
        "Vitalis hair tonic commercial vintage",
        "old Studebaker car commercial",
        "DeSoto car commercial vintage",
        "Packard automobile commercial vintage",
        "Nash Rambler vintage commercial",
        "old Zenith Space Command remote commercial",
        "vintage Philco television commercial",
        "DuMont television vintage commercial",
        "old Motorola TV commercial vintage",
        "Howdy Doody sponsor commercial vintage",
        "I Love Lucy sponsor commercial vintage",
        "Ed Sullivan Show commercial vintage",
        "Bonanza TV commercial break vintage",
        "vintage Texaco Star Theater commercial",
        "Chesterfield cigarette commercial vintage",
        "old Pall Mall cigarette commercial",
        "vintage Kent cigarette commercial",
        "Marlboro man early commercial",
        "old Anacin headache commercial",
        "Excedrin vintage commercial headache",
        "vintage Pepto Bismol commercial",
        "old Bayer aspirin commercial vintage",
        "S&H Green Stamps commercial vintage",
        "old Piggly Wiggly commercial",
        "vintage A&P grocery store commercial",
        "Sears Kenmore appliance vintage commercial",
        "old Woolworth five and dime commercial",
        "vintage Kresge store commercial",
        "old Howard Johnson commercial vintage",
        "Stuckey pecan shoppe commercial vintage",
        "vintage Holiday Inn motel commercial",
    ],
    "80s": [
        "1980s classic TV commercial",
        "80s retro commercial ad",
        "1985 TV advertisement original",
        "80s cereal commercial vintage",
        "1980s fast food commercial",
        "80s toy commercial original",
        "1980s car commercial vintage",
        "80s beer commercial classic",
        "1980s soda pop commercial",
        "80s candy bar commercial",
        "1984 TV ad classic",
        "1986 commercial break",
        "80s jeans commercial vintage",
        "1980s electronics commercial",
        "80s Saturday morning commercial",
        "1987 TV commercial classic",
        "80s perfume cologne commercial",
        "1983 TV advertisement",
        "80s board game commercial vintage",
        "1980s cleaning product commercial",
        "80s sneaker shoes commercial",
        "1989 TV commercial classic",
        "80s airline commercial vintage",
        "1981 TV ad original",
        "80s chewing gum commercial",
        "1980s computer commercial vintage",
        "80s action figure commercial",
        "1982 TV advertisement classic",
        "80s hair product commercial",
        "1988 TV commercial original",
        "80s walkman stereo commercial",
        "1980s department store commercial",
        "80s frozen food commercial vintage",
        "1985 Super Bowl commercial",
        "80s video game Atari Nintendo commercial",
        "1980s insurance commercial classic",
        "80s razor shaving commercial",
        "1986 TV advertisement original",
        "80s camera film commercial vintage",
        "1980s sports drink commercial",
        # --- WAVE 2: highly specific brand/product queries ---
        "Chia Pet commercial 1980s",
        "Clapper commercial clap on clap off",
        "Micro Machines fast talking guy commercial",
        "My Buddy Kid Sister doll commercial 80s",
        "Teddy Ruxpin talking bear commercial",
        "Skip It commercial 80s",
        "Popples commercial 80s toy",
        "ThunderCats toy commercial 80s",
        "Voltron commercial 1984",
        "Trapper Keeper Mead commercial 80s",
        "Where's the beef Wendy commercial 1984",
        "Max Headroom Coke commercial 1986",
        "California Raisins commercial 80s",
        "Bartles Jaymes wine cooler commercial",
        "Spuds MacKenzie Bud Light commercial",
        "Joe Isuzu commercial liar",
        "Clara Peller Wendy commercial beef",
        "Life Alert fallen commercial 80s",
        "Ginsu knife commercial 80s",
        "Soloflex commercial 80s",
        "Bowflex commercial 1980s",
        "Commodore 64 computer commercial",
        "Apple Macintosh 1984 commercial",
        "Atari 2600 commercial vintage",
        "Coleco ColecoVision commercial",
        "Intellivision commercial vintage",
        "80s Fisher Price toy commercial",
        "Huggies Pampers diaper commercial 80s",
        "Aqua Net hairspray commercial 80s",
        "Jhirmack Farrah Fawcett commercial",
        "Jordache jeans commercial 80s",
        "Members Only jacket commercial 80s",
        "Swatch watch commercial 80s",
        "Mountain Dew extreme commercial 80s",
        "Slice soda commercial 80s",
        "Jolt Cola commercial 80s",
        "Crystal Pepsi commercial",
        "old Domino Pizza Noid commercial 80s",
        "Dunkin Donuts time to make donuts commercial",
        "Jack in the Box commercial 1980s",
        # --- WAVE 3: more niche/specific ---
        "Monchhichi commercial 80s",
        "Rainbow Brite commercial 80s",
        "Strawberry Shortcake commercial 1980s",
        "Care Bears commercial 80s",
        "She-Ra Princess Power commercial 80s",
        "MASK toy commercial 80s",
        "Silverhawks commercial 80s",
        "Centurions commercial 80s",
        "Visionaries toy commercial 80s",
        "Dino Riders commercial 80s toy",
        "old Noxzema commercial 80s",
        "Agree shampoo commercial 80s",
        "Finesse shampoo commercial 1980s",
        "White Rain commercial 80s",
        "Coast soap commercial 80s",
        "Lever 2000 soap commercial 80s",
        "old Right Guard deodorant commercial 80s",
        "Sure deodorant commercial 80s",
        "Tang orange drink commercial 80s",
        "old Capri Sun commercial 80s",
        "Hi-C Ecto Cooler commercial 80s",
        "Hawaiian Punch commercial 80s",
        "Kool-Aid commercial 80s oh yeah",
        "old Sunny Delight commercial 80s",
        "Stove Top stuffing commercial 80s",
        "Shake N Bake commercial 80s",
        "Rice-A-Roni San Francisco treat commercial",
        "Hamburger Helper helping hand commercial 80s",
        "Chef Boyardee commercial 80s",
        "old Stouffer commercial 80s",
        "Lean Cuisine commercial 1980s",
        "Weight Watchers commercial 80s",
        "Bic pen lighter razor commercial 80s",
        "old Memorex cassette commercial 80s",
        "TDK tape commercial 80s",
        "Sony Walkman commercial vintage 80s",
        "old Zenith electronics commercial 80s",
        "Fisher Price commercial 80s toddler",
        "old Playskool commercial 80s",
        "Nerf commercial 80s vintage",
    ],
    "90s": [
        "1990s classic TV commercial",
        "90s retro commercial ad",
        "1995 TV advertisement original",
        "90s toy commercial vintage",
        "1990s snack food commercial",
        "90s video game commercial",
        "1990s car commercial classic",
        "90s cereal commercial vintage",
        "1996 TV commercial original",
        "90s soda commercial classic",
        "1990s fast food commercial",
        "90s candy commercial vintage",
        "1993 TV advertisement",
        "90s shoe commercial classic",
        "1998 TV commercial original",
        "90s beer commercial vintage",
        "1990s electronics commercial",
        "90s Saturday morning cartoon commercial",
        "1997 TV ad classic",
        "90s cologne perfume commercial",
        "1991 TV commercial vintage",
        "90s Nickelodeon commercial break",
        "1994 TV advertisement original",
        "90s pizza commercial classic",
        "1999 TV commercial vintage",
        "90s Gatorade sports drink commercial",
        "1992 TV advertisement classic",
        "90s Nerf toy commercial",
        "1990s computer internet commercial",
        "90s clothing fashion commercial vintage",
        "1996 Super Bowl commercial",
        "90s cleaning product commercial",
        "1990s cell phone pager commercial",
        "90s music CD commercial vintage",
        "1993 TV commercial classic",
        "90s insurance commercial funny",
        "1998 Super Bowl commercial",
        "90s frozen food commercial",
        "1990s shampoo hair commercial",
        "90s breakfast commercial vintage",
        # --- WAVE 2: highly specific brand/product queries ---
        "Crossfire board game commercial 90s",
        "Skip-It commercial 90s",
        "Pogs Slammer commercial 90s",
        "Talkboy Home Alone commercial",
        "Bop It commercial 90s",
        "Moon Shoes commercial 90s",
        "Creepy Crawlers commercial 90s",
        "Furby commercial 1998",
        "Tamagotchi commercial 90s",
        "Power Rangers toy commercial 90s",
        "Budweiser frogs commercial 90s",
        "Budweiser Wassup commercial",
        "Mentos fresh maker commercial 90s",
        "Snapple commercial made from best stuff",
        "Zima commercial 90s",
        "Surge soda commercial 90s",
        "Jolt Cola commercial 90s",
        "90s Nike Air Jordan commercial",
        "Bo Knows Nike commercial",
        "Reebok Pump commercial 90s",
        "LA Gear light up shoes commercial",
        "Bagel Bites pizza in the morning commercial",
        "Hot Pockets Jim Gaffigan commercial",
        "90s Fruit by the Foot Gushers commercial",
        "Ring Pop Push Pop commercial 90s",
        "Warheads candy commercial 90s",
        "90s Slim Jim snap into commercial",
        "90s Head and Shoulders commercial",
        "Herbal Essences shampoo commercial 90s",
        "Zest soap commercial 90s",
        "dial up internet AOL You've Got Mail commercial",
        "Gateway computer cow box commercial",
        "Dell Dude commercial",
        "90s collect call 1-800-COLLECT commercial",
        "MCI friends and family commercial 90s",
        "90s Taco Bell chihuahua commercial",
        "90s Burger King commercial Have It Your Way",
        "Little Caesars pizza pizza commercial 90s",
        "90s Oscar Mayer bologna song commercial",
        "Band-Aid stuck on commercial 90s",
        # --- WAVE 3: more niche/specific ---
        "Sock Em Boppers commercial 90s",
        "Sky Dancers commercial 90s toy",
        "Polly Pocket commercial 90s",
        "Mighty Max commercial 90s",
        "Street Sharks commercial 90s",
        "Beast Wars Transformers commercial 90s",
        "old Skechers commercial 90s",
        "old JNCO jeans commercial 90s",
        "Airwalk shoes commercial 90s",
        "old Doc Martens commercial 90s",
        "old Salon Selectives commercial 90s",
        "Pantene commercial 90s",
        "Suave shampoo commercial 90s",
        "old Secret deodorant commercial 90s",
        "Speed Stick commercial 90s",
        "Right Guard commercial 90s",
        "old Sunny D commercial 90s",
        "Capri Sun commercial 90s silver pouch",
        "Mondo drink commercial 90s squeeze",
        "Squeeze It drink commercial 90s",
        "old Tombstone pizza commercial 90s",
        "DiGiorno pizza commercial not delivery",
        "old Red Baron pizza commercial 90s",
        "Stouffer french bread pizza commercial 90s",
        "old Pop-Tarts commercial 90s crazy good",
        "Toaster Strudel commercial 90s",
        "old Eggo waffle commercial 90s leggo",
        "Kid Cuisine commercial 90s",
        "Lunchables commercial 90s",
        "old CompUSA commercial 90s",
        "old Circuit City commercial 90s",
        "Radio Shack commercial 90s",
        "old Best Buy commercial 90s",
        "old Sears commercial 90s",
        "JCPenney commercial 90s",
        "old Blockbuster Video commercial 90s",
        "Hollywood Video commercial 90s",
        "old Sam Goody Tower Records commercial",
        "old Toys R Us commercial 90s",
        "old KB Toys commercial 90s",
    ],
    "2000s": [
        "2000s classic TV commercial",
        "early 2000s commercial ad",
        "2005 TV advertisement",
        "2000s funny commercial",
        "2003 Super Bowl commercial",
        "2000s car commercial classic",
        "2001 TV commercial original",
        "2000s beer commercial funny",
        "2006 TV advertisement",
        "2000s fast food commercial",
        "2004 TV commercial classic",
        "2000s electronics commercial",
        "2002 TV ad original",
        "2000s soda commercial",
        "2007 TV commercial classic",
        "2000s insurance commercial funny",
        "2008 TV advertisement",
        "2000s cell phone commercial",
        "2000 millennium TV commercial",
        "2005 Super Bowl commercial",
        "2000s energy drink commercial",
        "2009 TV commercial classic",
        "2000s video game commercial",
        "2003 TV advertisement original",
        "2000s snack commercial",
        "2001 Super Bowl commercial",
        "2000s iPod Apple commercial",
        "2004 TV advertisement classic",
        "2000s razor shaving commercial",
        "2007 Super Bowl commercial",
        "2000s cereal breakfast commercial",
        "2006 TV commercial original",
        "2000s clothing fashion commercial",
        "2002 TV advertisement classic",
        "2000s movie trailer TV spot",
        "2008 Super Bowl commercial",
        "2000s cleaning product commercial",
        "2005 TV commercial original",
        "2000s cologne perfume commercial",
        "2009 TV advertisement classic",
        # --- WAVE 2: highly specific brand/product queries ---
        "ShamWow Vince commercial",
        "OxiClean Billy Mays commercial",
        "HeadOn apply directly forehead commercial",
        "Snuggie blanket sleeves commercial",
        "Geico caveman commercial so easy",
        "Geico gecko commercial 2000s",
        "Aflac duck commercial 2000s",
        "Budweiser Clydesdale 9/11 commercial",
        "Budweiser real men of genius commercial",
        "Bud Light commercial 2000s funny",
        "Nextel walkie talkie commercial 2000s",
        "Motorola RAZR phone commercial",
        "Blackberry phone commercial 2000s",
        "Vonage commercial 2000s",
        "FreeCreditReport.com band commercial",
        "Burger King subservient chicken commercial",
        "Quiznos Spongmonkeys commercial",
        "Jack in the Box antenna ball commercial",
        "Sonic drive-in two guys commercial",
        "Old Spice Terry Crews commercial",
        "Halo Xbox commercial 2001",
        "PlayStation 2 PS2 commercial",
        "Nintendo Wii commercial 2006",
        "Guitar Hero Rock Band commercial",
        "Apple silhouette iPod commercial",
        "Dell Dude dude getting Dell commercial",
        "Verizon can you hear me now commercial",
        "Sprint commercial 2000s",
        "T-Mobile Catherine Zeta Jones commercial",
        "Orbitz gum dirty mouth commercial",
        "Skittles taste the rainbow commercial 2000s",
        "M&M commercial 2000s funny",
        "Snickers commercial 2000s",
        "Twix commercial left right 2000s",
        "5 hour energy commercial",
        "Enzyte smiling Bob commercial",
        "Progressive insurance commercial 2000s",
        "LeBron James Nike commercial 2003",
        "Tiger Woods Nike commercial 2000s",
        "Peyton Manning commercial 2000s",
        # --- WAVE 3: more niche/specific ---
        "Swiffer WetJet commercial 2000s",
        "Febreze commercial 2000s nose blind",
        "old Oxi Clean commercial infomercial",
        "Magic Bullet infomercial commercial",
        "Proactiv acne commercial 2000s celebrity",
        "old Bowflex commercial 2000s",
        "Bally Total Fitness commercial 2000s",
        "old Circuit City commercial 2000s",
        "CompUSA commercial 2000s",
        "old Blockbuster Video commercial 2000s",
        "Netflix DVD mail commercial 2000s",
        "old CarFax commercial 2000s",
        "AutoTrader commercial 2000s",
        "old Lending Tree commercial 2000s",
        "Capital One David Spade commercial",
        "Discover Card cashback commercial 2000s",
        "old E-Trade baby commercial",
        "Dairy Queen Blizzard commercial 2000s",
        "Sonic Drive-In two guys commercial 2000s",
        "Applebees Chili commercial 2000s",
        "old Olive Garden commercial 2000s",
        "Outback Steakhouse commercial 2000s",
        "old Coors Light commercial 2000s",
        "Miller Lite Man Laws commercial",
        "Captain Morgan commercial 2000s",
        "old Smirnoff Ice commercial 2000s",
        "Grey Goose vodka commercial 2000s",
        "Lays chips commercial 2000s",
        "Pringles commercial 2000s once you pop",
        "old Starburst juicy commercial 2000s",
        "Jolly Rancher commercial 2000s",
        "Reese's commercial 2000s",
        "Kit Kat break me off commercial 2000s",
        "old Hershey Kisses commercial 2000s",
        "old Wii Sports commercial 2006",
        "Xbox 360 commercial 2005",
        "PSP PlayStation Portable commercial 2005",
        "old GameStop commercial 2000s",
        "Best Buy commercial 2000s",
        "Target commercial 2000s designer",
    ],
    "2010s": [
        "2010s classic TV commercial",
        "2015 TV advertisement",
        "2010s Super Bowl commercial",
        "2013 TV commercial classic",
        "2010s funny commercial",
        "2011 TV advertisement",
        "2010s car commercial",
        "2014 Super Bowl ad",
        "2016 TV commercial classic",
        "2010s beer commercial funny",
        "2012 TV advertisement",
        "2010s insurance commercial",
        "2017 TV commercial",
        "2010s fast food commercial",
        "2018 Super Bowl commercial",
        "2010s phone commercial",
        "2010 TV advertisement classic",
        "2019 TV commercial",
        "2010s snack commercial funny",
        "2015 Super Bowl ad",
        "2010s streaming service commercial",
        "2013 TV advertisement",
        "2010s energy drink commercial",
        "2016 Super Bowl commercial",
        "2010s perfume cologne commercial",
        "2011 Super Bowl commercial",
        "2010s soda commercial classic",
        "2014 TV advertisement",
        "2010s cleaning product commercial",
        "2017 Super Bowl commercial",
        "2010s clothing fashion commercial",
        "2012 TV commercial original",
        "2010s cereal breakfast commercial",
        "2019 Super Bowl commercial",
        "2010s movie trailer TV spot",
        # --- WAVE 2: highly specific brand/product queries ---
        "Progressive Flo commercial funny",
        "State Farm Jake from State Farm commercial",
        "Allstate Mayhem Dean Winters commercial",
        "Old Spice man your man could smell like",
        "Dos Equis most interesting man commercial",
        "Farmers Insurance seen a thing commercial",
        "Liberty Mutual emu Doug commercial",
        "GEICO hump day camel commercial",
        "Budweiser puppy love commercial",
        "Doritos Super Bowl crash commercial",
        "Tide Pod commercial Super Bowl",
        "Amazon Alexa loses voice commercial",
        "Apple iPhone commercial 2010s",
        "Samsung Galaxy commercial 2010s",
        "T-Mobile commercial funny 2010s",
        "Subway five dollar footlong commercial",
        "Wendy pretzel bacon commercial 2010s",
        "Taco Bell live mas commercial",
        "M&M Super Bowl commercial 2010s",
        "Snickers Betty White Super Bowl commercial",
        # --- WAVE 3: more niche/specific ---
        "Puppy Monkey Baby Mountain Dew commercial",
        "Esurance commercial 2010s",
        "Trivago guy commercial",
        "Hotels.com Captain Obvious commercial",
        "Booking.com commercial 2010s",
        "Charmin Bears commercial 2010s",
        "Mr Clean Super Bowl commercial 2017",
        "Old Spice Mom commercial 2010s",
        "Purple mattress commercial 2010s",
        "Casper mattress commercial 2010s",
        "Dollar Shave Club commercial original",
        "Squarespace Super Bowl commercial",
        "GoDaddy commercial 2010s",
        "Wix commercial 2010s",
        "Apple Watch commercial 2015",
        "Google Pixel commercial 2016",
        "Alexa what is commercial",
        "Ring doorbell commercial 2010s",
        "Peloton Christmas commercial 2019",
        "Kia hamster commercial 2010s",
    ],
}

DECADE_TARGETS: dict[str, int] = {
    "pre-80s": 500,
    "80s": 500,
    "90s": 500,
    "2000s": 500,
    "2010s": 250,
}

TARGET_PER_DECADE = 150  # Legacy default, overridden by DECADE_TARGETS
OUTPUT_BASE = Path(r"F:\Commercials")

# Duration filter: 10s-300s (individual commercials, not compilations)
MIN_DURATION = 10
MAX_DURATION = 300


def search_and_download(decade: str, queries: list[str], target: int) -> int:
    """Search YouTube and download individual commercial clips for a decade."""
    output_dir = OUTPUT_BASE / decade
    output_dir.mkdir(parents=True, exist_ok=True)

    # Count existing files so we don't re-download
    existing = len(list(output_dir.glob("*.mp4")))
    remaining = target - existing
    if remaining <= 0:
        print(f"[{decade}] Already have {existing} files, target is {target}. Skipping.")
        return existing

    print(f"[{decade}] Have {existing} files, need {remaining} more (target: {target})")

    downloaded = 0
    seen_ids: set[str] = set()

    # Also track existing filenames to avoid duplicates
    existing_names = {f.stem.lower() for f in output_dir.glob("*.mp4")}

    for query in queries:
        if downloaded >= remaining:
            break

        print(f"\n  [{decade}] Searching: {query} ({downloaded}/{remaining} so far)")

        # Search for more results to have better filtering options
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

            # Skip compilations
            title_lower = title.lower()
            if any(word in title_lower for word in ["compilation", "hours", "hour", "collection", "marathon", "top 10", "top 20", "top 5", "top 50", "top 100", "best of", "every commercial", "all commercials", "commercial block", "commercial break"]):
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


def main() -> None:
    OUTPUT_BASE.mkdir(parents=True, exist_ok=True)

    # Migrate legacy "70s" folder to "pre-80s" if it exists
    legacy_70s = OUTPUT_BASE / "70s"
    pre80s = OUTPUT_BASE / "pre-80s"
    if legacy_70s.exists() and not pre80s.exists():
        print(f"Renaming {legacy_70s} -> {pre80s}")
        legacy_70s.rename(pre80s)
    elif legacy_70s.exists() and pre80s.exists():
        # Both exist — move files from 70s into pre-80s
        import shutil
        for f in legacy_70s.glob("*.mp4"):
            dest = pre80s / f.name
            if not dest.exists():
                shutil.move(str(f), str(dest))
        # Remove empty 70s folder
        try:
            legacy_70s.rmdir()
        except OSError:
            pass

    total_target = sum(DECADE_TARGETS.values())
    print(f"Downloading commercials to {OUTPUT_BASE}")
    print(f"Target: {total_target} total across {len(DECADE_TARGETS)} decades\n")

    grand_total = 0
    for decade, queries in DECADE_QUERIES.items():
        target = DECADE_TARGETS.get(decade, TARGET_PER_DECADE)
        count = search_and_download(decade, queries, target)
        grand_total += count

    print(f"\n{'='*60}")
    print(f"Grand total: {grand_total} commercial clips")
    for decade in DECADE_QUERIES:
        d = OUTPUT_BASE / decade
        mp4s = list(d.glob("*.mp4")) if d.exists() else []
        total_mb = sum(f.stat().st_size for f in mp4s) / (1024 * 1024)
        print(f"  {decade}: {len(mp4s)} files ({total_mb:.0f} MB)")


if __name__ == "__main__":
    # Support running a single decade: python script.py pre-80s
    if len(sys.argv) > 1:
        decade_arg = sys.argv[1]
        if decade_arg not in DECADE_QUERIES:
            print(f"Unknown decade: {decade_arg}. Available: {list(DECADE_QUERIES.keys())}")
            sys.exit(1)
        OUTPUT_BASE.mkdir(parents=True, exist_ok=True)
        # Run migration if needed (only relevant for pre-80s)
        if decade_arg == "pre-80s":
            legacy_70s = OUTPUT_BASE / "70s"
            pre80s = OUTPUT_BASE / "pre-80s"
            if legacy_70s.exists() and not pre80s.exists():
                legacy_70s.rename(pre80s)
        target = DECADE_TARGETS.get(decade_arg, TARGET_PER_DECADE)
        count = search_and_download(decade_arg, DECADE_QUERIES[decade_arg], target)
        print(f"\n{decade_arg}: {count} total files")
    else:
        main()
